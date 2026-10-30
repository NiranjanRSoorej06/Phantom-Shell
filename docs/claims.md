# Claim ledger

| Claim | Proof command or file | Date verified | Status |
|---|---|---|---|
| Gemma 4 E4B returned schema-valid Plan JSON for a captured fixture failure and proposed `inspect_project_tree` | Live `plan_episode` output and `model_runs` row in `PROGRESS.md` | 2026-10-30 | VERIFIED |
| The PTY captured `echo hi`, `false`, Ctrl-C, and terminal resize; markers were hidden | `python scripts/test_pty_smoke.py` | 2026-10-30 | VERIFIED |
| Captured terminal events are returned by the authenticated dashboard API | `python scripts/test_pty_smoke.py`; `tests/security/test_dashboard.py` | 2026-10-30 | VERIFIED |
| Common configured secret patterns are redacted before event persistence | `python -m pytest tests/unit/test_ingest.py` | 2026-10-30 | VERIFIED |
| A forged supporting quote is rejected and unsupported verdicts become inconclusive | `python -m pytest tests/unit/test_verifier.py` | 2026-10-30 | VERIFIED |
| Dashboard binds to loopback and rejects requests without its token | `ss -ltnp`; `curl` dashboard/API checks in `PROGRESS.md` | 2026-10-30 | VERIFIED |
| The CLI selftest receives schema-valid JSON from the selected local model | `python -m phantomshell.cli selftest` | 2026-10-30 | VERIFIED |
| Model client accepts only `http://127.0.0.1` endpoints | `tests/security/test_brain.py`; `phantomshell/brain.py` | 2026-10-30 | VERIFIED |
| The full Session 1 → verified memory → Session 2 staleness flow works with Gemma | Not yet run end to end | — | UNVERIFIED |
| Runtime works with external networking disabled while local inference remains available | The namespace recipe could not set loopback without sudo; see `PROGRESS.md` | 2026-10-30 | UNVERIFIED |
| Setup succeeds from a fresh clone and clean virtual environment | Not yet run | — | UNVERIFIED |
