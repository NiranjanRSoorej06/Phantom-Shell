from phantomshell.ingest import fingerprint, prepare_event, redact, sanitize, strip_ansi
from phantomshell.store import Store, new_id, utc_now


def test_ansi_strip() -> None:
    assert strip_ansi("\x1b[31mred\x1b[0m\x1b]0;title\x07") == "red"


def test_redaction_patterns_and_command() -> None:
    source = (
        "AKIA1234567890ABCDEF ghp_" + "a" * 36 + " api_key=secret "
        "https://user:pass@example.com Bearer abcdefghijklmnop"
    )
    safe, count = redact(source)
    assert count >= 5
    assert "AKIA1234567890ABCDEF" not in safe
    assert "ghp_" not in safe
    assert "user:pass" not in safe
    command, output, hits, _ = prepare_event("echo token=supersecret", "ok")
    assert "supersecret" not in command
    assert hits == 1
    assert output == "ok"


def test_private_key_and_jwt_redaction() -> None:
    safe, count = redact(
        "-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY----- "
        "eyJabcdefgh.abcdefgh.abcdefgh"
    )
    assert count == 2
    assert "secret" not in safe
    assert "eyJ" not in safe


def test_fingerprint_stable_across_paths() -> None:
    first = fingerprint("python build.py", "ERROR: entry point not found: src/app.py")
    second = fingerprint("python build.py", "ERROR: entry point not found: src/main.py")
    unrelated = fingerprint("python build.py", "ERROR: syntax error in config")
    assert first == second
    assert first != unrelated


def test_sanitize_redacts_before_truncating() -> None:
    safe, hits = sanitize("\x1b[31msecret=private\x1b[0m", limit=128)
    assert hits == 1
    assert "private" not in safe


def test_database_never_receives_raw_command_or_output_secret(tmp_path) -> None:
    command, output, hits, fp = prepare_event("echo token=commandsecret", "api_key=outputsecret")
    store = Store(tmp_path / "events.sqlite")
    session_id = store.create_session(str(tmp_path))
    store.add_event({"id": new_id("evt"), "session_id": session_id, "ts": utc_now(), "type": "command_completed",
                     "command": command, "cwd": str(tmp_path), "exit_code": 1, "output_excerpt": output,
                     "fingerprint": fp, "redactions": hits, "note": None, "episode_id": None})
    persisted = repr(store.rows("events"))
    assert "commandsecret" not in persisted
    assert "outputsecret" not in persisted
    assert store.rows("events")[0]["redactions"] == 2
    store.close()
