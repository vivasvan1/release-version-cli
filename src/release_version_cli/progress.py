from __future__ import annotations

import sys
import threading
from types import TracebackType
from typing import TextIO

DOT_FRAMES = (".", "..", "...", "....", ".....", "......")


class StatusSpinner:
    def __init__(self, message: str, stream: TextIO | None = None, interval: float = 0.25) -> None:
        self.message = message
        self.stream = stream or sys.stderr
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._enabled = False

    def __enter__(self) -> StatusSpinner:
        self._enabled = bool(getattr(self.stream, "isatty", lambda: False)())
        if not self._enabled:
            return self
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if not self._enabled:
            return
        self._stop.set()
        if self._thread:
            self._thread.join()
        suffix = "failed" if exc_type else "done"
        self._write_frame(suffix)
        self.stream.write("\n")
        self.stream.flush()

    def _spin(self) -> None:
        index = 0
        while not self._stop.is_set():
            self._write_frame(DOT_FRAMES[index % len(DOT_FRAMES)])
            index += 1
            self._stop.wait(self.interval)

    def _write_frame(self, frame: str) -> None:
        self.stream.write(f"\r{self.message} {frame:<6}")
        self.stream.flush()


def status(message: str) -> StatusSpinner:
    return StatusSpinner(message)
