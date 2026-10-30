"""Exercise interactive capture without requiring a human terminal."""

from __future__ import annotations

import asyncio
import errno
import os
import pty
import select
import struct
import sys
import tempfile
import termios
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from phantomshell.server import create_app
from phantomshell.store import Store


def main() -> int:
    fd, path = tempfile.mkstemp(prefix="phantomshell-pty-", suffix=".sqlite3")
    os.close(fd)
    db_path = Path(path)
    root = ROOT
    pid, master = pty.fork()
    if pid == 0:
        env = dict(os.environ, PHANTOMSHELL_DB=str(db_path), PYTHONPATH=str(root))
        os.execvpe(sys.executable, [sys.executable, "-m", "phantomshell.cli", "run", "--no-model"], env)
    output = bytearray()
    try:
        time.sleep(0.6)
        os.write(master, b"echo hi\nfalse\nsleep 5\n")
        time.sleep(0.3)
        os.write(master, b"\x03")
        time.sleep(0.4)
        import fcntl

        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 40, 100, 0, 0))
        os.write(master, b"stty size\nexit\n")
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], 0.2)
            if ready:
                try:
                    chunk = os.read(master, 4096)
                except OSError as exc:
                    if exc.errno == errno.EIO:
                        break
                    raise
                if not chunk:
                    break
                output.extend(chunk)
            done, _status = os.waitpid(pid, os.WNOHANG)
            if done:
                break
        else:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
            raise AssertionError("interactive capture did not exit")
    finally:
        os.close(master)
    text = output.decode("utf-8", "replace")
    assert "phantom;start" not in text and "phantom;end" not in text
    store = Store(db_path)
    rows = store.rows("events")
    store.close()
    observed = [(row["command"], row["exit_code"], row["output_excerpt"]) for row in rows]
    expected = [("echo hi", 0, "hi\r\n"), ("false", 1, ""), ("sleep 5", 130, "^C\r\n"), ("stty size", 0, "40 100\r\n")]
    assert observed == expected, observed
    async def dashboard_events():
        app = create_app(db_path, "smoke-token", 8765)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8765") as client:
            response = await client.get("/api/events", headers={"Authorization": "Bearer smoke-token"})
            assert response.status_code == 200
            return response.json()

    served_rows = asyncio.run(dashboard_events())
    assert sorted((row["command"], row["exit_code"]) for row in served_rows) == sorted((row[0], row[1]) for row in expected)
    db_path.unlink(missing_ok=True)
    print("PTY/dashboard OK: events live through authenticated API; echo=0, false=1, Ctrl-C=130, resize=40x100, markers hidden")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
