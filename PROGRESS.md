# Build progress

### T0 — Preflight  [DONE]
- Time spent: not measured
- Files changed: `.gitignore`, `LICENSE`, `pyproject.toml`, `PROGRESS.md`, `docs/claims.md`
- Acceptance command: `python --version; git --version; rg --version; bash --version; ollama --version; ollama list; curl -sS --max-time 120 http://127.0.0.1:11434/api/chat -d '<JSON schema probe>'`
- Observed result: Python 3.13.7; Git 2.56.0; ripgrep 15.2.0; Bash 5.3.20; Ollama 0.40.7; 9.1 GiB available RAM, no `nvidia-smi`; downloaded `gemma4:e4b`; local schema probe returned `{"ok": true}` in 20.5 s (including 18.2 s model load). Ollama reported `total_duration=20507089762`, `eval_count=6`.
- Unverified assumptions: GPU unavailable or not NVIDIA; the probe tested `think:false` once only.
- Claims now safe to publish: Gemma 4 E4B answered one schema-constrained JSON probe locally via Ollama.
- Commit: initially blocked in the sandbox; elevated write permission later created root commit `7f27c8e` on 2026-10-30 and correction commit `d14eaeb` so the demo fixture is tracked directly. `git status --short` was clean after the correction.

### T1 — Store + ingest  [DONE]
- Time spent: not measured
- Files changed: `phantomshell/__init__.py`, `phantomshell/ingest.py`, `phantomshell/store.py`, `tests/unit/test_ingest.py`
- Acceptance command: `python -m pytest tests/unit -k "ansi or redaction or fingerprint"`
- Observed result: `4 passed, 1 deselected in 0.08s`.
- Unverified assumptions: redaction patterns do not cover every secret format.
- Claims now safe to publish: common configured secret patterns were redacted before storing the tested event row; pattern coverage is not comprehensive.

### T2 — Capture  [DONE]
- Time spent: not measured
- Files changed: `phantomshell/capture/`, `phantomshell/cli.py`, `scripts/test_pty_smoke.py`, `tests/unit/test_capture.py`
- Acceptance command: `python scripts/test_pty_smoke.py`
- Observed result: `PTY/dashboard OK: events live through authenticated API; echo=0, false=1, Ctrl-C=130, resize=40x100, markers hidden`; separate alt-screen parser test passed. `vim` is not installed, so a real editor run was not tested.
- Unverified assumptions: behavior on Bash 4.4 and macOS Homebrew Bash; editor-specific escape sequences beyond the parser fixture.
- Claims now safe to publish: the PTY smoke captured the four scripted commands with the expected exit codes, hid markers, and propagated resize.

### T3 — Episodes  [DONE]
- Time spent: not measured
- Files changed: `phantomshell/episodes.py`, `tests/unit/test_episodes.py`
- Acceptance command: `python -m pytest tests/unit -k episode_grouping_and_resolution`
- Observed result: `1 passed, 7 deselected in 0.08s`.
- Unverified assumptions: repeated episode matching uses exact fingerprint and same session as specified.
- Claims now safe to publish: repeated equal fingerprints group in one session and a later same-family success resolves the episode (unit test).

### T4 — Server + minimal dashboard  [DONE]
- Time spent: not measured
- Files changed: `phantomshell/server.py`, `phantomshell/static/index.html`, `tests/security/test_dashboard.py`, `scripts/test_pty_smoke.py`
- Acceptance command: `python -m pytest tests/security/test_dashboard.py -q`; `python scripts/test_pty_smoke.py`; live `ss -ltnp`; `curl` page/API checks.
- Observed result: dashboard auth/event test passed; PTY smoke returned a captured event through the authenticated API; live listener was `127.0.0.1:18765`; `/` returned HTTP 200 and unauthenticated `/api/events` returned HTTP 401. Server was stopped after the check.
- Unverified assumptions: browser rendering was checked through the static response and API, not through a graphical browser.
- Claims now safe to publish: the dashboard binds to loopback and requires its launch token for API reads.

