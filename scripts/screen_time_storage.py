"""Project-owned atomic UTF-8 state storage."""
import json
import os
from pathlib import Path

def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        with temporary.open('w', encoding='utf-8') as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()
