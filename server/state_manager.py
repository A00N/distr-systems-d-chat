"""Simple append-only chat log manager (persist to JSONL)."""
import json, os
from typing import List

class ChatState:
    def __init__(self, storage_path='chat_log.jsonl'):
        self.storage_path = storage_path
        self._log = []
        self._load()

    def _load(self):
        if os.path.exists(self.storage_path):
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        self._log.append(json.loads(line.strip()))
                    except Exception:
                        continue

    def append(self, msg: dict) -> int:
        # append message and persist, return index
        self._log.append(msg)
        idx = len(self._log) - 1
        try:
            with open(self.storage_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(msg, ensure_ascii=False) + '\n')
        except Exception:
            pass
        return idx

    def get_since_index(self, since_idx: int) -> List[dict]:
        if since_idx < 0:
            since_idx = 0
        return self._log[since_idx:]
