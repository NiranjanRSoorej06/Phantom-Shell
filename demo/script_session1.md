# Session 1

1. Run `./reset.sh`, then from this directory run `python build.py`.
2. Inspect the failure and approve the proposed read-only checks.
3. Confirm `config.toml` points to `src/app.py` and the tree contains `src/main.py`.
4. Change the config entry to `src/main.py`, then run `python build.py` again.
5. Confirm the episode resolves and the supported memory is promoted to verified.
