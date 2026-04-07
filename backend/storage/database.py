"""
database.py — Async SQLite database layer

One Database instance per game (eu5.db, ck3.db, etc.).
All operations are async (aiosqlite) for FastAPI compatibility.

Schema (tables, all prefixed with their group):

  Core:
    playthroughs        — one row per campaign (UUID PK from save metadata)
    snapshots           — one row per recorded snapshot (at configured frequency)
    events              — one row per detected event (every save parse)
                          Key columns:
                            dedup_key TEXT  — stable unique key for one-time events
                                             (NULL for repeatable events); enforced
                                             by a partial UNIQUE index so INSERT OR
                                             IGNORE silently drops re-emitted events
                                             on pipeline restart
                            country_tag TEXT — primary country for single-country
                                              events; NULL for wars/situations/ages

  Religions:
    religions           — static religion metadata (written once per religion per campaign)
    religion_snapshots  — per-religion metrics at each snapshot date

  Wars:
    wars                — static war metadata (written once on first sight)
    war_snapshots       — score progression at each snapshot date
    war_participants    — one row per country per war (status, losses, scores)

  Geography:
    locations           — static location metadata (raw material, port, holy sites)
    location_snapshots  — per-location ownership/demographics/economy at each snapshot
    provinces           — static province metadata
    province_snapshots  — per-province food economy at each snapshot

  Demographics:
    pop_snapshots       — individual pop rows at each snapshot (~107k rows per snapshot)
                          Aggregate queries via get_pop_aggregates() group by type,
                          culture, religion, estate, location, or status.

Schema migrations are handled automatically in _run_migrations() called from open().
"""

from __future__ import annotations

import json
import logging
import aiosqlite
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS playthroughs (
    id              TEXT PRIMARY KEY,   -- UUID from metadata.playthrough_id
    game            TEXT NOT NULL,      -- "eu5"
    playthrough_name TEXT,              -- e.g. "Upper Bavaria #dc5a8326"
    country_tag     TEXT,               -- e.g. "WUR"
    country_name    TEXT,               -- display name if known
    multiplayer     BOOLEAN,
    snapshot_freq   TEXT,               -- "every_save", "yearly", "5years", etc.
    enabled_fields  TEXT,               -- JSON list of enabled field keys
    game_version    TEXT,               -- game version from save metadata
    started_at      TEXT,               -- ISO timestamp of first snapshot
    last_seen_at    TEXT,               -- ISO timestamp of most recent activity
    last_game_date  TEXT                -- most recent in-game date seen
);

CREATE TABLE IF NOT EXISTS snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    playthrough_id  TEXT NOT NULL REFERENCES playthroughs(id),
    game_date       TEXT NOT NULL,      -- in-game date e.g. "1482.1.1"
    recorded_at     TEXT NOT NULL,      -- wall-clock ISO timestamp
    data            TEXT NOT NULL,      -- JSON blob of extracted country stats
    UNIQUE(playthrough_id, game_date)   -- one snapshot per date per campaign
);
CREATE INDEX IF NOT EXISTS idx_snapshots_playthrough
    ON snapshots(playthrough_id, game_date);

CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    playthrough_id  TEXT NOT NULL REFERENCES playthroughs(id),
    game_date       TEXT NOT NULL,      -- in-game date when event occurred
    event_type      TEXT NOT NULL,      -- "ruler_changed", "war_started", etc.
    payload         TEXT,               -- JSON with event-specific data
    aar_note        TEXT,               -- user-written AAR annotation (nullable)
    recorded_at     TEXT NOT NULL,      -- wall-clock ISO timestamp
    dedup_key       TEXT,               -- unique key for one-time events (nullable)
    country_tag     TEXT                -- primary country tag for single-country events (nullable)
);
CREATE INDEX IF NOT EXISTS idx_events_playthrough
    ON events(playthrough_id, game_date);
-- NOTE: idx_events_dedup and idx_events_country are created by _run_migrations()
--       (not here) because they reference dedup_key/country_tag columns that may
--       not exist yet on databases that predate the Phase 9 event-system rework.

-- ── Religion entity tables ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS religions (
    playthrough_id  TEXT    NOT NULL REFERENCES playthroughs(id),
    id              INTEGER NOT NULL,       -- religion_manager.database key (numeric)
    definition      TEXT    NOT NULL,       -- string key e.g. "catholic"
    name            TEXT,                   -- display name (localised)
    religion_group  TEXT,                   -- e.g. "christian", "buddhist"
    has_religious_head BOOLEAN DEFAULT 0,
    color_rgb       TEXT,                   -- JSON [r,g,b]
    PRIMARY KEY (playthrough_id, id)        -- composite PK — same pattern as cultures
);

CREATE TABLE IF NOT EXISTS religion_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    playthrough_id  TEXT NOT NULL REFERENCES playthroughs(id),
    snapshot_id     INTEGER NOT NULL REFERENCES snapshots(id),
    religion_id     INTEGER NOT NULL,
    game_date       TEXT NOT NULL,
    important_country TEXT,                 -- TAG of most important country (nullable)
    reform_desire   REAL,
    tithe           REAL,
    saint_power     REAL,
    timed_modifier_count INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_religion_snap
    ON religion_snapshots(playthrough_id, snapshot_id);

-- ── Culture entity table ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS cultures (
    id              INTEGER NOT NULL,
    playthrough_id  TEXT    NOT NULL,
    definition      TEXT    NOT NULL,          -- string key e.g. "upper_german_culture"
    name            TEXT,                      -- display name (localised)
    culture_group   TEXT,                      -- e.g. "west_germanic"
    PRIMARY KEY (playthrough_id, id)
);
CREATE INDEX IF NOT EXISTS idx_cultures_id ON cultures(playthrough_id, id);

-- ── War entity tables ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS wars (
    id              TEXT NOT NULL,           -- war_manager.database key (numeric string)
    playthrough_id  TEXT NOT NULL REFERENCES playthroughs(id),
    name_key        TEXT,                   -- war name key / template
    name_display    TEXT,                   -- resolved display name
    start_date      TEXT,
    end_date        TEXT,                   -- NULL while active
    is_civil_war    BOOLEAN DEFAULT 0,
    is_revolt       BOOLEAN DEFAULT 0,
    original_attacker_id INTEGER,           -- country numeric ID
    original_target_id INTEGER,             -- country numeric ID
    original_defenders TEXT,                -- JSON list of country IDs
    goal_type       TEXT,                   -- e.g. "parliament_conquer_province"
    casus_belli     TEXT,                   -- e.g. "cb_parliament_conquer_province"
    goal_target     TEXT,                   -- JSON blob of target info
    PRIMARY KEY(playthrough_id, id)
);

