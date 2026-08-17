from wowhelper.ui.embeds import build_signup_embed, format_date_de, group_roster
from wowhelper.wowaudit.models import (
    ROLE_HEAL,
    ROLE_MELEE,
    ROLE_RANGED,
    ROLE_TANK,
    STATUS_ABSENT,
    STATUS_LATE,
    STATUS_PRESENT,
    Character,
)


def make_roster():
    return [
        Character(1, "Huschee", role=ROLE_TANK, wow_class="Monk"),
        Character(2, "Seboh", role=ROLE_TANK, wow_class="Demon Hunter"),
        Character(3, "Karakamos", role=ROLE_MELEE, wow_class="Death Knight"),
        Character(4, "Alphataurus", role=ROLE_RANGED, wow_class="Druid"),
        Character(5, "Adellin", role=ROLE_HEAL, wow_class="Paladin"),
        Character(6, "Yaa", role=ROLE_RANGED, wow_class="Mage"),
        Character(7, "Dracäei", role=ROLE_HEAL, wow_class="Evoker"),
        Character(8, "Ðaylen", role=ROLE_MELEE, wow_class="Rogue"),
    ]


STATUSES = {
    "Huschee": STATUS_PRESENT,
    "Seboh": STATUS_PRESENT,
    "Karakamos": STATUS_PRESENT,
    "Alphataurus": STATUS_PRESENT,
    "Adellin": STATUS_PRESENT,
    "Yaa": STATUS_ABSENT,
    "Dracäei": STATUS_LATE,
    # Ðaylen: kein Eintrag -> Nicht angemeldet
}


def test_group_roster_counts():
    present_by_role, rest, present, total = group_roster(make_roster(), STATUSES)
    assert present == 5
    assert total == 8
    assert [c.name for c in present_by_role[ROLE_TANK]] == ["Huschee", "Seboh"]
    assert len(present_by_role[ROLE_MELEE]) == 1
    assert len(rest[STATUS_ABSENT]) == 1
    assert len(rest[STATUS_LATE]) == 1
    # Nicht angemeldet enthält Ðaylen
    assert [c.name for c in rest["unknown"]] == ["Ðaylen"]


def test_signup_not_in_roster_still_shown():
    statuses = dict(STATUSES, Gast=STATUS_PRESENT)
    present_by_role, _, present, total = group_roster(make_roster(), statuses)
    assert present == 6
    assert total == 9
    assert any(c.name == "Gast" for c in present_by_role["other"])


def test_embed_structure(texts):
    embed = build_signup_embed(
        date_iso="2026-07-23",
        instance="The Voidspire",
        difficulty="Mythic",
        start_time="20:00",
        end_time="23:00",
        wa_status="Locked",
        announcement=None,
        roster=make_roster(),
        statuses=STATUSES,
        texts=texts,
    )
    assert embed.title == "23.07.2026 • The Voidspire (Mythic)"
    field_names = [f.name for f in embed.fields]
    assert any("5/8" in f.value for f in embed.fields)
    assert any("Zusage (5)" in n for n in field_names)
    assert any("Tanks (2)" in n for n in field_names)
    assert any("Nicht angemeldet (1)" in n for n in field_names)
    assert any("Absage (1)" in n for n in field_names)
    assert any("Zu spät (1)" in n for n in field_names)
    # Kein Feld darf leer sein (Discord-API-Limit)
    assert all(f.value for f in embed.fields)


def test_embed_empty_roster(texts):
    embed = build_signup_embed(
        date_iso="2026-07-23", instance=None, difficulty=None, start_time=None,
        end_time=None, wa_status=None, announcement=None, roster=[], statuses={}, texts=texts,
    )
    assert any("0/0" in f.value for f in embed.fields)


def test_format_date_de():
    assert format_date_de("2026-07-23") == "23.07.2026"
