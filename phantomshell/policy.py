"""Backend-owned allowlist and action logging."""

from __future__ import annotations

import hashlib
import json

from phantomshell.store import Store, new_id, utc_now

POLICY = {
    "inspect_project_tree": ("read", True), "read_file_within_project": ("read", True),
    "search_project_files": ("read", True), "get_git_status": ("read", True),
    "get_recent_commits": ("read", True), "git_log_for_path": ("read", True),
}


def log_action(store: Store, tool: str, args: dict, decision: str, reason: str = "", output: str = "") -> str:
    action_id = new_id("act")
    store.connection.execute(
        "INSERT INTO action_log VALUES(?,?,?,?,?,?,?)",
        (action_id, utc_now(), tool, json.dumps(args, sort_keys=True), decision, reason,
         hashlib.sha256(output.encode()).hexdigest() if output else None),
    )
    store.connection.commit()
    return action_id


def authorize(store: Store, tool: str, args: dict, approved: bool) -> bool:
    if tool not in POLICY:
        log_action(store, tool, args, "blocked", "tool is not allowlisted")
        return False
    if not approved:
        log_action(store, tool, args, "proposed", "awaiting explicit user approval")
        return False
    log_action(store, tool, args, "approved")
    return True
