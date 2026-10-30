# Threat model

## Assets

- Terminal command text, output, current working directory, and project files.
- Local credentials that may appear accidentally in command arguments or output.
- Approval authority for filesystem reads and Git inspection.
- The SQLite event, evidence, model-run, and memory records.

## Untrusted inputs

Terminal output, command text, files, Git status/log text, memory text, and model responses are data. They can contain prompt injection, forged quotes, path tricks, or malicious instructions. The system wraps model context as untrusted data, escapes a literal closing tag, and never lets model text select a shell command.

## Controls

- Ingest strips ANSI/OSC sequences, redacts common credentials, then truncates before persistence.
- Project tools reject path escape, sensitive basenames, binary files, and symlink escape.
- Subprocesses use argument arrays and `shell=False`; Git disables pagers, hooks, and fsmonitor; ripgrep ignores config and follows no symlinks.
- Only backend-listed read-only tools can be proposed. Every stored proposal requires an explicit dashboard approval before execution.
- Evidence IDs must exist. Supporting quotes must be substrings of the corresponding evidence. A supported verdict without a verified quote becomes inconclusive.
- Dashboard APIs require a random launch token and local Host/Origin values. Uvicorn binds to loopback; no terminal-input API exists.
- Ollama requests are restricted to `127.0.0.1`; there is no remote model fallback.

## Limits

Regex redaction is not comprehensive. Local processes running as the same OS user can inspect the database or model memory. A local model can still produce incorrect hypotheses or conclusions; quote checks prove only that a quote exists, not that the interpretation is correct. Review results and run your own checks.
