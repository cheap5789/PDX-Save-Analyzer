"""
events.py — Diff two GameSummary objects to produce typed events

Each event has a type, the game date it was detected at, and a payload dict
with event-specific data.  Events are stored in the `events` table regardless
of snapshot frequency.

Event types detected:
    Global:
        age_transition          — current_age changed
        situation_started       — a situation went from inactive → active/during
        situation_ended         — a situation went from active → after
    Country:
        ruler_changed           — player ruler name changed (AI rulers: future work)
        culture_changed         — primary_culture changed
        religion_changed        — primary_religion changed
        great_power_rank_changed — significant rank change (configurable threshold)
        capital_moved           — capital location ID changed
        country_appeared        — a country exists now that didn't before
        country_annexed         — a country that existed before is now gone
    War:
        war_started             — new war ID appeared
        war_ended               — war ID disappeared
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.parser.eu5.summary import GameSummary, CountrySummary, WarSummary


@dataclass
class GameEvent:
    """A single detected event."""
    event_type: str          # one of the types listed above
    game_date: str           # in-game date when detected (from the new save)
    payload: dict[str, Any]  # event-specific data

    def __repr__(self) -> str:
        return f"GameEvent({self.event_type!r}, {self.game_date}, {self.payload})"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Rank change must be at least this big to generate an event (avoids noise)
RANK_CHANGE_THRESHOLD = 10


# ---------------------------------------------------------------------------
# Main diff function
# ---------------------------------------------------------------------------

def diff_summaries(
    old: GameSummary | None,
    new: GameSummary,
    rank_threshold: int = RANK_CHANGE_THRESHOLD,
) -> list[GameEvent]:
    """
    Compare two summaries and return a list of events.

    If old is None (first parse of a campaign), only structural events
    are emitted (e.g. initial war list).

    Args:
        old:             Previous summary (or None for first parse).
        new:             Current summary.
        rank_threshold:  Minimum rank change to emit rank_changed event.

    Returns:
        List of GameEvent, in no particular order.
    """
    events: list[GameEvent] = []
    date = new.game_date

    if old is None:
        # First parse — no previous state to diff against.
        # Optionally emit initial state events here in the future.
        return events

    # --- Global events ---
    _diff_age(old, new, date, events)
    _diff_situations(old, new, date, events)

    # --- Country events ---
    _diff_countries(old, new, date, events, rank_threshold)

    # --- War events ---
    _diff_wars(old, new, date, events)

    return events


# ---------------------------------------------------------------------------
# Internal diff functions
# ---------------------------------------------------------------------------

def _diff_age(
    old: GameSummary, new: GameSummary, date: str, events: list[GameEvent]
) -> None:
    if old.current_age != new.current_age:
        events.append(GameEvent(
            event_type="age_transition",
            game_date=date,
            payload={
                "from_age": old.current_age,
                "to_age": new.current_age,
                "from_age_display": old.current_age_display or old.current_age,
                "to_age_display": new.current_age_display or new.current_age,
            },
        ))


def _diff_situations(
    old: GameSummary, new: GameSummary, date: str, events: list[GameEvent]
) -> None:
    all_keys = set(old.situations) | set(new.situations)
    for key in all_keys:
        old_sit = old.situations.get(key)
        new_sit = new.situations.get(key)

        old_status = old_sit.status if old_sit else "inactive"
        new_status = new_sit.status if new_sit else "inactive"

        if old_status == new_status:
            continue

        # Situation started (inactive → anything active)
        if old_status == "inactive" and new_status != "inactive":
            events.append(GameEvent(
                event_type="situation_started",
                game_date=date,
                payload={
                    "situation": key,
                    "status": new_status,
                    "start_date": new_sit.start_date if new_sit else None,
                },
            ))
        # Situation ended (active/during → after)
        elif new_status == "after" and old_status not in ("after", "inactive"):
            events.append(GameEvent(
                event_type="situation_ended",
                game_date=date,
                payload={
                    "situation": key,
                    "previous_status": old_status,
                    "end_date": new_sit.end_date if new_sit else None,
                },
            ))
        # Any other status change
        elif old_status != new_status:
            events.append(GameEvent(
                event_type="situation_changed",
                game_date=date,
                payload={
                    "situation": key,
                    "from_status": old_status,
                    "to_status": new_status,
                },
            ))


def _diff_countries(
    old: GameSummary,
    new: GameSummary,
    date: str,
    events: list[GameEvent],
    rank_threshold: int,
) -> None:
    all_tags = set(old.countries) | set(new.countries)

    for tag in all_tags:
        old_c = old.countries.get(tag)
        new_c = new.countries.get(tag)

        # Country appeared
        if old_c is None and new_c is not None:
            events.append(GameEvent(
                event_type="country_appeared",
                game_date=date,
                payload={"tag": tag, "country": new_c.country_display or tag},
            ))
            continue

        # Country annexed / disappeared
        if old_c is not None and new_c is None:
            events.append(GameEvent(
                event_type="country_annexed",
                game_date=date,
                payload={"tag": tag, "country": old_c.country_display or tag},
            ))
            continue

        # Both exist — check fields
        assert old_c is not None and new_c is not None

        # Ruler change (player only — AI rulers TBD)
        if old_c.ruler_name and new_c.ruler_name and old_c.ruler_name != new_c.ruler_name:
            events.append(GameEvent(
                event_type="ruler_changed",
                game_date=date,
                payload={
                    "tag": tag,
                    "country": new_c.country_display or tag,
                    "from_ruler": old_c.ruler_name,
                    "to_ruler": new_c.ruler_name,
                },
            ))

        # Culture change
        if old_c.primary_culture != new_c.primary_culture:
            events.append(GameEvent(
                event_type="culture_changed",
                game_date=date,
                payload={
                    "tag": tag,
                    "country": new_c.country_display or tag,
                    "from_culture": new_c.culture_display if old_c.primary_culture != new_c.primary_culture else old_c.culture_display,
                    "to_culture": new_c.culture_display or new_c.primary_culture,
                    "from_culture_key": old_c.primary_culture,
                    "to_culture_key": new_c.primary_culture,
                },
            ))

        # Religion change
        if old_c.primary_religion != new_c.primary_religion:
            events.append(GameEvent(
                event_type="religion_changed",
                game_date=date,
                payload={
                    "tag": tag,
                    "country": new_c.country_display or tag,
                    "from_religion": old_c.religion_display or old_c.primary_religion,
                    "to_religion": new_c.religion_display or new_c.primary_religion,
                    "from_religion_key": old_c.primary_religion,
                    "to_religion_key": new_c.primary_religion,
                },
            ))

        # Rank change
        rank_delta = old_c.great_power_rank - new_c.great_power_rank  # positive = improved
        if abs(rank_delta) >= rank_threshold:
            events.append(GameEvent(
                event_type="great_power_rank_changed",
                game_date=date,
                payload={
                    "tag": tag,
                    "country": new_c.country_display or tag,
                    "from_rank": old_c.great_power_rank,
                    "to_rank": new_c.great_power_rank,
                    "delta": rank_delta,
                },
            ))

        # Capital moved
        if old_c.capital != new_c.capital:
            events.append(GameEvent(
                event_type="capital_moved",
                game_date=date,
                payload={
                    "tag": tag,
                    "country": new_c.country_display or tag,
                    "from_capital": old_c.capital,
                    "to_capital": new_c.capital,
                },
            ))


def _diff_wars(
    old: GameSummary, new: GameSummary, date: str, events: list[GameEvent]
) -> None:
    old_ids = set(old.wars)
    new_ids = set(new.wars)

    # New wars
    for wid in new_ids - old_ids:
        war = new.wars[wid]
        events.append(GameEvent(
            event_type="war_started",
            game_date=date,
            payload={
                "war_id": wid,
                "name": war.name_display or war.name,
                "name_key": war.name,
                "attackers": war.attackers,
                "defenders": war.defenders,
            },
        ))

    # Ended wars
    for wid in old_ids - new_ids:
        war = old.wars[wid]
        events.append(GameEvent(
            event_type="war_ended",
            game_date=date,
            payload={
                "war_id": wid,
                "name": war.name_display or war.name,
                "name_key": war.name,
            },
        ))
