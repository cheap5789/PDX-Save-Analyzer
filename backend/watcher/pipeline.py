"""
pipeline.py — Watcher pipeline orchestrator

Implements the state machine from CONFIGURATION.md:
    Save detected
      ├─ Parse via rakaly → EU5Save
      ├─ Check playthrough_id — switch if changed
      ├─ Event detection (always, every save)
      └─ Snapshot threshold check → record if due

Ties together: file_watcher, save_loader, snapshot extractor,
summary/event differ, and SQLite storage.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from backend.config import SessionConfig
from backend.parser.save_loader import EU5Save, load_save
from backend.parser.eu5.field_catalog import (
    FIELD_CATALOG, get_default_fields, get_field, FieldDef,
)
from backend.parser.eu5.snapshot import extract_snapshot
from backend.parser.eu5.summary import extract_summary, GameSummary
from backend.parser.eu5.events import diff_summaries, GameEvent
from backend.parser.eu5.religions import extract_religion_statics, extract_religion_snapshot_rows
from backend.parser.eu5.wars import (
    extract_war_statics, extract_war_snapshot_rows,
    extract_all_war_participants, detect_battle_events,
)
from backend.parser.eu5.geography import (
    extract_location_statics, extract_location_snapshot_rows,
    extract_province_statics, extract_province_snapshot_rows,
    detect_location_events,
)
from backend.parser.eu5.demographics import extract_pop_snapshot_rows
from backend.parser.eu5.game_date import should_snapshot
from backend.storage.database import Database
from backend.watcher.file_watcher import SaveFileWatcher

logger = logging.getLogger(__name__)


class WatcherPipeline:
    """
    Full watcher pipeline: watch dir → parse → diff → store.

    Usage:
        config = SessionConfig(...)
        pipeline = WatcherPipeline(config)
        await pipeline.start()
        # runs until stopped
        await pipeline.stop()
    """

    def __init__(
        self,
        config: SessionConfig,
        on_snapshot: Callable[[dict], Any] | None = None,
        on_events: Callable[[list[GameEvent]], Any] | None = None,
        on_playthrough_switch: Callable[[str, str], Any] | None = None,
    ):
        """
        Args:
            config:                Session configuration.
            on_snapshot:           Callback when a snapshot is recorded (receives snapshot dict).
            on_events:             Callback when events are detected (receives event list).
            on_playthrough_switch: Callback when playthrough switches (old_id, new_id).
        """
        self.config = config
        self._on_snapshot = on_snapshot
        self._on_events = on_events
        self._on_playthrough_switch = on_playthrough_switch

        self._db: Database | None = None
        self._watcher: SaveFileWatcher | None = None
        self._task: asyncio.Task | None = None
        self._running = False

        # State
        self._current_playthrough_id: str = ""
        self._last_summary: GameSummary | None = None
        self._enabled_fields: list[FieldDef] = []
        self._started_at: float = 0.0  # monotonic timestamp — files older than this are skipped
        self._last_battle_state: dict[str, dict] | None = None  # {war_id: {date, location}}
        self._last_location_state: dict[int, dict] | None = None  # {loc_id: {fields}}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the watcher pipeline."""
        logger.info(f"Starting pipeline for {self.config.game}")

        # Record start time — saves with mtime before this are ignored
        self._started_at = datetime.now(timezone.utc).timestamp()

        # Open database
        self._db = Database(self.config.db_path)
        await self._db.open()

        # Resolve enabled fields
        if self.config.enabled_field_keys:
            self._enabled_fields = [
                f for f in FIELD_CATALOG
                if f.key in self.config.enabled_field_keys
            ]
        else:
            self._enabled_fields = get_default_fields()

        # Start file watcher
        loop = asyncio.get_running_loop()
        self._watcher = SaveFileWatcher(
            watch_dir=self.config.save_directory,
            extensions=self.config.save_extensions(),
        )
        self._watcher.start(loop)

        # Start processing loop
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Pipeline running.")

    async def stop(self) -> None:
        """Stop the watcher pipeline and clean up."""
        self._running = False
        if self._watcher:
            self._watcher.stop()
            self._watcher = None
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._db:
            await self._db.close()
            self._db = None
        logger.info("Pipeline stopped.")

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        """Main processing loop: await saves, process each one."""
        assert self._watcher is not None
        assert self._db is not None

        while self._running:
            try:
                save_path = await self._watcher.get_next(timeout=1.0)
                if save_path is None:
                    continue
                await self._process_save(save_path)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error processing save file")

    async def _process_save(self, save_path: Path) -> None:
        """
        Process a single detected save file through the full pipeline.

        Steps:
            1. Parse save via rakaly → EU5Save
            2. Check playthrough_id — create/switch if needed
            3. Extract summary and diff for events (always)
            4. Check snapshot frequency threshold
            5. If due: extract snapshot and store
        """
        assert self._db is not None

        # Skip saves that existed before the watcher started.
        # Only files modified after pipeline start are processed.
        # (A future "reprocess" / backfill option may lift this restriction.)
        try:
            file_mtime = os.path.getmtime(save_path)
        except OSError:
            logger.warning(f"Cannot stat {save_path.name} — skipping")
            return
        if file_mtime < self._started_at:
            logger.debug(f"Skipping pre-existing save: {save_path.name}")
            return

        logger.info(f"Processing: {save_path.name}")

        # Step 1: Parse
        try:
            save = load_save(
                save_path,
                rakaly_bin=self.config.rakaly_bin,
                loc_dir=self.config.loc_dir if self.config.loc_dir.exists() else None,
                verbose=False,
            )
        except Exception:
            logger.exception(f"Failed to parse {save_path.name}")
            return

        # Step 2: Playthrough management
        pt_id = save.raw.get("metadata", {}).get("playthrough_id", "")
        if not pt_id:
            logger.warning("Save has no playthrough_id — skipping")
            return

        await self._handle_playthrough(save, pt_id)

        # Step 3: Event detection (always, every save)
        summary = extract_summary(save)
        events = diff_summaries(self._last_summary, summary)
        self._last_summary = summary

        # Collect all event dicts to insert
        all_event_dicts: list[dict] = []

        if events:
            all_event_dicts.extend(
                {"game_date": e.game_date, "event_type": e.event_type, "payload": e.payload}
                for e in events
            )

        # Step 3b: Battle event detection (always, every save)
        battle_events, new_battle_state = detect_battle_events(
            save, self._last_battle_state,
        )
        self._last_battle_state = new_battle_state
        if battle_events:
            all_event_dicts.extend(battle_events)  # already dicts

        # Step 3c: Location event detection (always, every save)
        loc_events, new_loc_state = detect_location_events(
            save, self._last_location_state,
        )
        self._last_location_state = new_loc_state
        if loc_events:
            all_event_dicts.extend(loc_events)  # already dicts

        if all_event_dicts:
            count = await self._db.insert_events(pt_id, all_event_dicts)
            logger.info(f"  {count} events recorded")
            if self._on_events:
                self._on_events(events)

        # Step 4: Snapshot frequency check
        last_snap_date = await self._db.get_last_snapshot_date(pt_id)
        if should_snapshot(save.game_date, last_snap_date, self.config.snapshot_freq):
            # Step 5: Extract and store snapshot
            snapshot_data = extract_snapshot(
                save,
                enabled_fields=self._enabled_fields,
            )
            snap_id = await self._db.insert_snapshot(pt_id, save.game_date, snapshot_data)
            logger.info(f"  Snapshot #{snap_id} recorded at {save.game_date}")
            if self._on_snapshot:
                self._on_snapshot(snapshot_data)

            # Step 6: Religion entity tracking
            try:
                rel_statics = extract_religion_statics(save)
                for r in rel_statics:
                    await self._db.upsert_religion(
                        playthrough_id=pt_id,
                        religion_id=r["religion_id"],
                        definition=r["definition"],
                        name=r.get("name", ""),
                        religion_group=r.get("religion_group", ""),
                        has_religious_head=r.get("has_religious_head", False),
                        color_rgb=r.get("color_rgb"),
                    )
                rel_rows = extract_religion_snapshot_rows(save)
                rel_count = await self._db.insert_religion_snapshots(
                    pt_id, snap_id, save.game_date, rel_rows,
                )
                logger.info(f"  {len(rel_statics)} religions upserted, {rel_count} snapshot rows")
            except Exception:
                logger.exception("Error in religion extraction")

            # Step 7: War entity tracking
            try:
                war_statics = extract_war_statics(save)
                for w in war_statics:
                    await self._db.upsert_war(pt_id, w)

                war_snap_rows = extract_war_snapshot_rows(save)
                war_snap_count = await self._db.insert_war_snapshots(
                    pt_id, snap_id, save.game_date, war_snap_rows,
                )

                all_participants = extract_all_war_participants(save)
                part_count = 0
                for wid, parts in all_participants.items():
                    part_count += await self._db.upsert_war_participants(
                        pt_id, wid, parts,
                    )

                logger.info(
                    f"  {len(war_statics)} wars upserted, "
                    f"{war_snap_count} war snapshot rows, "
                    f"{part_count} participants"
                )
            except Exception:
                logger.exception("Error in war extraction")

            # Step 8: Geography entity tracking (locations + provinces)
            try:
                loc_statics = extract_location_statics(save)
                loc_static_count = await self._db.bulk_upsert_locations(pt_id, loc_statics)

                loc_rows = extract_location_snapshot_rows(save)
                loc_snap_count = await self._db.insert_location_snapshots(
                    pt_id, snap_id, save.game_date, loc_rows,
                )

                prov_statics = extract_province_statics(save)
                prov_static_count = await self._db.bulk_upsert_provinces(pt_id, prov_statics)

                prov_rows = extract_province_snapshot_rows(save)
                prov_snap_count = await self._db.insert_province_snapshots(
                    pt_id, snap_id, save.game_date, prov_rows,
                )

                logger.info(
                    f"  Geography: {loc_static_count} locations, "
                    f"{loc_snap_count} loc snapshots, "
                    f"{prov_static_count} provinces, "
                    f"{prov_snap_count} prov snapshots"
                )
            except Exception:
                logger.exception("Error in geography extraction")

            # Step 9: Demographics — per-pop data
            try:
                pop_rows = extract_pop_snapshot_rows(save)
                pop_count = await self._db.insert_pop_snapshots(
                    pt_id, snap_id, save.game_date, pop_rows,
                )
                logger.info(f"  Demographics: {pop_count} pop snapshot rows")
            except Exception:
                logger.exception("Error in demographics extraction")
        else:
            logger.info(f"  Skipped snapshot (freq={self.config.snapshot_freq}, date={save.game_date})")

    # ------------------------------------------------------------------
    # Playthrough management
    # ------------------------------------------------------------------

    async def _handle_playthrough(self, save: EU5Save, pt_id: str) -> None:
        """Create, resume, or switch playthroughs as needed."""
        assert self._db is not None
        meta = save.raw.get("metadata", {})

        if pt_id != self._current_playthrough_id:
            old_id = self._current_playthrough_id

            if old_id:
                logger.info(f"  Playthrough switch: {old_id[:8]}... → {pt_id[:8]}...")
                # Log switch event on the OLD playthrough
                await self._db.insert_events(old_id, [{
                    "game_date": save.game_date,
                    "event_type": "playthrough_switch",
                    "payload": {"from_id": old_id, "to_id": pt_id},
                }])
                if self._on_playthrough_switch:
                    self._on_playthrough_switch(old_id, pt_id)

            self._current_playthrough_id = pt_id
            # Reset summary state for new playthrough
            self._last_summary = None

        # Upsert playthrough record
        field_keys = [f.key for f in self._enabled_fields]
        await self._db.upsert_playthrough(
            playthrough_id=pt_id,
            game=self.config.game,
            playthrough_name=meta.get("playthrough_name", ""),
            country_tag=save.player_country_tag,
            country_name=meta.get("player_country_name", ""),
            multiplayer=meta.get("multiplayer", False),
            snapshot_freq=self.config.snapshot_freq,
            enabled_fields=field_keys,
            game_version=meta.get("version", ""),
            game_date=save.game_date,
        )

        # Update config with auto-detected values
        if not self.config.country_tag:
            self.config.country_tag = save.player_country_tag
            self.config.country_name = meta.get("player_country_name", "")
            self.config.playthrough_id = pt_id
            self.config.multiplayer = meta.get("multiplayer", False)
            self.config.game_version = meta.get("version", "")
