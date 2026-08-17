"""⚠️ Feldnamen-Mapping für die wowaudit-API — der EINZIGE Ort mit rohen Feldnamen.

Die API ist nicht öffentlich dokumentiert. Die hier verwendeten Namen stammen aus
Routen-Probing und einem produktiv laufenden Bot (Shebbyy/WoWAuditBot); für
mehrdeutige Felder werden Kandidaten-Listen toleriert.

Nach dem ersten Lauf von  scripts/probe_api.py  mit echtem Key:
JSON-Dumps in probe_output/ mit den Kandidaten unten abgleichen und
falsche/überflüssige Kandidaten entfernen. Alle Anpassungen NUR in dieser Datei.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from .models import (
    ROLE_HEAL,
    ROLE_MELEE,
    ROLE_RANGED,
    ROLE_TANK,
    ROLE_UNKNOWN,
    STATUS_ABSENT,
    STATUS_LATE,
    STATUS_PRESENT,
    STATUS_UNKNOWN,
    Character,
    Raid,
    Signup,
)

# ---- Status-Mapping ---------------------------------------------------------

# lokal -> wowaudit (PUT /v1/raids/{id})
STATUS_TO_WOWAUDIT = {
    STATUS_PRESENT: "Present",
    STATUS_LATE: "Late",
    STATUS_ABSENT: "Absent",
    STATUS_UNKNOWN: "Unknown",
}

# wowaudit -> lokal (tolerant, lowercase-Vergleich)
_WA_STATUS_TO_LOCAL = {
    "present": STATUS_PRESENT,
    "accepted": STATUS_PRESENT,
    "signed": STATUS_PRESENT,
    "late": STATUS_LATE,
    "absent": STATUS_ABSENT,
    "declined": STATUS_ABSENT,
    "unknown": STATUS_UNKNOWN,
}


def parse_status(raw: Any) -> str:
    if not isinstance(raw, str):
        return STATUS_UNKNOWN
    return _WA_STATUS_TO_LOCAL.get(raw.strip().lower(), STATUS_UNKNOWN)


# ---- Rollen-Mapping ---------------------------------------------------------

_WA_ROLE_TO_LOCAL = {
    "tank": ROLE_TANK,
    "heal": ROLE_HEAL,
    "healer": ROLE_HEAL,
    "heals": ROLE_HEAL,
    "melee": ROLE_MELEE,
    "ranged": ROLE_RANGED,
}


def parse_role(raw: Any) -> str:
    if not isinstance(raw, str):
        return ROLE_UNKNOWN
    return _WA_ROLE_TO_LOCAL.get(raw.strip().lower(), ROLE_UNKNOWN)


def _first(raw: dict, *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
    return default


# ---- Characters (GET /v1/characters) ---------------------------------------


def parse_characters_response(data: Any) -> list[Character]:
    # Antwort ist entweder direkt eine Liste oder {"characters": [...]}
    items = data.get("characters", []) if isinstance(data, dict) else data
    return [parse_character(c) for c in items if isinstance(c, dict)]


def parse_character(raw: dict) -> Character:
    return Character(
        id=_first(raw, "id", "character_id"),
        name=str(_first(raw, "name", "character_name", default="?")),
        realm=_first(raw, "realm", "realm_name"),
        wow_class=_first(raw, "class", "character_class", "klass"),
        role=parse_role(_first(raw, "role", "character_role")),
        rank=_first(raw, "rank", "guild_rank"),
    )


# ---- Raids (GET /v1/raids, GET /v1/raids/{id}) ------------------------------


def parse_raids_response(data: Any) -> list[Raid]:
    items = data.get("raids", []) if isinstance(data, dict) else data
    raids = []
    for r in items:
        raid = parse_raid(r)
        if raid is not None:
            raids.append(raid)
    return raids


def parse_raid(raw: Any) -> Raid | None:
    if not isinstance(raw, dict):
        return None
    # Detail-Antworten können den Raid unter "raid" wrappen
    if "raid" in raw and isinstance(raw["raid"], dict):
        raw = raw["raid"]
    raid_id = _first(raw, "id", "raid_id")
    date_raw = _first(raw, "date")
    if raid_id is None or date_raw is None:
        return None
    try:
        date = dt.date.fromisoformat(str(date_raw)[:10])
    except ValueError:
        return None
    return Raid(
        id=int(raid_id),
        date=date,
        start_time=_first(raw, "start_time", "startTime"),
        end_time=_first(raw, "end_time", "endTime"),
        instance=_first(raw, "instance", "zone"),
        difficulty=_first(raw, "difficulty"),
        status=_first(raw, "status", "state"),
        signups=[s for s in map(parse_signup, _first(raw, "signups", default=[]) or []) if s],
    )


def parse_signup(raw: Any) -> Signup | None:
    if not isinstance(raw, dict):
        return None
    char = raw.get("character") if isinstance(raw.get("character"), dict) else {}
    name = _first(char, "name") or _first(raw, "character_name", "name")
    if not name:
        return None
    return Signup(
        character_id=_first(char, "id") or _first(raw, "character_id"),
        character_name=str(name),
        status=parse_status(_first(raw, "status", "signup_status")),
        comment=_first(raw, "comment"),
    )


# ---- Payloads (schreibend) --------------------------------------------------


def build_raid_create_payload(
    api_key: str,
    date: str,
    start_time: str,
    end_time: str,
    instance: str,
    difficulty: str,
) -> dict:
    # Belegt durch Shebbyy/WoWAuditBot: POST /v1/raids erwartet den Key im Body.
    return {
        "api_key": api_key,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "instance": instance,
        "difficulty": difficulty,
    }


def build_signup_update_payload(updates: list[Signup]) -> dict:
    """PUT /v1/raids/{id} — Signup-Status setzen.

    ⚠️ UNBESTÄTIGT: Der genaue Signup-Shape des PUT-Bodys muss per
    probe_api.py / Test gegen die echte API verifiziert werden.
    """
    return {
        "signups": [
            {
                "character_id": s.character_id,
                "character_name": s.character_name,
                "status": STATUS_TO_WOWAUDIT.get(s.status, "Unknown"),
            }
            for s in updates
        ]
    }


def build_wishlist_upload_payload(
    report_id: str,
    character_name: str,
    character_id: int | None,
) -> dict:
    """POST /v1/wishlists — Raidbots-Report hochladen.

    ⚠️ UNBESTÄTIGT: report_id + Charakter-Zuordnung sind plausibel, aber die
    exakten Pflichtfelder müssen per probe_api.py / erstem echten Upload
    verifiziert werden.
    """
    payload: dict = {
        "report_id": report_id,
        "character_name": character_name,
    }
    if character_id is not None:
        payload["character_id"] = character_id
    return payload
