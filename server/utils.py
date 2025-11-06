import json
from pathlib import Path

def load_config(path):
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text())

