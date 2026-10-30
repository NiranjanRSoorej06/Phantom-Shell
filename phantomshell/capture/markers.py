"""Incremental parser for PhantomShell OSC command markers."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass

_START = b"\x1b]777;phantom;start\x07"
_END = re.compile(rb"\x1b\]777;phantom;end;(\d+);([A-Za-z0-9+/=]*);([A-Za-z0-9+/=]*)\x07")
_ALT_ON = (b"\x1b[?1049h", b"\x1b[?47h", b"\x1b[?1047h")
_ALT_OFF = (b"\x1b[?1049l", b"\x1b[?47l", b"\x1b[?1047l")


@dataclass(frozen=True)
class CompletedCommand:
    command: str
    cwd: str
    exit_code: int
    output: str
    note: str | None = None


class MarkerParser:
    """Strip OSC markers from terminal bytes and emit bounded command events."""

    def __init__(self) -> None:
        self.pending = b""
        self.active = False
        self.command = ""
        self.cwd = ""
        self.output = bytearray()
        self.total = 0
        self.alt_screen = False
        self.alt_seen = False

    def _append(self, data: bytes) -> None:
        for on in _ALT_ON:
            if on in data:
                self.alt_screen = True
                self.alt_seen = True
        for off in _ALT_OFF:
            if off in data:
                self.alt_screen = False
        if self.active and not self.alt_screen:
            self.total += len(data)
            if len(self.output) < 8192:
                self.output.extend(data[: 8192 - len(self.output)])
            # Keep the last 8 KiB while retaining first 8 KiB.
            if self.total > 8192:
                tail = (bytes(self.output[8192:]) + data)[-8192:]
                self.output = self.output[:8192] + bytearray(tail)

    def feed(self, chunk: bytes) -> tuple[bytes, list[CompletedCommand]]:
        data = self.pending + chunk
        self.pending = b""
        visible = bytearray()
        events: list[CompletedCommand] = []
        cursor = 0
        while cursor < len(data):
            start = data.find(_START, cursor)
            end_match = _END.search(data, cursor)
            candidates = [(p, kind) for p, kind in ((start, "start"), (end_match.start() if end_match else -1, "end")) if p >= 0]
            if not candidates:
                keep = min(4096, max(len(_START), 128))
                safe_end = max(cursor, len(data) - keep)
                visible.extend(data[cursor:safe_end])
                self._append(data[cursor:safe_end])
                self.pending = data[safe_end:]
                break
            pos, kind = min(candidates)
            visible.extend(data[cursor:pos])
            self._append(data[cursor:pos])
            cursor = pos
            if kind == "start":
                cursor += len(_START)
                self.active = True
                self.command = ""
                self.cwd = ""
                self.output.clear()
                self.total = 0
                self.alt_screen = False
                self.alt_seen = False
                continue
            assert end_match is not None
            if self.active:
                try:
                    cwd = base64.b64decode(end_match.group(2)).decode("utf-8", "replace")
                    command = base64.b64decode(end_match.group(3)).decode("utf-8", "replace")
                    code = int(end_match.group(1))
                except (ValueError, UnicodeError):
                    cursor = end_match.end()
                    self.active = False
                    continue
                raw = bytes(self.output)
                if len(raw) > 8192:
                    raw = raw[:8192] + raw[-8192:]
                excerpt = raw.decode("utf-8", "replace")
                lines = excerpt.splitlines()
                if len(lines) > 40:
                    excerpt = "\n".join([*lines[:15], f"…[{len(lines)-40} lines omitted]…", *lines[-25:]])
                events.append(CompletedCommand(command, cwd, code, "" if self.alt_seen else excerpt, "alt_screen" if self.alt_seen else None))
                self.active = False
                self.output.clear()
                self.total = 0
                self.alt_seen = False
            cursor = end_match.end()
        return bytes(visible), events


def marker_start() -> str:
    return "\\e]777;phantom;start\\a"