### T5 — Brain Plan call  [DONE]
- Time spent: not measured
- Files changed: `phantomshell/brain.py`, `phantomshell/investigator.py`, `tests/security/test_brain.py`
- Acceptance command: `plan_episode` against the fixture event in `/tmp/phantomshell-events.sqlite3` using `gemma4:e4b`.
- Observed result: schema-valid Plan proposed `inspect_project_tree` with `{"depth": 2}` for the captured `python build.py` failure; `model_runs` recorded `valid_schema=1`, 701 prompt tokens, 262 output tokens, and 33,290 ms.
- Unverified assumptions: model quality across repeated trials and other error types.
- Claims now safe to publish: one live Gemma Plan call returned a relevant read-only check for a real captured fixture failure in 33.3 seconds.

### T6 — Verifier  [DONE]
- Time spent: not measured
- Files changed: `phantomshell/verify.py`, `tests/unit/test_verifier.py`
- Acceptance command: `python -m pytest tests/unit/test_verifier.py -q`
- Observed result: forged quote rejected; whitespace-normalized matching quote accepted; unsupported verdict had its cause replaced with a neutral inconclusive message. Covered by passing tests.
- Unverified assumptions: substring verification does not prove that a model's interpretation of a true quote is correct.
- Claims now safe to publish: a forged quote does not survive verification.

### T7 — Tools + policy + hardened subprocess  [DONE]
- Time spent: not measured
- Files changed: `phantomshell/tools.py`, `phantomshell/policy.py`, `phantomshell/investigator.py`, `tests/security/test_tools.py`, `tests/unit/test_investigator.py`
- Acceptance command: `python -m pytest tests/security/test_tools.py tests/unit/test_investigator.py -q`
- Observed result: path traversal, absolute path, symlink escape, `.env`, `.git/config`, max-byte/depth/commit limits, and unknown tool checks pass; approved tree inspection reached the fake Conclude path in a unit test.
- Unverified assumptions: broader malicious repository configurations and subprocess timeout behavior.
- Claims now safe to publish: unknown tools and the tested path escapes are blocked before execution.

### T8 — Conclude + approval UI  [DONE]
- Time spent: not measured
- Files changed: `phantomshell/investigator.py`, `phantomshell/server.py`, `phantomshell/static/index.html`, `phantomshell/verify.py`, `tests/unit/test_investigator.py`
- Acceptance command: approved `inspect_project_tree` proposal for the captured fixture event, followed by live Gemma Conclude; `python -m pytest tests/unit/test_investigator.py -q`.
- Observed result: Gemma returned `inconclusive` after approved tree, build-file, and config checks. Four quotes matched stored evidence, but the live model still did not support a cause. Verifier now clears cause-like narrative text for inconclusive verdicts. Unit coverage was added; rerun recorded below.
- Unverified assumptions: the live model may still choose insufficient checks for a fixture root cause.
- Claims now safe to publish: the real Plan requested relevant read-only checks; the live Conclude remained inconclusive despite quote-verified evidence, and deterministic verification suppresses cause-like text in that case.

### T9 — Memory save + resolution  [BLOCKED]
- Time spent: not measured
- Files changed: `phantomshell/memory.py`, `phantomshell/episodes.py`, `tests/unit/test_memory.py`, `tests/unit/test_investigator.py`
- Acceptance command: `python -m pytest tests/unit/test_memory.py tests/unit/test_investigator.py -q`
- Observed result: supported fake Conclude creates a proposed memory; a same-session, same-family success promotes it to verified. Memory persists in SQLite.
- Unverified assumptions: full model-generated supported investigation in the real fixture; the live run remained inconclusive, so no live memory was proposed or promoted.
- Claims now safe to publish: proposed memory promotion and persistence pass the unit scenario.

### T10 — Recall + staleness  [BLOCKED]
- Time spent: not measured
- Files changed: `phantomshell/memory.py`, `phantomshell/investigator.py`, `tests/unit/test_memory.py`
- Acceptance command: `python -m pytest tests/unit/test_memory.py -q`
- Observed result: exact-fingerprint recall and watched-file hash mismatch report `changed since`; unchanged file reports `same conditions`; empty watched set reports `not checked`. Full Session 2 recall, `config.toml` changed-since text, and rename-commit conclusion were not run.
- Unverified assumptions: live Plan will request reads of the configuration and relevant Git history needed for Session 2.
- Claims now safe to publish: unit-level fingerprint recall and watched-file staleness checks pass.

