#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [[ -d .git ]]; then rm -rf -- .git; fi
rm -f src/server.py
cat > src/main.py <<'EOF'
"""Fixture application's current module."""

def main() -> None:
    print("hello from fixture")
EOF
git init -q
git config user.name "PhantomShell Fixture"
git config user.email "fixture@localhost"
cat > config.toml <<'EOF'
entry = "src/main.py"
EOF
git add build.py config.toml src/main.py README.md
git commit -qm 'add application entry point'
cat > config.toml <<'EOF'
entry = "src/app.py"
EOF
git add config.toml
git commit -qm 'tweak config'
if [[ "${1:-}" == "--session2" ]]; then
  cat > config.toml <<'EOF'
entry = "src/main.py"
EOF
  git add config.toml
  git commit -qm 'restore entry after Session 1'
  git mv src/main.py src/server.py
  git commit -qm 'rename entry module'
fi
