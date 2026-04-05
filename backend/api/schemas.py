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


class UpdateAarNoteRequest(BaseModel):
    """PATCH /api/events/{id}/note — set or update an AAR note."""
    note: str = ""


class SavedConfig(BaseModel):
    """Persisted user config (data/{game}_config.json)."""
    game: str = "eu5"
    game_install_path: str = ""
    save_directory: str = ""
    snapshot_freq: str = "yearly"
    language: str = "english"
    enabled_field_keys: list[str] = []
    selected_playthrough_id: str = ""


class LoadPlaythroughRequest(BaseModel):
    """POST /api/load-playthrough — open a DB and set active playthrough for browsing."""
    game: str = "eu5"
    playthrough_id: str


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


class ReligionResponse(BaseModel):
    """Static religion record."""
    id: int
    playthrough_id: str
    definition: str
    name: str = ""
    religion_group: str = ""
    has_religious_head: bool = False
    color_rgb: list | None = None


class ReligionSnapshotResponse(BaseModel):
    """One row of religion dynamic data at a point in time."""
    id: int
    playthrough_id: str
    snapshot_id: int
    religion_id: int
    game_date: str
    important_country: str | None = None
    reform_desire: float | None = None
    tithe: float | None = None
    saint_power: float | None = None
    timed_modifier_count: int = 0


class WarResponse(BaseModel):
    """Static war record."""
    id: str
    playthrough_id: str
    name_key: str | None = None
    name_display: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_civil_war: bool = False
    is_revolt: bool = False
    original_attacker_id: str | None = None
    original_target_id: str | None = None
    original_defenders: list | str | None = None
    goal_type: str | None = None
    casus_belli: str | None = None
    goal_target: str | list | None = None


class WarSnapshotResponse(BaseModel):
    """War dynamic scores at a point in time."""
    id: int
    playthrough_id: str
    snapshot_id: int
    war_id: str
    game_date: str
    attacker_score: float | None = None
    defender_score: float | None = None
    net_war_score: float | None = None
    war_direction_quarter: float | None = None
    war_direction_year: float | None = None
    war_goal_held: bool | None = None


class WarParticipantResponse(BaseModel):
    """War participant record."""
    id: int
    playthrough_id: str
    war_id: str
    country_id: int | str
    country_tag: str | None = None
    side: str
    join_reason: str | None = None
    join_type: str | None = None
    called_by: str | None = None
    join_date: str | None = None
    status: str = "Active"
    score_combat: float = 0
    score_siege: float = 0
    score_joining: float = 0
    losses: dict | list | None = None
    io_id: str | None = None


# ---------------------------------------------------------------------------
# WebSocket message types
# ---------------------------------------------------------------------------

class WsMessage(BaseModel):
    """Generic WebSocket message envelope."""
    type: str                   # "snapshot", "events", "status", "error"
    data: dict | list | None = None
