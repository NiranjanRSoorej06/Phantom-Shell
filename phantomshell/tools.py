"""Allowlisted read-only project tools with path and subprocess hardening."""

from __future__ import annotations

import fnmatch
import hashlib
import os
import subprocess
from pathlib import Path

from phantomshell.ingest import sanitize

DENY = (".env*", "*.pem", "*.key", "id_rsa*", "id_ed25519*", "*.p12", ".netrc", "credentials*", "*secret*", ".git/config")
IGNORED_DIRS = {".git", "node_modules", ".venv", "__pycache__"}


class ToolBlocked(ValueError):
    pass


def safe_env() -> dict[str, str]:
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": "/nonexistent", "LANG": "C",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0", "GIT_PAGER": "cat", "GIT_CONFIG_COUNT": "0"}


def run_safe(argv: list[str], cwd: str | Path, timeout: int = 5, cap: int = 8192) -> str:
    result = subprocess.run(argv, cwd=cwd, env=safe_env(), capture_output=True, timeout=timeout, shell=False, check=False)
    return (result.stdout[:cap] + result.stderr[:1024]).decode("utf-8", "replace")


def within_project(root: str | Path, path: str) -> Path:
    base = Path(root).resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = base / candidate
    resolved = candidate.resolve()
    if resolved == base or not resolved.is_relative_to(base):
        raise ToolBlocked("path escapes project root")
    relative = resolved.relative_to(base).as_posix()
    if any(fnmatch.fnmatch(Path(relative).name, pattern) or fnmatch.fnmatch(relative, pattern) for pattern in DENY):
        raise ToolBlocked("sensitive path is blocked")
    if relative.startswith(".git/hooks/"):
        raise ToolBlocked("git hooks are blocked")
    return resolved


def inspect_project_tree(root: str | Path, path: str = ".", depth: int = 3) -> str:
    if not 0 <= depth <= 3:
        raise ToolBlocked("depth must be at most 3")
    start = Path(root).resolve() if path == "." else within_project(root, path)
    base = Path(root).resolve()
    entries: list[str] = []
    for current, dirs, files in os.walk(start, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in IGNORED_DIRS)
        level = len(Path(current).relative_to(start).parts)
        dirs[:] = dirs if level < depth else []
        for name in sorted([*dirs, *files]):
            candidate = Path(current) / name
            try:
                if candidate.resolve().is_relative_to(base):
                    entries.append(candidate.relative_to(base).as_posix())
            except OSError:
                continue
            if len(entries) >= 200:
                return "\n".join(entries)
    return "\n".join(entries)


def read_file_within_project(root: str | Path, path: str, max_bytes: int = 20_000) -> tuple[str, dict[str, str]]:
    if not 0 < max_bytes <= 20_000:
        raise ToolBlocked("max_bytes must be between 1 and 20000")
    target = within_project(root, path)
    with target.open("rb") as stream:
        prefix = stream.read(1024)
        if b"\0" in prefix:
            raise ToolBlocked("binary files are blocked")
        stream.seek(0)
        raw = stream.read(max_bytes)
    if b"\0" in raw[:1024]:
        raise ToolBlocked("binary files are blocked")
    content, _count = sanitize(raw[:max_bytes].decode("utf-8", "replace"), limit=max_bytes)
    digest = hashlib.sha256()
    with target.open("rb") as stream:
        for chunk in iter(lambda: stream.read(64 * 1024), b""):
            digest.update(chunk)
    watched = {target.relative_to(Path(root).resolve()).as_posix(): digest.hexdigest()}
    return content, watched


def search_project_files(root: str | Path, pattern: str, glob: str | None = None) -> str:
    if not pattern or len(pattern) > 200:
        raise ToolBlocked("pattern must contain 1 to 200 characters")
    argv = ["rg", "--no-config", "--fixed-strings", "--max-count", "5", "--no-follow", "--max-columns", "300", "-n", pattern]
    for denied in ("!.env*", "!**/.env*", "!**/*.pem", "!**/*.key", "!**/*secret*", "!**/credentials*", "!**/.netrc", "!**/.git/**"):
        argv.extend(["--glob", denied])
    if glob:
        argv.extend(["--glob", glob])
    argv.append(".")
    return run_safe(argv, root, cap=8192)


def git_status(root: str | Path) -> str:
    return run_safe(["git", "--no-pager", "-c", "core.fsmonitor=false", "-c", "core.pager=cat", "-c", "core.hooksPath=/dev/null", "status", "--porcelain=v1"], root, cap=4096)


def recent_commits(root: str | Path, n: int = 5) -> str:
    if not 1 <= n <= 10:
        raise ToolBlocked("n must be between 1 and 10")
    return run_safe(["git", "--no-pager", "-c", "core.fsmonitor=false", "-c", "core.pager=cat", "-c", "core.hooksPath=/dev/null", "log", "-M", f"-{n}", "--stat", "--oneline"], root, cap=8192)
