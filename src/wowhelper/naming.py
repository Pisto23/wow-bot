"""Charakternamen-Matching: case-insensitiv, Realm-Suffix, Sonderzeichen.

Im Kader stehen Namen wie Ðaylen, Mórli, Nërdz — die tippt niemand zuverlässig.
Match-Reihenfolge: exakt (casefold) -> diakritik-bereinigt -> Vorschläge.
"""

from __future__ import annotations

import difflib
import unicodedata

# Zeichen, die NFKD nicht zerlegt, aber offensichtliche ASCII-Entsprechungen haben
_EXTRA = str.maketrans({
    "ð": "d", "Ð": "d",
    "þ": "th", "Þ": "th",
    "ø": "o", "Ø": "o",
    "æ": "ae", "Æ": "ae",
    "œ": "oe", "Œ": "oe",
    "ß": "ss",
    "ł": "l", "Ł": "l",
})


def strip_realm(name: str) -> str:
    """'Name-Realm' -> 'Name'. Namen selbst enthalten kein '-'."""
    return name.split("-", 1)[0].strip()


def normalize(name: str) -> str:
    """Exakter Vergleichsschlüssel: NFC + casefold."""
    return unicodedata.normalize("NFC", strip_realm(name)).casefold()


def fold(name: str) -> str:
    """Toleranter Vergleichsschlüssel: Diakritika entfernen, Sonderzeichen ersetzen."""
    text = normalize(name).translate(_EXTRA)
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def match_character(query: str, names: list[str]) -> tuple[str | None, list[str]]:
    """Liefert (Treffer, Vorschläge). Treffer ist der Original-Name aus `names`."""
    by_exact = {normalize(n): n for n in names}
    hit = by_exact.get(normalize(query))
    if hit is not None:
        return hit, []

    by_fold: dict[str, str] = {}
    for n in names:
        by_fold.setdefault(fold(n), n)
    hit = by_fold.get(fold(query))
    if hit is not None:
        return hit, []

    close = difflib.get_close_matches(fold(query), list(by_fold), n=3, cutoff=0.6)
    return None, [by_fold[c] for c in close]
