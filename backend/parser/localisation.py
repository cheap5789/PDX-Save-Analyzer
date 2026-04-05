"""
localisation.py — EU5 localisation file loader

Parses all .yml localisation files from game-data/eu5/localization/english/
and returns a flat dict of { key: "Display Name" }.

Format of .yml files:
    l_english:
     KEY: "Display Name"
     KEY_ADJ: "Adjective"

Usage:
    from toolbox.localisation import load_localisation
    loc = load_localisation("game-data/eu5/localization/english")
    print(loc.get("WUR"))       # -> "Württemberg" (or whatever)
    print(loc.get("catholic"))  # -> "Catholic"
    print(loc.get("swedish"))   # -> "Swedish"
"""

import re
from pathlib import Path


# Match lines like:  KEY: "Value"  or  KEY: 'Value'
# Keys may contain letters, digits, underscores, hyphens, dots
_LINE_RE = re.compile(r'^\s+([\w\-\.]+):\s*["\'](.+?)["\']', re.UNICODE)


def load_localisation(loc_dir: str | Path) -> dict[str, str]:
    """
    Load all .yml files in loc_dir and return a merged key→display-name dict.
    Files are processed in alphabetical order; later files override earlier ones
    for duplicate keys (shouldn't normally happen, but just in case).
    """
    loc_dir = Path(loc_dir)
    result: dict[str, str] = {}

    yml_files = sorted(loc_dir.glob("*.yml"))
    if not yml_files:
        raise FileNotFoundError(f"No .yml files found in {loc_dir}")

    for yml_path in yml_files:
        _parse_yml(yml_path, result)

    return result


def _parse_yml(path: Path, out: dict[str, str]) -> None:
    """Parse a single localisation .yml file into out dict."""
    try:
        # EU5 .yml files use UTF-8-BOM
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="windows-1252", errors="replace")

    for line in text.splitlines():
        m = _LINE_RE.match(line)
        if m:
            key, value = m.group(1), m.group(2)
            # Skip entries with dynamic scripted values (runtime $ variables or
            # [ game-concept references).  But allow through entries whose only
            # $ variable is $ADJ$ — those are static cross-references used in
            # war name templates and are resolved by resolve_war_name().
            if "[" in value:
                continue
            remaining = value.replace("$ADJ$", "")
            if "$" in remaining:
                continue
            out[key] = value


# ---------------------------------------------------------------------------
# War name template resolver
# ---------------------------------------------------------------------------

# Templates from diplomacy_l_english.yml.
# Stored here because the loc loader deliberately skips scripted entries
# (those containing '$'), so these never land in the regular loc dict.
_WAR_NAME_TEMPLATES: dict[str, str] = {
    "NORMAL_WAR_NAME":                         "$NUM$$ORDER$ $FIRSTNAME$–$SECONDNAME$ War",
    "INDEPENDENCE_WAR_NAME":                    "$NUM$$ORDER$ Rebellion Against $SECONDNAME$",
    "AGRESSION_WAR_NAME":                       "$NUM$$ORDER$ War of $FIRSTNAME$ Aggression",
    "COALITION_WAR_NAME":                       "The $NUM$$ORDER$ War of the Anti-$SECONDNAME$ Coalition",
    "COLONIAL_WAR_NAME":                        "The $NUM$$ORDER$ Colonial War of $FIRSTNAME$ and $SECONDNAME$",
    "CLAIM_THRONE_WAR_NAME":                    "The $NUM$$ORDER$ War of the $SECONDNAME$ Succession",
    "ANNEXING_ME_WAR_NAME":                     "The $NUM$$ORDER$ War against Annexation of $FIRSTNAME$",
    "CRUSADE_WAR_NAME":                         "The $NUM$$ORDER$ Crusade against $SECONDNAME$",
    "EXCOM_WAR_NAME":                           "$NUM$$ORDER$ $FIRSTNAME$–$SECONDNAME$ Excommunication War",
    "HUNDRED_YEARS_WAR_NAME":                   "The $NUM$$ORDER$ Phase of the Hundred Years War",
    "TAKE_SHOGUNATE_NAME":                      "The $NUM$$ORDER$ War for the Shogunate",
    "DISSOLVE_TATAR_YOKE_NAME":                 "The $NUM$$ORDER$ War to Dissolve the Tatar Yoke",
    "CLAN_EXPANSION_WAR_NAME":                  "The $NUM$$ORDER$ Clan Expansion War Against $SECONDNAME$",
    "CIVIL_WAR_NAME":                           "$NUM$$ORDER$ $FIRSTNAME$ Civil War",
    "SENGOKU_WAR_NAME":                         "The $NUM$$ORDER$ War Against $SECONDNAME$ in the Sengoku",
    "NANBOKUCHOU_WAR_NAME":                     "The $NUM$$ORDER$ War Against $SECONDNAME$ in the Nanbokuchō",
    "red_turban_rebellions_WAR_NAME":           "The $NUM$$ORDER$ $FIRSTNAME$ Red Turban Rebellion",
    "red_turban_rebellions_AGAINST_OTHER_REBELS_WAR_NAME": "The $NUM$$ORDER$ $FIRSTNAME$–$SECONDNAME$ Regional Supremacy War",
    "UNIFY_ILKHANATE_WAR_NAME":                 "The $NUM$$ORDER$ War to Unify the Ilkhanate against $SECONDNAME$",
    "FALSE_ILKHAN_CLAIMANT_WAR_NAME":           "The $NUM$$ORDER$ Ilkhanate Claim War against $SECONDNAME$",
    "SHED_SHACKLES_OF_ILKHANATE_WAR_NAME":      "The $NUM$$ORDER$ War to Shed the Ilkhanate's Shackles against $SECONDNAME$",
}

