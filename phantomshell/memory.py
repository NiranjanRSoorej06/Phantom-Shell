"""Fingerprint recall and file-hash based staleness checks."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from phantomshell.store import Store, new_id, utc_now


def file_hash(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def check_staleness(root: str | Path, watched: list[dict[str, str]]) -> tuple[str, list[str]]:
    if not watched:
        return "not checked", []
    base = Path(root).resolve()
    changed = []
    for item in watched:
        candidate = (base / item["path"]).resolve()
        if not candidate.is_relative_to(base) or file_hash(candidate) != item["sha256"]:
            changed.append(item["path"])
    return ("changed since" if changed else "same conditions", changed)


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", value.lower()))


class Memory:
    def __init__(self, store: Store):
        self.store = store

    def propose(self, fingerprint: str, command_family: str, summary: str, cause: str,
                next_steps: list[str], source_episode: str, watched: list[dict[str, str]], git_head: str = "") -> str:
        memory_id = new_id("mem")
        self.store.connection.execute(
            "INSERT INTO memories(id,fingerprint,command_family,summary,cause,next_steps,status,source_episode,watched,git_head,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (memory_id, fingerprint, command_family, summary, cause, json.dumps(next_steps), "proposed",
             source_episode, json.dumps(watched), git_head, utc_now()),
        )
        self.store.connection.commit()
        return memory_id

    def promote_on_resolution(self, episode_id: str) -> None:
        self.store.connection.execute("UPDATE memories SET status='verified' WHERE source_episode=? AND status='proposed'", (episode_id,))
        self.store.connection.commit()

    def recall(self, fingerprint: str, command_family: str, root: str | Path, limit: int = 3) -> list[dict]:
        rows = [dict(row) for row in self.store.connection.execute(
            "SELECT * FROM memories WHERE status IN ('verified','proposed','stale') ORDER BY CASE status WHEN 'verified' THEN 0 ELSE 1 END, created_at DESC")]
        matches = []
        query_tokens = _tokens(command_family)
        for row in rows:
            score = 1.0 if row["fingerprint"] == fingerprint else 0.0
            if not score and row["command_family"] == command_family:
                tokens = _tokens(row["command_family"])
                score = len(tokens & query_tokens) / max(1, len(tokens | query_tokens))
            if score >= 0.6:
                status, changed = check_staleness(root, json.loads(row["watched"] or "[]"))
                row["recall_status"] = status
                row["changed_paths"] = changed
                row["last_checked_at"] = utc_now()
                self.store.connection.execute("UPDATE memories SET last_checked_at=? WHERE id=?", (row["last_checked_at"], row["id"]))
                if changed:
                    self.store.connection.execute("UPDATE memories SET status='stale' WHERE id=?", (row["id"],))
                matches.append(row)
                if len(matches) >= limit:
                    break
        self.store.connection.commit()
        return matches

    def delete(self, memory_id: str) -> bool:
        cursor = self.store.connection.execute("DELETE FROM memories WHERE id=?", (memory_id,))
        self.store.connection.commit()
        return cursor.rowcount > 0

    def clear(self) -> None:
        self.store.connection.execute("DELETE FROM memories")
        self.store.connection.commit()
