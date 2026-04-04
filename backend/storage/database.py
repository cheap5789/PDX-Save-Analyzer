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
