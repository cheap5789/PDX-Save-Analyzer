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


# Match lines like:  KEY: "Value"
# Paradox .yml files always use double quotes as the string delimiter.
# Earlier versions of this regex accepted single quotes as a fallback and
# used a non-greedy capture, which silently truncated any value containing
# an apostrophe (e.g. "Wet'suwet'en" -> "Wet"). The current form:
#   - accepts only " as the delimiter
#   - uses a greedy capture anchored to the final " on the line
#   - tolerates optional trailing whitespace and a "# comment"
#   - accepts empty strings ""
# Keys may contain letters, digits, underscores, hyphens, dots.
_LINE_RE = re.compile(r'^\s+([\w\-\.]+):\s*"(.*)"\s*(?:#.*)?$', re.UNICODE)


def load_localisation(loc_dir: str | Path) -> dict[str, str]:
    """
    Load all .yml files in loc_dir (non-recursive, top-level only) and return
    a merged key→display-name dict. Files are processed in alphabetical order;
    later files override earlier ones for duplicate keys (shouldn't normally
    happen, but just in case).

    Scripted entries (those containing ``$VAR$`` placeholders or
    ``[scripted]`` game-concept references) are filtered out so callers can
    safely look up ``loc.get(key)`` and get a display-ready string.
    For entries that DO need scripted templates (country display name
    overrides like ``NORTHERN_YUA: "Northern $YUA$"``), use
    ``load_scripted_localisation`` instead — it walks the tree recursively
    and preserves ``$VAR$`` placeholders.
    """
    loc_dir = Path(loc_dir)
    result: dict[str, str] = {}

    yml_files = sorted(loc_dir.glob("*.yml"))
    if not yml_files:
        raise FileNotFoundError(f"No .yml files found in {loc_dir}")

    for yml_path in yml_files:
        _parse_yml(yml_path, result, mode="regular")

    return result


def load_scripted_localisation(loc_dir: str | Path) -> dict[str, str]:
    """Return a dict of localisation entries that contain ``$VAR$``
    placeholders — the ones ``load_localisation`` deliberately filters out.

    Walks ``loc_dir`` **recursively** (``rglob``) so that scripted entries
    living inside event subdirectories (e.g. ``events/DHE/flavor_chi_l_english.yml``
    where ``NORTHERN_YUA: "Northern $YUA$"`` is defined) land in the map.
    Entries containing ``[`` game-concept references are still skipped —
    those require concept resolution which we do not implement.

    Returned values still contain their ``$KEY$`` tokens; callers use
    ``resolve_scripted_value`` to substitute them against the regular loc
    dict at lookup time.

    Why a separate dict: existing callers of ``load_localisation`` rely on
    the fact that values are display-ready strings with no unresolved
    placeholders. Adding scripted entries to that dict would silently leak
    raw ``$VAR$`` strings into the UI. Keeping them in a sibling dict
    preserves that invariant while still making overrides available to
    targeted resolvers (country display names, war names, etc.).

    Overlap with the regular dict: ``$ADJ$``-only entries (e.g. war name
    templates) are present in BOTH dicts by design — the regular dict
    needs them because ``resolve_war_name`` looks them up there, and the
    scripted dict needs them because they are legitimate scripted
    templates that a country display name might also reference.
    """
    loc_dir = Path(loc_dir)
    result: dict[str, str] = {}

    if not loc_dir.exists():
        return result

    for yml_path in sorted(loc_dir.rglob("*.yml")):
        _parse_yml(yml_path, result, mode="scripted_only")

    return result


# Matches $KEY$ tokens inside a scripted loc value.
_SCRIPTED_TOKEN_RE = re.compile(r"\$([A-Za-z0-9_]+)\$")


def resolve_scripted_value(
    template: str,
    loc: dict[str, str],
    extra: dict[str, str] | None = None,
) -> str:
    """Substitute ``$KEY$`` tokens in ``template`` with values from ``loc``
    (and optional ``extra``). Unknown tokens are left in place so the
    caller can detect failed resolution.

    Example:
        ``resolve_scripted_value("Northern $YUA$", {"YUA": "Yuán"})``
        → ``"Northern Yuán"``
    """
    if not template or "$" not in template:
        return template

    def _sub(match: "re.Match[str]") -> str:
        key = match.group(1)
        if extra is not None and key in extra:
            return extra[key]
        return loc.get(key, match.group(0))

    return _SCRIPTED_TOKEN_RE.sub(_sub, template)


