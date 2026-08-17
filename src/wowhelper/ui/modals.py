"""Modals: Charakter verlinken, Wishlist aktualisieren, Ankündigung bearbeiten."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:  # nur für Typen, keine Import-Zyklen zur Laufzeit
    from ..cogs.link_char import LinkCharCog
    from ..cogs.signup import SignupCog
    from ..cogs.wishlist import WishlistCog


class LinkCharModal(discord.ui.Modal):
    def __init__(self, cog: "LinkCharCog", team_key: str):
        texts = cog.bot.texts
        super().__init__(title=texts("link_char.modal_title"))
        self.cog = cog
        self.team_key = team_key
        self.name_input = discord.ui.TextInput(
            label=texts("link_char.name_label"),
            placeholder=texts("link_char.name_placeholder"),
            required=True,
            max_length=48,
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_link_submit(interaction, self.team_key, self.name_input.value)


class WishlistModal(discord.ui.Modal):
    def __init__(self, cog: "WishlistCog"):
        texts = cog.bot.texts
        super().__init__(title=texts("wishlist.modal_title"))
        self.cog = cog
        self.report_input = discord.ui.TextInput(
            label=texts("wishlist.input_label"),
            placeholder=texts("wishlist.input_placeholder"),
            required=True,
            max_length=200,
        )
        self.add_item(self.report_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_wishlist_submit(interaction, self.report_input.value)


class AnnounceModal(discord.ui.Modal):
    def __init__(self, cog: "SignupCog", raid_post_id: int, current: str | None):
        texts = cog.bot.texts
        super().__init__(title=texts("signup.announce_modal_title"))
        self.cog = cog
        self.raid_post_id = raid_post_id
        self.text_input = discord.ui.TextInput(
            label=texts("signup.announce_label"),
            placeholder=texts("signup.announce_placeholder"),
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000,
            default=current or None,
        )
        self.add_item(self.text_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await self.cog.handle_announce_submit(interaction, self.raid_post_id, self.text_input.value)
