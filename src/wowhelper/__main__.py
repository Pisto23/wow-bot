"""Einstiegspunkt: python -m wowhelper

Projekt-Root (config.yaml, texts.yaml, .env) ist das Arbeitsverzeichnis,
überschreibbar mit WOWHELPER_ROOT.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

from .bot import WowHelperBot
from .config import Settings, load_settings
from .texts import load_texts

LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"

log = logging.getLogger(__name__)


def setup_file_logging(root: Path, settings: Settings) -> None:
    """Rotierender File-Handler am Root-Logger — fängt auch discord.py-Logs."""
    log_file = root / settings.log_path
    log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level)
    log.info("Logge zusätzlich nach %s (Level %s)", log_file, settings.log_level)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    root = Path(os.environ.get("WOWHELPER_ROOT", ".")).resolve()

    settings = load_settings(root)
    setup_file_logging(root, settings)
    texts = load_texts(root)

    token = os.environ.get("DISCORD_TOKEN", "")
    if not token:
        sys.exit("DISCORD_TOKEN ist nicht gesetzt (.env).")

    # API-Keys früh prüfen — verständliche Fehlermeldung statt Crash im setup_hook
    for team in settings.teams.values():
        _ = team.api_key

    bot = WowHelperBot(settings, texts)
    try:
        bot.run(token, log_handler=None)
    except Exception:
        log.exception("Bot beendet durch unbehandelten Fehler")
        raise


if __name__ == "__main__":
    main()
