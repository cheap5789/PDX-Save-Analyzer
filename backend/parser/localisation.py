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
            # Skip entries with scripted values (contain $ or [ — these are templates)
            if "$" not in value and "[" not in value:
                out[key] = value


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
