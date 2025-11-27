import json
import os
from typing import Dict, List


class ChatState:
    """Very simple chat state machine.

    Stores committed chat messages as a list and appends them to a JSONL file.
    """

    def __init__(self, path: str = "chat_log.jsonl"):
        self.path = path
        self._log: List[Dict] = []
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    self._log.append(json.loads(line))
                except Exception:
                    continue

    async def apply(self, command: Dict) -> None:
        """Apply a committed command to the state."""
        self._log.append(command)
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(command, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def all_messages(self) -> List[Dict]:
        return list(self._log)
