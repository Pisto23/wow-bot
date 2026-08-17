"""Interne Datenmodelle — entkoppelt von den wowaudit-Feldnamen (siehe schema.py)."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

# Lokale Status-Enum, 1:1 die vier Kategorien aus dem Anmelde-Embed.
STATUS_PRESENT = "present"   # Zusage
STATUS_LATE = "late"         # Zu Spät
STATUS_ABSENT = "absent"     # Absage
STATUS_UNKNOWN = "unknown"   # Nicht angemeldet
ALL_STATUSES = (STATUS_PRESENT, STATUS_LATE, STATUS_ABSENT, STATUS_UNKNOWN)

ROLE_TANK = "tank"
ROLE_HEAL = "heal"
ROLE_MELEE = "melee"
ROLE_RANGED = "ranged"
ROLE_UNKNOWN = "unknown"


@dataclass
class Character:
    id: int | None
    name: str
    realm: str | None = None
    wow_class: str | None = None
    role: str = ROLE_UNKNOWN
    rank: str | None = None


@dataclass
class Signup:
    character_id: int | None
    character_name: str
    status: str  # lokale Status-Enum
    comment: str | None = None


@dataclass
class Raid:
    id: int
    date: dt.date
    start_time: str | None = None
    end_time: str | None = None
    instance: str | None = None
    difficulty: str | None = None
    status: str | None = None  # wowaudit-Raid-Status (z.B. "Planned", "Locked")
    signups: list[Signup] = field(default_factory=list)
