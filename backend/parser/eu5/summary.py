"""
summary.py — Extract a compact summary from an EU5Save for diffing

The summary captures state that changes discretely (ruler, wars, alliances,
culture, religion, rank, age, situations) as opposed to the continuous numeric
fields tracked by snapshots.

Two summaries are compared by events.py to produce a list of typed events.
Summaries are NOT stored in the database — they are ephemeral objects used
only for the diff step.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.parser.save_loader import EU5Save


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CountrySummary:
    """Compact state of a single country, used for diffing."""
    tag: str
    country_id: str
    exists: bool                        # True if country_type == "Real"
    primary_culture: str                # culture key (from save's culture_index)
    primary_religion: str               # religion key (from save's religion_index)
    great_power_rank: int
    capital: int | str                  # numeric location ID
    ruler_name: str                     # played_country.name for player, or "" for AI
    # NOTE: we don't yet have a reliable way to get AI rulers from the country
    # object.  For now ruler_name is only populated for the player country.
    # This is documented as an open question for future toolbox exploration.

    # Localised display names (for frontend display — empty if no loc loaded)
    country_display: str = ""           # localised country name
    culture_display: str = ""           # localised culture name
    religion_display: str = ""          # localised religion name


@dataclass
class WarSummary:
    """Compact state of an active war."""
    war_id: str
    name: str                           # war name if available
    name_display: str = ""              # localised war name (if found)
    attackers: list[str] = field(default_factory=list)  # country IDs or TAGs involved
    defenders: list[str] = field(default_factory=list)


@dataclass
class SituationStatus:
    """Status of a global situation (e.g. black_death)."""
    key: str
    status: str                         # "before", "during", "after", or "inactive"
    start_date: str | None = None
    end_date: str | None = None
    display: str = ""                   # localised situation name (empty = not loaded)


@dataclass
class GameSummary:
    """Full game state summary for one point in time."""
    game_date: str
    current_age: str
    player_tag: str
    player_ruler_name: str

    countries: dict[str, CountrySummary]        # TAG -> summary
    wars: dict[str, WarSummary]                 # war_id -> summary
    situations: dict[str, SituationStatus]      # situation_key -> status

    # Fields with defaults must come after required fields
    current_age_display: str = ""               # localised age name
    real_country_count: int = 0


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_summary(
    save: EU5Save,
    tracked_tags: list[str] | None = None,
) -> GameSummary:
    """
    Extract a GameSummary from an EU5Save.

    Args:
        save:          Parsed save object.
        tracked_tags:  Which country TAGs to include in the summary.
                       None = all Real countries.
    """
    from backend.parser.localisation import display_name as _dn, resolve_war_name as _rwn
    has_loc = bool(save.loc)

    # --- Countries ---
    countries: dict[str, CountrySummary] = {}
    all_real = save.all_real_countries()

    if tracked_tags is not None:
        tracked_set = set(tracked_tags)
        # Always include the player country
        tracked_set.add(save.player_country_tag)
    else:
        tracked_set = None

    for cid, tag, cdata in all_real:
        if tracked_set is not None and tag not in tracked_set:
            continue

        culture_id = cdata.get("primary_culture", -1)
        religion_id = cdata.get("primary_religion", -1)
        culture_key = save.resolve_culture(culture_id) if isinstance(culture_id, int) else str(culture_id)
        religion_key = save.resolve_religion(religion_id) if isinstance(religion_id, int) else str(religion_id)

        countries[tag] = CountrySummary(
            tag=tag,
            country_id=cid,
            exists=True,
            primary_culture=culture_key,
            primary_religion=religion_key,
            great_power_rank=cdata.get("great_power_rank", 9999),
            capital=cdata.get("capital", -1),
            ruler_name="",  # populated below for player only
            country_display=_dn(save.loc, tag) if has_loc else tag,
            culture_display=_dn(save.loc, culture_key) if has_loc else culture_key,
            religion_display=_dn(save.loc, religion_key) if has_loc else religion_key,
        )

    # Player ruler name
    player_tag = save.player_country_tag
    player_ruler = save.player_name
    if player_tag in countries:
        countries[player_tag].ruler_name = player_ruler

    # --- Wars ---
    wars: dict[str, WarSummary] = {}
    war_db = save.raw.get("war_manager", {}).get("database", {})
    for wid, wdata in war_db.items():
        if not isinstance(wdata, dict):
            continue
        # War name lives in wdata["war_name"] — a structured template object.
        # Use resolve_war_name() so both summary and wars.py produce identical
        # display names (template expansion + country adjective substitution).
        war_name_raw = wdata.get("war_name", {})
        if isinstance(war_name_raw, dict):
            name = war_name_raw.get("name", f"war_{wid}")
            name_display = _rwn(war_name_raw, save.loc) if has_loc else name
        else:
            name = str(war_name_raw) if war_name_raw else f"war_{wid}"
            name_display = _dn(save.loc, name) if has_loc else name

        attackers: list[str] = []
        defenders: list[str] = []

        # Try to extract participants — structure may vary
        for side_key, target_list in [("attackers", attackers), ("defenders", defenders)]:
            side = wdata.get(side_key, [])
            if isinstance(side, list):
                for entry in side:
                    if isinstance(entry, dict):
                        cid = str(entry.get("country", entry.get("value", "")))
                        tag = save.tag_index.get(cid, cid)
                        target_list.append(tag)
                    elif isinstance(entry, (int, str)):
                        tag = save.tag_index.get(str(entry), str(entry))
                        target_list.append(tag)

        wars[wid] = WarSummary(
            war_id=wid,
            name=name,
            name_display=name_display,
            attackers=attackers,
            defenders=defenders,
        )

    # --- Situations ---
    situations: dict[str, SituationStatus] = {}
    sit_mgr = save.raw.get("situation_manager", {})
    for sit_key, sit_data in sit_mgr.items():
        if sit_key.startswith("_") or not isinstance(sit_data, (dict, list)):
            continue

        # Localise situation key: try the key itself, then a _name variant
        sit_display = _dn(save.loc, sit_key) if has_loc else sit_key

        if isinstance(sit_data, list) and len(sit_data) == 0:
            # Empty list = not triggered
            situations[sit_key] = SituationStatus(
                key=sit_key, status="inactive", display=sit_display,
            )
        elif isinstance(sit_data, dict):
            # Has data — try to determine status
            status_val = sit_data.get("status", "unknown")
            if isinstance(status_val, str):
                status = status_val
            else:
                status = "active"
            situations[sit_key] = SituationStatus(
                key=sit_key,
                status=status,
                start_date=str(sit_data.get("start_date", "")),
                end_date=str(sit_data.get("end_date", "")),
                display=sit_display,
            )
        elif isinstance(sit_data, str):
            # Some situations store just the status string
            situations[sit_key] = SituationStatus(
                key=sit_key, status=sit_data, display=sit_display,
            )

    return GameSummary(
        game_date=save.game_date,
        current_age=save.current_age_key,
        current_age_display=save.current_age_name if has_loc else save.current_age_key,
        player_tag=player_tag,
        player_ruler_name=player_ruler,
        countries=countries,
        wars=wars,
        situations=situations,
        real_country_count=len(all_real),
    )
