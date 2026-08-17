"""SQLite-Zugriff (aiosqlite) mit einfachen user_version-Migrationen.

Abweichung zum ersten Entwurf, bewusst:
  - character_links hat PK (discord_id, team_key) — ein Charakter pro Raid-Slot,
    damit Spieler mit Chars in beiden Kadern beide verlinken können.
  - signups ist über (raid_post_id, character_name) gekeyt, discord_id ist
    nullable — Roster-Mitglieder ohne Discord-Verlinkung (Import aus wowaudit)
    haben keine Discord-ID.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

MIGRATIONS: list[str] = [
    # v1
    """
    CREATE TABLE character_links (
        discord_id            INTEGER NOT NULL,
        team_key              TEXT    NOT NULL,
        character_name        TEXT    NOT NULL,
        wowaudit_character_id INTEGER,
        realm                 TEXT,
        linked_at             TEXT    NOT NULL,
        PRIMARY KEY (discord_id, team_key)
    );
    CREATE TABLE raid_posts (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        team_key         TEXT    NOT NULL,
        wowaudit_raid_id INTEGER NOT NULL,
        raid_date        TEXT    NOT NULL,
        weekday          TEXT    NOT NULL,
        channel_id       INTEGER NOT NULL,
        message_id       INTEGER,
        thread_id        INTEGER,
        instance         TEXT,
        difficulty       TEXT,
        start_time       TEXT,
        end_time         TEXT,
        wa_status        TEXT,
        announcement     TEXT,
        created_at       TEXT    NOT NULL,
        UNIQUE (team_key, wowaudit_raid_id)
    );
    CREATE TABLE signups (
        raid_post_id          INTEGER NOT NULL REFERENCES raid_posts(id) ON DELETE CASCADE,
        character_name        TEXT    NOT NULL,
        wowaudit_character_id INTEGER,
        discord_id            INTEGER,
        status                TEXT    NOT NULL,
        updated_at            TEXT    NOT NULL,
        synced_at             TEXT,
        PRIMARY KEY (raid_post_id, character_name)
    );
    CREATE TABLE wishlist_uploads (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_id     INTEGER NOT NULL,
        team_key       TEXT    NOT NULL,
        report_id      TEXT    NOT NULL,
        character_name TEXT    NOT NULL,
        uploaded_at    TEXT    NOT NULL,
        ok             INTEGER NOT NULL,
        error          TEXT
    );
    """,
]


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


@dataclass
class RaidPost:
    id: int
    team_key: str
    wowaudit_raid_id: int
    raid_date: str
    weekday: str
    channel_id: int
    message_id: int | None
    thread_id: int | None
    instance: str | None
    difficulty: str | None
    start_time: str | None
    end_time: str | None
    wa_status: str | None
    announcement: str | None


@dataclass
class SignupRow:
    raid_post_id: int
    character_name: str
    wowaudit_character_id: int | None
    discord_id: int | None
    status: str
    updated_at: str
    synced_at: str | None

    @property
    def pending_sync(self) -> bool:
        return self.synced_at is None or self.updated_at > self.synced_at


@dataclass
class CharacterLink:
    discord_id: int
    team_key: str
    character_name: str
    wowaudit_character_id: int | None
    realm: str | None


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._conn: aiosqlite.Connection | None = None

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._conn is not None, "Database.connect() wurde nicht aufgerufen"
        return self._conn

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._migrate()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def _migrate(self) -> None:
        cur = await self.conn.execute("PRAGMA user_version")
        (version,) = await cur.fetchone()
        for target, script in enumerate(MIGRATIONS[version:], start=version + 1):
            await self.conn.executescript(script)
            await self.conn.execute(f"PRAGMA user_version={target}")
            await self.conn.commit()

    # ---- character_links ----------------------------------------------------

    async def upsert_character_link(
        self,
        discord_id: int,
        team_key: str,
        character_name: str,
        wowaudit_character_id: int | None,
        realm: str | None,
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO character_links (discord_id, team_key, character_name,
                                         wowaudit_character_id, realm, linked_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (discord_id, team_key) DO UPDATE SET
                character_name=excluded.character_name,
                wowaudit_character_id=excluded.wowaudit_character_id,
                realm=excluded.realm,
                linked_at=excluded.linked_at
            """,
            (discord_id, team_key, character_name, wowaudit_character_id, realm, utcnow()),
        )
        await self.conn.commit()

    async def get_character_links(self, discord_id: int) -> list[CharacterLink]:
        cur = await self.conn.execute(
            "SELECT * FROM character_links WHERE discord_id=?", (discord_id,)
        )
        return [
            CharacterLink(
                r["discord_id"], r["team_key"], r["character_name"],
                r["wowaudit_character_id"], r["realm"],
            )
            for r in await cur.fetchall()
        ]

    async def get_character_link(self, discord_id: int, team_key: str) -> CharacterLink | None:
        cur = await self.conn.execute(
            "SELECT * FROM character_links WHERE discord_id=? AND team_key=?",
            (discord_id, team_key),
        )
        r = await cur.fetchone()
        if r is None:
            return None
        return CharacterLink(
            r["discord_id"], r["team_key"], r["character_name"],
            r["wowaudit_character_id"], r["realm"],
        )

    # ---- raid_posts ---------------------------------------------------------

    @staticmethod
    def _raid_post(r: aiosqlite.Row) -> RaidPost:
        return RaidPost(
            r["id"], r["team_key"], r["wowaudit_raid_id"], r["raid_date"], r["weekday"],
            r["channel_id"], r["message_id"], r["thread_id"], r["instance"], r["difficulty"],
            r["start_time"], r["end_time"], r["wa_status"], r["announcement"],
        )

    async def create_raid_post(
        self,
        team_key: str,
        wowaudit_raid_id: int,
        raid_date: str,
        weekday: str,
        channel_id: int,
        message_id: int,
        thread_id: int | None,
        instance: str | None,
        difficulty: str | None,
        start_time: str | None,
        end_time: str | None,
        wa_status: str | None,
    ) -> int:
        cur = await self.conn.execute(
            """
            INSERT INTO raid_posts (team_key, wowaudit_raid_id, raid_date, weekday, channel_id,
                                    message_id, thread_id, instance, difficulty, start_time,
                                    end_time, wa_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (team_key, wowaudit_raid_id, raid_date, weekday, channel_id, message_id, thread_id,
             instance, difficulty, start_time, end_time, wa_status, utcnow()),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def get_raid_post_by_wowaudit(self, team_key: str, wowaudit_raid_id: int) -> RaidPost | None:
        cur = await self.conn.execute(
            "SELECT * FROM raid_posts WHERE team_key=? AND wowaudit_raid_id=?",
            (team_key, wowaudit_raid_id),
        )
        r = await cur.fetchone()
        return self._raid_post(r) if r else None

    async def get_raid_post_by_message(self, message_id: int) -> RaidPost | None:
        cur = await self.conn.execute(
            "SELECT * FROM raid_posts WHERE message_id=?", (message_id,)
        )
        r = await cur.fetchone()
        return self._raid_post(r) if r else None

    async def get_raid_post(self, raid_post_id: int) -> RaidPost | None:
        cur = await self.conn.execute("SELECT * FROM raid_posts WHERE id=?", (raid_post_id,))
        r = await cur.fetchone()
        return self._raid_post(r) if r else None

    async def list_active_raid_posts(self, today_iso: str) -> list[RaidPost]:
        cur = await self.conn.execute(
            "SELECT * FROM raid_posts WHERE raid_date >= ? ORDER BY raid_date", (today_iso,)
        )
        return [self._raid_post(r) for r in await cur.fetchall()]

    async def update_raid_meta(
        self,
        raid_post_id: int,
        instance: str | None,
        difficulty: str | None,
        start_time: str | None,
        end_time: str | None,
        wa_status: str | None,
    ) -> None:
        await self.conn.execute(
            """UPDATE raid_posts SET instance=?, difficulty=?, start_time=?, end_time=?, wa_status=?
               WHERE id=?""",
            (instance, difficulty, start_time, end_time, wa_status, raid_post_id),
        )
        await self.conn.commit()

    async def set_announcement(self, raid_post_id: int, text: str | None) -> None:
        await self.conn.execute(
            "UPDATE raid_posts SET announcement=? WHERE id=?", (text, raid_post_id)
        )
        await self.conn.commit()

    # ---- signups ------------------------------------------------------------

    @staticmethod
    def _signup(r: aiosqlite.Row) -> SignupRow:
        return SignupRow(
            r["raid_post_id"], r["character_name"], r["wowaudit_character_id"],
            r["discord_id"], r["status"], r["updated_at"], r["synced_at"],
        )

    async def set_signup(
        self,
        raid_post_id: int,
        character_name: str,
        status: str,
        discord_id: int | None,
        wowaudit_character_id: int | None,
        synced: bool = False,
    ) -> None:
        """Lokale Statusänderung (Button-Klick). synced=True bei Import aus wowaudit."""
        now = utcnow()
        await self.conn.execute(
            """
            INSERT INTO signups (raid_post_id, character_name, wowaudit_character_id,
                                 discord_id, status, updated_at, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (raid_post_id, character_name) DO UPDATE SET
                wowaudit_character_id=COALESCE(excluded.wowaudit_character_id, signups.wowaudit_character_id),
                discord_id=COALESCE(excluded.discord_id, signups.discord_id),
                status=excluded.status,
                updated_at=excluded.updated_at,
                synced_at=excluded.synced_at
            """,
            (raid_post_id, character_name, wowaudit_character_id, discord_id, status,
             now, now if synced else None),
        )
        await self.conn.commit()

    async def import_remote_signup(
        self,
        raid_post_id: int,
        character_name: str,
        status: str,
        wowaudit_character_id: int | None,
    ) -> None:
        """Status aus wowaudit übernehmen — aber niemals eine lokale,
        noch nicht zurückgeschriebene Änderung überschreiben."""
        now = utcnow()
        await self.conn.execute(
            """
            INSERT INTO signups (raid_post_id, character_name, wowaudit_character_id,
                                 discord_id, status, updated_at, synced_at)
            VALUES (?, ?, ?, NULL, ?, ?, ?)
            ON CONFLICT (raid_post_id, character_name) DO UPDATE SET
                wowaudit_character_id=COALESCE(excluded.wowaudit_character_id, signups.wowaudit_character_id),
                status=excluded.status,
                updated_at=excluded.updated_at,
                synced_at=excluded.synced_at
            WHERE signups.synced_at IS NOT NULL AND signups.updated_at <= signups.synced_at
            """,
            (raid_post_id, character_name, wowaudit_character_id, status, now, now),
        )
        await self.conn.commit()

    async def get_signups(self, raid_post_id: int) -> list[SignupRow]:
        cur = await self.conn.execute(
            "SELECT * FROM signups WHERE raid_post_id=?", (raid_post_id,)
        )
        return [self._signup(r) for r in await cur.fetchall()]

    async def pending_sync_signups(self) -> list[SignupRow]:
        cur = await self.conn.execute(
            "SELECT * FROM signups WHERE synced_at IS NULL OR updated_at > synced_at"
        )
        return [self._signup(r) for r in await cur.fetchall()]

    async def mark_signup_synced(self, raid_post_id: int, character_name: str) -> None:
        await self.conn.execute(
            "UPDATE signups SET synced_at=? WHERE raid_post_id=? AND character_name=?",
            (utcnow(), raid_post_id, character_name),
        )
        await self.conn.commit()

    # ---- wishlist_uploads ---------------------------------------------------

    async def record_wishlist_upload(
        self,
        discord_id: int,
        team_key: str,
        report_id: str,
        character_name: str,
        ok: bool,
        error: str | None = None,
    ) -> None:
        await self.conn.execute(
            """INSERT INTO wishlist_uploads (discord_id, team_key, report_id, character_name,
                                             uploaded_at, ok, error)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (discord_id, team_key, report_id, character_name, utcnow(), int(ok), error),
        )
        await self.conn.commit()
