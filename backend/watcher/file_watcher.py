"""
file_watcher.py — Async file watcher with completion-marker debounce

Monitors a directory for save file changes using watchdog.
Uses a "completion marker" strategy:
  1. Detect file creation/modification via watchdog
  2. Poll the file size at short intervals
  3. Only emit the file path once the size has been stable for a
     configurable duration (default 2s) — indicating the game has
     finished writing

This avoids triggering on partially-written saves (EU5 saves are ~34MB
and take a few seconds to write).

The watcher runs in a background thread (watchdog) and exposes an
async queue that the pipeline can await.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

logger = logging.getLogger(__name__)


class _SaveHandler(FileSystemEventHandler):
    """
    Watchdog handler that tracks file sizes and notifies when a save
    file has finished being written to.
    """

    def __init__(
        self,
        extensions: list[str],
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue[Path],
        stable_seconds: float = 2.0,
        poll_interval: float = 0.5,
    ):
        super().__init__()
        self._extensions = [ext.lower() for ext in extensions]
        self._loop = loop
        self._queue = queue
        self._stable_seconds = stable_seconds
        self._poll_interval = poll_interval
        # Track files currently being written: path -> (last_size, last_change_time)
        self._pending: dict[str, tuple[int, float]] = {}
        self._polling = False

    def _is_save_file(self, path: str) -> bool:
        return any(path.lower().endswith(ext) for ext in self._extensions)

    def on_created(self, event: FileCreatedEvent) -> None:
        if not event.is_directory and self._is_save_file(event.src_path):
            self._track(event.src_path)

    def on_modified(self, event: FileModifiedEvent) -> None:
        if not event.is_directory and self._is_save_file(event.src_path):
            self._track(event.src_path)

    def _track(self, path: str) -> None:
        """Start or reset tracking for a file."""
        try:
            size = os.path.getsize(path)
        except OSError:
            return
        self._pending[path] = (size, time.monotonic())
        if not self._polling:
            self._polling = True
            # Schedule polling in the asyncio loop
            self._loop.call_soon_threadsafe(
                self._loop.create_task, self._poll_loop()
            )

    async def _poll_loop(self) -> None:
        """Poll tracked files until all are stable or gone."""
        while self._pending:
            await asyncio.sleep(self._poll_interval)
            now = time.monotonic()
            stable_paths: list[str] = []

            for path, (last_size, last_change) in list(self._pending.items()):
                try:
                    current_size = os.path.getsize(path)
                except OSError:
                    # File disappeared — stop tracking
                    del self._pending[path]
                    continue

                if current_size != last_size:
                    # Still being written — reset
                    self._pending[path] = (current_size, now)
                elif (now - last_change) >= self._stable_seconds:
                    # Stable long enough — ready
                    stable_paths.append(path)

            for path in stable_paths:
                del self._pending[path]
                logger.info(f"Save file ready: {path}")
                await self._queue.put(Path(path))

        self._polling = False


class SaveFileWatcher:
    """
    Watches a directory for save files and yields paths via an async queue
    once each file is fully written.

    Usage:
        watcher = SaveFileWatcher(save_dir, extensions=[".eu5"])
        watcher.start(loop)
        async for path in watcher:
            process(path)
        watcher.stop()
    """

    def __init__(
        self,
        watch_dir: str | Path,
        extensions: list[str],
        stable_seconds: float = 2.0,
    ):
        self.watch_dir = Path(watch_dir)
        self.extensions = extensions
        self.stable_seconds = stable_seconds
        self._queue: asyncio.Queue[Path] = asyncio.Queue()
        self._observer: Observer | None = None
        self._handler: _SaveHandler | None = None

    def start(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Start watching. Must be called from within a running event loop."""
        if loop is None:
            loop = asyncio.get_running_loop()

        self._handler = _SaveHandler(
            extensions=self.extensions,
            loop=loop,
            queue=self._queue,
            stable_seconds=self.stable_seconds,
        )
        self._observer = Observer()
        self._observer.schedule(
            self._handler,
            str(self.watch_dir),
            recursive=False,
        )
        self._observer.start()
        logger.info(f"Watching {self.watch_dir} for {self.extensions}")

    def stop(self) -> None:
        """Stop watching and clean up."""
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
        logger.info("Watcher stopped.")

    async def get_next(self, timeout: float | None = None) -> Path | None:
        """
        Wait for the next fully-written save file path.

        Returns None on timeout. Blocks indefinitely if timeout is None.
        """
        try:
            if timeout is not None:
                return await asyncio.wait_for(self._queue.get(), timeout=timeout)
            return await self._queue.get()
        except asyncio.TimeoutError:
            return None

    def __aiter__(self):
        return self

    async def __anext__(self) -> Path:
        return await self._queue.get()
