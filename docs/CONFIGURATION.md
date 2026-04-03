# Configuration — Startup UI & Watcher Settings

> Design document for the session configuration layer.
> Agreed: 2026-04-03. Update if decisions change.

---

## Overview

Before the watcher starts, the user goes through a **startup configuration UI**. This is not a one-time setup — it is presented (or resumable) at the beginning of each analysis session, because the relevant parameters may differ between play sessions (different campaign, different game, different frequency needs).

The configuration drives three downstream systems:
1. **Which save directory** the file watcher monitors
2. **Which SQLite database file** receives snapshots
3. **How often** the watcher actually records a snapshot (vs. silently ignoring a save)

---

## Startup Configuration Fields

| Field | Type | Notes |
|-------|------|-------|
| **Game** | Dropdown | EU5 / CK3 / HOI4 / Victoria 3 / Imperator (only EU5 for now) |
| **Save directory** | Path picker | Default path per game (auto-suggested), overridable |
| **Country played** | Text / dropdown | For labelling; auto-detected from first save if left blank |
| **Multiplayer** | Toggle | Auto-detected from save metadata, but user can override |
| **Snapshot frequency** | Dropdown | See options below |

### Snapshot Frequency Options

The watcher detects *every* file system change, but only records a snapshot to the database when the in-game date crosses the configured threshold since the last recorded snapshot.

| Option | Description | Use case |
|--------|-------------|----------|
| Every save | Record on every detected save file | Short campaigns, heavy analysis, testing |
| Every in-game year | Record once per year (Jan 1) | Standard play — recommended default |
| Every 5 years | Record every 5 in-game years | Long campaigns, keeping DB lean |
| Every 10 years | Record every 10 in-game years | Very long campaigns / overview only |
| Every 25 years | Record every 25 in-game years | Minimal footprint, AAR milestone use |

> **Implementation note:** The in-game date is available from `metadata.date` in rakaly JSON output (e.g. `"1482.1.1"`). The watcher compares the year component of the new save against the year component of the last recorded snapshot. If the difference meets or exceeds the configured threshold, the snapshot is recorded. Otherwise the save is parsed for metadata only (to detect events) and discarded.

---

## Event Detection vs. Snapshot Recording

These are **two separate concerns**:

- **Snapshot recording**: only happens at configured frequency — stores full country stat data in the DB
- **Event detection**: happens on *every* detected save — compares current save to previous parse to detect ruler deaths, wars, crises, etc.

This means even with a 10-year snapshot frequency, an event (e.g. ruler death in year 3) is never missed — it is detected on the save where it occurs, logged to the events table, and associated with the nearest snapshot date.

---

## Database Organisation

### One database file per game

```
data/
├── eu5.db         ← all EU5 campaigns
├── ck3.db         ← all CK3 campaigns (future)
├── hoi4.db        ← all HOI4 campaigns (future)
└── vic3.db        ← all Victoria 3 campaigns (future)
```

Keeping one file per game means:
- Clean separation of incompatible schemas (each game has different fields)
- No cross-game query pollution
- Easy to delete or archive a game's full history without touching others
- SQLite file size stays manageable per game

### Within a game database: campaigns distinguished by `playthrough_id`

Each game DB has a `playthroughs` table. All snapshots and events are tagged with `playthrough_id` (the UUID from `metadata.playthrough_id`). This allows:
- Multiple EU5 campaigns stored in the same `eu5.db`
- Querying a single campaign's history
- Comparing stats across campaigns (future feature)

### Proposed Schema (eu5.db)

