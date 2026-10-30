import asyncio

import httpx

from phantomshell.server import create_app
from phantomshell.store import Store, new_id, utc_now


def test_dashboard_auth_and_host_origin(tmp_path) -> None:
    async def exercise() -> None:
        db_path = tmp_path / "db.sqlite"
        store = Store(db_path)
        session_id = store.create_session(str(tmp_path))
        store.add_event({"id": new_id("evt"), "session_id": session_id, "ts": utc_now(), "type": "command_completed",
                         "command": "python build.py", "cwd": str(tmp_path), "exit_code": 1,
                         "output_excerpt": "ERROR: fixture failure", "fingerprint": "test", "redactions": 0,
                         "note": None, "episode_id": None})
        store.close()
        app = create_app(db_path, "secret", 8765)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8765") as client:
            assert (await client.get("/api/events")).status_code == 401
            headers = {"Authorization": "Bearer secret", "Origin": "https://evil.example"}
            assert (await client.get("/api/events", headers=headers)).status_code == 403
            response = await client.get("/api/events", headers={"Authorization": "Bearer secret"})
            assert response.status_code == 200
            assert response.json()[0]["output_excerpt"] == "ERROR: fixture failure"

    asyncio.run(exercise())
