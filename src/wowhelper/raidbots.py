"""Raidbots-Report: Link/ID parsen und Report best-effort validieren."""

from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp

log = logging.getLogger(__name__)

# Report-IDs sind alphanumerische Tokens (typisch ~22 Zeichen)
_ID_RE = re.compile(r"^[A-Za-z0-9]{8,64}$")
_URL_RE = re.compile(
    r"raidbots\.com/(?:simbot/report|reports)/([A-Za-z0-9]{8,64})", re.IGNORECASE
)


def parse_report_id(raw: str) -> str | None:
    """Akzeptiert die volle Report-URL oder die blanke ID."""
    raw = raw.strip()
    m = _URL_RE.search(raw)
    if m:
        return m.group(1)
    if _ID_RE.match(raw):
        return raw
    return None


async def fetch_report_charname(session: aiohttp.ClientSession, report_id: str) -> tuple[bool | None, str | None]:
    """Best-effort-Validierung gegen Raidbots.

    Rückgabe: (exists, charname)
      exists=None  -> Validierung nicht möglich (Netzwerk etc.), Upload trotzdem versuchen
      exists=False -> Report existiert sicher nicht (404)
    """
    url = f"https://www.raidbots.com/reports/{report_id}/data.json"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 404:
                return False, None
            if resp.status != 200:
                return None, None
            data = await resp.json(content_type=None)
    except Exception as exc:  # noqa: BLE001 — Validierung ist optional
        log.info("Raidbots-Validierung nicht möglich (%s): %s", report_id, exc)
        return None, None
    return True, _extract_charname(data)


def _extract_charname(data: Any) -> str | None:
    """Charaktername aus dem Report ziehen — Pfade variieren je nach Sim-Typ."""
    candidates = (
        ("simbot", "meta", "rawFormData", "character", "name"),
        ("simbot", "player", "name"),
        ("sim", "players", 0, "name"),
    )
    for path in candidates:
        node = data
        try:
            for step in path:
                node = node[step]
        except (KeyError, IndexError, TypeError):
            continue
        if isinstance(node, str) and node:
            return node
    return None
