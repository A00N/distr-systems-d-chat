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
            # send JOIN to announce our username to the server
            try:
                join_msg = {'type': MessageType.JOIN, 'username': self.username}
                writer.write(encode_message(join_msg))
                await writer.drain()
            except Exception as e:
                logging.warning(f'Failed to send JOIN: {e}')
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
                # handle leave announcements from server
                if mtype == MessageType.LEAVE:
                    username = msg.get('username') or 'unknown'
                    if self.ui:
                        try:
                            self.ui.remove_user_connected(username)
                        except Exception:
                            self.ui.add_system_message(f"{username} disconnected")
                    continue
                # handle join announcements from server
                if mtype == MessageType.JOIN:
                    username = msg.get('username') or 'unknown'
                    if self.ui:
                        # show a simple '<username> connected' line
                        try:
                            self.ui.add_user_connected(username)
                        except Exception:
                            # fallback to system message if UI doesn't support it
                            self.ui.add_system_message(f"{username} connected")
                    continue
                if mtype == MessageType.BROADCAST or mtype == MessageType.CHAT:
                    username = msg.get('username') or msg.get('sender') or 'unknown'
                    text = msg.get('payload', {}).get('text') or msg.get('msg') or ''
                    if self.ui:
                        self.ui.add_message(username, text)
            except Exception:
                break
        if self.ui:
            self.ui.add_system_message('Disconnected from server')

    def send_leave(self):
        """Send a LEAVE message and close the writer (safe to call from UI thread)."""
        if not self.writer:
            return
        msg = {'type': MessageType.LEAVE, 'username': self.username}
        data = encode_message(msg)
        # schedule send and close on the asyncio loop
        asyncio.run_coroutine_threadsafe(self._async_send_and_close(data), self.loop)

    async def _async_send_and_close(self, data: bytes):
        try:
            self.writer.write(data)
            await self.writer.drain()
        except Exception:
            pass
        try:
            self.writer.close()
            await self.writer.wait_closed()
        except Exception:
            pass

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
        data = encode_message(msg)
        # run the actual write in the asyncio event loop thread
        asyncio.run_coroutine_threadsafe(self._async_send(data), self.loop)

    async def _async_send(self, data: bytes):
        try:
            self.writer.write(data)
            await self.writer.drain()
        except Exception as e:
            logging.error(f'Failed to send: {e}')
            if self.ui:
                self.ui.add_system_message('Failed to send message')
