"""/start_wishlist — Raidbots-Droptimizer nach wowaudit hochladen."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..db import CharacterLink
from ..naming import normalize
from ..raidbots import fetch_report_charname, parse_report_id
from ..ui.modals import WishlistModal
from ..ui.views import TeamChoiceView
from ..wowaudit.client import WowauditError

if TYPE_CHECKING:
    from ..bot import WowHelperBot

log = logging.getLogger(__name__)


class WishlistCog(commands.Cog):
    def __init__(self, bot: "WowHelperBot"):
        self.bot = bot

    @app_commands.command(name="start_wishlist", description="Lädt einen Raidbots-Sim (Droptimizer) zu wowaudit hoch")
    async def start_wishlist(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(WishlistModal(self))

    async def handle_wishlist_submit(self, interaction: discord.Interaction, raw: str) -> None:
        texts = self.bot.texts
        await interaction.response.defer(ephemeral=True, thinking=True)

        report_id = parse_report_id(raw)
        if report_id is None:
            await interaction.followup.send(texts("wishlist.invalid_input"), ephemeral=True)
            return

        links = await self.bot.db.get_character_links(interaction.user.id)
        if not links:
            await interaction.followup.send(texts("common.not_linked"), ephemeral=True)
            return

        exists, report_char = await fetch_report_charname(self.bot.http_session, report_id)
        if exists is False:
            await interaction.followup.send(
                texts("wishlist.report_not_found", report_id=report_id), ephemeral=True
            )
            return

        # Ziel-Kader bestimmen: eindeutig, per Report-Charname, sonst nachfragen
        link = self._resolve_link(links, report_char)
        if link is None:
            view = TeamChoiceView(
                self.bot,
                [l.team_key for l in links],
                lambda i, team_key: self._upload_for_team(i, links, team_key, report_id, report_char),
            )
            await interaction.followup.send(texts("wishlist.choose_team"), view=view, ephemeral=True)
            return

        await self._upload(interaction, link, report_id, report_char)

    @staticmethod
    def _resolve_link(links: list[CharacterLink], report_char: str | None) -> CharacterLink | None:
        if len(links) == 1:
            return links[0]
        if report_char:
            matches = [l for l in links if normalize(l.character_name) == normalize(report_char)]
            if len(matches) == 1:
                return matches[0]
        return None

    async def _upload_for_team(
        self,
        interaction: discord.Interaction,
        links: list[CharacterLink],
        team_key: str,
        report_id: str,
        report_char: str | None,
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        link = next(l for l in links if l.team_key == team_key)
        await self._upload(interaction, link, report_id, report_char)

    async def _upload(
        self,
        interaction: discord.Interaction,
        link: CharacterLink,
        report_id: str,
        report_char: str | None,
    ) -> None:
        texts = self.bot.texts
        prefix = ""
        if report_char and normalize(report_char) != normalize(link.character_name):
            prefix = texts(
                "wishlist.char_mismatch", report_char=report_char, linked_char=link.character_name
            ) + "\n"

        try:
            await self.bot.wowaudit[link.team_key].upload_wishlist(
                report_id, link.character_name, link.wowaudit_character_id
            )
        except WowauditError as exc:
            log.warning("Wishlist-Upload fehlgeschlagen: %s", exc)
            await self.bot.db.record_wishlist_upload(
                interaction.user.id, link.team_key, report_id, link.character_name,
                ok=False, error=str(exc)[:500],
            )
            await interaction.followup.send(
                prefix + texts("wishlist.upload_failed", error=f"HTTP {exc.status}"), ephemeral=True
            )
            return
        except Exception as exc:  # noqa: BLE001
            log.exception("Wishlist-Upload: unerwarteter Fehler")
            await self.bot.db.record_wishlist_upload(
                interaction.user.id, link.team_key, report_id, link.character_name,
                ok=False, error=str(exc)[:500],
            )
            await interaction.followup.send(prefix + texts("common.error_generic"), ephemeral=True)
            return

        await self.bot.db.record_wishlist_upload(
            interaction.user.id, link.team_key, report_id, link.character_name, ok=True
        )
        await interaction.followup.send(
            prefix + texts("wishlist.success", name=link.character_name), ephemeral=True
        )
