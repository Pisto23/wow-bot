import pytest

from wowhelper.db import Database
from wowhelper.wowaudit.models import STATUS_ABSENT, STATUS_PRESENT


@pytest.fixture
async def db(tmp_path):
    database = Database(tmp_path / "test.db")
    await database.connect()
    yield database
    await database.close()


async def make_post(db: Database, raid_id: int = 10) -> int:
    return await db.create_raid_post(
        team_key="raid1", wowaudit_raid_id=raid_id, raid_date="2026-08-13",
        weekday="thursday", channel_id=111, message_id=999, thread_id=None,
        instance="The Voidspire", difficulty="Mythic", start_time="20:00",
        end_time="23:00", wa_status="Planned",
    )


async def test_raid_post_unique_per_wowaudit_raid(db):
    await make_post(db)
    with pytest.raises(Exception):
        await make_post(db)


async def test_signup_upsert_and_pending(db):
    post_id = await make_post(db)
    await db.set_signup(post_id, "Huschee", STATUS_PRESENT, discord_id=42, wowaudit_character_id=1)
    rows = await db.get_signups(post_id)
    assert len(rows) == 1 and rows[0].status == STATUS_PRESENT and rows[0].pending_sync

    await db.mark_signup_synced(post_id, "Huschee")
    rows = await db.get_signups(post_id)
    assert not rows[0].pending_sync
    assert await db.pending_sync_signups() == []

    # Statuswechsel macht die Zeile wieder pending
    await db.set_signup(post_id, "Huschee", STATUS_ABSENT, discord_id=42, wowaudit_character_id=1)
    assert len(await db.pending_sync_signups()) == 1


async def test_remote_import_never_overwrites_pending_local(db):
    post_id = await make_post(db)
    # lokale Änderung (pending)
    await db.set_signup(post_id, "Huschee", STATUS_ABSENT, discord_id=42, wowaudit_character_id=1)
    # Remote-Import mit anderem Status darf sie nicht überschreiben
    await db.import_remote_signup(post_id, "Huschee", STATUS_PRESENT, 1)
    rows = await db.get_signups(post_id)
    assert rows[0].status == STATUS_ABSENT

    # nach Sync darf Remote wieder übernehmen
    await db.mark_signup_synced(post_id, "Huschee")
    await db.import_remote_signup(post_id, "Huschee", STATUS_PRESENT, 1)
    rows = await db.get_signups(post_id)
    assert rows[0].status == STATUS_PRESENT


async def test_remote_import_inserts_new(db):
    post_id = await make_post(db)
    await db.import_remote_signup(post_id, "Adellin", STATUS_PRESENT, 2)
    rows = await db.get_signups(post_id)
    assert rows[0].character_name == "Adellin"
    assert not rows[0].pending_sync  # Import gilt als synchronisiert


async def test_character_links_one_per_team(db):
    await db.upsert_character_link(42, "raid1", "Huschee", 1, "Blackhand")
    await db.upsert_character_link(42, "raid2", "Huschling", 9, "Blackhand")
    await db.upsert_character_link(42, "raid1", "Neuchar", 5, "Blackhand")  # überschreibt
    links = await db.get_character_links(42)
    assert {(l.team_key, l.character_name) for l in links} == {
        ("raid1", "Neuchar"), ("raid2", "Huschling"),
    }
    link = await db.get_character_link(42, "raid1")
    assert link is not None and link.wowaudit_character_id == 5


async def test_lookup_by_message(db):
    post_id = await make_post(db)
    post = await db.get_raid_post_by_message(999)
    assert post is not None and post.id == post_id
    assert await db.get_raid_post_by_message(1) is None
