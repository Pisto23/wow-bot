"""Views: persistente Anmelde-Buttons und der /link_char-Zwei-Schritt-Flow."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from ..wowaudit.models import STATUS_ABSENT, STATUS_LATE, STATUS_PRESENT

if TYPE_CHECKING:
    from ..bot import WowHelperBot
    from ..cogs.link_char import LinkCharCog

# Feste custom_ids — Grundlage der Persistenz über Neustarts hinweg. Nie ändern.
CID_PRESENT = "wowhelper:signup:present"
CID_LATE = "wowhelper:signup:late"
CID_ABSENT = "wowhelper:signup:absent"
CID_REFRESH = "wowhelper:signup:refresh"
CID_ANNOUNCE = "wowhelper:signup:announce"


class SignupView(discord.ui.View):
    """Persistente View unter jedem Anmelde-Post. Der Raid wird über die
    Message-ID aufgelöst, daher genügt eine einzige registrierte Instanz."""

    def __init__(self, bot: "WowHelperBot"):
        super().__init__(timeout=None)
        self.bot = bot
        labels = {
            CID_PRESENT: bot.texts("signup.btn_present"),
            CID_LATE: bot.texts("signup.btn_late"),
            CID_ABSENT: bot.texts("signup.btn_absent"),
            CID_REFRESH: bot.texts("signup.btn_refresh"),
            CID_ANNOUNCE: bot.texts("signup.btn_announce"),
        }
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id in labels:
                child.label = labels[child.custom_id]

    def _cog(self):
        cog = self.bot.get_cog("SignupCog")
        assert cog is not None
        return cog

    @discord.ui.button(label="Zusage", style=discord.ButtonStyle.primary, custom_id=CID_PRESENT, row=0)
    async def present(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._cog().handle_status_click(interaction, STATUS_PRESENT)

    @discord.ui.button(label="Zu Spät", style=discord.ButtonStyle.primary, custom_id=CID_LATE, row=0)
    async def late(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._cog().handle_status_click(interaction, STATUS_LATE)

    @discord.ui.button(label="Absage", style=discord.ButtonStyle.primary, custom_id=CID_ABSENT, row=0)
    async def absent(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._cog().handle_status_click(interaction, STATUS_ABSENT)

    @discord.ui.button(label="Manuell aktualisieren", style=discord.ButtonStyle.secondary, custom_id=CID_REFRESH, row=1)
    async def refresh(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._cog().handle_refresh_click(interaction)

    @discord.ui.button(label="Ankündigung bearbeiten", style=discord.ButtonStyle.secondary, custom_id=CID_ANNOUNCE, row=1)
    async def announce(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        await self._cog().handle_announce_click(interaction)


class LinkCharView(discord.ui.View):
    """Ephemer: Raid-Slot wählen, dann per 'Weiter' zum Namens-Modal."""

    def __init__(self, cog: "LinkCharCog"):
        super().__init__(timeout=300)
        self.cog = cog
        self.selected_team: str | None = None

        texts = cog.bot.texts
        self.select = discord.ui.Select(
            placeholder=texts("link_char.select_placeholder"),
            options=[
                discord.SelectOption(label=team.label, value=key)
                for key, team in cog.bot.settings.teams.items()
            ],
            row=0,
        )
        self.select.callback = self._on_select
        self.add_item(self.select)

        self.continue_btn = discord.ui.Button(
            label=texts("link_char.btn_continue"), style=discord.ButtonStyle.primary, row=1
        )
        self.continue_btn.callback = self._on_continue
        self.add_item(self.continue_btn)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        self.selected_team = self.select.values[0]
        await interaction.response.defer()

    async def _on_continue(self, interaction: discord.Interaction) -> None:
        if self.selected_team is None:
            await interaction.response.send_message(
                self.cog.bot.texts("link_char.no_selection"), ephemeral=True
            )
            return
        from .modals import LinkCharModal

        await interaction.response.send_modal(LinkCharModal(self.cog, self.selected_team))


class TeamChoiceView(discord.ui.View):
    """Ephemer: Kader-Auswahl, wenn ein User in mehreren Kadern verlinkt ist
    und die Zuordnung (z.B. beim Wishlist-Upload) nicht eindeutig ist."""

    def __init__(self, bot: "WowHelperBot", team_keys: list[str], callback):
        super().__init__(timeout=300)
        self._callback = callback
        self.select = discord.ui.Select(
            placeholder=bot.texts("link_char.select_placeholder"),
            options=[
                discord.SelectOption(label=bot.settings.teams[k].label, value=k)
                for k in team_keys
            ],
        )
        self.select.callback = self._on_select
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction) -> None:
        await self._callback(interaction, self.select.values[0])
        self.stop()
