"""/link_char — Discord-Account mit einem wowaudit-Charakter verknüpfen."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from ..naming import match_character
from ..ui.views import LinkCharView

if TYPE_CHECKING:
    from ..bot import WowHelperBot

log = logging.getLogger(__name__)


class LinkCharCog(commands.Cog):
    def __init__(self, bot: "WowHelperBot"):
        self.bot = bot

    @app_commands.command(name="link_char", description="Verknüpft deinen wowaudit-Charakter mit deinem Discord-Account")
    async def link_char(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            self.bot.texts("link_char.choose_text"),
            view=LinkCharView(self),
            ephemeral=True,
        )

    async def handle_link_submit(
        self, interaction: discord.Interaction, team_key: str, raw_name: str
    ) -> None:
        texts = self.bot.texts
        team = self.bot.settings.teams[team_key]
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            roster = await self.bot.wowaudit[team_key].get_characters()
        except Exception:  # noqa: BLE001
            log.exception("Roster-Fetch für /link_char fehlgeschlagen (%s)", team_key)
            await interaction.followup.send(texts("link_char.roster_error"), ephemeral=True)
            return

        hit, suggestions = match_character(raw_name, [c.name for c in roster])
        if hit is None:
            msg = texts("link_char.not_found", name=raw_name.strip(), team=team.label)
            if suggestions:
                msg += "\n" + texts("link_char.suggestions", names=", ".join(f"**{s}**" for s in suggestions))
            await interaction.followup.send(msg, ephemeral=True)
            return

        char = next(c for c in roster if c.name == hit)
        await self.bot.db.upsert_character_link(
            discord_id=interaction.user.id,
            team_key=team_key,
            character_name=char.name,
            wowaudit_character_id=char.id,
            realm=char.realm,
        )
        await interaction.followup.send(
            texts("link_char.success", name=char.name, team=team.label), ephemeral=True
        )
