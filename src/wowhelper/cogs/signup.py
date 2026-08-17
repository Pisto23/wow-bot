"""Raid-Anmeldung: Scheduler, Anmelde-Post, Status-Buttons, wowaudit-Writeback."""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
from typing import TYPE_CHECKING, Callable

import discord
from discord.ext import commands, tasks

from ..config import WEEKDAY_NAMES
from ..db import RaidPost, SignupRow
from ..ui.embeds import build_signup_embed, format_date_de
from ..ui.modals import AnnounceModal
from ..wowaudit.client import WowauditError
from ..wowaudit.models import Raid, Signup

if TYPE_CHECKING:
    from ..bot import WowHelperBot

log = logging.getLogger(__name__)


def raids_due(
    raids: list[Raid],
    existing_ids: set[int],
    today: dt.date,
    lead_days: int,
    channel_for_weekday: Callable[[int], int | None],
) -> list[Raid]:
    """Pure Entscheidung: welche Raids brauchen jetzt einen Anmelde-Post?"""
    due = []
    horizon = today + dt.timedelta(days=lead_days)
    for raid in raids:
        if raid.id in existing_ids:
            continue
        if not (today <= raid.date <= horizon):
            continue
        if channel_for_weekday(raid.date.weekday()) is None:
            continue
        due.append(raid)
    return due


