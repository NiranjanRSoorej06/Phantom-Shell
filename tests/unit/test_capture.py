import base64

from phantomshell.capture.markers import MarkerParser
from phantomshell.capture.pty_session import check_bash_version


def _end(code: int, cwd: str, command: str) -> bytes:
    b64 = lambda value: base64.b64encode(value.encode()).decode()
    return f"\x1b]777;phantom;end;{code};{b64(cwd)};{b64(command)}\x07".encode()


def test_markers_roundtrip_split_and_orphan_end() -> None:
    parser = MarkerParser()
    _orphan_visible, orphan_events = parser.feed(_end(0, "/tmp", "ignored"))
    assert orphan_events == []
    marker = b"\x1b]777;phantom;start\x07"
    visible, events = parser.feed(b"before" + marker[:10])
    assert visible == b""
    assert events == []
    visible, events = parser.feed(marker[10:] + b"hello\n" + _end(1, "/tmp", "false"))
    assert b"phantom" not in visible
    assert events[0].command == "false"
    assert events[0].exit_code == 1
    assert "hello" in events[0].output


def test_alt_screen_skipped() -> None:
    parser = MarkerParser()
    start = b"\x1b]777;phantom;start\x07"
    parser.feed(start + b"before")
    parser.feed(b"\x1b[?1049hvim contents\x1b[?1049l")
    _, events = parser.feed(_end(0, "/tmp", "vim"))
    assert events[0].output == ""
    assert events[0].note == "alt_screen"


def test_supported_bash_version() -> None:
    assert check_bash_version() >= (4, 4)
