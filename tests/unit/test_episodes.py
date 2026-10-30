from phantomshell.episodes import EpisodeManager
from phantomshell.store import Store, new_id, utc_now


def _event(store: Store, session: str, command: str, code: int, fp: str) -> dict:
    event = {"id": new_id("evt"), "session_id": session, "ts": utc_now(), "type": "command_completed",
             "command": command, "cwd": "/tmp", "exit_code": code, "output_excerpt": "err",
             "fingerprint": fp, "redactions": 0, "note": None, "episode_id": None}
    store.add_event(event)
    return event


def test_episode_grouping_and_resolution(tmp_path) -> None:
    store = Store(tmp_path / "db.sqlite")
    manager = EpisodeManager(store)
    session = store.create_session("/tmp")
    first = _event(store, session, "python build.py", 1, "same")
    second = _event(store, session, "python build.py", 1, "same")
    success = _event(store, session, "python build.py", 0, "success")
    episode = manager.attach(first)
    assert manager.attach(second) == episode
    assert manager.attach(success) == episode
    row = store.rows("episodes")[0]
    assert row["occurrences"] == 2
    assert row["status"] == "resolved"
    assert row["resolved_event"] == success["id"]
    store.close()