class SignupCog(commands.Cog):
    def __init__(self, bot: "WowHelperBot"):
        self.bot = bot
        self.scheduler_loop.change_interval(minutes=5)
        self.refresh_loop.change_interval(minutes=max(1, bot.settings.refresh_minutes))
        self.writeback_loop.change_interval(minutes=10)

    async def cog_load(self) -> None:
        self.scheduler_loop.start()
        self.refresh_loop.start()
        self.writeback_loop.start()

    async def cog_unload(self) -> None:
        self.scheduler_loop.cancel()
        self.refresh_loop.cancel()
        self.writeback_loop.cancel()

    # ---- Hilfen -------------------------------------------------------------

    def _today(self) -> dt.date:
        return dt.datetime.now(self.bot.settings.tz).date()

    async def _channel(self, channel_id: int) -> discord.TextChannel | None:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            try:
                channel = await self.bot.fetch_channel(channel_id)
            except discord.HTTPException:
                return None
        return channel if isinstance(channel, discord.TextChannel) else None

    async def build_embed(self, post: RaidPost, force_roster: bool = False) -> discord.Embed:
        client = self.bot.wowaudit[post.team_key]
        try:
            roster = await client.get_characters(force=force_roster)
        except Exception:  # noqa: BLE001 — Embed muss auch ohne API rendern
            log.exception("Roster-Fetch fehlgeschlagen (%s)", post.team_key)
            roster = []
        signups = await self.bot.db.get_signups(post.id)
        statuses = {s.character_name: s.status for s in signups}
        return build_signup_embed(
            date_iso=post.raid_date,
            instance=post.instance,
            difficulty=post.difficulty,
            start_time=post.start_time,
            end_time=post.end_time,
            wa_status=post.wa_status,
            announcement=post.announcement,
            roster=roster,
            statuses=statuses,
            texts=self.bot.texts,
            class_emojis=self.bot.settings.class_emojis,
        )

    async def _edit_post_message(self, post: RaidPost, embed: discord.Embed) -> None:
        channel = await self._channel(post.channel_id)
        if channel is None or post.message_id is None:
            return
        try:
            await channel.get_partial_message(post.message_id).edit(embed=embed)
        except discord.NotFound:
            log.warning("Anmelde-Post %s wurde gelöscht (message_id=%s)", post.id, post.message_id)
        except discord.HTTPException:
            log.exception("Embed-Edit fehlgeschlagen (post=%s)", post.id)

    async def _rerender(self, post_id: int, force_roster: bool = False) -> None:
        post = await self.bot.db.get_raid_post(post_id)
        if post is not None:
            await self._edit_post_message(post, await self.build_embed(post, force_roster))

    # ---- Anmelde-Post erstellen --------------------------------------------

    async def create_raid_post(self, team_key: str, raid: Raid) -> RaidPost | None:
        """Postet die Anmeldung für einen wowaudit-Raid. None, wenn kein Channel
        konfiguriert ist oder der Post bereits existiert (Race abgefangen)."""
        settings = self.bot.settings
        team = settings.teams[team_key]
        texts = self.bot.texts
        channel_id = team.channel_for_weekday(raid.date.weekday())
        if channel_id is None:
            return None
        channel = await self._channel(channel_id)
        if channel is None:
            log.error("Channel %s (%s) nicht erreichbar", channel_id, team_key)
            return None

        client = self.bot.wowaudit[team_key]
        try:
            detail = await client.get_raid(raid.id) or raid
        except WowauditError:
            detail = raid
        try:
            roster = await client.get_characters()
        except Exception:  # noqa: BLE001
            roster = []

        date_iso = raid.date.isoformat()
        statuses = {s.character_name: s.status for s in detail.signups}
        embed = build_signup_embed(
            date_iso=date_iso,
            instance=detail.instance,
            difficulty=detail.difficulty,
            start_time=detail.start_time,
            end_time=detail.end_time,
            wa_status=detail.status,
            announcement=None,
            roster=roster,
            statuses=statuses,
            texts=texts,
            class_emojis=settings.class_emojis,
        )

        from ..ui.views import SignupView

        content = None
        if team.mention_role_id:
            content = (
                f"<@&{team.mention_role_id}> "
                + texts("signup.mention_line", date=format_date_de(date_iso))
            )
        message = await channel.send(content=content, embed=embed, view=SignupView(self.bot))

        thread_id = None
        try:
            thread = await message.create_thread(
                name=texts(
                    "signup.thread_name",
                    date=format_date_de(date_iso),
                    start=detail.start_time or "?",
                    instance=detail.instance or "?",
                )[:100]
            )
            thread_id = thread.id
        except discord.HTTPException:
            log.exception("Thread-Erstellung fehlgeschlagen (%s)", team_key)

        try:
            post_id = await self.bot.db.create_raid_post(
                team_key=team_key,
                wowaudit_raid_id=raid.id,
                raid_date=date_iso,
                weekday=WEEKDAY_NAMES[raid.date.weekday()],
                channel_id=channel_id,
                message_id=message.id,
                thread_id=thread_id,
                instance=detail.instance,
                difficulty=detail.difficulty,
                start_time=detail.start_time,
                end_time=detail.end_time,
                wa_status=detail.status,
            )
        except Exception:  # noqa: BLE001 — UNIQUE-Race: parallel erstellt
            log.warning("Raid %s (%s) wurde parallel gepostet — räume auf", raid.id, team_key)
            await message.delete()
            return None

        for s in detail.signups:
            await self.bot.db.import_remote_signup(post_id, s.character_name, s.status, s.character_id)

        log.info("Anmelde-Post erstellt: %s Raid %s -> #%s", team_key, raid.id, channel.name)
        return await self.bot.db.get_raid_post(post_id)

    # ---- Loops --------------------------------------------------------------

    @tasks.loop(minutes=5)
    async def scheduler_loop(self) -> None:
        today = self._today()
        active = await self.bot.db.list_active_raid_posts(today.isoformat())
        for team_key, team in self.bot.settings.teams.items():
            try:
                raids = await self.bot.wowaudit[team_key].get_raids()
            except Exception:  # noqa: BLE001
                log.exception("Raid-Liste nicht abrufbar (%s)", team_key)
                continue
            existing = {p.wowaudit_raid_id for p in active if p.team_key == team_key}
            for raid in raids_due(
                raids, existing, today, self.bot.settings.post_lead_days, team.channel_for_weekday
            ):
                if await self.bot.db.get_raid_post_by_wowaudit(team_key, raid.id):
                    continue
                try:
                    await self.create_raid_post(team_key, raid)
                except Exception:  # noqa: BLE001
                    log.exception("Anmelde-Post fehlgeschlagen (%s, Raid %s)", team_key, raid.id)

    @tasks.loop(minutes=10)
    async def refresh_loop(self) -> None:
        for post in await self.bot.db.list_active_raid_posts(self._today().isoformat()):
            try:
                await self._refresh_post(post)
            except Exception:  # noqa: BLE001
                log.exception("Refresh fehlgeschlagen (post=%s)", post.id)

    async def _refresh_post(self, post: RaidPost, force_roster: bool = False) -> None:
        """Meta + Remote-Signups aus wowaudit ziehen (best effort), dann re-rendern."""
        client = self.bot.wowaudit[post.team_key]
        try:
            detail = await client.get_raid(post.wowaudit_raid_id)
        except Exception:  # noqa: BLE001
            detail = None
        if detail is not None:
            await self.bot.db.update_raid_meta(
                post.id, detail.instance, detail.difficulty,
                detail.start_time, detail.end_time, detail.status,
            )
            for s in detail.signups:
                await self.bot.db.import_remote_signup(
                    post.id, s.character_name, s.status, s.character_id
                )
        await self._rerender(post.id, force_roster=force_roster)

    @tasks.loop(minutes=10)
    async def writeback_loop(self) -> None:
        pending = await self.bot.db.pending_sync_signups()
        by_post: dict[int, list] = {}
        for row in pending:
            by_post.setdefault(row.raid_post_id, []).append(row)
        for post_id, rows in by_post.items():
            post = await self.bot.db.get_raid_post(post_id)
            if post is None:
                continue
            await self._writeback(post, rows)

    async def _writeback(self, post: RaidPost, rows: list) -> None:
        """Best-Effort: Fehler werden geloggt, nie propagiert."""
        client = self.bot.wowaudit[post.team_key]
        updates = [
            Signup(character_id=r.wowaudit_character_id, character_name=r.character_name, status=r.status)
            for r in rows
        ]
        try:
            await client.update_signups(post.wowaudit_raid_id, updates)
        except Exception:  # noqa: BLE001
            log.warning("Writeback fehlgeschlagen (post=%s, raid=%s) — Retry im nächsten Zyklus",
                        post.id, post.wowaudit_raid_id, exc_info=True)
            return
        for r in rows:
            await self.bot.db.mark_signup_synced(post.id, r.character_name)

    @scheduler_loop.before_loop
    @refresh_loop.before_loop
    @writeback_loop.before_loop
    async def _wait_ready(self) -> None:
        await self.bot.wait_until_ready()

    # ---- Button-Handler (aufgerufen aus ui.views.SignupView) ---------------

    async def _post_from_interaction(self, interaction: discord.Interaction) -> RaidPost | None:
        if interaction.message is None:
            return None
        return await self.bot.db.get_raid_post_by_message(interaction.message.id)

    async def handle_status_click(self, interaction: discord.Interaction, status: str) -> None:
        texts = self.bot.texts
        post = await self._post_from_interaction(interaction)
        if post is None:
            await interaction.response.send_message(texts("common.error_generic"), ephemeral=True)
            return
        link = await self.bot.db.get_character_link(interaction.user.id, post.team_key)
        if link is None:
            await interaction.response.send_message(texts("common.not_linked"), ephemeral=True)
            return

        await self.bot.db.set_signup(
            post.id, link.character_name, status,
            discord_id=interaction.user.id,
            wowaudit_character_id=link.wowaudit_character_id,
        )
        embed = await self.build_embed(post)
        await interaction.response.edit_message(embed=embed)

        row = SignupRow(
            raid_post_id=post.id,
            character_name=link.character_name,
            wowaudit_character_id=link.wowaudit_character_id,
            discord_id=interaction.user.id,
            status=status,
            updated_at="",
            synced_at=None,
        )
        asyncio.create_task(self._writeback(post, [row]))

    async def handle_refresh_click(self, interaction: discord.Interaction) -> None:
        texts = self.bot.texts
        post = await self._post_from_interaction(interaction)
        if post is None:
            await interaction.response.send_message(texts("common.error_generic"), ephemeral=True)
            return
        await interaction.response.defer()
        await self._refresh_post(post, force_roster=True)
        await interaction.followup.send(texts("signup.refreshed"), ephemeral=True)

    async def handle_announce_click(self, interaction: discord.Interaction) -> None:
        texts = self.bot.texts
        post = await self._post_from_interaction(interaction)
        if post is None:
            await interaction.response.send_message(texts("common.error_generic"), ephemeral=True)
            return
        member = interaction.user
        team = self.bot.settings.teams[post.team_key]
        allowed = isinstance(member, discord.Member) and (
            member.guild_permissions.manage_guild
            or (team.raidlead_role_id and member.get_role(team.raidlead_role_id) is not None)
        )
        if not allowed:
            await interaction.response.send_message(
                texts("signup.announce_no_permission"), ephemeral=True
            )
            return
        await interaction.response.send_modal(AnnounceModal(self, post.id, post.announcement))

    async def handle_announce_submit(
        self, interaction: discord.Interaction, raid_post_id: int, text: str
    ) -> None:
        await self.bot.db.set_announcement(raid_post_id, text.strip() or None)
        await interaction.response.send_message(
            self.bot.texts("signup.announce_saved"), ephemeral=True
        )
        await self._rerender(raid_post_id)
