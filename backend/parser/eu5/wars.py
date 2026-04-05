"""
wars.py — Extract war entity data from an EU5Save

Wars are a parallel tracked entity type alongside countries and religions.
Each war has:
  - Static data (identity, participants, goals) written/updated once
  - Snapshot data (scores, momentum) recorded per snapshot
  - Participant data (side, losses, status) upserted on each snapshot

War objects live in war_manager.database, keyed by numeric string.
Entries with value "none" are sentinel/empty slots and must be skipped.

Participant data is in war.all[] — an array of participant objects, NOT
in attacker.countries/defender.countries.
"""

from __future__ import annotations

import json
from typing import Any

from backend.parser.save_loader import EU5Save
from backend.parser.localisation import resolve_war_name


def extract_war_statics(save: EU5Save) -> list[dict[str, Any]]:
    """
    Extract static war data for all wars in the save.

    Returns a list of dicts with keys matching the wars DB table.
    Called every snapshot — upsert handles create-or-update (e.g. end_date).
    """
    wm = save.raw.get("war_manager", {}).get("database", {})
    results = []

    for wid, wdata in wm.items():
        if not isinstance(wdata, dict):
            continue

        # War name — structured template object in save; resolve via localisation
        war_name_raw = wdata.get("war_name", {})
        name_key = (
            war_name_raw.get("name", f"war_{wid}")
            if isinstance(war_name_raw, dict)
            else str(war_name_raw) if war_name_raw else f"war_{wid}"
        )
        name_display = (
            resolve_war_name(war_name_raw, save.loc)
            if isinstance(war_name_raw, dict) and save.loc
            else name_key
        )

        # Goal / casus belli
        goal = wdata.get("take_province", {})
        goal_type = goal.get("type") if isinstance(goal, dict) else None
        casus_belli = goal.get("casus_belli") if isinstance(goal, dict) else None
        goal_target = goal.get("target") if isinstance(goal, dict) else None

        results.append({
            "id": wid,
            "name_key": name_key,
            "name_display": name_display,
            "start_date": wdata.get("start_date"),
            "end_date": wdata.get("end_date"),
            "is_civil_war": bool(wdata.get("has_civil_war", False)),
            "is_revolt": bool(wdata.get("revolt", False)),
            "original_attacker_id": wdata.get("original_attacker"),
            "original_target_id": wdata.get("original_attacker_target"),
            "original_defenders": wdata.get("original_defenders"),
            "goal_type": goal_type,
            "casus_belli": casus_belli,
            "goal_target": goal_target,
        })

    return results


def extract_war_snapshot_rows(save: EU5Save) -> list[dict[str, Any]]:
    """
    Extract per-war dynamic score data for one snapshot.

    Only emits rows for active wars (no end_date).
    Score model: attacker_score and defender_score are independent cumulative pools.
    net_war_score = attacker_score - defender_score (derived).

    Returns a list of dicts with keys matching war_snapshots table.
    """
    wm = save.raw.get("war_manager", {}).get("database", {})
    results = []

    for wid, wdata in wm.items():
        if not isinstance(wdata, dict):
            continue
        # Only snapshot active wars
        if wdata.get("end_date"):
            continue

        attacker_score = wdata.get("attacker_score")
        defender_score = wdata.get("defender_score")

        # Derive net score (both can be None for new wars)
        net = None
        if attacker_score is not None and defender_score is not None:
            net = attacker_score - defender_score
        elif attacker_score is not None:
            net = attacker_score
        elif defender_score is not None:
            net = -defender_score

        results.append({
            "war_id": wid,
            "attacker_score": attacker_score,
            "defender_score": defender_score,
            "net_war_score": net,
            "war_direction_quarter": wdata.get("war_direction_quarter"),
            "war_direction_year": wdata.get("war_direction_year"),
            "war_goal_held": wdata.get("war_goal_held"),
        })

    return results


