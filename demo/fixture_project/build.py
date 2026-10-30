from pathlib import Path
import sys
import tomllib

config = tomllib.loads(Path("config.toml").read_text())
entry = Path(config["entry"])
if not entry.exists():
    print(f"ERROR: entry point not found: {entry.as_posix()}")
    sys.exit(1)
print("BUILD OK")
