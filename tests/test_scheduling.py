import datetime as dt

from wowhelper.cogs.signup import raids_due
from wowhelper.config import TeamConfig
from wowhelper.wowaudit.models import Raid

TODAY = dt.date(2026, 8, 10)  # ein Montag

TEAM = TeamConfig(
    label="Raid 1",
    wowaudit_key_env="X",
    channels={"thursday": 111, "sunday": 222},
)


def make_raid(raid_id: int, date: dt.date) -> Raid:
    return Raid(id=raid_id, date=date)


def test_due_within_lead_and_mapped_weekday():
    raids = [
        make_raid(1, dt.date(2026, 8, 13)),  # Donnerstag, in 3 Tagen
        make_raid(2, dt.date(2026, 8, 16)),  # Sonntag, in 6 Tagen
    ]
    due = raids_due(raids, set(), TODAY, 7, TEAM.channel_for_weekday)
    assert [r.id for r in due] == [1, 2]


def test_not_due_outside_lead():
    raids = [make_raid(1, dt.date(2026, 8, 20))]  # Donnerstag, in 10 Tagen
    assert raids_due(raids, set(), TODAY, 7, TEAM.channel_for_weekday) == []


def test_past_raid_never_due():
    raids = [make_raid(1, dt.date(2026, 8, 6))]
    assert raids_due(raids, set(), TODAY, 7, TEAM.channel_for_weekday) == []


def test_unmapped_weekday_skipped():
    raids = [make_raid(1, dt.date(2026, 8, 11))]  # Dienstag
    assert raids_due(raids, set(), TODAY, 7, TEAM.channel_for_weekday) == []


def test_existing_post_skipped_idempotent():
    raids = [make_raid(1, dt.date(2026, 8, 13))]
    first = raids_due(raids, set(), TODAY, 7, TEAM.channel_for_weekday)
    assert [r.id for r in first] == [1]
    # zweiter Lauf: Post existiert jetzt
    second = raids_due(raids, {1}, TODAY, 7, TEAM.channel_for_weekday)
    assert second == []


def test_channel_zero_counts_as_unconfigured():
    team = TeamConfig(label="X", wowaudit_key_env="X", channels={"thursday": 0})
    raids = [make_raid(1, dt.date(2026, 8, 13))]
    assert raids_due(raids, set(), TODAY, 7, team.channel_for_weekday) == []
