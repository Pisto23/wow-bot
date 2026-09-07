"""Typisierte Konfiguration aus config.yaml + Secrets aus .env."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
WEEKDAY_NAMES = {v: k for k, v in WEEKDAYS.items()}


class TeamConfig(BaseModel):
    label: str
    wowaudit_key_env: str
    mention_role_id: int | None = None
    raidlead_role_id: int | None = None
    channels: dict[str, int] = Field(default_factory=dict)

    @field_validator("channels")
    @classmethod
    def _known_weekdays(cls, v: dict[str, int]) -> dict[str, int]:
        for day in v:
            if day.lower() not in WEEKDAYS:
                raise ValueError(f"Unbekannter Wochentag in channels: {day!r}")
        return {k.lower(): val for k, val in v.items()}

    @property
    def api_key(self) -> str:
        key = os.environ.get(self.wowaudit_key_env, "")
        if not key:
            raise RuntimeError(
                f"API-Key fehlt: Umgebungsvariable {self.wowaudit_key_env} ist nicht gesetzt (.env)."
            )
        return key

    def channel_for_weekday(self, weekday: int) -> int | None:
        """weekday: 0=Montag … 6=Sonntag. Liefert Channel-ID oder None."""
        channel = self.channels.get(WEEKDAY_NAMES[weekday])
        return channel or None


class Settings(BaseModel):
    timezone: str = "Europe/Berlin"
    post_lead_days: int = 7
    refresh_minutes: int = 10
    guild_name: str = ""
    guild_id: int | None = None
    db_path: str = "data/wowhelper.db"
    log_path: str = "data/logs/wowhelper.log"
    log_level: str = "INFO"
    class_emojis: dict[str, str] = Field(default_factory=dict)
    teams: dict[str, TeamConfig]

    @field_validator("log_level")
    @classmethod
    def _known_level(cls, v: str) -> str:
        level = v.upper()
        if level not in logging.getLevelNamesMapping():
            raise ValueError(f"Unbekanntes log_level: {v!r} (z.B. DEBUG, INFO, WARNING)")
        return level

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


def load_settings(root: Path) -> Settings:
    load_dotenv(root / ".env")
    raw = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))
    return Settings.model_validate(raw)
