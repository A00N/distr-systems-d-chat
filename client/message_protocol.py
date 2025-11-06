import json
from enum import Enum

class MessageType(str, Enum):
    CHAT = 'CHAT'
    FORWARD = 'FORWARD'  # worker -> coordinator
    BROADCAST = 'BROADCAST'  # coordinator -> workers/clients
    SYNC_REQ = 'SYNC_REQ'
    SYNC_RESP = 'SYNC_RESP'
    JOIN = 'JOIN'
    HEARTBEAT = 'HEARTBEAT'

def encode_message(msg: dict) -> bytes:
    return (json.dumps(msg) + '\n').encode('utf-8')

def decode_message(data: str) -> dict:
    # data may contain newline
    try:
        return json.loads(data)
    except Exception:
        return {}