### T11 — Security hardening  [BLOCKED]
- Time spent: not measured
- Files changed: `phantomshell/brain.py`, `phantomshell/tools.py`, `phantomshell/server.py`, `tests/security/`
- Acceptance command: `python -m pytest tests/unit tests/security -q`; live `ss -ltnp`; `curl` auth check.
- Observed result: `24 passed`; listener verified on `127.0.0.1`; API without bearer token returned 401; wrong Host/Origin checks pass. Ollama-down capture continuation, malformed JSON twice, and an actual tool timeout were not exercised.
- Unverified assumptions: the remaining unrun security scenarios.
- Claims now safe to publish: the tested injection fixture remains quoted untrusted data; the tested secret/path/auth protections pass.

### T12 — Eval + offline  [BLOCKED]
- Time spent: not measured
- Files changed: `docs/evaluation.md`
- Acceptance command: `sudo unshare -n ...` per §8.4.
- Observed result: `unshare -rn true` succeeded, but setting `lo` up failed with `Operation not permitted`; the full command stopped because sudo required a password. No offline result or evaluation trials are claimed.
- Unverified assumptions: full stack behavior with external routes disabled.
- Claims now safe to publish: no offline claim; no evaluation metric.

### T13 — README, docs, claims, cleanup  [BLOCKED]
- Time spent: not measured
- Files changed: `README.md`, `docs/architecture.md`, `docs/threat-model.md`, `docs/evaluation.md`, `docs/claims.md`, `docs/dev-post-draft.md`, `LICENSE`, `pyproject.toml`
- Acceptance command: `python -m pytest tests/unit tests/security -q`; `ruff check phantomshell tests scripts`; fresh-clone selftest not run.
- Observed result: `25 passed`; Ruff reported `All checks passed!`; PTY smoke returned `PTY/dashboard OK: events live through authenticated API; echo=0, false=1, Ctrl-C=130, resize=40x100, markers hidden`; `python -m phantomshell.cli selftest` returned `Selftest passed: gemma4:e4b returned schema-valid JSON; redaction and fingerprint checks passed.` Clean-clone setup remains unverified. Root commits were created with approved elevated access.
- Unverified assumptions: clean-venv installation and completed challenge submission requirements.
- Claims now safe to publish: only rows marked VERIFIED in `docs/claims.md`.

### T14 — Demo capture  [BLOCKED]
- Time spent: not measured
- Files changed: `demo/fixture_project/`, `demo/script_session1.md`, `demo/script_session2.md`, `scripts/test_pty_smoke.py`
- Acceptance command: `./reset.sh`; `python build.py`; `./reset.sh --session2`; `python build.py`; `git log -M --oneline --stat -4`.
- Observed result: Session 1 fixture prints `ERROR: entry point not found: src/app.py`; Session 2 prints `ERROR: entry point not found: src/main.py`; Git history shows `src/main.py => src/server.py`. No owner screen recording or screenshots exist.
- Unverified assumptions: recorded two-session demo with real model output.
- Claims now safe to publish: fixture reset and its deterministic failures/rename history work.

### T15 — DEV post  [BLOCKED]
- Time spent: not measured
- Files changed: `docs/dev-post-draft.md`
- Acceptance command: review `docs/dev-post-draft.md` against §9.3 and §9.7.
- Observed result: ordered draft exists with `TODO(owner)` for repository URL, recording/screenshots, and saved agent-session link; it is explicitly marked not ready to publish.
- Unverified assumptions: owner profile details and submission assets.
- Claims now safe to publish: none; publish only after the remaining UNVERIFIED claim rows and TODOs are resolved.

## OWNER QUESTIONS

- TODO(owner): confirm preferred public repository URL and DEV handle before publishing.
- Root `.git` write access was granted for the implementation commits; the latest observed `git status --short` was clean.
- The live DEV API `ends_at` timestamp appeared one day early; the [official Week 4 challenge page](https://dev.to/challenges/hacktoberfest-week4-2026-10-26) and its rules show the deadline as Oct 31, 2026 at 11:59 PM PDT, matching `plan.md`.
