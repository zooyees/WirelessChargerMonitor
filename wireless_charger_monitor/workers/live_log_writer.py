"""Background writer for live capture logs — batches writes and periodic flush."""

from __future__ import annotations

import queue
import threading
import time
from typing import Callable

_SHUTDOWN = object()


class LiveLogWriter:
    """Queue log lines on a worker thread; flush on interval or buffer size."""

    def __init__(
        self,
        flush_interval_sec: float = 0.1,
        max_buffer_bytes: int = 65536,
    ):
        self._flush_interval = flush_interval_sec
        self._max_buffer_bytes = max_buffer_bytes
        self._queue: queue.Queue[str | object] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False
        self._accept_writes = False
        self._file = None
        self._on_error: Callable[[Exception], None] | None = None
        self._error_reported = False

    @property
    def is_open(self) -> bool:
        return self._accept_writes and self._running

    def open(self, path: str, *, on_error: Callable[[Exception], None] | None = None) -> None:
        self.close()
        self._on_error = on_error
        self._error_reported = False
        self._file = open(path, 'a', encoding='utf-8-sig', newline='\n')
        self._running = True
        self._accept_writes = True
        self._thread = threading.Thread(target=self._run, name='LiveLogWriter', daemon=True)
        self._thread.start()

    def write_line(self, msg: str) -> None:
        if self._accept_writes:
            self._queue.put(msg)

    def write_lines(self, lines: list[str]) -> None:
        if not self._accept_writes or not lines:
            return
        for msg in lines:
            self._queue.put(msg)

    def close(self) -> None:
        self._accept_writes = False
        was_running = self._running
        self._running = False
        if was_running:
            self._queue.put(_SHUTDOWN)
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=5.0)
        self._thread = None
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
            self._file = None

    def _report_error(self, exc: Exception) -> None:
        if self._error_reported:
            return
        self._error_reported = True
        self._accept_writes = False
        self._running = False
        try:
            self._queue.put(_SHUTDOWN)
        except Exception:
            pass
        if self._on_error:
            self._on_error(exc)

    def _flush_buffer(self, handle, parts: list[str]) -> None:
        if not parts or handle is None:
            return
        try:
            handle.write('\n'.join(parts))
            handle.write('\n')
            handle.flush()
        except (OSError, ValueError) as exc:
            self._report_error(exc)
        finally:
            parts.clear()

    def _drain_queue(self, pending: list[str]) -> None:
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is _SHUTDOWN:
                continue
            pending.append(item)

    def _run(self) -> None:
        pending: list[str] = []
        pending_bytes = 0
        last_flush = time.monotonic()
        handle = self._file
        shutdown_seen = False

        while True:
            now = time.monotonic()
            due_flush = pending and (now - last_flush >= self._flush_interval)

            try:
                if due_flush:
                    item = self._queue.get_nowait()
                else:
                    timeout = max(0.01, self._flush_interval - (now - last_flush))
                    item = self._queue.get(timeout=timeout)
            except queue.Empty:
                if pending and (due_flush or not self._running):
                    self._flush_buffer(handle, pending)
                    pending_bytes = 0
                    last_flush = time.monotonic()
                if shutdown_seen and not pending:
                    break
                if not self._running and self._queue.empty() and not pending:
                    break
                continue

            if item is _SHUTDOWN:
                shutdown_seen = True
                self._drain_queue(pending)
                if pending:
                    self._flush_buffer(handle, pending)
                    pending_bytes = 0
                    last_flush = time.monotonic()
                if self._queue.empty() and not pending:
                    break
                continue

            pending.append(item)
            pending_bytes += len(item) + 1
            if pending_bytes >= self._max_buffer_bytes:
                self._flush_buffer(handle, pending)
                pending_bytes = 0
                last_flush = time.monotonic()

            if shutdown_seen and self._queue.empty() and not pending:
                break

        if pending:
            self._flush_buffer(handle, pending)