def extract_war_participants(
    save: EU5Save,
    war_id: str,
    wdata: dict,
) -> list[dict[str, Any]]:
    """
    Extract participant data for a single war.

    Participants are in wdata["all"] — an array of participant objects.
    Each has: country, history.request (side/reason/join_type), history.joined
    (date/scores/losses), status.

    Returns a list of dicts with keys matching war_participants table.
    """
    participants_raw = wdata.get("all", [])
    if not isinstance(participants_raw, list):
        return []

    results = []
    for p in participants_raw:
        if not isinstance(p, dict):
            continue

        country_id = p.get("country")
        if country_id is None:
            continue

        country_tag = save.tag_index.get(str(country_id), str(country_id))

        # Parse history
        history = p.get("history", {})
        request = history.get("request", {}) if isinstance(history, dict) else {}
        joined = history.get("joined", {}) if isinstance(history, dict) else {}

        side = request.get("side", "Unknown")
        join_reason = request.get("reason", "")
        join_type = request.get("join_type", "")
        called_by = request.get("called_by")

        join_date = joined.get("date") if isinstance(joined, dict) else None

        # Scores from joined
        scores = joined.get("score", {}) if isinstance(joined, dict) else {}
        score_combat = scores.get("Combat", 0) if isinstance(scores, dict) else 0
        score_siege = scores.get("Siege", 0) if isinstance(scores, dict) else 0
        score_joining = scores.get("JoiningWar", 0) if isinstance(scores, dict) else 0

        # Losses
        losses_raw = joined.get("losses", {}) if isinstance(joined, dict) else {}
        losses = losses_raw.get("losses") if isinstance(losses_raw, dict) else None

        status = p.get("status", "Active")
        io_id = p.get("io")

        results.append({
            "country_id": country_id,
            "country_tag": country_tag,
            "side": side,
            "join_reason": join_reason,
            "join_type": join_type,
            "called_by": called_by,
            "join_date": join_date,
            "status": str(status),
            "score_combat": score_combat or 0,
            "score_siege": score_siege or 0,
            "score_joining": score_joining or 0,
            "losses": losses if losses else None,
            "io_id": io_id,
        })

    return results


def extract_all_war_participants(save: EU5Save) -> dict[str, list[dict]]:
    """
    Extract participants for ALL wars in the save.

    Returns {war_id: [participant_dicts]}.
    """
    wm = save.raw.get("war_manager", {}).get("database", {})
    result = {}
    for wid, wdata in wm.items():
        if not isinstance(wdata, dict):
            continue
        participants = extract_war_participants(save, wid, wdata)
        if participants:
            result[wid] = participants
    return result


def detect_battle_events(
    save: EU5Save,
    prev_battles: dict[str, dict] | None,
) -> tuple[list[dict], dict[str, dict]]:
    """
    Detect new battles by comparing battle.date between snapshots.

    Args:
        save:          Current save.
        prev_battles:  {war_id: {date, location}} from previous snapshot.
                       None on first run.

    Returns:
        (events, current_battles)
        events: list of battle event dicts (for the events table)
        current_battles: updated battle state for next diff
    """
    wm = save.raw.get("war_manager", {}).get("database", {})
    current_battles: dict[str, dict] = {}
    events: list[dict] = []

    for wid, wdata in wm.items():
        if not isinstance(wdata, dict):
            continue

        battle = wdata.get("battle")
        if not isinstance(battle, dict):
            continue

        battle_date = battle.get("date")
        battle_location = battle.get("location")
        if battle_date is None:
            continue

        current_battles[wid] = {"date": battle_date, "location": battle_location}

        # Compare with previous
        if prev_battles is not None:
            prev = prev_battles.get(wid, {})
            if prev.get("date") != battle_date:
                # New battle detected!
                attacker = battle.get("attacker", {})
                defender = battle.get("defender", {})

                events.append({
                    "game_date": str(battle_date),
                    "event_type": "battle",
                    "payload": {
                        "war_id": wid,
                        "location_id": battle_location,
                        "date": str(battle_date),
                        "result": battle.get("result"),
                        "attacker_losses": attacker.get("total"),
                        "defender_losses": defender.get("total"),
                        "attacker_country": attacker.get("who", {}).get("country")
                            if isinstance(attacker.get("who"), dict) else None,
                        "defender_country": defender.get("who", {}).get("country")
                            if isinstance(defender.get("who"), dict) else None,
                    },
                })

    return events, current_battles
