"""
database.py — Async SQLite database layer

One Database instance per game (eu5.db, ck3.db, etc.).
All operations are async (aiosqlite) for FastAPI compatibility.

Tables:
    playthroughs  — one row per campaign
    snapshots     — one row per recorded snapshot (at configured frequency)
    events        — one row per detected event (every save)
"""

from __future__ import annotations

import json
import aiosqlite
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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
    data            TEXT NOT NULL       -- JSON blob of extracted country stats
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
    recorded_at     TEXT NOT NULL       -- wall-clock ISO timestamp
);
CREATE INDEX IF NOT EXISTS idx_events_playthrough
    ON events(playthrough_id, game_date);

-- ── Religion entity tables ──────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS religions (
    id              INTEGER PRIMARY KEY,    -- religion_manager.database key (numeric)
    playthrough_id  TEXT NOT NULL REFERENCES playthroughs(id),
    definition      TEXT NOT NULL,          -- string key e.g. "catholic"
    name            TEXT,                   -- display name (localised)
    religion_group  TEXT,                   -- e.g. "christian", "buddhist"
    has_religious_head BOOLEAN DEFAULT 0,
    color_rgb       TEXT,                   -- JSON [r,g,b]
    UNIQUE(playthrough_id, id)
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
    slave_raid_date TEXT                        -- nullable; date of last slave raid
);
CREATE INDEX IF NOT EXISTS idx_loc_snap_pt
    ON location_snapshots(playthrough_id, snapshot_id);
CREATE INDEX IF NOT EXISTS idx_loc_snap_loc
    ON location_snapshots(playthrough_id, location_id, game_date);

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

    async def insert_snapshot(
        self,
        playthrough_id: str,
        game_date: str,
        data: dict,
    ) -> int:
        """
        Insert a snapshot and update the playthrough's last_seen_at / last_game_date.
        Returns the new snapshot ID.
        """
        now = _now_iso()
        cursor = await self.conn.execute(
            """INSERT INTO snapshots (playthrough_id, game_date, recorded_at, data)
               VALUES (?, ?, ?, ?)""",
            (playthrough_id, game_date, now, json.dumps(data)),
        )
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
        Bulk-insert events. Each dict must have: game_date, event_type, payload.
        Returns the number of events inserted.
        """
        if not events:
            return 0

        now = _now_iso()
        rows = [
            (playthrough_id, e["game_date"], e["event_type"],
             json.dumps(e.get("payload", {})), None, now)
            for e in events
        ]
        await self.conn.executemany(
            """INSERT INTO events
               (playthrough_id, game_date, event_type, payload, aar_note, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            rows,
        )
        await self.conn.commit()
        return len(rows)

    async def get_events(
        self,
        playthrough_id: str,
        event_type: str | None = None,
        limit: int = 0,
    ) -> list[dict]:
        """Get events for a playthrough, optionally filtered by type."""
        query = "SELECT * FROM events WHERE playthrough_id = ?"
        params: list[Any] = [playthrough_id]

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        query += " ORDER BY game_date ASC"

        if limit > 0:
            query += " LIMIT ?"
            params.append(limit)

        cursor = await self.conn.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

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
               (id, playthrough_id, definition, name, religion_group,
                has_religious_head, color_rgb)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(playthrough_id, id) DO UPDATE SET
                   name = excluded.name,
                   has_religious_head = excluded.has_religious_head""",
            (religion_id, playthrough_id, definition, name, religion_group,
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
             r.get("owner_id"), r.get("controller_id"), r.get("previous_owner_id"),
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
                owner_id, controller_id, previous_owner_id,
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
               VALUES (?,?,?,?, ?,?,?,?,?, ?,?,?, ?,?,?, ?,?, ?,?,?, ?,?,?, ?,?, ?,?,?, ?, ?,?,?)""",
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
