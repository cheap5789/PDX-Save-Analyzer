"""
routes.py — FastAPI REST + WebSocket endpoints

Endpoints:
    POST /api/start                         Launch the watcher pipeline
    POST /api/stop                          Stop the watcher pipeline
    GET  /api/status                        Current watcher/pipeline status
    GET  /api/playthroughs                  List all playthroughs
    GET  /api/snapshots/{id}                Snapshots for a playthrough
    GET  /api/events/{id}                   Events for a playthrough
    GET  /api/fields                        Available field catalog
    GET  /api/religions/{id}                Religion statics for a playthrough
    GET  /api/religions/{id}/snapshots      Religion dynamic data over time
    GET  /api/wars/{id}                     War statics for a playthrough
    GET  /api/wars/{id}/snapshots           War score data over time
    GET  /api/wars/{id}/participants        War participants with scores/losses
    PATCH /api/events/{id}/note             Set AAR note on an event
    WS   /ws                                Live push (snapshots + events)
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query

from backend.api.schemas import (
    StartRequest, StatusResponse, PlaythroughResponse,
    SnapshotResponse, EventResponse, FieldDefResponse, WsMessage,
    UpdateAarNoteRequest, SavedConfig, LoadPlaythroughRequest,
    ReligionResponse, ReligionSnapshotResponse,
    WarResponse, WarSnapshotResponse, WarParticipantResponse,
)
from backend.config import SessionConfig
from backend.parser.eu5.field_catalog import FIELD_CATALOG
from backend.parser.eu5.events import GameEvent
from backend.storage.database import Database
from backend.watcher.pipeline import WatcherPipeline

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Shared state — set by app.py at startup
# ---------------------------------------------------------------------------

_pipeline: WatcherPipeline | None = None
_db: Database | None = None
_ws_clients: set[WebSocket] = set()


def set_shared_state(pipeline: WatcherPipeline | None, db: Database | None) -> None:
    """Called by app.py to inject pipeline/db references."""
    global _pipeline, _db
    _pipeline = pipeline
    _db = db


def get_ws_clients() -> set[WebSocket]:
    return _ws_clients


# ---------------------------------------------------------------------------
# WebSocket broadcast helpers
# ---------------------------------------------------------------------------

async def _broadcast(msg: WsMessage) -> None:
    """Send a message to all connected WebSocket clients."""
    if not _ws_clients:
        return
    payload = msg.model_dump_json()
    dead: list[WebSocket] = []
    for ws in _ws_clients:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.discard(ws)


async def broadcast_snapshot(data: dict) -> None:
    """Called by pipeline callback when a snapshot is recorded."""
    await _broadcast(WsMessage(type="snapshot", data=data))


async def broadcast_events(events: list[GameEvent]) -> None:
    """Called by pipeline callback when events are detected."""
    event_dicts = [
        {"event_type": e.event_type, "game_date": e.game_date, "payload": e.payload}
        for e in events
    ]
    await _broadcast(WsMessage(type="events", data=event_dicts))


async def broadcast_status() -> None:
    """Push current status to all WS clients."""
    status = await _build_status()
    await _broadcast(WsMessage(type="status", data=status.model_dump()))


# ---------------------------------------------------------------------------
# POST /api/start
# ---------------------------------------------------------------------------

@router.post("/api/start", response_model=StatusResponse)
async def start_pipeline(req: StartRequest) -> StatusResponse:
    """Launch the watcher pipeline with the given configuration."""
    global _pipeline, _db, _browse_db, _browse_playthrough_id

    if _pipeline and _pipeline.is_running:
        raise HTTPException(400, "Pipeline is already running. Stop it first.")

    # Close browse-mode DB if open (mutually exclusive with pipeline)
    if _browse_db:
        await _browse_db.close()
        _browse_db = None
        _browse_playthrough_id = None

    config = SessionConfig(
        game=req.game,
        game_install_path=Path(req.game_install_path),
        save_directory=Path(req.save_directory),
        snapshot_freq=req.snapshot_freq,
        language=req.language,
        enabled_field_keys=req.enabled_field_keys,
    )

    # Persist config for next session auto-fill
    _save_config_from_request(req)

    # Validate paths
    if not config.save_directory.exists():
        raise HTTPException(400, f"Save directory not found: {config.save_directory}")
    if not config.rakaly_bin.exists():
        raise HTTPException(400, f"Rakaly binary not found: {config.rakaly_bin}")

    # Create pipeline with WS broadcast callbacks
    loop = asyncio.get_running_loop()

    def _on_snapshot(data: dict) -> None:
        asyncio.run_coroutine_threadsafe(broadcast_snapshot(data), loop)

    def _on_events(events: list[GameEvent]) -> None:
        asyncio.run_coroutine_threadsafe(broadcast_events(events), loop)

    def _on_switch(old_id: str, new_id: str) -> None:
        asyncio.run_coroutine_threadsafe(broadcast_status(), loop)

    _pipeline = WatcherPipeline(
        config,
        on_snapshot=_on_snapshot,
        on_events=_on_events,
        on_playthrough_switch=_on_switch,
    )
    await _pipeline.start()

    # Keep a reference to the pipeline's DB for REST queries
    _db = _pipeline._db

    logger.info("Pipeline started via API")
    return await _build_status()


# ---------------------------------------------------------------------------
# POST /api/stop
# ---------------------------------------------------------------------------

@router.post("/api/stop", response_model=StatusResponse)
async def stop_pipeline() -> StatusResponse:
    """Stop the watcher pipeline."""
    global _pipeline, _db

    if not _pipeline or not _pipeline.is_running:
        raise HTTPException(400, "Pipeline is not running.")

    await _pipeline.stop()
    _pipeline = None
    _db = None

    logger.info("Pipeline stopped via API")
    return await _build_status()


# ---------------------------------------------------------------------------
# GET /api/status
# ---------------------------------------------------------------------------

@router.get("/api/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    return await _build_status()


async def _build_status() -> StatusResponse:
    # Pipeline running → live status
    if _pipeline and _pipeline.is_running:
        config = _pipeline.config
        pt_id = _pipeline._current_playthrough_id

        snap_count = 0
        evt_count = 0
        if _db and pt_id:
            snap_count = await _db.snapshot_count(pt_id)
            evt_count = await _db.event_count(pt_id)

        return StatusResponse(
            running=True,
            game=config.game,
            playthrough_id=pt_id or None,
            country_tag=config.country_tag or None,
            country_name=config.country_name or None,
            game_date=await _db.get_last_game_date(pt_id) if _db and pt_id else None,
            snapshot_freq=config.snapshot_freq,
            snapshot_count=snap_count,
            event_count=evt_count,
        )

    # Browse mode → show loaded playthrough info
    if _browse_db and _browse_playthrough_id:
        pt = await _browse_db.get_playthrough(_browse_playthrough_id)
        if pt:
            snap_count = await _browse_db.snapshot_count(_browse_playthrough_id)
            evt_count = await _browse_db.event_count(_browse_playthrough_id)
            return StatusResponse(
                running=False,
                game=pt.get("game", ""),
                playthrough_id=_browse_playthrough_id,
                country_tag=pt.get("country_tag"),
                country_name=pt.get("country_name"),
                game_date=pt.get("last_game_date"),
                snapshot_freq=pt.get("snapshot_freq"),
                snapshot_count=snap_count,
                event_count=evt_count,
            )

    return StatusResponse(running=False)


# ---------------------------------------------------------------------------
# GET /api/playthroughs
# ---------------------------------------------------------------------------

@router.get("/api/playthroughs", response_model=list[PlaythroughResponse])
async def list_playthroughs(
    game: str = Query("eu5", description="Game to list playthroughs for"),
) -> list[PlaythroughResponse]:
    # Try active DB first, otherwise open the game's DB for a quick read
    if _db:
        rows = await _db.list_playthroughs(game=game)
        return [PlaythroughResponse(**r) for r in rows]
    if _browse_db:
        rows = await _browse_db.list_playthroughs(game=game)
        return [PlaythroughResponse(**r) for r in rows]

    # No active DB — try to open the game's DB read-only for listing
    db_path = Path("data") / f"{game}.db"
    if not db_path.exists():
        return []  # no data yet, return empty list instead of error
    temp_db = Database(db_path)
    await temp_db.open()
    try:
        rows = await temp_db.list_playthroughs(game=game)
        return [PlaythroughResponse(**r) for r in rows]
    finally:
        await temp_db.close()


# ---------------------------------------------------------------------------
# GET /api/snapshots/{playthrough_id}
# ---------------------------------------------------------------------------

@router.get("/api/snapshots/{playthrough_id}", response_model=list[SnapshotResponse])
async def get_snapshots(
    playthrough_id: str,
    limit: int = Query(0, ge=0, description="Max results (0=all)"),
    after: str | None = Query(None, description="Only snapshots after this game date"),
) -> list[SnapshotResponse]:
    db = await _get_db()
    rows = await db.get_snapshots(playthrough_id, limit=limit, after_date=after)
    result = []
    for r in rows:
        d = dict(r)
        d["data"] = json.loads(d["data"]) if isinstance(d["data"], str) else d["data"]
        result.append(SnapshotResponse(**d))
    return result


# ---------------------------------------------------------------------------
# GET /api/events/{playthrough_id}
# ---------------------------------------------------------------------------

@router.get("/api/events/{playthrough_id}", response_model=list[EventResponse])
async def get_events(
    playthrough_id: str,
    event_type: str | None = Query(None, description="Filter by event type"),
    limit: int = Query(0, ge=0, description="Max results (0=all)"),
) -> list[EventResponse]:
    db = await _get_db()
    rows = await db.get_events(playthrough_id, event_type=event_type, limit=limit)
    result = []
    for r in rows:
        d = dict(r)
        d["payload"] = json.loads(d["payload"]) if isinstance(d.get("payload"), str) else d.get("payload")
        result.append(EventResponse(**d))
    return result


# ---------------------------------------------------------------------------
# GET /api/fields
# ---------------------------------------------------------------------------

@router.get("/api/fields", response_model=list[FieldDefResponse])
async def get_fields(
    category: str | None = Query(None, description="Filter by category"),
) -> list[FieldDefResponse]:
    fields = FIELD_CATALOG
    if category:
        fields = [f for f in fields if f.category == category]
    return [
        FieldDefResponse(
            key=f.key,
            display_name=f.display_name,
            category=f.category,
            value_type=f.value_type,
            default_enabled=f.default_enabled,
            description=f.description,
        )
        for f in fields
    ]


# ---------------------------------------------------------------------------
# GET /api/religions/{playthrough_id}
# ---------------------------------------------------------------------------

@router.get("/api/religions/{playthrough_id}", response_model=list[ReligionResponse])
async def get_religions(playthrough_id: str) -> list[ReligionResponse]:
    """List all religion static records for a playthrough."""
    db = await _get_db()
    rows = await db.get_religions(playthrough_id)
    result = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("color_rgb"), str):
            d["color_rgb"] = json.loads(d["color_rgb"])
        result.append(ReligionResponse(**d))
    return result


# ---------------------------------------------------------------------------
# GET /api/religions/{playthrough_id}/snapshots
# ---------------------------------------------------------------------------

@router.get(
    "/api/religions/{playthrough_id}/snapshots",
    response_model=list[ReligionSnapshotResponse],
)
async def get_religion_snapshots(
    playthrough_id: str,
    religion_id: int | None = Query(None, description="Filter by religion ID"),
) -> list[ReligionSnapshotResponse]:
    """Religion dynamic data over time."""
    db = await _get_db()
    rows = await db.get_religion_snapshots(playthrough_id, religion_id=religion_id)
    return [ReligionSnapshotResponse(**dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# GET /api/wars/{playthrough_id}
# ---------------------------------------------------------------------------

@router.get("/api/wars/{playthrough_id}", response_model=list[WarResponse])
async def get_wars(
    playthrough_id: str,
    active_only: bool = Query(False, description="Only return active wars"),
) -> list[WarResponse]:
    """List all wars for a playthrough."""
    db = await _get_db()
    rows = await db.get_wars(playthrough_id, active_only=active_only)
    result = []
    for r in rows:
        d = dict(r)
        for key in ("original_defenders", "goal_target"):
            if isinstance(d.get(key), str):
                try:
                    d[key] = json.loads(d[key])
                except (json.JSONDecodeError, TypeError):
                    pass
        result.append(WarResponse(**d))
    return result


# ---------------------------------------------------------------------------
# GET /api/wars/{playthrough_id}/snapshots
# ---------------------------------------------------------------------------

@router.get(
    "/api/wars/{playthrough_id}/snapshots",
    response_model=list[WarSnapshotResponse],
)
async def get_war_snapshots(
    playthrough_id: str,
    war_id: str | None = Query(None, description="Filter by war ID"),
) -> list[WarSnapshotResponse]:
    """War score data over time."""
    db = await _get_db()
    rows = await db.get_war_snapshots(playthrough_id, war_id=war_id)
    return [WarSnapshotResponse(**dict(r)) for r in rows]


# ---------------------------------------------------------------------------
# GET /api/wars/{playthrough_id}/participants
# ---------------------------------------------------------------------------

@router.get(
    "/api/wars/{playthrough_id}/participants",
    response_model=list[WarParticipantResponse],
)
async def get_war_participants(
    playthrough_id: str,
    war_id: str | None = Query(None, description="Filter by war ID"),
) -> list[WarParticipantResponse]:
    """War participants with their status and scores."""
    db = await _get_db()
    rows = await db.get_war_participants(playthrough_id, war_id=war_id)
    result = []
    for r in rows:
        d = dict(r)
        if isinstance(d.get("losses"), str):
            try:
                d["losses"] = json.loads(d["losses"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(WarParticipantResponse(**d))
    return result


# ---------------------------------------------------------------------------
# Config persistence — one file per game: data/{game}_config.json
# ---------------------------------------------------------------------------


def _config_path(game: str) -> Path:
    return Path("data") / f"{game}_config.json"


def _save_config_from_request(req: StartRequest) -> None:
    """Persist the config to a game-specific JSON file."""
    _save_config_obj(SavedConfig(
        game=req.game,
        game_install_path=req.game_install_path,
        save_directory=req.save_directory,
        snapshot_freq=req.snapshot_freq,
        language=req.language,
        enabled_field_keys=req.enabled_field_keys,
    ))


def _save_config_obj(cfg: SavedConfig) -> None:
    path = _config_path(cfg.game)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(cfg.model_dump_json(indent=2))


def _load_config(game: str = "eu5") -> SavedConfig | None:
    path = _config_path(game)
    if not path.exists():
        return None
    try:
        return SavedConfig.model_validate_json(path.read_text())
    except Exception:
        return None


@router.get("/api/config", response_model=SavedConfig)
async def get_config(
    game: str = Query("eu5", description="Game to load config for"),
) -> SavedConfig:
    """Return the persisted config for a game, or defaults if none saved."""
    saved = _load_config(game)
    if saved:
        return saved
    # Return defaults with all fields enabled
    all_keys = [f.key for f in FIELD_CATALOG]
    return SavedConfig(game=game, enabled_field_keys=all_keys)


@router.post("/api/config", response_model=SavedConfig)
async def save_config(cfg: SavedConfig) -> SavedConfig:
    """Save config to disk without starting the pipeline."""
    _save_config_obj(cfg)
    return cfg


# ---------------------------------------------------------------------------
# POST /api/load-playthrough — open DB for browsing without running pipeline
# ---------------------------------------------------------------------------

_browse_db: Database | None = None   # standalone DB for read-only browsing
_browse_playthrough_id: str | None = None


async def _get_db() -> Database:
    """Return the active DB — either from the running pipeline or from browse mode."""
    if _db:
        return _db
    if _browse_db:
        return _browse_db
    raise HTTPException(400, "No database open. Start the pipeline or load a playthrough.")


@router.post("/api/load-playthrough")
async def load_playthrough(req: LoadPlaythroughRequest) -> dict:
    """Open a game DB and set the active playthrough for browsing historical data."""
    global _browse_db, _browse_playthrough_id

    if _pipeline and _pipeline.is_running:
        raise HTTPException(400, "Pipeline is running. Stop it first to browse a different playthrough.")

    db_path = Path("data") / f"{req.game}.db"
    if not db_path.exists():
        raise HTTPException(404, f"No database found for game '{req.game}'. No data has been recorded yet.")

    # Close previous browse DB if open
    if _browse_db:
        await _browse_db.close()

    _browse_db = Database(db_path)
    await _browse_db.open()

    # Verify playthrough exists
    pt = await _browse_db.get_playthrough(req.playthrough_id)
    if not pt:
        await _browse_db.close()
        _browse_db = None
        raise HTTPException(404, f"Playthrough '{req.playthrough_id}' not found in {req.game}.db")

    _browse_playthrough_id = req.playthrough_id
    snap_count = await _browse_db.snapshot_count(req.playthrough_id)
    evt_count = await _browse_db.event_count(req.playthrough_id)

    return {
        "loaded": True,
        "playthrough_id": req.playthrough_id,
        "game": req.game,
        "country_tag": pt.get("country_tag", ""),
        "country_name": pt.get("country_name", ""),
        "last_game_date": pt.get("last_game_date", ""),
        "snapshot_count": snap_count,
        "event_count": evt_count,
    }


# ---------------------------------------------------------------------------
# PATCH /api/events/{event_id}/note
# ---------------------------------------------------------------------------

@router.patch("/api/events/{event_id}/note", response_model=EventResponse)
async def update_event_note(event_id: int, req: UpdateAarNoteRequest) -> EventResponse:
    """Set or update the AAR note on an event."""
    db = await _get_db()

    await db.update_aar_note(event_id, req.note)

    # Fetch the updated event to return it
    cursor = await db.conn.execute(
        "SELECT * FROM events WHERE id = ?", (event_id,)
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(404, f"Event {event_id} not found.")

    d = dict(row)
    d["payload"] = json.loads(d["payload"]) if isinstance(d.get("payload"), str) else d.get("payload")
    return EventResponse(**d)


# ---------------------------------------------------------------------------
# WS /ws
# ---------------------------------------------------------------------------

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    _ws_clients.add(ws)
    logger.info(f"WebSocket client connected ({len(_ws_clients)} total)")

    # Send current status immediately on connect
    status = await _build_status()
    await ws.send_text(
        WsMessage(type="status", data=status.model_dump()).model_dump_json()
    )

    try:
        while True:
            # Keep connection alive; we don't expect messages from client
            # but read to detect disconnects
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _ws_clients.discard(ws)
        logger.info(f"WebSocket client disconnected ({len(_ws_clients)} total)")