CREATE TABLE IF NOT EXISTS war_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    playthrough_id  TEXT NOT NULL REFERENCES playthroughs(id),
    snapshot_id     INTEGER NOT NULL REFERENCES snapshots(id),
    war_id          TEXT NOT NULL,
    game_date       TEXT NOT NULL,
    attacker_score  REAL,
    defender_score  REAL,
    net_war_score   REAL,                   -- derived: attacker - defender
    war_direction_quarter REAL,
    war_direction_year REAL,
    war_goal_held   INTEGER                 -- location ID (nullable)
);
CREATE INDEX IF NOT EXISTS idx_war_snap
    ON war_snapshots(playthrough_id, snapshot_id);

CREATE TABLE IF NOT EXISTS war_participants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    playthrough_id  TEXT NOT NULL REFERENCES playthroughs(id),
    war_id          TEXT NOT NULL,
    country_id      INTEGER NOT NULL,       -- numeric country ID
    country_tag     TEXT,                   -- resolved TAG
    side            TEXT NOT NULL,           -- "Attacker" or "Defender"
    join_reason     TEXT,                   -- "Instigator", "Target", "Called", etc.
    join_type       TEXT,                   -- "Always", "Called", etc.
    called_by       INTEGER,                -- country ID that called (nullable)
    join_date       TEXT,
    status          TEXT DEFAULT 'Active',  -- "Active", "Left", "Declined"
    score_combat    REAL DEFAULT 0,
    score_siege     REAL DEFAULT 0,
    score_joining   REAL DEFAULT 0,
    losses          TEXT,                   -- JSON blob {unit_type: {cause: count}}
    io_id           INTEGER,                -- international_organization link (nullable)
    UNIQUE(playthrough_id, war_id, country_id)
);

-- ── Geography entity tables ────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS locations (
    id              INTEGER NOT NULL,           -- location ID from locations.locations key
    playthrough_id  TEXT NOT NULL REFERENCES playthroughs(id),
    province_id     INTEGER,                    -- references provinces.id (nullable for sea/TI)
    raw_material    TEXT,                       -- e.g. "clay", "wheat", "lumber"
    is_port         BOOLEAN DEFAULT 0,          -- has a port
    holy_sites      TEXT,                       -- JSON list of religion IDs
    PRIMARY KEY(playthrough_id, id)
);

CREATE TABLE IF NOT EXISTS location_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    playthrough_id  TEXT NOT NULL REFERENCES playthroughs(id),
    snapshot_id     INTEGER NOT NULL REFERENCES snapshots(id),
    location_id     INTEGER NOT NULL,
    game_date       TEXT NOT NULL,
    -- Ownership & Control
    owner_id        INTEGER,
    controller_id   INTEGER,
    previous_owner_id INTEGER,
    last_owner_change TEXT,
    last_controller_change TEXT,
    cores           TEXT,                       -- JSON list of country IDs
    garrison        REAL,
    control         REAL,                       -- 0-1 float
    -- Demographics & Culture
    culture_id      INTEGER,
    secondary_culture_id INTEGER,
    cultural_unity  REAL,
    religion_id     INTEGER,
    religious_unity REAL,
    language        TEXT,
    dialect         TEXT,
    pop_count       INTEGER,                   -- counters.Pops
    -- Economic Geography
    rank            TEXT,                       -- "rural_settlement", "town", "city"
    development     REAL,
    prosperity      REAL,
    tax             REAL,
    possible_tax    REAL,
    market_id       INTEGER,
    market_access   REAL,
    value_flow      REAL,
    institutions    TEXT,                       -- JSON blob {institution_key: spread_pct}
    -- Geopolitical Status
    integration_type TEXT,                      -- "core", "integrated", "conquered", "colonized", "none"
    integration_owner_id INTEGER,
    slave_raid_date TEXT,                       -- nullable; date of last slave raid
    owner_tag TEXT                              -- resolved country tag for owner_id (e.g. "BAV")
);
CREATE INDEX IF NOT EXISTS idx_loc_snap_pt
    ON location_snapshots(playthrough_id, snapshot_id);
CREATE INDEX IF NOT EXISTS idx_loc_snap_loc
    ON location_snapshots(playthrough_id, location_id, game_date);
CREATE INDEX IF NOT EXISTS idx_loc_snap_owner_tag
    ON location_snapshots(playthrough_id, owner_tag);

CREATE TABLE IF NOT EXISTS provinces (
    id              INTEGER NOT NULL,           -- province_id from provinces.database key
    playthrough_id  TEXT NOT NULL REFERENCES playthroughs(id),
    province_definition TEXT,                   -- config key string
    capital_location_id INTEGER,
    PRIMARY KEY(playthrough_id, id)
);

CREATE TABLE IF NOT EXISTS province_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    playthrough_id  TEXT NOT NULL REFERENCES playthroughs(id),
    snapshot_id     INTEGER NOT NULL REFERENCES snapshots(id),
    province_id     INTEGER NOT NULL,
    game_date       TEXT NOT NULL,
    owner_id        INTEGER,
    food_current    REAL,
    food_max        REAL,
    food_change_delta REAL,
    trade_balance   REAL,
    goods_produced  TEXT                        -- JSON blob {good_type: amount}
);
CREATE INDEX IF NOT EXISTS idx_prov_snap
    ON province_snapshots(playthrough_id, snapshot_id);

-- ── Demographics entity table ──────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pop_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    playthrough_id  TEXT NOT NULL REFERENCES playthroughs(id),
    snapshot_id     INTEGER NOT NULL REFERENCES snapshots(id),
    game_date       TEXT NOT NULL,
    location_id     INTEGER NOT NULL,
    pop_id          INTEGER NOT NULL,           -- key in population.database
    type            TEXT NOT NULL,               -- nobles, clergy, burghers, peasants, laborers, soldiers, tribesmen, slaves
    estate          TEXT,                        -- nobles_estate, clergy_estate, etc.
    culture_id      INTEGER,
    religion_id     INTEGER,
    size            REAL,                        -- population mass scalar
    status          TEXT,                        -- Primary, Accepted, Tolerated, or NULL
    satisfaction    REAL,                        -- 0-1 (slaves always 0)
    intervention_satisfaction REAL,              -- nullable; government policy modifier
    literacy        REAL,                        -- 0-100 percentage
    owner_id        INTEGER                     -- nullable; controlling country when != location owner
);
CREATE INDEX IF NOT EXISTS idx_pop_snap_pt
    ON pop_snapshots(playthrough_id, snapshot_id);
