"""
schemas.py — Pydantic models for API request/response validation

Keeps the API contract explicit and separated from internal dataclasses.
"""

from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class StartRequest(BaseModel):
    """POST /api/start — launch the watcher pipeline."""
    game: str = "eu5"
    game_install_path: str
    save_directory: str
    snapshot_freq: str = "yearly"
    language: str = "english"
    enabled_field_keys: list[str] = []  # empty = use defaults


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class StatusResponse(BaseModel):
    """GET /api/status"""
    running: bool
    game: str | None = None
    playthrough_id: str | None = None
    country_tag: str | None = None
    country_name: str | None = None
    game_date: str | None = None
    snapshot_freq: str | None = None
    snapshot_count: int = 0
    event_count: int = 0


class PlaythroughResponse(BaseModel):
    id: str
    game: str
    playthrough_name: str | None = None
    country_tag: str | None = None
    country_name: str | None = None
    multiplayer: bool = False
    snapshot_freq: str | None = None
    game_version: str | None = None
    started_at: str | None = None
    last_seen_at: str | None = None
    last_game_date: str | None = None


class SnapshotResponse(BaseModel):
    id: int
    playthrough_id: str
    game_date: str
    recorded_at: str
    data: dict


class EventResponse(BaseModel):
    id: int
    playthrough_id: str
    game_date: str
    event_type: str
    payload: dict | None = None
    aar_note: str | None = None
    recorded_at: str


class FieldDefResponse(BaseModel):
    """One entry from the field catalog."""
    key: str
    display_name: str
    category: str
    value_type: str
    default_enabled: bool
    description: str = ""


# ---------------------------------------------------------------------------
# WebSocket message types
# ---------------------------------------------------------------------------

class WsMessage(BaseModel):
    """Generic WebSocket message envelope."""
    type: str                   # "snapshot", "events", "status", "error"
    data: dict | list | None = None
