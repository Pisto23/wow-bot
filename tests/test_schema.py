"""Parsing-Tests gegen die angenommenen wowaudit-Strukturen.

Diese Fixtures kodieren die Annahmen aus schema.py. Nach dem ersten Lauf von
scripts/probe_api.py mit echtem Key: Fixtures durch echte Dumps ersetzen.
"""

import datetime as dt

from wowhelper.wowaudit import schema
from wowhelper.wowaudit.models import (
    ROLE_HEAL,
    ROLE_MELEE,
    ROLE_TANK,
    STATUS_ABSENT,
    STATUS_LATE,
    STATUS_PRESENT,
    STATUS_UNKNOWN,
)

CHARACTERS_FIXTURE = {
    "characters": [
        {"id": 1, "name": "Huschee", "realm": "Blackhand", "class": "Monk", "role": "Tank", "rank": "Raider"},
        {"id": 2, "name": "Adellin", "realm": "Blackhand", "class": "Paladin", "role": "Heal"},
        {"id": 3, "name": "Karakamos", "realm": "Blackhand", "class": "Death Knight", "role": "Melee"},
        {"id": 4, "name": "Kaputt", "realm": None, "class": None, "role": "Gibberish"},
    ]
}

RAIDS_FIXTURE = {
    "raids": [
        {"id": 10, "date": "2026-08-13", "start_time": "20:00", "end_time": "23:00",
         "instance": "The Voidspire", "difficulty": "Mythic", "status": "Planned"},
        {"id": 11, "date": "2026-08-16", "start_time": "20:00", "end_time": "23:00",
         "instance": "The Voidspire", "difficulty": "Mythic", "status": "Planned"},
        {"id": 12, "date": "kaputt"},
    ]
}

RAID_DETAIL_FIXTURE = {
    "raid": {
        "id": 10, "date": "2026-08-13", "start_time": "20:00", "end_time": "23:00",
        "instance": "The Voidspire", "difficulty": "Mythic", "status": "Locked",
        "signups": [
            {"character": {"id": 1, "name": "Huschee"}, "status": "Present"},
            {"character": {"id": 2, "name": "Adellin"}, "status": "Absent"},
            {"character_id": 3, "character_name": "Karakamos", "status": "Late"},
            {"character": {"id": 4, "name": "Kaputt"}, "status": "Whatever"},
            {"status": "Present"},  # ohne Namen -> verwerfen
        ],
    }
}


def test_parse_characters():
    chars = schema.parse_characters_response(CHARACTERS_FIXTURE)
    assert [c.name for c in chars] == ["Huschee", "Adellin", "Karakamos", "Kaputt"]
    assert chars[0].role == ROLE_TANK
    assert chars[1].role == ROLE_HEAL
    assert chars[2].role == ROLE_MELEE
    assert chars[3].role == "unknown"
    assert chars[0].id == 1


def test_parse_characters_bare_list():
    chars = schema.parse_characters_response(CHARACTERS_FIXTURE["characters"])
    assert len(chars) == 4


def test_parse_raids_skips_broken():
    raids = schema.parse_raids_response(RAIDS_FIXTURE)
    assert [r.id for r in raids] == [10, 11]
    assert raids[0].date == dt.date(2026, 8, 13)
    assert raids[0].instance == "The Voidspire"


def test_parse_raid_detail_signups():
    raid = schema.parse_raid(RAID_DETAIL_FIXTURE)
    assert raid is not None and raid.status == "Locked"
    statuses = {s.character_name: s.status for s in raid.signups}
    assert statuses == {
        "Huschee": STATUS_PRESENT,
        "Adellin": STATUS_ABSENT,
        "Karakamos": STATUS_LATE,
        "Kaputt": STATUS_UNKNOWN,
    }
    by_name = {s.character_name: s for s in raid.signups}
    assert by_name["Karakamos"].character_id == 3


def test_status_roundtrip():
    for local, wa in schema.STATUS_TO_WOWAUDIT.items():
        assert schema.parse_status(wa) == local


def test_wishlist_payload():
    payload = schema.build_wishlist_upload_payload("abc123", "Huschee", 1)
    assert payload["report_id"] == "abc123"
    assert payload["character_name"] == "Huschee"
    assert payload["character_id"] == 1
    assert "character_id" not in schema.build_wishlist_upload_payload("abc123", "Huschee", None)