CREATE INDEX IF NOT EXISTS idx_pop_snap_loc
    ON pop_snapshots(playthrough_id, location_id, game_date);
CREATE INDEX IF NOT EXISTS idx_pop_snap_type
    ON pop_snapshots(playthrough_id, type, game_date);

-- ── Country reference table ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS countries (
    playthrough_id  TEXT    NOT NULL,
    country_id      INTEGER NOT NULL,   -- numeric game ID
    tag             TEXT    NOT NULL,   -- 3-letter TAG e.g. "BAV", "FRA"
    name            TEXT,               -- localised display name (nullable)
    prev_tags       TEXT,               -- JSON array of predecessor TAGs (nullable)
    canonical_tag   TEXT NOT NULL,      -- terminal TAG in succession chain (self if no successor)
    PRIMARY KEY (playthrough_id, country_id),
    UNIQUE (playthrough_id, tag)
);
CREATE INDEX IF NOT EXISTS idx_countries_tag ON countries(playthrough_id, tag);
CREATE INDEX IF NOT EXISTS idx_countries_canonical ON countries(playthrough_id, canonical_tag);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Database class
# ---------------------------------------------------------------------------

class Database:
    """
    Async SQLite wrapper for one game's database file.

    Usage:
        db = Database("data/eu5.db")
        await db.open()
        ...
        await db.close()

    Or as an async context manager:
        async with Database("data/eu5.db") as db:
            ...
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def open(self) -> None:
        """Open (or create) the database and ensure schema exists."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(str(self.db_path))
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(_SCHEMA_SQL)
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.commit()
        await self._run_migrations()

    async def _run_migrations(self) -> None:
        """
        Idempotent schema migrations.

        Migration 1 — snapshot deduplication (unique constraint):
          Existing snapshots tables have no UNIQUE(playthrough_id, game_date)
          constraint.  We can't ADD CONSTRAINT via SQLite ALTER TABLE, so we
          rebuild the table if the unique index doesn't exist yet.

        Migration 2 — events columns (dedup_key, country_tag):
          Adds dedup_key and country_tag columns if absent, and creates the
          supporting indexes.
        """
        # --- Migration 1: ensure snapshots unique constraint exists ---
        cursor = await self.conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name='idx_snapshots_unique_date'"
        )
        if not await cursor.fetchone():
            # Rebuild snapshots table with the UNIQUE constraint.
            # We rename the old table, create the new one, copy data, drop old.
            await self.conn.executescript("""
                ALTER TABLE snapshots RENAME TO snapshots_old;

                CREATE TABLE snapshots (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    playthrough_id  TEXT NOT NULL REFERENCES playthroughs(id),
                    game_date       TEXT NOT NULL,
                    recorded_at     TEXT NOT NULL,
                    data            TEXT NOT NULL,
                    UNIQUE(playthrough_id, game_date)
                );

                INSERT OR IGNORE INTO snapshots
                    SELECT id, playthrough_id, game_date, recorded_at, data
                    FROM snapshots_old
                    ORDER BY id ASC;

                DROP TABLE snapshots_old;
            """)
            await self.conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_snapshots_playthrough "
                "ON snapshots(playthrough_id, game_date)"
            )
            await self.conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_unique_date "
                "ON snapshots(playthrough_id, game_date)"
            )
            await self.conn.commit()
            logger.info("DB migration: added UNIQUE constraint to snapshots(playthrough_id, game_date)")

        # --- Migration 2: events dedup_key / country_tag columns ---
        cursor = await self.conn.execute("PRAGMA table_info(events)")
        cols = {row[1] for row in await cursor.fetchall()}

        needs_migration = "dedup_key" not in cols or "country_tag" not in cols
        if needs_migration:
            if "dedup_key" not in cols:
                await self.conn.execute("ALTER TABLE events ADD COLUMN dedup_key TEXT")
            if "country_tag" not in cols:
                await self.conn.execute("ALTER TABLE events ADD COLUMN country_tag TEXT")

            # Clear old events — they have no dedup_key so they'd always be
            # re-inserted on the next pipeline run (the new INSERT OR IGNORE would
            # not de-duplicate against them).  The pipeline re-records everything
            # from the next save parse anyway.
            await self.conn.execute("DELETE FROM events")
            await self.conn.commit()
            logger.info(
                "DB migration: added dedup_key + country_tag columns to events; "
                "cleared stale event rows"
            )

        # Always ensure the dedup/country indexes exist (idempotent).
        # These are NOT in _SCHEMA_SQL because on an old DB the columns don't
        # exist yet when executescript runs — so we create them here, after
        # the ALTER TABLE above has guaranteed the columns are present.
        await self.conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_events_dedup "
            "ON events(playthrough_id, dedup_key) WHERE dedup_key IS NOT NULL"
        )
        await self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_country "
            "ON events(playthrough_id, country_tag)"
        )
        await self.conn.commit()

        # --- Migration 3: owner_tag column on location_snapshots ---
        cursor = await self.conn.execute("PRAGMA table_info(location_snapshots)")
        loc_cols = {row[1] for row in await cursor.fetchall()}
        if "owner_tag" not in loc_cols:
            await self.conn.execute(
                "ALTER TABLE location_snapshots ADD COLUMN owner_tag TEXT"
            )
            # Index created idempotently below
        await self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_loc_snap_owner_tag "
            "ON location_snapshots(playthrough_id, owner_tag)"
        )
        await self.conn.commit()
        if "owner_tag" not in loc_cols:
            logger.info(
                "DB migration: added owner_tag column + index to location_snapshots; "
                "run backfill to populate existing data"
            )

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def __aenter__(self) -> Database:
        await self.open()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not open. Call open() or use 'async with'.")
        return self._conn

    # ------------------------------------------------------------------
    # Playthroughs
    # ------------------------------------------------------------------

    async def get_playthrough(self, playthrough_id: str) -> dict | None:
        """Get a playthrough by its UUID, or None if not found."""
        cursor = await self.conn.execute(
            "SELECT * FROM playthroughs WHERE id = ?", (playthrough_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def upsert_playthrough(
        self,
        playthrough_id: str,
        game: str,
        playthrough_name: str = "",
        country_tag: str = "",
        country_name: str = "",
        multiplayer: bool = False,
        snapshot_freq: str = "yearly",
        enabled_fields: list[str] | None = None,
        game_version: str = "",
        game_date: str = "",
    ) -> None:
        """Create or update a playthrough record."""
        now = _now_iso()
        fields_json = json.dumps(enabled_fields) if enabled_fields else "[]"

        existing = await self.get_playthrough(playthrough_id)
        if existing is None:
            await self.conn.execute(
                """INSERT INTO playthroughs
                   (id, game, playthrough_name, country_tag, country_name,
                    multiplayer, snapshot_freq, enabled_fields, game_version,
                    started_at, last_seen_at, last_game_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (playthrough_id, game, playthrough_name, country_tag,
                 country_name, multiplayer, snapshot_freq, fields_json,
                 game_version, now, now, game_date),
            )
        else:
            await self.conn.execute(
                """UPDATE playthroughs
                   SET playthrough_name = ?, country_tag = ?, country_name = ?,
                       multiplayer = ?, game_version = ?,
                       last_seen_at = ?, last_game_date = ?
                   WHERE id = ?""",
                (playthrough_name, country_tag, country_name, multiplayer,
                 game_version, now, game_date, playthrough_id),
            )
        await self.conn.commit()

    async def update_playthrough_freq(
        self, playthrough_id: str, snapshot_freq: str
    ) -> None:
        """Update just the snapshot frequency for a playthrough."""
        await self.conn.execute(
            "UPDATE playthroughs SET snapshot_freq = ? WHERE id = ?",
            (snapshot_freq, playthrough_id),
        )
        await self.conn.commit()

    async def update_playthrough_fields(
        self, playthrough_id: str, enabled_fields: list[str]
    ) -> None:
        """Update the enabled field set for a playthrough."""
        await self.conn.execute(
            "UPDATE playthroughs SET enabled_fields = ? WHERE id = ?",
            (json.dumps(enabled_fields), playthrough_id),
        )
        await self.conn.commit()

    async def list_playthroughs(self, game: str | None = None) -> list[dict]:
        """List all playthroughs, optionally filtered by game."""
        if game:
            cursor = await self.conn.execute(
                "SELECT * FROM playthroughs WHERE game = ? ORDER BY last_seen_at DESC",
                (game,),
            )
        else:
            cursor = await self.conn.execute(
                "SELECT * FROM playthroughs ORDER BY last_seen_at DESC"
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_last_game_date(self, playthrough_id: str) -> str | None:
        """Get the most recent in-game date for a playthrough (from playthroughs table)."""
        cursor = await self.conn.execute(
            "SELECT last_game_date FROM playthroughs WHERE id = ?",
            (playthrough_id,),
        )
        row = await cursor.fetchone()
        return row["last_game_date"] if row else None

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    async def snapshot_exists(self, playthrough_id: str, game_date: str) -> bool:
        """Return True if a snapshot for this playthrough+date is already stored."""
        cursor = await self.conn.execute(
            "SELECT 1 FROM snapshots WHERE playthrough_id = ? AND game_date = ? LIMIT 1",
            (playthrough_id, game_date),
        )
        return await cursor.fetchone() is not None

    async def insert_snapshot(
        self,
        playthrough_id: str,
        game_date: str,
        data: dict,
    ) -> int | None:
        """
        Insert a snapshot and update the playthrough's last_seen_at / last_game_date.

        Returns the new snapshot ID, or None if a snapshot for this
        (playthrough_id, game_date) pair already exists (silently skipped).
        """
        now = _now_iso()
        cursor = await self.conn.execute(
            """INSERT OR IGNORE INTO snapshots (playthrough_id, game_date, recorded_at, data)
               VALUES (?, ?, ?, ?)""",
            (playthrough_id, game_date, now, json.dumps(data)),
        )
        if cursor.lastrowid == 0:
            # IGNORE fired — a snapshot for this date already exists
            return None
        # Update playthrough timestamps
        await self.conn.execute(
            "UPDATE playthroughs SET last_seen_at = ?, last_game_date = ? WHERE id = ?",
            (now, game_date, playthrough_id),
        )
        await self.conn.commit()
        return cursor.lastrowid  # type: ignore

    async def get_snapshots(
        self,
        playthrough_id: str,
        limit: int = 0,
        after_date: str | None = None,
    ) -> list[dict]:
        """
        Get snapshots for a playthrough, ordered by game date.
        Optional: limit count, filter after a game date.
        """
        query = "SELECT * FROM snapshots WHERE playthrough_id = ?"
        params: list[Any] = [playthrough_id]

        if after_date:
            query += " AND game_date > ?"
            params.append(after_date)

        query += " ORDER BY game_date ASC"

        if limit > 0:
            query += " LIMIT ?"
            params.append(limit)

        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_last_snapshot_date(self, playthrough_id: str) -> str | None:
        """Get the game date of the most recent snapshot for a playthrough."""
        cursor = await self.conn.execute(
            """SELECT game_date FROM snapshots
               WHERE playthrough_id = ?
               ORDER BY game_date DESC LIMIT 1""",
            (playthrough_id,),
        )
        row = await cursor.fetchone()
        return row["game_date"] if row else None

    async def snapshot_count(self, playthrough_id: str) -> int:
        cursor = await self.conn.execute(
            "SELECT COUNT(*) as cnt FROM snapshots WHERE playthrough_id = ?",
            (playthrough_id,),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    async def insert_events(
        self,
        playthrough_id: str,
        events: list[dict],
    ) -> int:
        """
        Bulk-insert events using INSERT OR IGNORE.

        Each dict must have: game_date, event_type, payload.
        Optional fields: dedup_key (str|None), country_tag (str|None).

        INSERT OR IGNORE silently drops rows that violate the unique index on
        (playthrough_id, dedup_key), which prevents one-time events like
        situation_started and war_started from being recorded twice when the
        pipeline restarts.

        Returns the number of rows passed in (some may have been ignored).
        """
        if not events:
            return 0

        now = _now_iso()
        rows = [
            (
                playthrough_id,
                e["game_date"],
                e["event_type"],
                json.dumps(e.get("payload", {})),
                None,
                now,
                e.get("dedup_key"),
                e.get("country_tag"),
            )
            for e in events
        ]
        await self.conn.executemany(
            """INSERT OR IGNORE INTO events
               (playthrough_id, game_date, event_type, payload, aar_note, recorded_at,
                dedup_key, country_tag)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        await self.conn.commit()
        return len(rows)

    async def get_events(
        self,
        playthrough_id: str,
        event_type: str | None = None,
        country_tags: list[str] | None = None,
        include_global: bool = True,
        limit: int = 0,
    ) -> list[dict]:
        """
        Get events for a playthrough with optional type and country filters.

        country_tags:   list of country tags to filter by (None = no filter).
        include_global: when True (default) and country_tags is set, NULL-tagged
                        events (age transitions, situations, all wars) are always
                        included alongside the tag-matched events.
                        When False, only directly-tagged events and war events
                        where a selected tag appears in payload.participants are
                        returned.
        """
        query = "SELECT * FROM events WHERE playthrough_id = ?"
        params: list[Any] = [playthrough_id]

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        if country_tags:
            ph = ",".join("?" * len(country_tags))
            if include_global:
                # NULL-tagged events always shown; also match direct country events.
                query += f" AND (country_tag IS NULL OR country_tag IN ({ph}))"
                params.extend(country_tags)
            else:
                # Only tagged events matching the selection, plus war/global events
                # where a participant tag matches.
                participant_match = (
                    f"EXISTS (SELECT 1 FROM json_each(json_extract(payload, '$.participants')) "
                    f"WHERE value IN ({ph}))"
                )
                query += f" AND (country_tag IN ({ph}) OR {participant_match})"
                params.extend(country_tags)   # country_tag IN
                params.extend(country_tags)   # participant_match

        query += " ORDER BY game_date ASC"

        if limit > 0:
            query += " LIMIT ?"
            params.append(limit)

        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_event_country_tags(self, playthrough_id: str) -> list[str]:
        """Return sorted list of distinct non-null country tags in events for a playthrough."""
        cursor = await self.conn.execute(
            """SELECT DISTINCT country_tag FROM events
               WHERE playthrough_id = ? AND country_tag IS NOT NULL
               ORDER BY country_tag""",
            (playthrough_id,),
        )
        rows = await cursor.fetchall()
        return [row["country_tag"] for row in rows]

    async def event_count(self, playthrough_id: str) -> int:
        cursor = await self.conn.execute(
            "SELECT COUNT(*) as cnt FROM events WHERE playthrough_id = ?",
            (playthrough_id,),
        )
        row = await cursor.fetchone()
        return row["cnt"] if row else 0

    async def update_aar_note(self, event_id: int, note: str) -> None:
        """Set or update the AAR annotation on an event."""
        await self.conn.execute(
            "UPDATE events SET aar_note = ? WHERE id = ?",
            (note, event_id),
        )
        await self.conn.commit()

    # ------------------------------------------------------------------
    # Religions
    # ------------------------------------------------------------------

    async def upsert_religion(
        self,
        playthrough_id: str,
        religion_id: int,
        definition: str,
        name: str = "",
        religion_group: str = "",
        has_religious_head: bool = False,
        color_rgb: list | None = None,
    ) -> None:
        """Create or update a religion static record."""
        await self.conn.execute(
            """INSERT INTO religions
               (playthrough_id, id, definition, name, religion_group,
                has_religious_head, color_rgb)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(playthrough_id, id) DO UPDATE SET
                   definition = excluded.definition,
                   name = excluded.name,
                   religion_group = excluded.religion_group,
                   has_religious_head = excluded.has_religious_head,
                   color_rgb = excluded.color_rgb""",
            (playthrough_id, religion_id, definition, name, religion_group,
             has_religious_head, json.dumps(color_rgb) if color_rgb else None),
        )

    async def insert_religion_snapshots(
        self,
        playthrough_id: str,
        snapshot_id: int,
        game_date: str,
        rows: list[dict],
    ) -> int:
        """Bulk-insert religion snapshot rows."""
        if not rows:
            return 0
        data = [
            (playthrough_id, snapshot_id, r["religion_id"], game_date,
             r.get("important_country"), r.get("reform_desire"),
             r.get("tithe"), r.get("saint_power"),
             r.get("timed_modifier_count", 0))
            for r in rows
        ]
        await self.conn.executemany(
            """INSERT INTO religion_snapshots
               (playthrough_id, snapshot_id, religion_id, game_date,
                important_country, reform_desire, tithe, saint_power,
                timed_modifier_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            data,
        )
        return len(data)

    async def get_religion_snapshots(
        self,
        playthrough_id: str,
        religion_id: int | None = None,
    ) -> list[dict]:
        """Get religion snapshots, optionally filtered by religion_id."""
        query = "SELECT * FROM religion_snapshots WHERE playthrough_id = ?"
        params: list[Any] = [playthrough_id]
        if religion_id is not None:
            query += " AND religion_id = ?"
            params.append(religion_id)
        query += " ORDER BY game_date ASC"
        cursor = await self.conn.execute(query, params)
        return [dict(r) for r in await cursor.fetchall()]

    async def get_religions(self, playthrough_id: str) -> list[dict]:
        """Get all religion static records for a playthrough."""
        cursor = await self.conn.execute(
            "SELECT * FROM religions WHERE playthrough_id = ? ORDER BY id",
            (playthrough_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    # ------------------------------------------------------------------
    # Cultures
    # ------------------------------------------------------------------

    async def bulk_upsert_cultures(
        self,
        playthrough_id: str,
        rows: list[dict],
    ) -> int:
        """Upsert culture static rows.  ON CONFLICT updates name so later
        saves (with fuller localisation) can override earlier stubs."""
        if not rows:
            return 0
        data = [
            (
                playthrough_id,
                r["culture_id"],
                r["definition"],
                r.get("name"),
                r.get("culture_group", ""),
            )
            for r in rows
        ]
        await self.conn.executemany(
            """INSERT INTO cultures
               (playthrough_id, id, definition, name, culture_group)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(playthrough_id, id) DO UPDATE SET
                   name         = COALESCE(excluded.name, name),
                   culture_group = COALESCE(excluded.culture_group, culture_group)""",
            data,
        )
        await self.conn.commit()
        return len(data)

    async def get_cultures(self, playthrough_id: str) -> list[dict]:
        """Get all culture static records for a playthrough."""
        cursor = await self.conn.execute(
            "SELECT * FROM cultures WHERE playthrough_id = ? ORDER BY id",
            (playthrough_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    # ------------------------------------------------------------------
    # Wars
    # ------------------------------------------------------------------

    async def upsert_war(self, playthrough_id: str, war: dict) -> None:
        """Create or update a war static record."""
        await self.conn.execute(
            """INSERT INTO wars
               (id, playthrough_id, name_key, name_display, start_date, end_date,
                is_civil_war, is_revolt, original_attacker_id, original_target_id,
                original_defenders, goal_type, casus_belli, goal_target)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(playthrough_id, id) DO UPDATE SET
                   end_date = excluded.end_date,
                   name_display = excluded.name_display""",
            (war["id"], playthrough_id, war.get("name_key"), war.get("name_display"),
             war.get("start_date"), war.get("end_date"),
             war.get("is_civil_war", False), war.get("is_revolt", False),
             war.get("original_attacker_id"), war.get("original_target_id"),
             json.dumps(war.get("original_defenders")),
             war.get("goal_type"), war.get("casus_belli"),
             json.dumps(war.get("goal_target"))),
        )

    async def insert_war_snapshots(
        self,
        playthrough_id: str,
        snapshot_id: int,
        game_date: str,
        rows: list[dict],
    ) -> int:
        """Bulk-insert war snapshot rows."""
        if not rows:
            return 0
        data = [
            (playthrough_id, snapshot_id, r["war_id"], game_date,
             r.get("attacker_score"), r.get("defender_score"),
             r.get("net_war_score"), r.get("war_direction_quarter"),
             r.get("war_direction_year"), r.get("war_goal_held"))
            for r in rows
        ]
        await self.conn.executemany(
            """INSERT INTO war_snapshots
               (playthrough_id, snapshot_id, war_id, game_date,
                attacker_score, defender_score, net_war_score,
                war_direction_quarter, war_direction_year, war_goal_held)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            data,
        )
        return len(data)

    async def upsert_war_participants(
        self,
        playthrough_id: str,
        war_id: str,
        participants: list[dict],
    ) -> int:
        """Upsert war participant records (insert or update status/scores)."""
        if not participants:
            return 0
        for p in participants:
            await self.conn.execute(
                """INSERT INTO war_participants
                   (playthrough_id, war_id, country_id, country_tag, side,
                    join_reason, join_type, called_by, join_date, status,
                    score_combat, score_siege, score_joining, losses, io_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(playthrough_id, war_id, country_id) DO UPDATE SET
                       status = excluded.status,
                       score_combat = excluded.score_combat,
                       score_siege = excluded.score_siege,
                       score_joining = excluded.score_joining,
                       losses = excluded.losses""",
                (playthrough_id, war_id, p["country_id"], p.get("country_tag"),
                 p["side"], p.get("join_reason"), p.get("join_type"),
                 p.get("called_by"), p.get("join_date"), p.get("status", "Active"),
                 p.get("score_combat", 0), p.get("score_siege", 0),
                 p.get("score_joining", 0),
                 json.dumps(p.get("losses")) if p.get("losses") else None,
                 p.get("io_id")),
            )
        return len(participants)

    async def get_wars(
        self,
        playthrough_id: str,
        active_only: bool = False,
    ) -> list[dict]:
        """Get all wars for a playthrough."""
        query = "SELECT * FROM wars WHERE playthrough_id = ?"
        params: list[Any] = [playthrough_id]
        if active_only:
            query += " AND end_date IS NULL"
        query += " ORDER BY start_date ASC"
        cursor = await self.conn.execute(query, params)
        return [dict(r) for r in await cursor.fetchall()]

    async def get_war_participants(
        self, playthrough_id: str, war_id: str | None = None,
    ) -> list[dict]:
        """Get war participants, optionally filtered by war_id."""
        query = "SELECT * FROM war_participants WHERE playthrough_id = ?"
        params: list[Any] = [playthrough_id]
        if war_id is not None:
            query += " AND war_id = ?"
            params.append(war_id)
        query += " ORDER BY war_id, side, join_date"
        cursor = await self.conn.execute(query, params)
        return [dict(r) for r in await cursor.fetchall()]

    async def get_war_snapshots(
        self, playthrough_id: str, war_id: str | None = None,
    ) -> list[dict]:
        """Get war snapshot history, optionally filtered by war_id."""
        query = "SELECT * FROM war_snapshots WHERE playthrough_id = ?"
        params: list[Any] = [playthrough_id]
        if war_id is not None:
            query += " AND war_id = ?"
            params.append(war_id)
        query += " ORDER BY game_date ASC"
        cursor = await self.conn.execute(query, params)
        return [dict(r) for r in await cursor.fetchall()]

    # ------------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------------

    async def upsert_location(self, playthrough_id: str, loc: dict) -> None:
        """Create or update a location static record."""
        await self.conn.execute(
            """INSERT INTO locations
               (id, playthrough_id, province_id, raw_material, is_port, holy_sites)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(playthrough_id, id) DO UPDATE SET
                   raw_material = excluded.raw_material,
                   is_port = excluded.is_port""",
            (loc["id"], playthrough_id,
             loc.get("province_id"), loc.get("raw_material"),
             loc.get("is_port", False),
             json.dumps(loc.get("holy_sites")) if loc.get("holy_sites") else None),
        )

    async def bulk_upsert_locations(
        self, playthrough_id: str, locs: list[dict],
    ) -> int:
        """Bulk upsert location static records."""
        if not locs:
            return 0
        data = [
            (loc["id"], playthrough_id,
             loc.get("province_id"), loc.get("raw_material"),
             loc.get("is_port", False),
             json.dumps(loc.get("holy_sites")) if loc.get("holy_sites") else None)
            for loc in locs
        ]
        await self.conn.executemany(
            """INSERT INTO locations
               (id, playthrough_id, province_id, raw_material, is_port, holy_sites)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(playthrough_id, id) DO UPDATE SET
                   raw_material = excluded.raw_material,
                   is_port = excluded.is_port""",
            data,
        )
        return len(data)

    async def insert_location_snapshots(
        self,
        playthrough_id: str,
        snapshot_id: int,
        game_date: str,
        rows: list[dict],
    ) -> int:
        """Bulk-insert location snapshot rows (one per owned location)."""
        if not rows:
            return 0
        data = [
            (playthrough_id, snapshot_id, r["location_id"], game_date,
             r.get("owner_id"), r.get("owner_tag"), r.get("controller_id"), r.get("previous_owner_id"),
             r.get("last_owner_change"), r.get("last_controller_change"),
             json.dumps(r["cores"]) if r.get("cores") else None,
             r.get("garrison"), r.get("control"),
             r.get("culture_id"), r.get("secondary_culture_id"), r.get("cultural_unity"),
             r.get("religion_id"), r.get("religious_unity"),
             r.get("language"), r.get("dialect"), r.get("pop_count"),
             r.get("rank"), r.get("development"), r.get("prosperity"),
             r.get("tax"), r.get("possible_tax"),
             r.get("market_id"), r.get("market_access"), r.get("value_flow"),
             json.dumps(r["institutions"]) if r.get("institutions") else None,
             r.get("integration_type"), r.get("integration_owner_id"),
             r.get("slave_raid_date"))
            for r in rows
        ]
        await self.conn.executemany(
            """INSERT INTO location_snapshots
               (playthrough_id, snapshot_id, location_id, game_date,
                owner_id, owner_tag, controller_id, previous_owner_id,
                last_owner_change, last_controller_change,
                cores, garrison, control,
                culture_id, secondary_culture_id, cultural_unity,
                religion_id, religious_unity,
                language, dialect, pop_count,
                rank, development, prosperity,
                tax, possible_tax,
                market_id, market_access, value_flow,
                institutions,
                integration_type, integration_owner_id,
                slave_raid_date)
               VALUES (?,?,?,?, ?,?,?,?,?,?, ?,?,?, ?,?,?, ?,?, ?,?,?, ?,?,?, ?,?, ?,?,?, ?, ?,?,?)""",
            data,
        )
        return len(data)

    async def get_locations(self, playthrough_id: str) -> list[dict]:
        """Get all location static records for a playthrough."""
        cursor = await self.conn.execute(
            "SELECT * FROM locations WHERE playthrough_id = ? ORDER BY id",
            (playthrough_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_location_snapshots(
        self,
        playthrough_id: str,
        location_id: int | None = None,
        snapshot_id: int | None = None,
        owner_id: int | None = None,
    ) -> list[dict]:
        """Get location snapshots with optional filters."""
        query = "SELECT * FROM location_snapshots WHERE playthrough_id = ?"
        params: list[Any] = [playthrough_id]
        if location_id is not None:
            query += " AND location_id = ?"
            params.append(location_id)
        if snapshot_id is not None:
            query += " AND snapshot_id = ?"
            params.append(snapshot_id)
        if owner_id is not None:
            query += " AND owner_id = ?"
            params.append(owner_id)
        query += " ORDER BY game_date ASC, location_id ASC"
        cursor = await self.conn.execute(query, params)
        return [dict(r) for r in await cursor.fetchall()]

    # ------------------------------------------------------------------
    # Provinces
    # ------------------------------------------------------------------

    async def bulk_upsert_provinces(
        self, playthrough_id: str, provs: list[dict],
    ) -> int:
        """Bulk upsert province static records."""
        if not provs:
            return 0
        data = [
            (p["id"], playthrough_id,
             p.get("province_definition"), p.get("capital_location_id"))
            for p in provs
        ]
        await self.conn.executemany(
            """INSERT INTO provinces
               (id, playthrough_id, province_definition, capital_location_id)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(playthrough_id, id) DO UPDATE SET
                   province_definition = excluded.province_definition,
                   capital_location_id = excluded.capital_location_id""",
            data,
        )
        return len(data)

    async def insert_province_snapshots(
        self,
        playthrough_id: str,
        snapshot_id: int,
        game_date: str,
        rows: list[dict],
    ) -> int:
        """Bulk-insert province snapshot rows."""
        if not rows:
            return 0
        data = [
            (playthrough_id, snapshot_id, r["province_id"], game_date,
             r.get("owner_id"), r.get("food_current"), r.get("food_max"),
             r.get("food_change_delta"), r.get("trade_balance"),
             json.dumps(r["goods_produced"]) if r.get("goods_produced") else None)
            for r in rows
        ]
        await self.conn.executemany(
            """INSERT INTO province_snapshots
               (playthrough_id, snapshot_id, province_id, game_date,
                owner_id, food_current, food_max, food_change_delta,
                trade_balance, goods_produced)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            data,
        )
        return len(data)

    async def get_provinces(self, playthrough_id: str) -> list[dict]:
        """Get all province static records for a playthrough."""
        cursor = await self.conn.execute(
            "SELECT * FROM provinces WHERE playthrough_id = ? ORDER BY id",
            (playthrough_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_province_snapshots(
        self,
        playthrough_id: str,
        province_id: int | None = None,
        snapshot_id: int | None = None,
    ) -> list[dict]:
        """Get province snapshots with optional filters."""
        query = "SELECT * FROM province_snapshots WHERE playthrough_id = ?"
        params: list[Any] = [playthrough_id]
        if province_id is not None:
            query += " AND province_id = ?"
            params.append(province_id)
        if snapshot_id is not None:
            query += " AND snapshot_id = ?"
            params.append(snapshot_id)
        query += " ORDER BY game_date ASC, province_id ASC"
        cursor = await self.conn.execute(query, params)
        return [dict(r) for r in await cursor.fetchall()]

    # ------------------------------------------------------------------
    # Pop Snapshots (Demographics)
    # ------------------------------------------------------------------

    async def insert_pop_snapshots(
        self,
        playthrough_id: str,
        snapshot_id: int,
        game_date: str,
        rows: list[dict],
    ) -> int:
        """Bulk-insert pop snapshot rows (~107k per snapshot)."""
        if not rows:
            return 0
        data = [
            (playthrough_id, snapshot_id, game_date,
             r["location_id"], r["pop_id"], r["type"],
             r.get("estate"), r.get("culture_id"), r.get("religion_id"),
             r.get("size"), r.get("status"),
             r.get("satisfaction"), r.get("intervention_satisfaction"),
             r.get("literacy"), r.get("owner_id"))
            for r in rows
        ]
        await self.conn.executemany(
            """INSERT INTO pop_snapshots
               (playthrough_id, snapshot_id, game_date,
                location_id, pop_id, type,
                estate, culture_id, religion_id,
                size, status,
                satisfaction, intervention_satisfaction,
                literacy, owner_id)
               VALUES (?,?,?, ?,?,?, ?,?,?, ?,?, ?,?, ?,?)""",
            data,
        )
        return len(data)

    async def get_pop_snapshots(
        self,
        playthrough_id: str,
        location_id: int | None = None,
        snapshot_id: int | None = None,
        pop_type: str | None = None,
        owner_id: int | None = None,
    ) -> list[dict]:
        """Get pop snapshots with optional filters.

        WARNING: Unfiltered queries return ~107k rows per snapshot.
        Always pass at least one filter.
        """
        query = "SELECT * FROM pop_snapshots WHERE playthrough_id = ?"
        params: list[Any] = [playthrough_id]
        if location_id is not None:
            query += " AND location_id = ?"
            params.append(location_id)
        if snapshot_id is not None:
            query += " AND snapshot_id = ?"
            params.append(snapshot_id)
        if pop_type is not None:
            query += " AND type = ?"
            params.append(pop_type)
        if owner_id is not None:
            query += " AND owner_id = ?"
            params.append(owner_id)
        query += " ORDER BY game_date ASC, location_id ASC, pop_id ASC"
        cursor = await self.conn.execute(query, params)
        return [dict(r) for r in await cursor.fetchall()]

    async def get_pop_aggregates(
        self,
        playthrough_id: str,
        group_by: str = "type",
        from_date: str | None = None,
        to_date: str | None = None,
        owner_tags: list[str] | None = None,
    ) -> list[dict]:
        """Get aggregated pop data grouped by a dimension over a date range.

        group_by:   "type", "culture_id", "religion_id", "status", "location_id", "estate"
        from_date:  EU5 game date string lower bound e.g. "1444.11.11"
        to_date:    EU5 game date string upper bound — defaults to from_date (point-in-time)
        owner_tags: list of country TAGs to filter by (e.g. ["SWI","BRN"] for Switzerland
                    including its predecessor Bern) — resolved via location_snapshots.owner_tag
        """
        valid_groups = {"type", "culture_id", "religion_id", "status", "location_id", "estate"}
        if group_by not in valid_groups:
            group_by = "type"

        # Normalise date range
        if from_date and not to_date:
            to_date = from_date  # point-in-time

        if owner_tags:
            # Join via location_snapshots to filter by owning countries
            ph = ",".join("?" * len(owner_tags))
            query = f"""
                SELECT ps.{group_by},
                       ps.game_date,
                       COUNT(*) as pop_count,
                       SUM(ps.size) as total_size,
                       AVG(ps.satisfaction) as avg_satisfaction,
                       AVG(ps.literacy) as avg_literacy
                FROM pop_snapshots ps
                JOIN location_snapshots ls
                    ON ps.playthrough_id = ls.playthrough_id
                   AND ps.snapshot_id   = ls.snapshot_id
                   AND ps.location_id   = ls.location_id
                WHERE ps.playthrough_id = ?
                  AND ls.owner_tag IN ({ph})
            """
            params: list[Any] = [playthrough_id, *owner_tags]
        else:
            query = f"""
                SELECT {group_by},
                       game_date,
                       COUNT(*) as pop_count,
                       SUM(size) as total_size,
                       AVG(satisfaction) as avg_satisfaction,
                       AVG(literacy) as avg_literacy
                FROM pop_snapshots
                WHERE playthrough_id = ?
            """
            params = [playthrough_id]

        if from_date:
            query += " AND ps.game_date >= ?" if owner_tags else " AND game_date >= ?"
            params.append(from_date)
        if to_date:
            query += " AND ps.game_date <= ?" if owner_tags else " AND game_date <= ?"
            params.append(to_date)

        group_col = f"ps.{group_by}" if owner_tags else group_by
        date_col = "ps.game_date" if owner_tags else "game_date"
        query += f" GROUP BY {group_col}, {date_col} ORDER BY {date_col} ASC"

        cursor = await self.conn.execute(query, params)
        return [dict(r) for r in await cursor.fetchall()]

    # ------------------------------------------------------------------
    # Countries
    # ------------------------------------------------------------------

    async def bulk_upsert_countries(
        self,
        playthrough_id: str,
        rows: list[dict],
    ) -> int:
        """Upsert country reference rows.  ON CONFLICT updates name and prev_tags
        so later saves (with richer data) can overwrite earlier stubs.
        canonical_tag is set to tag on first insert; call
        finalize_country_canonical_tags() after the full backfill to propagate
        succession chains.
        """
        if not rows:
            return 0
        data = [
            (
                playthrough_id,
                r["country_id"],
                r["tag"],
                r.get("name"),
                json.dumps(r["prev_tags"]) if r.get("prev_tags") else None,
                r["tag"],  # canonical_tag defaults to self
            )
            for r in rows
        ]
        await self.conn.executemany(
            """INSERT INTO countries
               (playthrough_id, country_id, tag, name, prev_tags, canonical_tag)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(playthrough_id, country_id) DO UPDATE SET
                   name = COALESCE(excluded.name, name),
                   prev_tags = COALESCE(excluded.prev_tags, prev_tags)""",
            data,
        )
        await self.conn.commit()
        return len(data)

    async def get_countries(self, playthrough_id: str) -> list[dict]:
        """Return all country rows for a playthrough, ordered by tag."""
        cursor = await self.conn.execute(
            "SELECT * FROM countries WHERE playthrough_id = ? ORDER BY tag",
            (playthrough_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def finalize_country_canonical_tags(self, playthrough_id: str) -> None:
        """Walk prev_tags chains and update canonical_tag to the terminal successor.

        For example: BRN has prev_tags=null, SWI has prev_tags=["BRN"].
        After this call, BRN.canonical_tag = "SWI" and SWI.canonical_tag = "SWI".
        """
        rows = await self.get_countries(playthrough_id)
        # Build tag → current canonical
        canonical: dict[str, str] = {r["tag"]: r["tag"] for r in rows}

        # Build predecessor → successor mapping from prev_tags
        predecessor_of: dict[str, str] = {}  # old_tag -> new_tag
        for r in rows:
            if r.get("prev_tags"):
                try:
                    prev_list = json.loads(r["prev_tags"])
                    for old_tag in prev_list:
                        predecessor_of[old_tag] = r["tag"]
                except (json.JSONDecodeError, TypeError):
                    pass

        # Propagate: follow chains until stable
        changed = True
        while changed:
            changed = False
            for old_tag, new_tag in predecessor_of.items():
                if old_tag not in canonical:
                    canonical[old_tag] = new_tag
                    changed = True
                    continue
                # new_tag's canonical (in case it too was superseded)
                target = canonical.get(new_tag, new_tag)
                if canonical[old_tag] != target:
                    canonical[old_tag] = target
                    changed = True

        # Write back only rows whose canonical_tag changed
        updates = [
            (canonical[r["tag"]], playthrough_id, r["tag"])
            for r in rows
            if canonical.get(r["tag"], r["tag"]) != r.get("canonical_tag", r["tag"])
        ]
        if updates:
            await self.conn.executemany(
                "UPDATE countries SET canonical_tag = ? WHERE playthrough_id = ? AND tag = ?",
                updates,
            )
            await self.conn.commit()
            logger.info(
                f"finalize_country_canonical_tags: updated {len(updates)} rows "
                f"for playthrough {playthrough_id}"
            )

    async def get_pop_country_owners(self, playthrough_id: str) -> list[dict]:
        """Return distinct country tags that own locations, with their latest game date.

        Used to populate the country picker in the Demographics tab.
        Results are sorted alphabetically by owner_tag.
        """
        cursor = await self.conn.execute(
            """
            SELECT owner_tag,
                   MAX(game_date) as latest_game_date,
                   COUNT(DISTINCT location_id) as location_count
            FROM location_snapshots
            WHERE playthrough_id = ?
              AND owner_tag IS NOT NULL
            GROUP BY owner_tag
            ORDER BY owner_tag ASC
            """,
            (playthrough_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]
