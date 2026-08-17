#!/usr/bin/env python3
"""Schema-Discovery für die wowaudit-API.

Ruft mit einem echten API-Key die relevanten Endpoints ab und dumpt die
JSON-Strukturen nach probe_output/. Damit werden die Feldnamen fixiert,
auf die src/wowhelper/wowaudit/schema.py aufbaut:

  - Rollen-Feld in GET /v1/characters
  - Signup-Struktur in GET /v1/raids/{id}
  - Antwort von GET /v1/wishlists (Gegenprobe für den POST-Payload)

Aufruf:
    python scripts/probe_api.py --team raid1
    python scripts/probe_api.py --key <api_key>

Nur Standardbibliothek, kein venv nötig.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://wowaudit.com/v1"
OUT_DIR = Path(__file__).resolve().parent.parent / "probe_output"


def load_dotenv(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip("'\"")
    return env


def key_for_team(team: str) -> str:
    root = Path(__file__).resolve().parent.parent
    env = load_dotenv(root / ".env")
    try:
        import yaml  # optional, nur wenn installiert

        cfg = yaml.safe_load((root / "config.yaml").read_text())
        env_name = cfg["teams"][team]["wowaudit_key_env"]
    except Exception:
        env_name = f"{team.upper()}_WOWAUDIT_KEY"
    key = env.get(env_name, "")
    if not key:
        sys.exit(f"Kein Key: {env_name} ist in .env nicht gesetzt.")
    return key


def get(path: str, key: str):
    req = urllib.request.Request(BASE + path, headers={"Authorization": key})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            pass
        return e.code, body


def summarize(data, depth: int = 0):
    """Struktur statt Masse: Listen auf das erste Element reduzieren."""
    if isinstance(data, list):
        return {"__list_len__": len(data), "__first__": summarize(data[0], depth + 1)} if data else []
    if isinstance(data, dict):
        return {k: summarize(v, depth + 1) for k, v in data.items()}
    return data


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--team", default=None, help="Team-Key aus config.yaml (z.B. raid1)")
    ap.add_argument("--key", default=None, help="wowaudit API-Key direkt angeben")
    args = ap.parse_args()

    key = args.key or key_for_team(args.team or "raid1")
    OUT_DIR.mkdir(exist_ok=True)

    endpoints = ["/characters", "/raids", "/team", "/wishlists"]
    raid_id = None

    for ep in endpoints:
        status, data = get(ep, key)
        name = ep.strip("/").replace("/", "_")
        (OUT_DIR / f"{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\n===== GET /v1{ep} -> {status} =====")
        print(json.dumps(summarize(data), indent=2, ensure_ascii=False)[:4000])
        if ep == "/raids" and isinstance(data, dict):
            raids = data.get("raids") or []
            if raids:
                raid_id = raids[-1].get("id")

    if raid_id is not None:
        status, data = get(f"/raids/{raid_id}", key)
        (OUT_DIR / "raid_detail.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"\n===== GET /v1/raids/{raid_id} -> {status} =====")
        print(json.dumps(summarize(data), indent=2, ensure_ascii=False)[:6000])
    else:
        print("\nKein Raid vorhanden — /v1/raids/{id} wurde nicht geprobt. "
              "Lege in wowaudit einen Raid an und probe erneut.")

    print(f"\nVollständige Dumps liegen in {OUT_DIR}/")
    print("Abgleichen mit: src/wowhelper/wowaudit/schema.py")


if __name__ == "__main__":
    main()
