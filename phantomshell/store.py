"""Small SQLite store for sanitized events and investigation state."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, project_root TEXT, started_at TEXT, ended_at TEXT, model TEXT, git_head TEXT);
CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, session_id TEXT, ts TEXT, type TEXT, command TEXT, cwd TEXT,
  exit_code INTEGER, output_excerpt TEXT, fingerprint TEXT, redactions INTEGER DEFAULT 0, note TEXT, episode_id TEXT);
CREATE TABLE IF NOT EXISTS episodes(id TEXT PRIMARY KEY, session_id TEXT, fingerprint TEXT, command_family TEXT,
  status TEXT CHECK(status IN('open','resolved','abandoned')), first_event TEXT, last_event TEXT,
  resolved_event TEXT, occurrences INTEGER DEFAULT 1, changes_between TEXT);
CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY, episode_id TEXT, kind TEXT, source TEXT, content TEXT,
  content_sha256 TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS investigations(id TEXT PRIMARY KEY, episode_id TEXT, verdict TEXT, result_json TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY, fingerprint TEXT, command_family TEXT, summary TEXT, cause TEXT,
  next_steps TEXT, status TEXT CHECK(status IN('proposed','verified','stale','archived')),
  source_episode TEXT, watched TEXT, git_head TEXT, created_at TEXT, last_checked_at TEXT);
CREATE TABLE IF NOT EXISTS action_log(id TEXT PRIMARY KEY, ts TEXT, tool TEXT, args_json TEXT,
  decision TEXT CHECK(decision IN('proposed','approved','rejected','executed','failed','blocked')),
  reason TEXT, output_sha256 TEXT);
CREATE TABLE IF NOT EXISTS model_runs(id TEXT PRIMARY KEY, ts TEXT, purpose TEXT, model TEXT, prompt_tokens INTEGER,
  output_tokens INTEGER, total_ms INTEGER, valid_schema INTEGER, error TEXT);
"""


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    """SQLite wrapper; callers only pass sanitized payloads to write methods."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def create_session(self, project_root: str, model: str | None = None) -> str:
        session_id = new_id("ses")
        self.connection.execute(
            "INSERT INTO sessions(id,project_root,started_at,model) VALUES(?,?,?,?)",
            (session_id, project_root, utc_now(), model),
        )
        self.connection.commit()
        return session_id

    def add_event(self, event: dict[str, Any]) -> None:
        fields = ("id", "session_id", "ts", "type", "command", "cwd", "exit_code", "output_excerpt", "fingerprint", "redactions", "note", "episode_id")
        self.connection.execute(
            f"INSERT INTO events({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
            tuple(event.get(field) for field in fields),
        )
        self.connection.commit()

    def add_evidence(self, episode_id: str, kind: str, source: str, content: str) -> str:
        import hashlib

        evidence_id = new_id("E")
        digest = hashlib.sha256(content.encode()).hexdigest()
        self.connection.execute(
            "INSERT INTO evidence VALUES(?,?,?,?,?,?,?)",
            (evidence_id, episode_id, kind, source, content, digest, utc_now()),
        )
        self.connection.commit()
        return evidence_id

    def rows(self, table: str) -> list[dict[str, Any]]:
        allowed = {"sessions", "events", "episodes", "evidence", "investigations", "memories", "action_log", "model_runs"}
        if table not in allowed:
            raise ValueError("unknown table")
        return [dict(row) for row in self.connection.execute(f"SELECT * FROM {table}")]

    def log_model_run(self, purpose: str, model: str, stats: dict[str, Any]) -> None:
        self.connection.execute(
            "INSERT INTO model_runs VALUES(?,?,?,?,?,?,?,?,?)",
            (new_id("run"), utc_now(), purpose, model, stats.get("prompt_eval_count"),
             stats.get("eval_count"), stats.get("total_ms"), int(bool(stats.get("valid_schema"))),
             stats.get("error")),
        )
        self.connection.commit()

    def save_investigation(self, episode_id: str, verdict: str, result: dict[str, Any]) -> str:
        investigation_id = new_id("inv")
        self.connection.execute(
            "INSERT INTO investigations VALUES(?,?,?,?,?)",
            (investigation_id, episode_id, verdict, json.dumps(result), utc_now()),
        )
        self.connection.commit()
        return investigation_id
