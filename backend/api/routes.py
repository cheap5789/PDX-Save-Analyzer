"""
routes.py — FastAPI REST + WebSocket endpoints

Endpoints:
    POST /api/start             Launch the watcher pipeline
    POST /api/stop              Stop the watcher pipeline
    GET  /api/status            Current watcher/pipeline status
    GET  /api/playthroughs      List all playthroughs
    GET  /api/snapshots/{id}    Snapshots for a playthrough
    GET  /api/events/{id}       Events for a playthrough
    GET  /api/fields            Available field catalog
    WS   /ws                    Live push (snapshots + events)
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
    UpdateAarNoteRequest, SavedConfig,
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
    global _pipeline, _db

    if _pipeline and _pipeline.is_running:
        raise HTTPException(400, "Pipeline is already running. Stop it first.")

    config = SessionConfig(
        game=req.game,
        game_install_path=Path(req.game_install_path),
        save_directory=Path(req.save_directory),
        snapshot_freq=req.snapshot_freq,
        language=req.language,
        enabled_field_keys=req.enabled_field_keys,
    )

    # Persist config for next session auto-fill
    _save_config(req)

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
    if not _pipeline or not _pipeline.is_running:
        return StatusResponse(running=False)

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


# ---------------------------------------------------------------------------
# GET /api/playthroughs
# ---------------------------------------------------------------------------

@router.get("/api/playthroughs", response_model=list[PlaythroughResponse])
async def list_playthroughs(
    game: str | None = Query(None, description="Filter by game"),
) -> list[PlaythroughResponse]:
    if not _db:
        raise HTTPException(400, "No database open. Start the pipeline first.")
    rows = await _db.list_playthroughs(game=game)
    return [PlaythroughResponse(**r) for r in rows]


# ---------------------------------------------------------------------------
# GET /api/snapshots/{playthrough_id}
# ---------------------------------------------------------------------------

@router.get("/api/snapshots/{playthrough_id}", response_model=list[SnapshotResponse])
async def get_snapshots(
    playthrough_id: str,
    limit: int = Query(0, ge=0, description="Max results (0=all)"),
    after: str | None = Query(None, description="Only snapshots after this game date"),
) -> list[SnapshotResponse]:
    if not _db:
        raise HTTPException(400, "No database open. Start the pipeline first.")
    rows = await _db.get_snapshots(playthrough_id, limit=limit, after_date=after)
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
    if not _db:
        raise HTTPException(400, "No database open. Start the pipeline first.")
    rows = await _db.get_events(playthrough_id, event_type=event_type, limit=limit)
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
# Config persistence
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path("data/user_config.json")


def _save_config(req: StartRequest) -> None:
    """Persist the config to disk so it can be restored on next launch."""
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config_data = SavedConfig(
        game=req.game,
        game_install_path=req.game_install_path,
        save_directory=req.save_directory,
        snapshot_freq=req.snapshot_freq,
        language=req.language,
        enabled_field_keys=req.enabled_field_keys,
    )
    _CONFIG_PATH.write_text(config_data.model_dump_json(indent=2))


def _load_config() -> SavedConfig | None:
    """Load the most recently saved config, or None if not found."""
    if not _CONFIG_PATH.exists():
        return None
    try:
        return SavedConfig.model_validate_json(_CONFIG_PATH.read_text())
    except Exception:
        return None


@router.get("/api/config", response_model=SavedConfig)
async def get_config() -> SavedConfig:
    """Return the persisted config, or defaults if none saved."""
    saved = _load_config()
    if saved:
        return saved
    return SavedConfig()


# ---------------------------------------------------------------------------
# PATCH /api/events/{event_id}/note
# ---------------------------------------------------------------------------

@router.patch("/api/events/{event_id}/note", response_model=EventResponse)
async def update_event_note(event_id: int, req: UpdateAarNoteRequest) -> EventResponse:
    """Set or update the AAR note on an event."""
    if not _db:
        raise HTTPException(400, "No database open. Start the pipeline first.")

    await _db.update_aar_note(event_id, req.note)

    # Fetch the updated event to return it
    cursor = await _db.conn.execute(
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