```sql
-- One row per campaign
CREATE TABLE playthroughs (
    id              TEXT PRIMARY KEY,   -- UUID from metadata.playthrough_id
    game            TEXT NOT NULL,      -- "eu5"
    playthrough_name TEXT,              -- e.g. "Upper Bavaria #dc5a8326"
    country_tag     TEXT,               -- e.g. "WUR"
    country_name    TEXT,               -- display name if known
    multiplayer     BOOLEAN,
    snapshot_freq   TEXT,               -- "yearly", "5years", etc.
    started_at      TEXT,               -- ISO timestamp of first snapshot
    last_seen_at    TEXT                -- ISO timestamp of most recent snapshot
);

-- One row per recorded snapshot (at configured frequency)
CREATE TABLE snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    playthrough_id  TEXT NOT NULL REFERENCES playthroughs(id),
    game_date       TEXT NOT NULL,      -- in-game date e.g. "1482.1.1"
    recorded_at     TEXT NOT NULL,      -- wall-clock ISO timestamp
    data            TEXT NOT NULL       -- JSON blob of extracted country stats
);

-- One row per detected event (every save, not just snapshot saves)
CREATE TABLE events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    playthrough_id  TEXT NOT NULL REFERENCES playthroughs(id),
    game_date       TEXT NOT NULL,      -- in-game date when event occurred
    event_type      TEXT NOT NULL,      -- "ruler_death", "war_start", "war_end", "crisis_start", etc.
    payload         TEXT,               -- JSON with event-specific data
    aar_note        TEXT,               -- user-written AAR annotation (nullable)
    recorded_at     TEXT NOT NULL       -- wall-clock ISO timestamp
);
```

---

## Auto-Detection from Save

Several config fields can be auto-populated from the first save detected after the watcher starts:

| Field | Source in save |
|-------|---------------|
| Country tag | `countries.tags[played_country.country]` |
| Country display name | `metadata.player_country_name` |
| Multiplayer | `metadata.multiplayer` |
| Game date (start) | `metadata.date` |
| Playthrough ID | `metadata.playthrough_id` |
| Game version | `metadata.version` |

This means the startup UI only *needs* the user to confirm: **game** and **save directory**. Everything else can be proposed from the first save and confirmed by the user.

---

---

## Multi-Campaign Behaviour (agreed 2026-04-03)

### Context
- A full SP campaign (1337–1836) takes ~50 hours of play, typically completed in many short sessions
- A MP campaign runs over weeks or months, in 4–5 hour shared sessions
- SP and MP campaigns are likely running in parallel across time (one ongoing MP + occasional SP)
- Only **one game instance runs at a time** — two different save files will never appear simultaneously
- However, a player may close one campaign and open another without resetting the watcher (e.g. Prussia → Spain)

### Decisions

**Multiple campaigns stored simultaneously: yes.**
All campaigns across time are stored in the same game DB, keyed by `playthrough_id`. The UI can show and switch between past campaigns. No data is ever overwritten.

**Automatic campaign switch detection: yes.**
The watcher reads `metadata.playthrough_id` from every parsed save. If the ID differs from the last recorded ID, the watcher automatically:
1. Marks the previous playthrough as inactive
2. Creates or resumes the new playthrough record
3. Logs the switch as a system event in the events table
No user action needed. The UUID in the save file is the source of truth.

**Snapshot frequency changeable mid-campaign: yes.**
Since frequency is just a threshold applied at parse time (comparing current game date against last snapshot's game date in the DB), changing it has zero performance impact. It takes effect immediately on the next detected save. The setting is stored in `user_config.json` per playthrough.

**Auto-resume on app restart: yes, with confirmation.**
On startup, if a previously active playthrough is found in the DB for the configured game + save directory, the watcher proposes to resume it. The user confirms or starts fresh. This avoids forcing users to re-configure for every MP session.

### Watcher State Machine

```
App starts
  └─> Config UI (game + save dir, frequency)
        └─> Watcher armed, waiting for file change
              └─> Save detected
                    ├─> Parse metadata (playthrough_id, date)
                    ├─> Same playthrough_id as last?
                    │     ├─ YES → continue normally
                    │     └─ NO  → log switch event, activate new/resumed playthrough
                    ├─> Event detection (every save, always)
                    └─> Snapshot threshold reached?
                          ├─ YES → record full snapshot to DB
                          └─ NO  → discard parsed data, keep events only
```
