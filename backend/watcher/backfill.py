"""
backfill.py — Historical save import for a given playthrough.

Scans a save folder for .eu5 files, finds all that belong to the specified
playthrough_id, and imports any not already in the database.

Event detection is deliberately skipped — we cannot reconstruct sequential
diffs from potentially incomplete historical saves.  Only snapshot data
(steps equivalent to pipeline steps 5-9) is imported per save.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Any

from backend.parser.save_loader import load_save
from backend.parser.eu5.field_catalog import FieldDef
from backend.parser.eu5.snapshot import extract_snapshot
from backend.parser.eu5.religions import extract_religion_statics, extract_religion_snapshot_rows
from backend.parser.eu5.cultures import extract_culture_statics
from backend.parser.eu5.wars import (
    extract_war_statics, extract_war_snapshot_rows,
    extract_all_war_participants,
)
from backend.parser.eu5.military import (
    load_unit_type_catalog,
    extract_country_military,
    extract_war_participant_snapshots,
    extract_new_battles,
    extract_sieges,
    build_war_participant_index,
    build_active_war_country_ids,
)
from backend.parser.eu5.geography import (
    extract_location_statics, extract_location_snapshot_rows,
    extract_province_statics, extract_province_snapshot_rows,
)
from backend.parser.eu5.geography_index import GeographyIndex
from backend.parser.eu5.demographics import extract_pop_snapshot_rows
from backend.parser.eu5.countries import extract_country_rows
from backend.storage.database import Database

logger = logging.getLogger(__name__)


async def run_backfill(
    playthrough_id: str,
    save_folder: Path,
    db: Database,
    rakaly_bin: Path,
    loc_dir: Path | None,
    enabled_fields: list[FieldDef],
    broadcast_fn: Callable[[dict], Any] | None = None,
    game_install_path: Path | None = None,
) -> dict:
    """
    Scan save_folder for .eu5 files belonging to playthrough_id and import
    any not already in the database.

    Args:
        playthrough_id:  The campaign UUID to match against.
        save_folder:     Directory to scan for .eu5 files.
        db:              Open and writable database instance.
        rakaly_bin:      Path to the rakaly binary.
        loc_dir:         Localisation directory (may be None if not found).
        enabled_fields:  Fields to extract per snapshot.
        broadcast_fn:    Optional async callable(progress_dict) for WS progress.

    Returns:
        Summary dict: {total, matched, added, skipped, errors}
    """

    async def _progress(data: dict) -> None:
        if broadcast_fn:
            try:
                await broadcast_fn(data)
            except Exception:
                pass

    # Collect and sort all .eu5 files by modification time (oldest first).
    # Sorting by mtime approximates chronological order which is nicer for
    # the DB even though the duplicate guard makes ordering non-critical.
    try:
        # Pre-filter by playthrough_id in the filename — EU5 autosaves embed
        # the campaign UUID in the filename, so this avoids parsing unrelated saves.
        save_files = sorted(
            [p for p in save_folder.glob("*.eu5") if playthrough_id in p.name],
            key=lambda p: p.stat().st_mtime,
        )
    except Exception:
        logger.exception("Backfill: failed to list save folder")
        await _progress({"total": 0, "processed": 0, "matched": 0, "added": 0,
                          "skipped": 0, "errors": 1, "done": True, "current_file": ""})
        return {"total": 0, "matched": 0, "added": 0, "skipped": 0, "errors": 1}

    total = len(save_files)
    matched = 0
    added = 0
    skipped = 0
    errors = 0

    # Initial broadcast so the UI shows 0/N immediately
    await _progress({
        "total": total, "processed": 0, "matched": 0,
        "added": 0, "skipped": 0, "errors": 0,
        "done": False, "current_file": "",
    })

    effective_loc_dir = loc_dir if (loc_dir and loc_dir.exists()) else None

    # Load unit type catalog once (needed for regiment extraction)
    unit_type_catalog: dict = {}
    geo_index: GeographyIndex | None = None
    if game_install_path and Path(game_install_path).exists():
        unit_type_catalog = load_unit_type_catalog(game_install_path)
        if not unit_type_catalog:
            logger.error(
                "Backfill: unit type catalog is empty — military regiment data will "
                "NOT be collected. Check that game_install_path points to the EU5 "
                "install directory and that common/unit_types/ (or similar) exists."
            )
        # Load geographic hierarchy index from same install path.
        # A missing definitions.txt is a real misconfiguration: the Territory
        # tab, geographic filters, and any region-based event will silently
        # degrade.  Log at ERROR so it actually surfaces.
        try:
            geo_index = GeographyIndex.load(game_install_path)
        except FileNotFoundError as exc:
            logger.error(
                "Backfill: GeographyIndex.load() failed - definitions.txt not "
                "found under %s. Locations will be saved WITHOUT area/region/"
                "sub_continent/continent fields. Root cause: %s",
                game_install_path, exc,
            )
        except Exception as exc:  # noqa: BLE001  — want full stack on parser errors
            logger.error(
                "Backfill: GeographyIndex.load() failed while parsing "
                "definitions.txt under %s. Locations will be saved WITHOUT "
                "geographic hierarchy fields.",
                game_install_path, exc_info=True,
            )
    else:
        logger.warning(
            "Backfill: game_install_path not provided or not found — "
            "military and geography extraction will be skipped."
        )

    # Track most recent battle per war to detect newly-recorded battles
    prev_battle_states: dict[str, dict] = {}

    for i, save_path in enumerate(save_files):
        # Broadcast progress at start of each file so UI stays responsive
        await _progress({
            "total": total, "processed": i,
            "matched": matched, "added": added,
            "skipped": skipped, "errors": errors,
            "done": False, "current_file": save_path.name,
        })

        # --- Parse ---
        try:
            save = load_save(
                save_path,
                rakaly_bin=rakaly_bin,
                loc_dir=effective_loc_dir,
                verbose=False,
            )
        except Exception:
            logger.warning(f"Backfill: failed to parse {save_path.name}", exc_info=True)
            errors += 1
            continue

        # --- Check playthrough_id ---
        pt_id = save.raw.get("metadata", {}).get("playthrough_id", "")
        if pt_id != playthrough_id:
            continue  # Different campaign — skip silently

        matched += 1

        # Upsert playthrough record so it exists in the DB even if the
        # pipeline has never seen this file.
        meta = save.raw.get("metadata", {})
        field_keys = [f.key for f in enabled_fields]
        try:
            await db.upsert_playthrough(
                playthrough_id=pt_id,
                game="eu5",
                playthrough_name=meta.get("playthrough_name", ""),
                country_tag=save.player_country_tag,
                country_name=meta.get("player_country_name", ""),
                multiplayer=meta.get("multiplayer", False),
                snapshot_freq="every_save",
                enabled_fields=field_keys,
                game_version=meta.get("version", ""),
                game_date=save.game_date,
            )
        except Exception:
            logger.warning(f"Backfill: upsert_playthrough failed for {save_path.name}", exc_info=True)

        # --- Duplicate guard ---
        if await db.snapshot_exists(pt_id, save.game_date):
            logger.debug(f"Backfill: {save_path.name} already in DB ({save.game_date})")
            skipped += 1
            continue

        # --- Extract and store snapshot ---
        try:
            snapshot_data = extract_snapshot(save, enabled_fields=enabled_fields)
            snap_id = await db.insert_snapshot(pt_id, save.game_date, snapshot_data)
        except Exception:
            logger.warning(f"Backfill: snapshot extraction failed for {save_path.name}", exc_info=True)
            errors += 1
            continue

        if snap_id is None:
            # Race-condition duplicate inserted between our check and write
            skipped += 1
            continue

        logger.info(f"Backfill: imported {save_path.name} → snapshot #{snap_id} ({save.game_date})")

        # --- Religions ---
        try:
            rel_statics = extract_religion_statics(save)
            for r in rel_statics:
                await db.upsert_religion(
                    playthrough_id=pt_id,
                    religion_id=r["religion_id"],
                    definition=r["definition"],
                    name=r.get("name", ""),
                    religion_group=r.get("religion_group", ""),
                    has_religious_head=r.get("has_religious_head", False),
                    color_rgb=r.get("color_rgb"),
                )
            rel_rows = extract_religion_snapshot_rows(save)
            await db.insert_religion_snapshots(pt_id, snap_id, save.game_date, rel_rows)
        except Exception:
            logger.warning(f"Backfill: religion extraction failed for {save_path.name}", exc_info=True)

        # --- Cultures ---
        # Empty culture_rows is a symptom, not a benign outcome: a healthy
        # EU5 save has ~2k culture_manager entries. Surface it loudly.
        try:
            culture_rows = extract_culture_statics(save)
            if not culture_rows:
                logger.error(
                    "Backfill: extract_culture_statics returned 0 rows for %s "
                    "- culture_manager.database is empty or in an unexpected "
                    "shape. Location snapshots will reference unresolvable "
                    "culture IDs.",
                    save_path.name,
                )
            else:
                await db.bulk_upsert_cultures(pt_id, culture_rows)
        except Exception:
            logger.error(
                f"Backfill: culture extraction failed for {save_path.name}",
                exc_info=True,
            )

        # --- Wars ---
        try:
            war_statics = extract_war_statics(save)
            for w in war_statics:
                await db.upsert_war(pt_id, w)
            war_snap_rows = extract_war_snapshot_rows(save)
            await db.insert_war_snapshots(pt_id, snap_id, save.game_date, war_snap_rows)
            all_participants = extract_all_war_participants(save)
            for wid, parts in all_participants.items():
                await db.upsert_war_participants(pt_id, wid, parts)
            # War participant snapshots (scores + cumulative losses per active war)
            wp_snap_rows = extract_war_participant_snapshots(save)
            await db.bulk_insert_war_participant_snapshots(
                pt_id, snap_id, save.game_date, wp_snap_rows,
            )
        except Exception:
            logger.warning(f"Backfill: war extraction failed for {save_path.name}", exc_info=True)

        # --- Military ---
        try:
            active_war_ids = build_active_war_country_ids(save)
            mil_rows = extract_country_military(save, unit_type_catalog, active_war_ids)
            await db.bulk_insert_country_military_snapshots(
                pt_id, snap_id, save.game_date, mil_rows,
            )
        except Exception:
            logger.warning(f"Backfill: military extraction failed for {save_path.name}", exc_info=True)

        # --- Battles ---
        try:
            new_battles, prev_battle_states = extract_new_battles(save, prev_battle_states)
            for battle in new_battles:
                await db.upsert_battle(pt_id, snap_id, battle)
            if new_battles:
                logger.debug(f"Backfill: {len(new_battles)} battles recorded for {save_path.name}")
        except Exception:
            logger.warning(f"Backfill: battle extraction failed for {save_path.name}", exc_info=True)

        # --- Sieges ---
        try:
            wp_index = build_war_participant_index(save)
            siege_rows = extract_sieges(save, wp_index)
            active_siege_ids: set[str] = set()
            for siege in siege_rows:
                await db.upsert_siege(pt_id, snap_id, save.game_date, siege)
                active_siege_ids.add(str(siege["siege_game_id"]))
            await db.mark_sieges_inactive(pt_id, active_siege_ids)
        except Exception:
            logger.warning(f"Backfill: siege extraction failed for {save_path.name}", exc_info=True)

        # --- Geography ---
        try:
            loc_statics = extract_location_statics(save, geo_index=geo_index)
            await db.bulk_upsert_locations(pt_id, loc_statics)
            loc_rows = extract_location_snapshot_rows(save)
            await db.insert_location_snapshots(pt_id, snap_id, save.game_date, loc_rows)
            prov_statics = extract_province_statics(save)
            await db.bulk_upsert_provinces(pt_id, prov_statics)
            prov_rows = extract_province_snapshot_rows(save)
            await db.insert_province_snapshots(pt_id, snap_id, save.game_date, prov_rows)
        except Exception:
            logger.warning(f"Backfill: geography extraction failed for {save_path.name}", exc_info=True)

        # --- Countries ---
        try:
            country_rows = extract_country_rows(save)
            await db.bulk_upsert_countries(pt_id, country_rows)
        except Exception:
            logger.warning(f"Backfill: country extraction failed for {save_path.name}", exc_info=True)

        # --- Demographics ---
        try:
            pop_rows = extract_pop_snapshot_rows(save)
            await db.insert_pop_snapshots(pt_id, snap_id, save.game_date, pop_rows)
        except Exception:
            logger.warning(f"Backfill: demographics extraction failed for {save_path.name}", exc_info=True)

        added += 1

    # Finalise country succession chains now that all saves have been processed
    if matched > 0:
        try:
            await db.finalize_country_canonical_tags(playthrough_id)
        except Exception:
            logger.warning("Backfill: finalize_country_canonical_tags failed", exc_info=True)

    # Final broadcast
    await _progress({
        "total": total, "processed": total,
        "matched": matched, "added": added,
        "skipped": skipped, "errors": errors,
        "done": True, "current_file": "",
    })

    logger.info(
        f"Backfill complete: {total} files scanned, "
        f"{matched} matched playthrough, {added} added, "
        f"{skipped} skipped (already in DB), {errors} errors"
    )
    return {
        "total": total,
        "matched": matched,
        "added": added,
        "skipped": skipped,
        "errors": errors,
    }
