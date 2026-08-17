"""Admin-Befehle: /raid_post (Dry-Run/Sofort-Post), /resync, /link_status."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from ..bot import WowHelperBot

log = logging.getLogger(__name__)


class AdminCog(commands.Cog):
    def __init__(self, bot: "WowHelperBot"):
        self.bot = bot

    async def _team_autocomplete(
        self, _: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=team.label, value=key)
            for key, team in self.bot.settings.teams.items()
            if current.lower() in key.lower() or current.lower() in team.label.lower()
        ][:25]

    @app_commands.command(name="raid_post", description="Postet die Anmeldung für einen wowaudit-Raid sofort")
    @app_commands.describe(team="Kader", raid_id="wowaudit Raid-ID")
    @app_commands.autocomplete(team=_team_autocomplete)
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def raid_post(self, interaction: discord.Interaction, team: str, raid_id: int) -> None:
        texts = self.bot.texts
        if team not in self.bot.settings.teams:
            await interaction.response.send_message(texts("common.error_generic"), ephemeral=True)
            return
        label = self.bot.settings.teams[team].label
        await interaction.response.defer(ephemeral=True, thinking=True)

        if await self.bot.db.get_raid_post_by_wowaudit(team, raid_id):
            await interaction.followup.send(
                texts("admin.raid_post_exists", raid_id=raid_id, team=label), ephemeral=True
            )
            return

        try:
            raid = await self.bot.wowaudit[team].get_raid(raid_id)
        except Exception:  # noqa: BLE001
            log.exception("/raid_post: Raid-Fetch fehlgeschlagen")
            raid = None
        if raid is None:
            await interaction.followup.send(
                texts("admin.raid_not_found", raid_id=raid_id, team=label), ephemeral=True
            )
            return

        signup_cog = self.bot.get_cog("SignupCog")
        post = await signup_cog.create_raid_post(team, raid)
        if post is None:
            await interaction.followup.send(texts("admin.no_channel"), ephemeral=True)
            return
        await interaction.followup.send(
            texts("admin.raid_post_done", raid_id=raid_id, team=label), ephemeral=True
        )

    @app_commands.command(name="resync", description="Stößt Writeback zu wowaudit und Embed-Refresh sofort an")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.guild_only()
    async def resync(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        signup_cog = self.bot.get_cog("SignupCog")
        await signup_cog.writeback_loop()
        await signup_cog.refresh_loop()
        await interaction.followup.send(self.bot.texts("admin.resync_done"), ephemeral=True)

    @app_commands.command(name="link_status", description="Zeigt deine verlinkten Charaktere")
    async def link_status(self, interaction: discord.Interaction) -> None:
        texts = self.bot.texts
        links = await self.bot.db.get_character_links(interaction.user.id)
        if not links:
            await interaction.response.send_message(texts("admin.link_status_none"), ephemeral=True)
            return
        lines = [
            texts(
                "admin.link_status_line",
                team=self.bot.settings.teams[l.team_key].label if l.team_key in self.bot.settings.teams else l.team_key,
                name=l.character_name,
            )
            for l in links
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)
