# Dagor Raidbot (wow-helper)

Discord-Bot mit wowaudit-Anbindung für die Gilde **Dagor**:

- **Automatische Raid-Anmeldung** — liest anstehende Raids aus wowaudit und postet
  pro Termin ein Anmelde-Embed in den passenden Wochentags-Channel
  (`#do-raidanmeldung` / `#so-raidanmeldung`), mit Buttons **Zusage / Zu Spät / Absage**.
  Status wird lokal gespeichert und best-effort nach wowaudit zurückgeschrieben.
- **`/link_char`** — verknüpft deinen Discord-Account mit deinem wowaudit-Charakter
  (Raid-Slot wählen → Weiter → Charaktername eingeben).
- **`/start_wishlist`** — Pop-up für einen Raidbots-Link/ID; der Droptimizer-Sim
  wird zu wowaudit hochgeladen (Loot-Wishlist-Tracking).
- **Admin:** `/raid_post` (Anmeldung sofort posten), `/resync`, `/link_status`.

## Setup

### 1. Discord-Bot anlegen

1. [Discord Developer Portal](https://discord.com/developers/applications) → *New Application* → *Bot*.
2. **Privileged Gateway Intents**: `Server Members Intent` aktivieren.
3. Token kopieren → `.env` (`DISCORD_TOKEN`).
4. Einladen über *OAuth2 → URL Generator*: Scopes `bot` + `applications.commands`;
   Berechtigungen: *Send Messages, Embed Links, Create Public Threads,
   Send Messages in Threads, Manage Messages*.

### 2. wowaudit-Keys

Pro Kader (Team) den API-Key aus wowaudit holen (nur Team-Admins:
`wowaudit.com/<region>/<realm>/<gilde>/<team>` → *API*) → `.env`
(`RAID1_WOWAUDIT_KEY`, `RAID2_WOWAUDIT_KEY`).

### 3. Konfigurieren

```bash
cp .env.example .env       # Token + API-Keys eintragen
$EDITOR config.yaml        # Channel-IDs, Rollen-IDs, guild_id eintragen
$EDITOR texts.yaml         # optional: alle Bot-Texte anpassen
```

### 4. API-Schema verifizieren (einmalig, wichtig!)

Die wowaudit-API ist nicht öffentlich dokumentiert. Einige Feldnamen in
[src/wowhelper/wowaudit/schema.py](src/wowhelper/wowaudit/schema.py) sind als
Kandidaten hinterlegt und müssen einmal gegen die echte API geprüft werden:

```bash
python scripts/probe_api.py --team raid1
```

Die JSON-Dumps landen in `probe_output/`. Abweichende Feldnamen **nur** in
`schema.py` korrigieren (Rollen-Feld, Signup-Struktur, Wishlist-Payload).

### 5. Starten

Lokal (mit [uv](https://docs.astral.sh/uv/)):

```bash
uv sync
uv run python -m wowhelper
```

Docker:

```bash
docker compose up -d --build
```

## Entwicklung

```bash
uv run pytest                          # Unit-Tests
uv run python -m wowhelper.ui.embeds   # Embed-Demo (ASCII) ohne Discord
```

Struktur: `src/wowhelper/wowaudit/` (API-Client, **schema.py** = einziger Ort mit
rohen wowaudit-Feldnamen), `src/wowhelper/ui/` (Embeds, Views, Modals),
`src/wowhelper/cogs/` (Features), `texts.yaml` (alle sichtbaren Strings).

## Betrieb

- SQLite liegt in `data/` (Docker: Volume `botdata`).
- Anmelde-Buttons sind persistent — Bot-Neustarts brechen keine Posts.
- Writeback zu wowaudit ist best-effort; nicht synchronisierte Status werden
  alle 10 Minuten erneut versucht (`/resync` stößt es sofort an).
