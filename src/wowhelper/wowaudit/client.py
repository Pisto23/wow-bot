"""Async-Client für die wowaudit-API: Auth, Retry/Backoff, Roster-TTL-Cache."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

from . import schema
from .models import Character, Raid, Signup

log = logging.getLogger(__name__)

BASE_URL = "https://wowaudit.com/v1"


class WowauditError(Exception):
    def __init__(self, status: int, body: Any):
        self.status = status
        self.body = body
        super().__init__(f"wowaudit API error {status}: {str(body)[:300]}")


class WowauditClient:
    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession,
        base_url: str = BASE_URL,
        roster_ttl: float = 600.0,
        backoff: float = 2.0,
    ):
        self._api_key = api_key
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._roster_ttl = roster_ttl
        self._backoff = backoff
        self._roster_cache: tuple[float, list[Character]] | None = None

    async def _request(self, method: str, path: str, json: dict | None = None) -> Any:
        url = f"{self._base_url}{path}"
        headers = {"Authorization": self._api_key, "Accept": "application/json"}
        last_exc: Exception | None = None
        for attempt in range(3):
            if attempt:
                await asyncio.sleep(self._backoff * 2 ** (attempt - 1))
            try:
                async with self._session.request(
                    method, url, headers=headers, json=json,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status in (429,) or resp.status >= 500:
                        last_exc = WowauditError(resp.status, await resp.text())
                        log.warning("wowaudit %s %s -> %s (Versuch %d)", method, path, resp.status, attempt + 1)
                        continue
                    if resp.status >= 400:
                        raise WowauditError(resp.status, await resp.text())
                    if resp.content_type == "application/json":
                        return await resp.json()
                    return await resp.text()
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_exc = exc
                log.warning("wowaudit %s %s Netzwerkfehler: %s (Versuch %d)", method, path, exc, attempt + 1)
        raise last_exc if last_exc else WowauditError(0, "unbekannter Fehler")

    # ---- lesend -------------------------------------------------------------

    async def get_characters(self, force: bool = False) -> list[Character]:
        now = time.monotonic()
        if not force and self._roster_cache and now - self._roster_cache[0] < self._roster_ttl:
            return self._roster_cache[1]
        data = await self._request("GET", "/characters")
        roster = schema.parse_characters_response(data)
        self._roster_cache = (now, roster)
        return roster

    async def get_raids(self) -> list[Raid]:
        data = await self._request("GET", "/raids")
        return schema.parse_raids_response(data)

    async def get_raid(self, raid_id: int) -> Raid | None:
        data = await self._request("GET", f"/raids/{raid_id}")
        return schema.parse_raid(data)

    # ---- schreibend ---------------------------------------------------------

    async def update_signups(self, raid_id: int, updates: list[Signup]) -> Any:
        payload = schema.build_signup_update_payload(updates)
        return await self._request("PUT", f"/raids/{raid_id}", json=payload)

    async def upload_wishlist(
        self, report_id: str, character_name: str, character_id: int | None
    ) -> Any:
        payload = schema.build_wishlist_upload_payload(report_id, character_name, character_id)
        return await self._request("POST", "/wishlists", json=payload)
