# PhantomShell: a terminal ghost that remembers failures—and shows its evidence

This is a submission draft for the [Hacktoberfest Open-Source AI Challenge: Week 4](https://dev.to/challenges/hacktoberfest-week4-2026-10-26). Required tags: `devchallenge`, `hf26challenge`.

## What I Built

PhantomShell is a local terminal investigator. It captures completed Bash commands, removes common secret patterns before storage, groups repeated failures, and asks Gemma running through Ollama to suggest read-only checks. The backend owns tool permissions. A conclusion can be marked supported only when its quoted evidence exists in the stored event or tool output.

In one captured fixture run, `python build.py` printed:

```text
ERROR: entry point not found: src/app.py
```

Gemma proposed `inspect_project_tree` with `depth: 2`. The check returned `src/main.py`; the following Conclude call stayed inconclusive. That is the honest result from this run, not a successful root-cause demonstration.

## Demo

TODO(owner): add a real screen recording and screenshots after recording both sessions from `demo/script_session1.md` and `demo/script_session2.md`. No demo media has been captured yet.

## Code

TODO(owner): add the public repository URL. Local commits exist, but the repository has not been pushed from this workspace.

## How I Built It

The terminal wrapper uses Bash hooks and a PTY to mark command boundaries. Python strips the markers and ANSI output, redacts, fingerprints failures, and stores events in SQLite. Gemma returns JSON-schema constrained Plan and Conclude responses. The backend validates tool names and arguments; each proposed check waits for a user approval. A verifier checks quoted text against evidence and downgrades unsupported conclusions.

The implementation uses Python, FastAPI, SQLite, and Ollama's loopback API. One live Gemma Plan on the fixture returned a valid `inspect_project_tree` proposal in 33.3 seconds. A live Conclude returned `inconclusive`; the full two-session flow is still unverified.

## Why Does Open Innovation Matter?

Terminal logs can contain private code and credentials. Keeping inference on the developer's machine gives the user control over the model and the data path. PhantomShell's model client only targets `127.0.0.1`, with no remote fallback. I have not yet verified the full app inside an isolated network namespace, so I am not claiming that the end-to-end workflow works offline.

## My Agent Session

TODO(owner): add a real DevRelay/Entire session URL only if one has been saved.

## The Spirit of It

The useful moment was the ghost declining to call a cause supported after a real read-only check. Its first wording still claimed the check was pending; a verifier fix now replaces unsupported cause text with a neutral inconclusive message. The remaining work is to demonstrate the memory across sessions and show the evidence in a real recording.

## Prize Categories

- Best Use of Gemma: Gemma 4 E4B runs locally through Ollama for both Plan and Conclude calls.

---

**Not ready to publish:** repository URL, real demo recording/screenshots, owner profile details, final end-to-end run, and review of all UNVERIFIED entries in `docs/claims.md` are still outstanding.
