"""Loopback-only read-only event dashboard with per-launch bearer token."""

from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from phantomshell.investigator import approve_action
from phantomshell.memory import Memory
from phantomshell.store import Store


class ActionRequest(BaseModel):
    action_id: str


def create_app(db_path: str | Path, token: str | None = None, port: int = 8765) -> FastAPI:
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.token = token or secrets.token_hex(16)
    app.state.db_path = str(db_path)
    app.state.port = port

    @app.middleware("http")
    async def local_security(request: Request, call_next):
        host_header = request.headers.get("host", "")
        if host_header not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
            return JSONResponse({"detail": "local Host required"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin not in {f"http://{host_header}", "null"}:
            return JSONResponse({"detail": "local Origin required"}, status_code=403)
        if request.url.path not in {"/", "/favicon.ico"} and request.headers.get("authorization") != f"Bearer {app.state.token}":
            return JSONResponse({"detail": "token required"}, status_code=401)
        return await call_next(request)

    @app.get("/", response_class=HTMLResponse)
    async def index() -> FileResponse:
        return FileResponse(Path(__file__).parent / "static" / "index.html")

    @app.get("/api/events")
    async def events() -> list[dict]:
        store = Store(app.state.db_path)
        try:
            return list(reversed(store.rows("events")[-500:]))
        finally:
            store.close()

    @app.get("/api/investigations")
    async def investigations() -> list[dict]:
        import json
        store = Store(app.state.db_path)
        try:
            return [{"episode_id": row[0], "verdict": row[1], "result": json.loads(row[2]), "created_at": row[3]}
                    for row in store.connection.execute("SELECT episode_id,verdict,result_json,created_at FROM investigations ORDER BY created_at DESC LIMIT 30")]
        finally:
            store.close()

    @app.get("/api/status")
    async def status() -> dict[str, str]:
        import os
        return {"model": os.environ.get("PHANTOM_MODEL", "gemma4:e4b"), "inference": "local inference ✓",
                "network": "no external calls (Ollama loopback only)", "monitoring": "on"}

    @app.get("/api/actions")
    async def actions() -> list[dict]:
        store = Store(app.state.db_path)
        try:
            return [dict(row) for row in store.connection.execute("SELECT id,tool,args_json,reason FROM action_log WHERE decision='proposed' ORDER BY ts")]
        finally:
            store.close()

    @app.post("/api/approve")
    async def approve(request: ActionRequest) -> dict:
        store = Store(app.state.db_path)
        try:
            action = store.connection.execute("SELECT args_json FROM action_log WHERE id=? AND decision='proposed'", (request.action_id,)).fetchone()
            if not action:
                raise HTTPException(404, "pending action not found")
            import json
            episode_id = json.loads(action[0]).get("_episode_id")
            root = store.connection.execute("SELECT s.project_root FROM episodes e JOIN sessions s ON s.id=e.session_id WHERE e.id=?", (episode_id,)).fetchone()
            if not root:
                raise HTTPException(404, "project not found")
            try:
                return approve_action(store, request.action_id, root[0])
            except Exception as exc:
                raise HTTPException(400, f"approval failed: {exc}") from exc
        finally:
            store.close()

    @app.post("/api/reject")
    async def reject(request: ActionRequest) -> dict[str, bool]:
        store = Store(app.state.db_path)
        try:
            cursor = store.connection.execute("UPDATE action_log SET decision='rejected',reason='rejected by user' WHERE id=? AND decision='proposed'", (request.action_id,))
            store.connection.commit()
            return {"rejected": cursor.rowcount == 1}
        finally:
            store.close()

    @app.get("/api/memories")
    async def memories() -> list[dict]:
        store = Store(app.state.db_path)
        try:
            return [dict(row) for row in store.connection.execute("SELECT id,summary,status,created_at FROM memories ORDER BY created_at DESC LIMIT 100")]
        finally:
            store.close()

    @app.delete("/api/memory/{memory_id}")
    async def delete_memory(memory_id: str) -> dict[str, bool]:
        store = Store(app.state.db_path)
        try:
            return {"deleted": Memory(store).delete(memory_id)}
        finally:
            store.close()

    @app.get("/api/stream")
    async def stream() -> StreamingResponse:
        async def generate():
            import asyncio
            import json

            last = ""
            while True:
                store = Store(app.state.db_path)
                try:
                    rows = store.rows("events")[-200:]
                finally:
                    store.close()
                current = json.dumps(rows, sort_keys=True, default=str)
                if current != last:
                    yield f"data: {current}\n\n"
                    last = current
                await asyncio.sleep(1)
        return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    return app


def serve(db_path: str | Path, port: int = 8765) -> None:
    import uvicorn

    token = secrets.token_hex(16)
    app = create_app(db_path, token, port)
    print(f"Dashboard: http://127.0.0.1:{port}/#t={token}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
