"""Run an interactive Bash process through a local pseudo-terminal."""

from __future__ import annotations

import fcntl
import os
import pty
import re
import select
import signal
import subprocess
import sys
import termios
import tty
from collections.abc import Callable
from pathlib import Path

from phantomshell.capture.markers import MarkerParser


def check_bash_version() -> tuple[int, ...]:
    env = dict(os.environ)
    env.pop("BASH_ENV", None)
    result = subprocess.run(["bash", "--noprofile", "--norc", "-c", "printf '%s' \"$BASH_VERSION\""],
                            env=env, capture_output=True, text=True, timeout=3, check=True)
    match = re.match(r"(\d+(?:\.\d+)+)", result.stdout)
    if not match:
        raise RuntimeError("could not determine Bash version")
    version = tuple(int(part) for part in match.group(1).split("."))
    if version < (4, 4):
        raise RuntimeError("PhantomShell interactive capture requires Bash 4.4 or later")
    return version


def run_shell(on_event: Callable[[object], None] | None = None) -> int:
    """Run wrapped Bash in the current terminal, forwarding events to callback."""
    check_bash_version()
    pid, master = pty.fork()
    if pid == 0:
        hook = Path(__file__).with_name("hooks.sh")
        os.execlp("bash", "bash", "--rcfile", str(hook), "-i")
    parser = MarkerParser()
    old_attrs = None
    old_winch = signal.getsignal(signal.SIGWINCH)

    def resize(_sig: int, _frame: object) -> None:
        try:
            size = fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, b"\0" * 8)
            fcntl.ioctl(master, termios.TIOCSWINSZ, size)
        except OSError:
            pass

    try:
        if sys.stdin.isatty():
            old_attrs = termios.tcgetattr(sys.stdin.fileno())
            tty.setraw(sys.stdin.fileno())
            resize(signal.SIGWINCH, None)
            signal.signal(signal.SIGWINCH, resize)
        while True:
            ready, _, _ = select.select([sys.stdin, master], [], [], 0.1)
            if sys.stdin in ready:
                data = os.read(sys.stdin.fileno(), 4096)
                if data:
                    os.write(master, data)
            if master in ready:
                try:
                    data = os.read(master, 4096)
                except OSError:
                    break
                if not data:
                    break
                visible, events = parser.feed(data)
                if visible:
                    os.write(sys.stdout.fileno(), visible)
                if on_event:
                    for event in events:
                        on_event(event)
            done, status = os.waitpid(pid, os.WNOHANG)
            if done:
                return os.waitstatus_to_exitcode(status)
    finally:
        if old_attrs is not None:
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_attrs)
        signal.signal(signal.SIGWINCH, old_winch)
        os.close(master)
    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)
