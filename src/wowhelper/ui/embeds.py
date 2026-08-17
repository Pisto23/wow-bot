"""Anmelde-Embed — rein aus Daten gebaut, ohne laufenden Bot testbar.

Layout nach dem Referenz-Screenshot des alten Dagor Raidbots:
Titel, Zeit/Aktuell/Status, Ankündigung, Zusagen nach Rollen gruppiert,
darunter Nicht angemeldet / Absage / Zu spät.
"""

from __future__ import annotations

import datetime as dt

import discord

from ..texts import Texts
from ..wowaudit.models import (
    ROLE_HEAL,
    ROLE_MELEE,
    ROLE_RANGED,
    ROLE_TANK,
    STATUS_ABSENT,
    STATUS_LATE,
    STATUS_PRESENT,
    STATUS_UNKNOWN,
    Character,
)

_ZWSP = "​"
_FIELD_LIMIT = 1024

ROLE_GROUP_ORDER = (
    (ROLE_TANK, "signup.group_tanks"),
    (ROLE_MELEE, "signup.group_melees"),
    (ROLE_RANGED, "signup.group_ranged"),
    (ROLE_HEAL, "signup.group_healers"),
    ("other", "signup.group_other"),
)

OTHER_GROUP_ORDER = (
    (STATUS_UNKNOWN, "signup.group_unknown"),
    (STATUS_ABSENT, "signup.group_absent"),
    (STATUS_LATE, "signup.group_late"),
)


def format_date_de(date_iso: str) -> str:
    return dt.date.fromisoformat(date_iso).strftime("%d.%m.%Y")


def _clip(value: str) -> str:
    if len(value) <= _FIELD_LIMIT:
        return value
    return value[: _FIELD_LIMIT - 2] + " …"


def group_roster(
    roster: list[Character], statuses: dict[str, str]
) -> tuple[dict[str, list[Character]], dict[str, list[Character]], int, int]:
    """Gruppiert in (Zusagen nach Rolle, Rest nach Status) + (Zusagen, Gesamt)."""
    known_roles = {ROLE_TANK, ROLE_HEAL, ROLE_MELEE, ROLE_RANGED}
    by_name = {c.name: c for c in roster}
    # Signups von Chars, die nicht (mehr) im Roster sind, trotzdem anzeigen
    for name in statuses:
        by_name.setdefault(name, Character(id=None, name=name))

    present_by_role: dict[str, list[Character]] = {}
    rest_by_status: dict[str, list[Character]] = {}
    present_count = 0
    for name in sorted(by_name, key=str.casefold):
        char = by_name[name]
        status = statuses.get(name, STATUS_UNKNOWN)
        if status == STATUS_PRESENT:
            present_count += 1
            role = char.role if char.role in known_roles else "other"
            present_by_role.setdefault(role, []).append(char)
        else:
            rest_by_status.setdefault(status, []).append(char)
    return present_by_role, rest_by_status, present_count, len(by_name)


def build_signup_embed(
    *,
    date_iso: str,
    instance: str | None,
    difficulty: str | None,
    start_time: str | None,
    end_time: str | None,
    wa_status: str | None,
    announcement: str | None,
    roster: list[Character],
    statuses: dict[str, str],
    texts: Texts,
    class_emojis: dict[str, str] | None = None,
) -> discord.Embed:
    class_emojis = class_emojis or {}
    present_by_role, rest_by_status, present_count, total = group_roster(roster, statuses)

    embed = discord.Embed(
        title=texts(
            "signup.title",
            date=format_date_de(date_iso),
            instance=instance or "?",
            difficulty=difficulty or "?",
        ),
        description=texts("signup.description"),
        colour=discord.Colour.blurple(),
    )
    embed.add_field(
        name=texts("signup.field_time"),
        value=texts("signup.time_value", start=start_time or "?", end=end_time or "?"),
        inline=True,
    )
    embed.add_field(name=texts("signup.field_current"), value=f"{present_count}/{total}", inline=True)
    embed.add_field(name=texts("signup.field_status"), value=wa_status or "—", inline=True)
    embed.add_field(
        name=texts("signup.field_announcement"),
        value=_clip(announcement or texts("signup.no_announcement")),
        inline=False,
    )

    def emoji(char: Character) -> str:
        e = class_emojis.get(char.wow_class or "")
        return f"{e} " if e else ""

    embed.add_field(name=f"{texts('signup.group_signed')} ({present_count})", value=_ZWSP, inline=False)
    for role, text_key in ROLE_GROUP_ORDER:
        members = present_by_role.get(role, [])
        if not members:
            continue
        lines = "\n".join(f"{emoji(c)}🟢 {c.name}" for c in members)
        embed.add_field(name=f"{texts(text_key)} ({len(members)})", value=_clip(lines), inline=True)

    for status, text_key in OTHER_GROUP_ORDER:
        members = rest_by_status.get(status, [])
        if not members:
            continue
        lines = "\n".join(f"• {emoji(c)}{c.name}" for c in members)
        embed.add_field(name=f"{texts(text_key)} ({len(members)})", value=_clip(lines), inline=True)

    embed.set_footer(text=texts("signup.footer"))
    return embed


def _demo() -> None:  # pragma: no cover — manueller Sichttest: python -m wowhelper.ui.embeds
    from pathlib import Path

    from ..texts import load_texts
    from ..wowaudit.models import ROLE_HEAL, ROLE_MELEE, ROLE_RANGED, ROLE_TANK

    texts = load_texts(Path(__file__).resolve().parents[3])
    roster = [
        Character(1, "Huschee", role=ROLE_TANK, wow_class="Monk"),
        Character(2, "Seboh", role=ROLE_TANK, wow_class="Demon Hunter"),
        Character(3, "Karakamos", role=ROLE_MELEE, wow_class="Death Knight"),
        Character(4, "Alphataurus", role=ROLE_RANGED, wow_class="Druid"),
        Character(5, "Adellin", role=ROLE_HEAL, wow_class="Paladin"),
        Character(6, "Ðaylen", role=ROLE_MELEE, wow_class="Rogue"),
        Character(7, "Yaa", role=ROLE_RANGED, wow_class="Mage"),
        Character(8, "Dracäei", role=ROLE_HEAL, wow_class="Evoker"),
    ]
    statuses = {
        "Huschee": STATUS_PRESENT, "Seboh": STATUS_PRESENT, "Karakamos": STATUS_PRESENT,
        "Alphataurus": STATUS_PRESENT, "Adellin": STATUS_PRESENT,
        "Yaa": STATUS_ABSENT, "Dracäei": STATUS_LATE,
    }
    embed = build_signup_embed(
        date_iso="2026-07-23", instance="The Voidspire", difficulty="Mythic",
        start_time="20:00", end_time="23:00", wa_status="Locked", announcement=None,
        roster=roster, statuses=statuses, texts=texts,
    )
    print(f"== {embed.title} ==\n{embed.description}\n")
    for f in embed.fields:
        print(f"[{f.name}]" + ("" if f.value == _ZWSP else f"\n{f.value}"))
        print()
    print(f"-- {embed.footer.text}")


if __name__ == "__main__":  # pragma: no cover
    _demo()