_ORDINAL_SUFFIX = {1: "st", 2: "nd", 3: "rd"}


def _ordinal(n: int) -> tuple[str, str]:
    """Return (num_str, order_str) for an ordinal.  n=1 → ("", "") so the
    first war of a type has no numeric prefix."""
    if n <= 1:
        return "", ""
    suffix = "th" if (n % 100) in (11, 12, 13) else _ORDINAL_SUFFIX.get(n % 10, "th")
    return str(n), suffix


def _resolve_base_adj(base: dict, loc: dict[str, str]) -> str:
    """Extract the adjective display string from a war_name bases entry."""
    if not isinstance(base, dict):
        return ""

    # Explicit adjective key stored under base.key.Adjective
    key_block = base.get("key")
    if isinstance(key_block, dict):
        adj_key = key_block.get("Adjective", "")
        if adj_key:
            val = loc.get(adj_key, "")
            if val and "$ADJ$" in val:
                # One level of nesting: resolve $ADJ$ from the inner base TAG
                inner_bases = base.get("bases", {})
                inner_tag = inner_bases.get("Base", "") if isinstance(inner_bases, dict) else ""
                inner_adj = loc.get(f"{inner_tag}_ADJ", inner_tag) if inner_tag else ""
                val = val.replace("$ADJ$", inner_adj).strip()
            if val:
                return val

    # Fallback: {name}_ADJ in loc, then name itself
    name = base.get("name", "")
    return loc.get(f"{name}_ADJ", loc.get(name, name))


def resolve_war_name(war_name_raw: dict, loc: dict[str, str]) -> str:
    """
    Build a human-readable war name from the structured war_name object in an
    EU5 save and the loaded localisation dict.

    war_name_raw is the dict at war_manager.database[id].war_name.  Expected
    fields:
      name     — template key, e.g. "NORMAL_WAR_NAME"
      ordinal  — 1-based occurrence count for this template (1 = no prefix)
      bases    — { "First": {...}, "Second": {...} } country adjective info

    Returns a ready-to-display string like "Ternaten–Bacan War" or
    "2nd Rebellion Against Niuwu".
    """
    if not isinstance(war_name_raw, dict):
        return ""

    template_key = war_name_raw.get("name", "")
    template = _WAR_NAME_TEMPLATES.get(template_key, "")
    if not template:
        # Unknown template — convert the key to a readable fallback
        return template_key.replace("_WAR_NAME", "").replace("_NAME", "").replace("_", " ").title() + " War"

    ordinal = war_name_raw.get("ordinal", 1)
    num_str, order_str = _ordinal(ordinal)

    bases = war_name_raw.get("bases", {})
    if not isinstance(bases, dict):
        bases = {}

    firstname  = _resolve_base_adj(bases.get("First",  {}), loc)
    secondname = _resolve_base_adj(bases.get("Second", {}), loc)

    result = template
    result = result.replace("$NUM$",        num_str)
    result = result.replace("$ORDER$",      order_str)
    result = result.replace("$FIRSTNAME$",  firstname)
    result = result.replace("$SECONDNAME$", secondname)

    # Collapse any double spaces left by empty substitutions, then strip
    result = re.sub(r"  +", " ", result).strip()
    return result


def display_name(loc: dict[str, str], key: str, fallback: str | None = None) -> str:
    """
    Look up a display name, trying the key as-is and then with common suffixes removed.
    Returns fallback (or the raw key) if not found.
    """
    if key in loc:
        return loc[key]
    # Try stripping _culture / _religion / _group suffixes common in EU5
    for suffix in ("_culture", "_religion", "_group", "_language"):
        stripped = key.removesuffix(suffix)
        if stripped in loc:
            return loc[stripped]
    return fallback if fallback is not None else key


if __name__ == "__main__":
    import sys
    loc_path = sys.argv[1] if len(sys.argv) > 1 else "game-data/eu5/localization/english"
    loc = load_localisation(loc_path)
    print(f"Loaded {len(loc):,} localisation entries")
    # Quick smoke test
    for test_key in ["WUR", "SWE", "DAN", "catholic", "swedish", "danish", "age_3_discovery"]:
        print(f"  {test_key!r:30s} -> {display_name(loc, test_key)!r}")
