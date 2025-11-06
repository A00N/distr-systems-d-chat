import asyncio, json, logging
from message_protocol import MessageType, encode_message, decode_message

class ClientProtocol:
    def __init__(self, loop, host, port, username):
        self.loop = loop
        self.host = host
        self.port = port
        self.username = username
        self.writer = None
        self.ui = None

    def set_ui(self, ui):
        self.ui = ui

    async def connect(self):
        try:
            reader, writer = await asyncio.open_connection(self.host, self.port)
            self.writer = writer
            # start reader task
            self.loop.create_task(self._reader_loop(reader))
        except Exception as e:
            logging.error(f'Failed to connect to server: {e}')
            if self.ui:
                self.ui.add_system_message('Connection failed')

    async def _reader_loop(self, reader):
        while True:
            try:
                line = await reader.readline()
                if not line:
                    break
                msg = decode_message(line.decode().strip())
                if not msg:
                    continue
                mtype = msg.get('type')
                if mtype == MessageType.BROADCAST or mtype == MessageType.CHAT:
                    username = msg.get('username') or msg.get('sender') or 'unknown'
                    text = msg.get('payload', {}).get('text') or msg.get('msg') or ''
                    if self.ui:
                        self.ui.add_message(username, text)
            except Exception:
                break
        if self.ui:
            self.ui.add_system_message('Disconnected from server')

    def send_chat(self, text: str):
        if not self.writer:
            if self.ui:
                self.ui.add_system_message('Not connected')
            return
        msg = {
            'type': MessageType.CHAT,
            'username': self.username,
            'payload': {'text': text}
        }
        try:
            self.writer.write(encode_message(msg))
            # no await here; writer runs in event loop
        except Exception as e:
            logging.error(f'Failed to send: {e}')
            if self.ui:
                self.ui.add_system_message('Failed to send message')
