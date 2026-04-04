#!/usr/bin/env python3
"""
run_server.py — Start the FastAPI server

The server boots idle. The frontend (or curl) sends POST /api/start
to launch the watcher pipeline with configuration.

Usage:
    python run_server.py
    python run_server.py --port 8000 --host 0.0.0.0 --verbose

Then:
    curl -X POST http://localhost:8000/api/start \
         -H "Content-Type: application/json" \
         -d '{"game_install_path": "C:/...", "save_directory": "C:/..."}'
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="PDX Save Analyzer — API Server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    import uvicorn
    uvicorn.run(
        "backend.api.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        log_level="debug" if args.verbose else "info",
    )


if __name__ == "__main__":
    main()
