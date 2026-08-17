"""Einstiegspunkt: python -m wowhelper

Projekt-Root (config.yaml, texts.yaml, .env) ist das Arbeitsverzeichnis,
überschreibbar mit WOWHELPER_ROOT.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from .bot import WowHelperBot
from .config import load_settings
from .texts import load_texts


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )
    root = Path(os.environ.get("WOWHELPER_ROOT", ".")).resolve()

    settings = load_settings(root)
    texts = load_texts(root)

    token = os.environ.get("DISCORD_TOKEN", "")
    if not token:
        sys.exit("DISCORD_TOKEN ist nicht gesetzt (.env).")

    # API-Keys früh prüfen — verständliche Fehlermeldung statt Crash im setup_hook
    for team in settings.teams.values():
        _ = team.api_key

    bot = WowHelperBot(settings, texts)
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
