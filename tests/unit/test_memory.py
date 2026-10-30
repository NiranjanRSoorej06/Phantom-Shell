import hashlib

from phantomshell.memory import Memory, check_staleness
from phantomshell.store import Store, new_id


def test_staleness(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("entry='main.py'")
    item = {"path": "config.toml", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    assert check_staleness(tmp_path, [item]) == ("same conditions", [])
    path.write_text("entry='server.py'")
    assert check_staleness(tmp_path, [item]) == ("changed since", ["config.toml"])
    assert check_staleness(tmp_path, []) == ("not checked", [])


def test_memory_recall_and_promotion(tmp_path) -> None:
    store = Store(tmp_path / "db.sqlite")
    episode = new_id("ep")
    memory = Memory(store)
    path = tmp_path / "file.txt"
    path.write_text("same")
    watch = [{"path": "file.txt", "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]
    memory_id = memory.propose("f1", "python build.py", "summary", "cause", [], episode, watch)
    memory.promote_on_resolution(episode)
    result = memory.recall("f1", "python build.py", tmp_path)
    assert result[0]["id"] == memory_id
    assert result[0]["status"] == "verified"
    path.write_text("changed")
    assert memory.recall("f1", "python build.py", tmp_path)[0]["recall_status"] == "changed since"
    assert memory.delete(memory_id)
    store.close()
