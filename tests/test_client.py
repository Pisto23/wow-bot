"""Client-Tests gegen einen echten aiohttp-Testserver (kein Response-Mocking)."""

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from wowhelper.wowaudit.client import WowauditClient, WowauditError


class FakeWowaudit:
    def __init__(self):
        self.requests: list[tuple[str, str, dict, dict | None]] = []
        self.fail_raids_times = 0
        self.unauthorized = False
        self.characters_payload = {"characters": [{"id": 1, "name": "A", "role": "Tank"}]}

    def build_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/characters", self.characters)
        app.router.add_get("/raids", self.raids)
        app.router.add_post("/wishlists", self.wishlists)
        return app

    async def _record(self, request: web.Request) -> None:
        body = await request.json() if request.can_read_body else None
        self.requests.append((request.method, request.path, dict(request.headers), body))

    async def characters(self, request: web.Request) -> web.Response:
        await self._record(request)
        return web.json_response(self.characters_payload)

    async def raids(self, request: web.Request) -> web.Response:
        await self._record(request)
        if self.unauthorized:
            return web.json_response({"error": "unauthorized"}, status=401)
        if self.fail_raids_times > 0:
            self.fail_raids_times -= 1
            return web.json_response({"error": "boom"}, status=500)
        return web.json_response({"raids": [{"id": 1, "date": "2026-08-13"}]})

    async def wishlists(self, request: web.Request) -> web.Response:
        await self._record(request)
        return web.json_response({"success": True})


@pytest.fixture
async def env():
    fake = FakeWowaudit()
    server = TestServer(fake.build_app())
    await server.start_server()
    session = aiohttp.ClientSession()
    client = WowauditClient(
        "secret-key", session,
        base_url=str(server.make_url("")).rstrip("/"),
        backoff=0.01,
    )
    yield client, fake
    await session.close()
    await server.close()


async def test_auth_header_is_raw_key(env):
    client, fake = env
    await client.get_characters()
    _, _, headers, _ = fake.requests[0]
    assert headers["Authorization"] == "secret-key"  # roher Key, kein "Bearer"


async def test_roster_cache(env):
    client, fake = env
    first = await client.get_characters()
    second = await client.get_characters()
    assert first is second
    assert len(fake.requests) == 1  # zweiter Aufruf kam aus dem Cache

    fake.characters_payload = {"characters": []}
    third = await client.get_characters(force=True)
    assert third == []
    assert len(fake.requests) == 2


async def test_retry_on_500_then_success(env):
    client, fake = env
    fake.fail_raids_times = 1
    raids = await client.get_raids()
    assert [r.id for r in raids] == [1]
    assert len(fake.requests) == 2


async def test_4xx_raises_without_retry(env):
    client, fake = env
    fake.unauthorized = True
    with pytest.raises(WowauditError) as exc_info:
        await client.get_raids()
    assert exc_info.value.status == 401
    assert len(fake.requests) == 1  # kein Retry bei 4xx


async def test_upload_wishlist_posts_payload(env):
    client, fake = env
    await client.upload_wishlist("report123abc", "Huschee", 1)
    method, path, _, body = fake.requests[0]
    assert (method, path) == ("POST", "/wishlists")
    assert body["report_id"] == "report123abc"
    assert body["character_name"] == "Huschee"
    assert body["character_id"] == 1
