"""
find_key.py — Search for a key anywhere in an EU5 save

Recursively searches the entire save JSON for any key matching the search
term, printing the full path and value for each match.

Usage:
    python -m toolbox.find_key <save_file> <search_term> [--exact] [--max 50]
    python -m toolbox.find_key save.eu5 treasury
    python -m toolbox.find_key save.eu5 war_exhaustion --exact
    python -m toolbox.find_key save.eu5 gold --max 20
"""

import json
import argparse
import sys
from typing import Any, Generator


def _search(
    node: Any,
    term: str,
    exact: bool,
    path: list[str],
) -> Generator[tuple[str, Any], None, None]:
    """Recursively yield (dotpath, value) for matching keys."""
    if isinstance(node, dict):
        for k, v in node.items():
            current_path = path + [str(k)]
            key_matches = (k == term) if exact else (term.lower() in str(k).lower())
            if key_matches:
                yield ".".join(current_path), v
            # Always recurse
            yield from _search(v, term, exact, current_path)

    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _search(v, term, exact, path + [f"[{i}]"])


def _format_value(val: Any, max_len: int = 120) -> str:
    if isinstance(val, dict):
        return f"dict ({len(val)} keys): {list(val.keys())[:6]!r}…"
    if isinstance(val, list):
        return f"list ({len(val)} items)"
    s = str(val)
    return s[:max_len] + ("…" if len(s) > max_len else "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Find a key anywhere in an EU5 save")
    parser.add_argument("save", help="Path to .eu5 save file")
    parser.add_argument("term", help="Key name to search for")
    parser.add_argument("--rakaly", default="bin/rakaly/rakaly")
    parser.add_argument("--exact", action="store_true",
                        help="Exact match only (default: substring match)")
    parser.add_argument("--max", type=int, default=50,
                        help="Max results to show (default 50)")
    parser.add_argument("--no-recurse-lists", action="store_true",
                        help="Skip searching inside large lists (faster for big saves)")
    args = parser.parse_args()

    from toolbox.save_loader import load_save
    print(f"Loading save and searching for {args.term!r}…", file=sys.stderr)
    save = load_save(args.save, rakaly_bin=args.rakaly, verbose=False)

    count = 0
    for path, val in _search(save.raw, args.term, args.exact, []):
        print(f"  {path}")
        print(f"    = {_format_value(val)}")
        count += 1
        if count >= args.max:
            print(f"\n… stopped at {args.max} results. Use --max to increase limit.")
            break

    if count == 0:
        print(f"No keys matching {args.term!r} found.")
    else:
        print(f"\n{count} result(s) found.")


if __name__ == "__main__":
    main()
