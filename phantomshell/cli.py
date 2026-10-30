"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from phantomshell.capture.pty_session import run_shell
from phantomshell.ingest import prepare_event
from phantomshell.store import Store, new_id


def _db_path() -> Path:
    return Path(os.environ.get("PHANTOMSHELL_DB", Path.home() / ".local/share/phantomshell/events.sqlite3"))


def cmd_run(args: argparse.Namespace) -> int:
    if args.command:
        # Safe non-interactive fallback: argv list, shell=False.
        import subprocess

        argv = args.command[1:] if args.command[:1] == ["--"] else args.command
        if not argv:
            raise SystemExit("run -- requires a command")
        result = subprocess.run(argv, capture_output=True, text=True, check=False)
        command, output, redactions, fp = prepare_event(" ".join(argv), result.stdout + result.stderr)
        db = _db_path()
        db.parent.mkdir(parents=True, exist_ok=True)
        store = Store(db)
        row = store.connection.execute("SELECT id FROM sessions WHERE project_root=? AND ended_at IS NULL ORDER BY started_at DESC LIMIT 1", (os.getcwd(),)).fetchone()
        session_id = row[0] if row else store.create_session(os.getcwd(), os.environ.get("PHANTOM_MODEL", "gemma4:e4b"))
        event = {"id": new_id("evt"), "session_id": session_id, "ts": datetime.now(UTC).isoformat(),
                 "type": "command_completed", "command": command, "cwd": os.getcwd(),
                 "exit_code": result.returncode, "output_excerpt": output, "fingerprint": fp,
                 "redactions": redactions, "note": None, "episode_id": None}
        store.add_event(event)
        from phantomshell.episodes import EpisodeManager
        event["episode_id"] = EpisodeManager(store).attach(event)
        if event["episode_id"] and result.returncode != 0 and not args.no_model:
            try:
                from phantomshell.brain import BrainError
                from phantomshell.investigator import plan_episode
                occurrences = store.connection.execute("SELECT occurrences FROM episodes WHERE id=?", (event["episode_id"],)).fetchone()[0]
                if occurrences <= 2:
                    plan_episode(store, event["episode_id"], os.getcwd())
            except BrainError as exc:
                print(f"PhantomShell analysis unavailable: {exc}", file=sys.stderr)
        store.close()
        print(output, end="")
        if args.json:
            print(json.dumps(event, ensure_ascii=False))
        return result.returncode

    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    store = Store(db)
    session_id = store.create_session(os.getcwd(), os.environ.get("PHANTOM_MODEL", "gemma4:e4b"))

    def save(item: object) -> None:
        command, output, redactions, fp = prepare_event(item.command, item.output)  # type: ignore[attr-defined]
        event = {"id": new_id("evt"), "session_id": session_id,
                         "ts": datetime.now(UTC).isoformat(), "type": "command_completed",
                         "command": command, "cwd": item.cwd, "exit_code": item.exit_code,
                         "output_excerpt": output, "fingerprint": fp, "redactions": redactions,
                         "note": item.note, "episode_id": None}
        store.add_event(event)
        from phantomshell.episodes import EpisodeManager
        episode_id = EpisodeManager(store).attach(event)
        if episode_id and item.exit_code != 0 and not args.no_model:
            try:
                from phantomshell.brain import BrainError
                from phantomshell.investigator import plan_episode
                occurrences = store.connection.execute("SELECT occurrences FROM episodes WHERE id=?", (episode_id,)).fetchone()[0]
                if occurrences <= 2:
                    plan_episode(store, episode_id, item.cwd)
            except BrainError as exc:
                print(f"PhantomShell analysis unavailable: {exc}", file=sys.stderr)

    try:
        return run_shell(save)
    finally:
        store.close()


def main() -> None:
    parser = argparse.ArgumentParser(prog="phantomshell")
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run", help="open an instrumented interactive Bash, or capture one command")
    run.add_argument("--json", action="store_true", help="print the captured event as JSON")
    run.add_argument("--no-model", action="store_true", help="capture without local model analysis")
    run.add_argument("command", nargs=argparse.REMAINDER)
    run.set_defaults(func=cmd_run)
    report = sub.add_parser("report", help="print stored terminal events")
    report.set_defaults(func=lambda _args: _report())
    serve = sub.add_parser("serve", help="start the loopback-only read-only dashboard")
    serve.add_argument("--port", type=int, default=8765)
    serve.set_defaults(func=lambda parsed: _serve(parsed.port))
    memory = sub.add_parser("memory", help="list or delete saved incident memories")
    memory.add_argument("operation", choices=["list", "delete", "clear"])
    memory.add_argument("id", nargs="?")
    memory.set_defaults(func=lambda parsed: _memory(parsed.operation, parsed.id))
    selftest = sub.add_parser("selftest", help="probe local JSON-schema inference and core capture utilities")
    selftest.set_defaults(func=lambda _args: _selftest())
    args = parser.parse_args()
    raise SystemExit(args.func(args))


def _report() -> int:
    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    store = Store(db)
    try:
        for event in store.rows("events"):
            print(f"{event['exit_code']} {event['command']}\n{event['output_excerpt']}")
    finally:
        store.close()
    return 0


def _serve(port: int) -> int:
    from phantomshell.server import serve

    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    serve(db, port)
    return 0


def _memory(operation: str, memory_id: str | None) -> int:
    from phantomshell.memory import Memory

    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    store = Store(db)
    try:
        memory = Memory(store)
        if operation == "list":
            for row in store.rows("memories"):
                print(f"{row['id']} [{row['status']}] {row['summary']}")
        elif operation == "delete":
            if not memory_id:
                raise SystemExit("memory delete requires an id")
            print("deleted" if memory.delete(memory_id) else "not found")
        else:
            memory.clear()
            print("memories cleared")
    finally:
        store.close()
    return 0


def _selftest() -> int:
    from phantomshell.brain import BrainError, OllamaBrain
    from phantomshell.ingest import fingerprint, sanitize

    schema = {"type": "object", "additionalProperties": False, "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
    try:
        result = OllamaBrain().call("selftest", {"task": "Reply with ok=true."}, schema)
    except BrainError as exc:
        print(f"Selftest failed: {exc}", file=sys.stderr)
        return 1
    safe, hits = sanitize("token=selftest-secret")
    if "selftest-secret" in safe or hits != 1 or not fingerprint("python build.py", "ERROR: fixture"):
        print("Selftest failed: ingest utilities", file=sys.stderr)
        return 1
    if result.get("ok") is not True:
        print(f"Selftest failed: unexpected model payload {result}", file=sys.stderr)
        return 1
    print(f"Selftest passed: {os.environ.get('PHANTOM_MODEL', 'gemma4:e4b')} returned schema-valid JSON; redaction and fingerprint checks passed.")
    return 0


if __name__ == "__main__":
    main()
