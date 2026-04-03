"""
explore.py — Interactive EU5 save browser

Loads a save file and lets you navigate its JSON structure interactively,
with resolved culture/religion/country names wherever possible.

Usage:
    python -m toolbox.explore <save_file> [--rakaly bin/rakaly/rakaly] [--loc game-data/eu5/localization/english]

Commands inside the browser:
    .                  Show current object (keys + types)
    ..                 Go up one level
    <key>              Descend into key (works for dicts and list indices)
    /path/to/key       Jump to absolute path
    find <term>        Search all keys at current level for term
    info               Show session metadata summary
    q / quit           Exit
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Any


def _type_label(v: Any) -> str:
    if isinstance(v, dict):
        return f"dict  ({len(v)} keys)"
    if isinstance(v, list):
        sample = type(v[0]).__name__ if v else "empty"
        return f"list  ({len(v)} × {sample})"
    if isinstance(v, bool):
        return f"bool  {v}"
    if isinstance(v, int):
        return f"int   {v}"
    if isinstance(v, float):
        return f"float {v:.4g}"
    s = str(v)
    preview = s[:60] + ("…" if len(s) > 60 else "")
    return f"str   {preview!r}"


def _resolve_label(save, key: str, val: Any) -> str:
    """Add a resolved name hint for known numeric ID fields."""
    if not hasattr(save, "resolve_culture"):
        return ""
    hints = {
        "primary_culture": lambda v: f"  → {save.resolve_culture_name(v)!r}",
        "primary_religion": lambda v: f"  → {save.resolve_religion_name(v)!r}",
    }
    if key in hints and isinstance(val, int):
        try:
            return hints[key](val)
        except Exception:
            pass
    return ""


def _show_node(save, node: Any, path: list[str], max_items: int = 40) -> None:
    """Pretty-print a node's contents."""
    print(f"\n📍 /{'/'.join(path)}")
    print("─" * 60)

    if isinstance(node, dict):
        items = list(node.items())
        for i, (k, v) in enumerate(items[:max_items]):
            hint = _resolve_label(save, k, v)
            print(f"  {k:<40s}  {_type_label(v)}{hint}")
        if len(items) > max_items:
            print(f"  … ({len(items) - max_items} more keys — use 'find' to search)")

    elif isinstance(node, list):
        for i, v in enumerate(node[:max_items]):
            print(f"  [{i}]  {_type_label(v)}")
        if len(node) > max_items:
            print(f"  … ({len(node) - max_items} more items)")

    else:
        print(f"  {_type_label(node)}")

    print()


def _navigate(root: Any, path_parts: list[str]) -> tuple[Any, bool]:
    """Navigate to a path. Returns (node, success)."""
    node = root
    for part in path_parts:
        if isinstance(node, dict):
            if part not in node:
                # Try numeric key
                if part.lstrip("-").isdigit() and int(part) in node:
                    node = node[int(part)]
                else:
                    return None, False
            else:
                node = node[part]
        elif isinstance(node, list):
            try:
                node = node[int(part)]
            except (ValueError, IndexError):
                return None, False
        else:
            return None, False
    return node, True


def _show_info(save) -> None:
    """Print save session summary."""
    print("\n" + "═" * 60)
    print("  EU5 SAVE SUMMARY")
    print("═" * 60)
    print(f"  Date        : {save.game_date}")
    print(f"  Version     : {save.game_version}")
    print(f"  Multiplayer : {save.is_multiplayer}")
    print(f"  Player      : {save.player_name}")
    print(f"  Country     : {save.player_country_name} ({save.player_country_tag})")
    print(f"  Age         : {save.current_age_name} ({save.current_age_key})")
    print()
    # Player country stats
    cd = save.player_country_data()
    currency = cd.get("currency_data", {})
    if currency:
        print("  Country resources (currency_data):")
        for k, v in currency.items():
            print(f"    {k:<25s} {v}")
    print()
    real_countries = save.all_real_countries()
    print(f"  Total real countries: {len(real_countries)}")
    print("═" * 60 + "\n")


def browse(save, raw: dict) -> None:
    """Main interactive loop."""
    stack: list[tuple[list[str], Any]] = [  # (path, node)
        ([], raw)
    ]
    current_path, current_node = stack[-1]

    _show_info(save)
    _show_node(save, current_node, current_path)

    while True:
        try:
            cmd = input("explore> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not cmd:
            continue

        if cmd in ("q", "quit", "exit"):
            print("Bye.")
            break

        if cmd == "info":
            _show_info(save)
            continue

        if cmd == ".":
            _show_node(save, current_node, current_path)
            continue

        if cmd == "..":
            if len(stack) > 1:
                stack.pop()
                current_path, current_node = stack[-1]
                _show_node(save, current_node, current_path)
            else:
                print("Already at root.")
            continue

        if cmd.startswith("find "):
            term = cmd[5:].lower()
            if isinstance(current_node, dict):
                matches = [(k, v) for k, v in current_node.items() if term in k.lower()]
                if matches:
                    print(f"\nMatches for {term!r}:")
                    for k, v in matches[:30]:
                        print(f"  {k:<40s}  {_type_label(v)}")
                else:
                    print(f"No keys matching {term!r} at this level.")
            else:
                print("find only works inside a dict node.")
            continue

        # Absolute path navigation
        if cmd.startswith("/"):
            parts = [p for p in cmd.split("/") if p]
            node, ok = _navigate(raw, parts)
            if ok:
                stack = [([], raw), (parts, node)]
                current_path, current_node = parts, node
                _show_node(save, current_node, current_path)
            else:
                print(f"Path not found: {cmd}")
            continue

        # Relative navigation — single key or index
        node, ok = _navigate(current_node, [cmd])
        if ok:
            new_path = current_path + [cmd]
            stack.append((new_path, node))
            current_path, current_node = stack[-1]
            _show_node(save, current_node, current_path)
        else:
            # Show available keys if dict
            if isinstance(current_node, dict):
                close = [k for k in current_node if cmd.lower() in k.lower()]
                if close:
                    print(f"Key {cmd!r} not found. Did you mean: {close[:5]}")
                else:
                    print(f"Key {cmd!r} not found here.")
            else:
                print(f"Cannot navigate into {type(current_node).__name__} with key {cmd!r}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive EU5 save file browser")
    parser.add_argument("save", help="Path to .eu5 save file")
    parser.add_argument("--rakaly", default="bin/rakaly/rakaly", help="Path to rakaly binary")
    parser.add_argument("--loc", default="game-data/eu5/localization/english",
                        help="Path to localisation directory")
    parser.add_argument("--no-loc", action="store_true", help="Skip loading localisation")
    args = parser.parse_args()

    from toolbox.save_loader import load_save
    print(f"Loading {args.save}…")
    save = load_save(
        args.save,
        rakaly_bin=args.rakaly,
        loc_dir=None if args.no_loc else args.loc,
        verbose=True,
    )
    print("Ready.\n")
    browse(save, save.raw)


if __name__ == "__main__":
    main()
