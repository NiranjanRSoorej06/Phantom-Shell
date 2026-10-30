"""Sanitize captured terminal data before it is stored or shown."""

from __future__ import annotations

import hashlib
import re

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07]*\x07")
_REDACTIONS: tuple[tuple[str, re.Pattern[str], str], ...] = (
    ("aws_key", re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED:aws_key]"),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), "[REDACTED:github_token]"),
    (
        "private_key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
        "[REDACTED:private_key]",
    ),
    (
        "jwt",
        re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
        "[REDACTED:jwt]",
    ),
    (
        "assignment",
        re.compile(r"(?i)\b(api[_-]?key|secret|token|passw(or)?d|authorization)\b\s*[=:]\s*\S+"),
        r"\1=[REDACTED]",
    ),
    ("url_credentials", re.compile(r"://[^/\s:@]+:[^/\s@]+@"), "://[REDACTED]@"),
    ("bearer", re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{10,}"), "Bearer [REDACTED]"),
)
_ERR = re.compile(
    r"(error|failed|cannot|can't|could not|not found|no such|traceback|exception|refused|denied|EADDRINUSE)",
    re.IGNORECASE,
)
_PATH = re.compile(r"(?:[a-z]:)?[\w.\-~@+]*(?:[/\\][\w.\-~@+]+)+", re.IGNORECASE)


def strip_ansi(text: str) -> str:
    """Remove ANSI control sequences and OSC terminal metadata."""
    return ANSI_RE.sub("", text)


def redact(text: str) -> tuple[str, int]:
    """Redact known credential formats and return the replacement count."""
    count = 0
    for _name, pattern, replacement in _REDACTIONS:
        text, hits = pattern.subn(replacement, text)
        count += hits
    return text, count


def truncate_excerpt(text: str, limit: int = 16_384, max_lines: int = 40) -> str:
    """Bound event payloads and keep useful leading and trailing context."""
    lines = text.splitlines()
    if len(lines) > max_lines:
        omitted = len(lines) - 40
        text = "\n".join([*lines[:15], f"…[{omitted} lines omitted]…", *lines[-25:]])
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text
    marker = b"\n...[output truncated]...\n"
    budget = max(0, limit - len(marker))
    head = encoded[: budget // 2].decode("utf-8", "ignore")
    tail = encoded[-(budget - budget // 2) :].decode("utf-8", "ignore")
    return f"{head}{marker.decode()}{tail}"


def sanitize(text: str, *, limit: int = 16_384) -> tuple[str, int]:
    """Apply the required ingest order: ANSI removal, redaction, then truncation."""
    clean, count = redact(strip_ansi(text))
    return truncate_excerpt(clean, limit), count


def normalize(line: str) -> str:
    value = line.lower().strip()
    value = _PATH.sub("<path>", value)
    value = re.sub(r"0x[0-9a-f]+|\b[0-9a-f]{7,40}\b", "<hex>", value)
    value = re.sub(r"\b\d+(?:\.\d+)*\b", "<n>", value)
    return re.sub(r"\s+", " ", value)[:200]


def fingerprint(command: str, output: str) -> str:
    """Hash a normalized error line and the command family."""
    lines = [line for line in output.splitlines() if line.strip()]
    key = next((line for line in lines if _ERR.search(line)), lines[-1] if lines else "")
    family = " ".join(command.split()[:2])
    return hashlib.sha256(f"{family}|{normalize(key)}".encode()).hexdigest()[:16]


def prepare_event(command: str, output: bytes | str) -> tuple[str, str, int, str]:
    """Sanitize command and output; return command, excerpt, redaction count, fingerprint."""
    raw_output = output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output
    safe_command, command_hits = redact(strip_ansi(command))
    excerpt, output_hits = sanitize(raw_output)
    return safe_command, excerpt, command_hits + output_hits, fingerprint(safe_command, excerpt)
