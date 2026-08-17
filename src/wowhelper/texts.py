"""Loader für texts.yaml — alle sichtbaren Strings, ohne Code editierbar."""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

log = logging.getLogger(__name__)


class Texts:
    def __init__(self, data: dict):
        self._data = data

    def __call__(self, key: str, **fmt) -> str:
        """texts("signup.btn_present") -> "Zusage". Fehlende Keys fallen auf den Key selbst zurück."""
        node = self._data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                log.warning("Text fehlt in texts.yaml: %s", key)
                return key
            node = node[part]
        text = str(node)
        if fmt:
            try:
                return text.format(**fmt)
            except (KeyError, IndexError):
                log.warning("Platzhalter passen nicht für Text %s", key)
                return text
        return text


def load_texts(root: Path) -> Texts:
    data = yaml.safe_load((root / "texts.yaml").read_text(encoding="utf-8"))
    return Texts(data or {})
