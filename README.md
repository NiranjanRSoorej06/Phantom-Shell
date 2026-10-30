# PhantomShell

PhantomShell watches commands in a wrapped Bash, remembers repeated failures, and asks a local Gemma model to suggest read-only checks. It keeps terminal capture, permissions, tools, and evidence verification in deterministic Python code. The model can propose checks and explanations; only a user-approved action reaches a tool.

## Current status

This repository implements capture, sanitization, SQLite storage, failure episodes, Ollama JSON-schema calls, read-only tools, quote verification, memory, and a token-protected loopback dashboard. The PTY smoke test and the local Gemma Plan call passed on the build machine. The full two-session demo and offline namespace recipe have not been verified yet; see [PROGRESS.md](PROGRESS.md) and [docs/claims.md](docs/claims.md).

## Requirements

- Python 3.11 or later
- Bash 4.4 or later
- Ollama with `gemma4:e4b` pulled
- `git` and `rg` for project inspection tools
- Linux, WSL2, or macOS with Homebrew Bash; native Windows is unsupported

Install in a virtual environment:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
ollama pull gemma4:e4b
```

## Run

Start the dashboard in one terminal:

```bash
phantomshell serve
```

Start an instrumented interactive Bash in another:

```bash
phantomshell run
```

Or capture one command with the deterministic fallback:

```bash
phantomshell run -- python build.py
```

Append `--no-model` before `--` to capture without inference. Events are stored under `~/.local/share/phantomshell/events.sqlite3` by default; set `PHANTOMSHELL_DB` to choose another path. The dashboard prints a per-launch token URL, binds to `127.0.0.1`, displays captured events, and offers approve/reject controls for proposed read-only checks.

Saved incident memory commands:

```bash
phantomshell memory list
phantomshell memory delete <id>
phantomshell memory clear
```

## Demo fixture

The fixture has no Python dependencies or network requirement:

```bash
cd demo/fixture_project
./reset.sh
python build.py
```

The initial config points to `src/app.py`; the fixture contains `src/main.py`. The session scripts describe the intended investigation and memory workflow. `reset.sh --session2` adds a rename commit after a resolved Session 1 state.

## Safety boundaries

- Output and command strings are redacted before they are stored or sent to Ollama.
- The model cannot run commands. Tool names and arguments are checked by the backend.
- Tools are read-only and restricted to the project root; sensitive files and symlink escapes are blocked.
- A conclusion is supported only when a quoted substring matches stored evidence. Unsupported conclusions are downgraded to inconclusive.
- The dashboard has no terminal input and accepts only loopback Host/Origin values plus its bearer token.
- Model requests use `http://127.0.0.1:11434` only. No remote fallback is implemented.

See [docs/architecture.md](docs/architecture.md) and [docs/threat-model.md](docs/threat-model.md) for details. See [docs/evaluation.md](docs/evaluation.md) for the current evidence and unrun checks.

## Tests

```bash
python -m pytest tests/unit tests/security
python scripts/test_pty_smoke.py
```

## License

PhantomShell is MIT licensed. Gemma 4 is Apache 2.0 under [Google's model card](https://ai.google.dev/gemma/docs/core/model_card_4). The Ollama runtime is MIT licensed ([official API specification](https://github.com/ollama/ollama/blob/main/docs/openapi.yaml)). Current Python package metadata reports httpx and Uvicorn as BSD-3-Clause, and FastAPI, pytest, and Ruff as MIT. Recheck the selected versions' license files before redistribution.

## Post-deadline commits

TODO(owner): list any commits made after the Hacktoberfest challenge deadline, or state “None” after verifying the final Git history.
