"""
schema_dump.py — Dump the full key schema of an EU5 save to JSON

Produces a compact tree of keys with their types and sample values
(no large lists or full data — just structure). Useful for documentation
and understanding what's in a save without scrolling through raw JSON.

Usage:
    python -m toolbox.schema_dump <save_file> [--out schema.json] [--depth 4]
    python -m toolbox.schema_dump <save_file> --section countries.database.2186
"""

import json
import argparse
import sys
from pathlib import Path
from typing import Any


def _schema_node(val: Any, depth: int, max_depth: int) -> Any:
    """Recursively build a schema node."""
    if depth >= max_depth:
        return _leaf(val)

    if isinstance(val, dict):
        if not val:
            return {"_type": "dict", "_size": 0}
        schema = {"_type": "dict", "_size": len(val)}
        for k, v in val.items():
            schema[k] = _schema_node(v, depth + 1, max_depth)
        return schema

    if isinstance(val, list):
        if not val:
            return {"_type": "list", "_size": 0}
        # Sample first element only
        sample = _schema_node(val[0], depth + 1, max_depth)
        return {"_type": "list", "_size": len(val), "_sample": sample}

    return _leaf(val)


def _leaf(val: Any) -> dict:
    if isinstance(val, bool):
        return {"_type": "bool", "_value": val}
    if isinstance(val, int):
        return {"_type": "int", "_value": val}
    if isinstance(val, float):
        return {"_type": "float", "_value": round(val, 4)}
    if isinstance(val, str):
        preview = val[:80] + ("…" if len(val) > 80 else "")
        return {"_type": "str", "_value": preview}
    return {"_type": type(val).__name__}


def navigate_path(data: dict, dotpath: str) -> Any:
    """Navigate a dot-separated path like 'countries.database.2186'"""
    node = data
    for part in dotpath.split("."):
        if isinstance(node, dict):
            if part in node:
                node = node[part]
            elif part.lstrip("-").isdigit():
                node = node.get(int(part)) or node.get(part)
            else:
                raise KeyError(f"Key {part!r} not found")
        elif isinstance(node, list):
            node = node[int(part)]
        else:
            raise KeyError(f"Cannot navigate into {type(node).__name__} at {part!r}")
    return node


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump EU5 save schema to JSON")
    parser.add_argument("save", help="Path to .eu5 save file")
    parser.add_argument("--rakaly", default="bin/rakaly/rakaly")
    parser.add_argument("--out", default=None, help="Output JSON file (default: stdout)")
    parser.add_argument("--depth", type=int, default=4, help="Max tree depth (default 4)")
    parser.add_argument("--section", default=None,
                        help="Dot-path to a specific section e.g. countries.database.2186")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print output")
    args = parser.parse_args()

    from toolbox.save_loader import load_save
    print("Loading save…", file=sys.stderr)
    save = load_save(args.save, rakaly_bin=args.rakaly, verbose=True)

    data = save.raw
    if args.section:
        print(f"Navigating to: {args.section}", file=sys.stderr)
        data = navigate_path(data, args.section)

    print(f"Building schema (depth={args.depth})…", file=sys.stderr)
    schema = _schema_node(data, 0, args.depth)

    indent = 2 if args.pretty else None
    output = json.dumps(schema, indent=indent, ensure_ascii=False)

    if args.out:
        Path(args.out).write_text(output, encoding="utf-8")
        print(f"Schema written to {args.out}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
