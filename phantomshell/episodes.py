"""Deterministic failure episode grouping and resolution."""

from __future__ import annotations

from phantomshell.store import Store, new_id


def command_family(command: str) -> str:
    return " ".join(command.split()[:2])


class EpisodeManager:
    def __init__(self, store: Store):
        self.store = store

    def attach(self, event: dict[str, object]) -> str | None:
        session_id = str(event["session_id"])
        code = int(event["exit_code"])
        family = command_family(str(event["command"]))
        if code != 0:
            row = self.store.connection.execute(
                "SELECT * FROM episodes WHERE session_id=? AND fingerprint=? AND status='open' ORDER BY rowid DESC LIMIT 1",
                (session_id, event["fingerprint"]),
            ).fetchone()
            if row:
                episode_id = row["id"]
                self.store.connection.execute(
                    "UPDATE episodes SET occurrences=occurrences+1,last_event=? WHERE id=?",
                    (event["id"], episode_id),
                )
            else:
                episode_id = new_id("ep")
                self.store.connection.execute(
                    "INSERT INTO episodes(id,session_id,fingerprint,command_family,status,first_event,last_event) VALUES(?,?,?,?,?,?,?)",
                    (episode_id, session_id, event["fingerprint"], family, "open", event["id"], event["id"]),
                )
        else:
            row = self.store.connection.execute(
                "SELECT * FROM episodes WHERE session_id=? AND command_family=? AND status='open' ORDER BY rowid DESC LIMIT 1",
                (session_id, family),
            ).fetchone()
            if not row:
                return None
            episode_id = row["id"]
            self.store.connection.execute(
                "UPDATE episodes SET status='resolved',resolved_event=?,last_event=? WHERE id=?",
                (event["id"], event["id"], episode_id),
            )
            from phantomshell.memory import Memory
            Memory(self.store).promote_on_resolution(episode_id)
        self.store.connection.execute("UPDATE events SET episode_id=? WHERE id=?", (episode_id, event["id"]))
        self.store.connection.commit()
        return episode_id
