"""Bot-Klasse: Lifecycle, Cogs, persistente Views, Command-Sync."""

from __future__ import annotations

import logging

import aiohttp
import discord
from discord.ext import commands

from .config import Settings
from .db import Database
from .texts import Texts
from .wowaudit.client import WowauditClient

log = logging.getLogger(__name__)


class WowHelperBot(commands.Bot):
    def __init__(self, settings: Settings, texts: Texts):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
        )
        self.settings = settings
        self.texts = texts
        self.db = Database(settings.db_path)
        self.http_session: aiohttp.ClientSession | None = None
        self.wowaudit: dict[str, WowauditClient] = {}

    async def setup_hook(self) -> None:
        self.http_session = aiohttp.ClientSession()
        await self.db.connect()
        for key, team in self.settings.teams.items():
            self.wowaudit[key] = WowauditClient(team.api_key, self.http_session)

        from .cogs.admin import AdminCog
        from .cogs.link_char import LinkCharCog
        from .cogs.signup import SignupCog
        from .cogs.wishlist import WishlistCog
        from .ui.views import SignupView

        await self.add_cog(SignupCog(self))
        await self.add_cog(LinkCharCog(self))
        await self.add_cog(WishlistCog(self))
        await self.add_cog(AdminCog(self))

        # Eine registrierte Instanz bedient alle Anmelde-Posts (feste custom_ids)
        self.add_view(SignupView(self))

        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Slash-Commands für Guild %s synchronisiert", self.settings.guild_id)
        else:
            await self.tree.sync()
            log.info("Slash-Commands global synchronisiert (bis zu 1h Verzögerung)")

    async def on_ready(self) -> None:
        log.info("Eingeloggt als %s (%s)", self.user, self.user.id if self.user else "?")

    async def close(self) -> None:
        await super().close()
        if self.http_session is not None:
            await self.http_session.close()
        await self.db.close()
