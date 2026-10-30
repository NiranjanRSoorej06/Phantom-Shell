"""Plan, user-approved checks, verified conclusions, and memory proposals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from phantomshell.brain import OllamaBrain
from phantomshell.ingest import sanitize
from phantomshell.memory import Memory
from phantomshell.policy import POLICY, log_action
from phantomshell.store import Store
from phantomshell.tools import (
    ToolBlocked,
    git_status,
    inspect_project_tree,
    read_file_within_project,
    recent_commits,
    run_safe,
    search_project_files,
    within_project,
)
from phantomshell.verify import verify_conclusion


def _cap_text(value: str, limit: int) -> str:
    return value.encode("utf-8")[:limit].decode("utf-8", "ignore")


def _validate_tool_args(tool: str, args: dict[str, Any]) -> None:
    allowed = {
        "inspect_project_tree": {"path", "depth"}, "read_file_within_project": {"path", "max_bytes"},
        "search_project_files": {"pattern", "glob"}, "get_git_status": set(),
        "get_recent_commits": {"n", "stat"}, "git_log_for_path": {"path", "n"},
    }
    if tool not in POLICY or not isinstance(args, dict) or set(args) - allowed.get(tool, set()):
        raise ToolBlocked("unknown tool or argument")
    required = {"read_file_within_project": {"path"}, "search_project_files": {"pattern"}, "git_log_for_path": {"path"}}
    if not required.get(tool, set()).issubset(args):
        raise ToolBlocked("required argument missing")
    if tool == "inspect_project_tree" and not 0 <= args.get("depth", 3) <= 3:
        raise ToolBlocked("depth limit exceeded")
    if tool == "read_file_within_project" and not 1 <= args.get("max_bytes", 20000) <= 20000:
        raise ToolBlocked("file size limit exceeded")
    if tool in {"get_recent_commits", "git_log_for_path"} and not 1 <= args.get("n", 5) <= 10:
        raise ToolBlocked("commit limit exceeded")
    if tool == "search_project_files" and (not isinstance(args["pattern"], str) or not args["pattern"] or len(args["pattern"]) > 200):
        raise ToolBlocked("invalid search pattern")
    if any(not isinstance(args.get(k, default), expected) for k, expected, default in (
        ("path", str, "."), ("depth", int, 3), ("max_bytes", int, 20000), ("n", int, 5)) if k in args):
        raise ToolBlocked("invalid argument type")


def execute_tool(root: str | Path, tool: str, args: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    _validate_tool_args(tool, args)
    watched: list[dict[str, str]] = []
    if tool == "inspect_project_tree":
        output = inspect_project_tree(root, args.get("path", "."), args.get("depth", 3))
    elif tool == "read_file_within_project":
        output, hashes = read_file_within_project(root, args["path"], args.get("max_bytes", 20000))
        watched = [{"path": p, "sha256": h} for p, h in hashes.items()]
    elif tool == "search_project_files":
        output = search_project_files(root, args["pattern"], args.get("glob"))
    elif tool == "get_git_status":
        output = git_status(root)
    elif tool == "get_recent_commits":
        output = recent_commits(root, args.get("n", 5))
    else:
        target = within_project(root, args["path"])
        output = run_safe(["git", "--no-pager", "-c", "core.fsmonitor=false", "-c", "core.pager=cat", "-c", "core.hooksPath=/dev/null", "log", "-M", "--follow", f"-{args.get('n', 5)}", "--", str(target.relative_to(Path(root).resolve()))], root, cap=4096)
    sanitized, _count = sanitize(output, limit=8192)
    return sanitized, watched


def plan_episode(store: Store, episode_id: str, root: str | Path, brain: OllamaBrain | None = None) -> dict[str, Any]:
    episode = store.connection.execute("SELECT * FROM episodes WHERE id=?", (episode_id,)).fetchone()
    if not episode:
        raise ValueError("episode not found")
    events = [dict(row) for row in store.connection.execute("SELECT * FROM events WHERE episode_id=? ORDER BY ts", (episode_id,))]
    incident = []
    evidence_ids = []
    for event in events:
        content = f"command: {event['command']}\nexit_code: {event['exit_code']}\n{event['output_excerpt']}"
        evidence_id = store.add_evidence(episode_id, "event", "terminal", content)
        evidence_ids.append(evidence_id)
        incident.append({"id": evidence_id, "command": event["command"], "exit_code": event["exit_code"],
                         "output": f"<untrusted_data id=\"{evidence_id}\" source=\"terminal\">{_cap_text(content, 6000).replace('</untrusted_data>', '&lt;/untrusted_data&gt;')}</untrusted_data>"})
    recalled = Memory(store).recall(episode["fingerprint"], episode["command_family"], root)
    memories = [{"label": "POSSIBLY OUTDATED — treat only as a hypothesis", "status": item["status"], "recall_status": item["recall_status"], "changed_paths": item["changed_paths"],
                 "data": f"<untrusted_data id=\"{item['id']}\" source=\"memory\">{item['summary']} Cause hypothesis: {item['cause']}</untrusted_data>"}
                for item in recalled]
    engine = brain or OllamaBrain()
    plan = engine.plan({"style": "engineer", "incident": incident, "recalled_memories": memories, "nearby_changes": "none"}, store)
    valid_observations = []
    invalid_observations = []
    for observation in plan.get("observations", []):
        if set(observation.get("evidence_ids", [])) <= set(evidence_ids):
            valid_observations.append(observation)
        else:
            invalid_observations.append(observation)
    plan["observations"] = valid_observations
    if invalid_observations:
        plan["unverified_observations"] = invalid_observations
    store.save_investigation(episode_id, "planning", plan)
    for proposal in plan.get("requested_tools", []):
        tool, args = proposal.get("tool"), proposal.get("args", {})
        try:
            _validate_tool_args(tool, args)
        except (ToolBlocked, TypeError):
            log_action(store, tool or "unknown", args if isinstance(args, dict) else {}, "blocked", "invalid tool arguments")
            continue
        log_action(store, tool, {**args, "_episode_id": episode_id, "_why": proposal.get("why", "")}, "proposed", "awaiting user approval")
    return plan


def approve_action(store: Store, action_id: str, root: str | Path, brain: OllamaBrain | None = None) -> dict[str, Any]:
    row = store.connection.execute("SELECT * FROM action_log WHERE id=? AND decision='proposed'", (action_id,)).fetchone()
    if not row:
        raise ValueError("action is not awaiting approval")
    stored = json.loads(row["args_json"])
    episode_id = stored.pop("_episode_id", None)
    stored.pop("_why", None)
    if not episode_id or not authorize_safe(store, row["tool"], stored):
        store.connection.execute("UPDATE action_log SET decision='blocked',reason='policy or argument validation failed' WHERE id=?", (action_id,))
        store.connection.commit()
        raise ToolBlocked("tool policy blocked this action")
    store.connection.execute("UPDATE action_log SET decision='approved',reason='approved by user' WHERE id=?", (action_id,))
    store.connection.commit()
    try:
        output, watched = execute_tool(root, row["tool"], stored)
    except Exception as exc:
        store.connection.execute("UPDATE action_log SET decision='failed',reason=? WHERE id=?", (str(exc)[:300], action_id))
        store.connection.commit()
        raise
    import hashlib
    stored["_episode_id"] = episode_id
    stored["_watched"] = watched
    store.connection.execute("UPDATE action_log SET decision='executed',args_json=?,output_sha256=? WHERE id=?",
                             (json.dumps(stored, sort_keys=True), hashlib.sha256(output.encode()).hexdigest(), action_id))
    store.connection.commit()
    evidence_id = store.add_evidence(episode_id, "tool", row["tool"], output)
    result = {"action_id": action_id, "evidence_id": evidence_id, "output": output, "watched": watched}
    remaining = store.connection.execute("SELECT COUNT(*) FROM action_log WHERE decision='proposed' AND json_extract(args_json,'$._episode_id')=?", (episode_id,)).fetchone()[0]
    if remaining == 0:
        result["conclusion"] = conclude_episode(store, episode_id, root, brain)
    return result


def authorize_safe(store: Store, tool: str, args: dict[str, Any]) -> bool:
    try:
        _validate_tool_args(tool, args)
    except (ToolBlocked, TypeError):
        return False
    return tool in POLICY


def conclude_episode(store: Store, episode_id: str, root: str | Path, brain: OllamaBrain | None = None) -> dict[str, Any]:
    rows = [dict(row) for row in store.connection.execute("SELECT id,content FROM evidence WHERE episode_id=?", (episode_id,))]
    evidence = {row["id"]: row["content"] for row in rows}
    plan_row = store.connection.execute("SELECT result_json FROM investigations WHERE episode_id=? AND verdict='planning' ORDER BY created_at DESC LIMIT 1", (episode_id,)).fetchone()
    plan = json.loads(plan_row[0]) if plan_row else {}
    untrusted_evidence = {evidence_id: f"<untrusted_data id=\"{evidence_id}\">{_cap_text(content, 2800).replace('</untrusted_data>', '&lt;/untrusted_data&gt;')}</untrusted_data>"
                         for evidence_id, content in evidence.items()}
    output = (brain or OllamaBrain()).conclude({"plan": plan, "evidence": untrusted_evidence}, store)
    checked = verify_conclusion(output, evidence)
    store.save_investigation(episode_id, checked["verdict"], checked)
    if checked["verdict"] == "supported":
        episode = store.connection.execute("SELECT fingerprint,command_family FROM episodes WHERE id=?", (episode_id,)).fetchone()
        watched: dict[str, str] = {}
        for action in store.connection.execute("SELECT args_json FROM action_log WHERE decision='executed'"):
            action_data = json.loads(action[0])
            if action_data.get("_episode_id") != episode_id:
                continue
            for item in action_data.get("_watched", []):
                watched[item["path"]] = item["sha256"]
        Memory(store).propose(episode["fingerprint"], episode["command_family"], checked["cause"], checked["cause"],
                              checked.get("next_steps", []), episode_id,
                              [{"path": path, "sha256": digest} for path, digest in watched.items()])
    return checked
