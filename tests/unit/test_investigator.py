
from phantomshell.episodes import EpisodeManager
from phantomshell.investigator import _validate_tool_args, approve_action
from phantomshell.policy import log_action
from phantomshell.store import Store, new_id, utc_now
from phantomshell.tools import ToolBlocked


class FakeBrain:
    def conclude(self, data, store):
        evidence_id = data["evidence_rows"][0]["id"]
        return {"verdict": "supported", "cause": "The expected file is absent.",
                "supporting": [{"claim": "The build command failed.", "evidence_id": evidence_id,
                                "quote": "python build.py"}], "ruled_out": [], "next_steps": ["Check the entry path."],
                "narrative": "The expected file is absent."}


def test_tool_args_reject_unrecognized_fields() -> None:
    _validate_tool_args("inspect_project_tree", {"path": ".", "depth": 2})
    try:
        _validate_tool_args("inspect_project_tree", {"depth": 2, "reason": "extra"})
    except ToolBlocked:
        pass
    else:
        raise AssertionError("unexpected tool arguments were accepted")


def test_approved_check_concludes_and_proposes_memory(tmp_path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "src").mkdir()
    (root / "src/main.py").write_text("pass\n")
    store = Store(tmp_path / "db.sqlite")
    session_id = store.create_session(str(root))
    event = {"id": new_id("evt"), "session_id": session_id, "ts": utc_now(), "type": "command_completed",
             "command": "python build.py", "cwd": str(root), "exit_code": 1,
             "output_excerpt": "ERROR: entry point not found: src/app.py", "fingerprint": "fp",
             "redactions": 0, "note": None, "episode_id": None}
    store.add_event(event)
    episode_id = EpisodeManager(store).attach(event)
    store.add_evidence(episode_id, "event", "terminal", "command: python build.py\nexit_code: 1")
    store.save_investigation(episode_id, "planning", {"requested_tools": []})
    action_id = log_action(store, "inspect_project_tree", {"depth": 2, "_episode_id": episode_id}, "proposed")
    result = approve_action(store, action_id, root, FakeBrain())
    assert result["conclusion"]["verdict"] == "supported"
    assert store.rows("action_log")[0]["decision"] == "executed"
    assert store.rows("memories")[0]["status"] == "proposed"
    success = {"id": new_id("evt"), "session_id": session_id, "ts": utc_now(), "type": "command_completed",
               "command": "python build.py", "cwd": str(root), "exit_code": 0, "output_excerpt": "BUILD OK",
               "fingerprint": "success", "redactions": 0, "note": None, "episode_id": None}
    store.add_event(success)
    assert EpisodeManager(store).attach(success) == episode_id
    assert store.rows("memories")[0]["status"] == "verified"
    store.close()
