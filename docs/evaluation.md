# Evaluation

No mini-evaluation run set has been completed yet. This file intentionally contains no latency, success-rate, or offline claims.

| Scenario | Config | Trials (n) | Schema valid | Verified quote | Root cause hit | Median latency | Offline |
|---|---|---:|---:|---:|---:|---:|---|
| Entry-point mismatch | Full | 0 | — | — | — | — | Not tested |
| ModuleNotFoundError after rename | Full | 0 | — | — | — | — | Not tested |
| Missing config environment variable | Full | 0 | — | — | — | — | Not tested |
| All scenarios | `--no-model` | 0 | n/a | n/a | n/a | n/a | Not tested |

One live Gemma Plan call on the captured entry-point fixture returned a schema-valid hypothesis and a `inspect_project_tree` request. This is a single functional check, not an evaluation trial; its observed output is recorded in `PROGRESS.md`.

Follow-up live checks approved tree inspection, reading `build.py`, and reading `config.toml`. Gemma's Conclude remained inconclusive despite four evidence-matched quotes, so no root-cause hit or memory promotion is counted. The verifier clears cause-like narrative text when the verdict is inconclusive.

To run the network-isolated recipe, first confirm the local Ollama daemon works, then run the project inside a network namespace with loopback enabled. The required `unshare -rn` check has not been run in this environment.
