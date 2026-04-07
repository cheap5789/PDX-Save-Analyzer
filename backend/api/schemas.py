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


class BackfillRequest(BaseModel):
    """POST /api/playthroughs/{id}/backfill — scan save folder and import historical saves."""
    save_directory: str                # Path to scan for .eu5 files
    game_install_path: str = ""        # Used to locate localisation files; optional
    language: str = "english"         # Localisation subfolder name
    game: str = "eu5"                  # Which game DB to write into


class SaveScanResult(BaseModel):
    """One discovered playthrough from GET /api/scan-saves."""
    playthrough_id: str
    country_name: str
    playthrough_name: str
    save_count: int
    earliest_date: str               # EU5 date string of the oldest save found
    latest_date: str                 # EU5 date string of the newest save found
    multiplayer: bool


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
    country_tag: str | None = None
    dedup_key: str | None = None


class FieldDefResponse(BaseModel):
    """One entry from the field catalog."""
    key: str
    display_name: str
    category: str
    value_type: str
    default_enabled: bool
    description: str = ""
    display_format: str = ""  # "x1000", "percent", or "" (plain)


class ReligionResponse(BaseModel):
    """Static religion record."""
    id: int
    playthrough_id: str
    definition: str
    name: str = ""
    religion_group: str = ""


class CultureResponse(BaseModel):
    """Static culture record."""
    id: int
    playthrough_id: str
    definition: str
    name: str = ""
    culture_group: str = ""
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
    original_attacker_id: int | None = None
    original_target_id: int | None = None
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
    war_goal_held: int | None = None


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
    called_by: int | None = None
    join_date: str | None = None
    status: str = "Active"
    score_combat: float = 0
    score_siege: float = 0
    score_joining: float = 0
    losses: dict | list | None = None
    io_id: int | None = None


class LocationResponse(BaseModel):
    """Static location record."""
    id: int
    playthrough_id: str
    province_id: int | None = None
    raw_material: str | None = None
    is_port: bool = False
    holy_sites: list | None = None


class LocationSnapshotResponse(BaseModel):
    """Location snapshot row — one per owned location per snapshot."""
    id: int
    playthrough_id: str
    snapshot_id: int
    location_id: int
    game_date: str
    owner_id: int | None = None
    controller_id: int | None = None
    previous_owner_id: int | None = None
    last_owner_change: str | None = None
    last_controller_change: str | None = None
    cores: list | None = None
    garrison: float | None = None
    control: float | None = None
    culture_id: int | None = None
    secondary_culture_id: int | None = None
    cultural_unity: float | None = None
    religion_id: int | None = None
    religious_unity: float | None = None
    language: str | None = None
    dialect: str | None = None
    pop_count: int | None = None
    rank: str | None = None
    development: float | None = None
    prosperity: float | None = None
    tax: float | None = None
    possible_tax: float | None = None
    market_id: int | None = None
    market_access: float | None = None
    value_flow: float | None = None
    institutions: dict | None = None
    integration_type: str | None = None
    integration_owner_id: int | None = None
    slave_raid_date: str | None = None


class ProvinceResponse(BaseModel):
    """Static province record."""
    id: int
    playthrough_id: str
    province_definition: str | None = None
    capital_location_id: int | None = None


class ProvinceSnapshotResponse(BaseModel):
    """Province snapshot row — food economy data per snapshot."""
    id: int
    playthrough_id: str
    snapshot_id: int
    province_id: int
    game_date: str
    owner_id: int | None = None
    food_current: float | None = None
    food_max: float | None = None
    food_change_delta: float | None = None
    trade_balance: float | None = None
    goods_produced: dict | None = None


class PopSnapshotResponse(BaseModel):
    """Individual pop snapshot row."""
    id: int
    playthrough_id: str
    snapshot_id: int
    game_date: str
    location_id: int
    pop_id: int
    type: str
    estate: str | None = None
    culture_id: int | None = None
    religion_id: int | None = None
    size: float | None = None
    status: str | None = None
    satisfaction: float | None = None
    intervention_satisfaction: float | None = None
    literacy: float | None = None
    owner_id: int | None = None


class PopAggregateResponse(BaseModel):
    """Aggregated pop data (grouped by type, culture, religion, etc.)."""
    game_date: str
    pop_count: int
    total_size: float
    avg_satisfaction: float | None = None
    avg_literacy: float | None = None
    # The group key — one of these will be populated depending on group_by
    type: str | None = None
    culture_id: int | None = None
    religion_id: int | None = None
    status: str | None = None
    location_id: int | None = None
    estate: str | None = None


class PopCountryOwnerResponse(BaseModel):
    """One entry per country that owns at least one location in the playthrough."""
    owner_tag: str
    latest_game_date: str
    location_count: int


class CountryResponse(BaseModel):
    """Country reference row — stable per playthrough, supports succession chains."""
    playthrough_id: str
    country_id: int
    tag: str
    name: str | None = None
    prev_tags: list[str] | None = None   # predecessor TAGs (e.g. ["BRN"] for SWI)
    canonical_tag: str                   # terminal successor tag (self if no successor)


# ---------------------------------------------------------------------------
# WebSocket message types
# ---------------------------------------------------------------------------

class WsMessage(BaseModel):
    """Generic WebSocket message envelope."""
    type: str                   # "snapshot", "events", "status", "error"
    data: dict | list | None = None
