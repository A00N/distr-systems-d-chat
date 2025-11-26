import json


def encode_msg(msg: dict) -> bytes:
    """Encode a message as JSON line (for RAFT RPCs)."""
    return (json.dumps(msg) + "\n").encode("utf-8")


def decode_msg(line: str) -> dict:
    try:
        return json.loads(line)
    except Exception:
        return {}