def _parse_yml(path: Path, out: dict[str, str], *, mode: str = "regular") -> None:
    """Parse a single localisation .yml file into ``out`` dict.

    Args:
        path: .yml file to parse.
        out:  Target dict; keys are added/overwritten in place.
        mode: One of:
              - "regular"       Keep only display-ready entries. Skip ``[``
                                concept refs; skip ``$VAR$`` entries except
                                the narrow ``$ADJ$``-only war-template case.
                                This is what ``load_localisation`` uses.
              - "scripted_only" Keep ONLY the entries ``regular`` mode
                                skips — i.e. entries containing ``$VAR$``
                                placeholders (with any variable). ``[``
                                refs are still skipped. This is what
                                ``load_scripted_localisation`` uses so the
                                two dicts are disjoint.
    """
    try:
        # EU5 .yml files use UTF-8-BOM
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="windows-1252", errors="replace")

    for line in text.splitlines():
        m = _LINE_RE.match(line)
        if m:
            key, value = m.group(1), m.group(2)
            # Always skip [game-concept] references — we don't resolve them.
            if "[" in value:
                continue
            has_any_var = "$" in value
            has_non_adj_var = "$" in value.replace("$ADJ$", "")
            if mode == "regular":
                # Keep plain entries and the narrow $ADJ$-only case used by
                # war name templates (resolve_war_name reads those directly
                # out of the regular loc dict).
                if has_non_adj_var:
                    continue
            elif mode == "scripted_only":
                # Keep every entry that has any $-placeholder at all. This
                # includes $ADJ$-only entries (which will also appear in the
                # regular dict) so that a single scripted_loc lookup can
                # resolve horde_civil_war_pretender_country and similar.
                if not has_any_var:
                    continue
            else:
                raise ValueError(f"unknown mode: {mode}")
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


# ---------------------------------------------------------------------------
# Geographic localisation loaders
# ---------------------------------------------------------------------------
#
# Geographic slugs (continent / sub_continent / region / area /
# province_definition / location) are scattered across a handful of
# files in the localization tree.  We expose a small loader that returns
# one dict per level so the rest of the codebase doesn't have to know
# the file layout.
#
#   continent / sub_continent / region   →  region_names_l_english.yml
#   area                                 →  area_l_english.yml
#   province_definition                  →  province_names_l_english.yml
#   location (canonical)                 →  location_names/location_names_l_english.yml
#
# Per-culture location overrides
# (location_names/location_names_<culture_group>_l_english.yml) are
# deferred to a later phase per agreement on 2026-04-07 and are NOT
# loaded here.

_GEO_FILE_REGION   = "region_names_l_english.yml"
_GEO_FILE_AREA     = "area_l_english.yml"
_GEO_FILE_PROVINCE = "province_names_l_english.yml"
_GEO_FILE_LOCATION = ("location_names", "location_names_l_english.yml")


def _candidate_loc_roots(loc_dir: Path) -> list[Path]:
    """Return possible roots that contain the per-domain .yml files.

    The watcher passes the language root (``.../localization/english``).
    Some installs nest the relevant files one level deeper inside
    ``main_menu/``; we accept both.
    """
    return [loc_dir, loc_dir / "main_menu"]


def _read_yml_into(path: Path, out: dict[str, str]) -> int:
    """Read a single yml file into ``out``.  Returns the number of
    keys added.  Silently returns 0 if the file does not exist."""
    if not path.exists():
        return 0
    before = len(out)
    _parse_yml(path, out)
    return len(out) - before


def load_geo_localisation(loc_dir: str | Path) -> dict[str, dict[str, str]]:
    """Return ``{level → {slug → display_name}}`` for the geographic
    levels we localise.

    Levels::

        "region_or_continent"   – region_names_l_english.yml (mixes
                                  continent / sub_continent / region)
        "area"                  – area_l_english.yml
        "province"              – province_names_l_english.yml
        "location"              – location_names/location_names_l_english.yml

    On 2026-04-07 we confirmed slugs do NOT collide between continent /
    sub_continent / region in vanilla EU5, so a single dict for those
    three levels is safe.
    """
    loc_dir = Path(loc_dir)
    result: dict[str, dict[str, str]] = {
        "region_or_continent": {},
        "area":                {},
        "province":            {},
        "location":            {},
    }

    roots = _candidate_loc_roots(loc_dir)

    def _try(filename, target_key):
        for root in roots:
            n = _read_yml_into(root / filename, result[target_key])
            if n:
                return n
        return 0

    def _try_nested(parts, target_key):
        for root in roots:
            n = _read_yml_into(root.joinpath(*parts), result[target_key])
            if n:
                return n
        return 0

    _try(_GEO_FILE_REGION,   "region_or_continent")
    _try(_GEO_FILE_AREA,     "area")
    _try(_GEO_FILE_PROVINCE, "province")
    _try_nested(_GEO_FILE_LOCATION, "location")

    return result


def fmt_geo(geo_loc: dict[str, dict[str, str]], slug: str | None) -> str:
    """Look up a geographic slug across all levels.  Returns the slug
    itself if no display name is found, or ``""`` for ``None``."""
    if not slug:
        return ""
    for level in ("location", "province", "area", "region_or_continent"):
        v = geo_loc.get(level, {}).get(slug)
        if v:
            return v
    return slug


if __name__ == "__main__":
    import sys
    loc_path = sys.argv[1] if len(sys.argv) > 1 else "game-data/eu5/localization/english"
    loc = load_localisation(loc_path)
    print(f"Loaded {len(loc):,} localisation entries")
    # Quick smoke test
    for test_key in ["WUR", "SWE", "DAN", "catholic", "swedish", "danish", "age_3_discovery"]:
        print(f"  {test_key!r:30s} -> {display_name(loc, test_key)!r}")
