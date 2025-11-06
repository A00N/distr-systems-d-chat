"""High-level server node implementation (asyncio).

Responsibilities:
- Accept client connections (TCP)
- For workers: connect to coordinator
- For coordinator: accept worker connections and broadcast messages
- Maintain heartbeats and simple join/sync
"""
import asyncio
import logging
from message_protocol import MessageType, encode_message, decode_message
import time

class ServerNode:
    def __init__(self, host, port, mode, coordinator, peers, state, config=None):
        self.host = host
        self.port = port
        self.mode = mode
        self.coordinator = coordinator  # 'host:port' or None
        self.peers = peers or []  # list of 'host:port'
        self.state = state
        self.config = config or {}
        self.server = None
        self.clients = set()  # client writer streams
        self.workers = {}  # for coordinator: addr -> writer
        self.coordinator_writer = None  # for worker: writer to coordinator
        self._lock = asyncio.Lock()

    async def start(self):
        self.server = await asyncio.start_server(self._handle_connection, self.host, self.port)
        addr = self.server.sockets[0].getsockname()
        logging.info(f'Server started on {addr} as {self.mode}')
        # If worker, connect to coordinator
        if self.mode == 'worker' and self.coordinator:
            asyncio.create_task(self._connect_to_coordinator())
        # start heartbeat
        asyncio.create_task(self._heartbeat_loop())
        async with self.server:
            await self.server.serve_forever()

    async def _handle_connection(self, reader, writer):
        peer = writer.get_extra_info('peername')
        logging.info(f'Incoming connection from {peer}')
        # simple protocol: first message indicates role: CLIENT or SERVER (worker/coordinator)
        try:
            while not reader.at_eof():
                line = await reader.readline()
                if not line:
                    break
                try:
                    msg = decode_message(line.decode().strip())
                except Exception:
                    continue
                await self._process_message(msg, reader, writer)
        except ConnectionResetError:
            logging.info(f'Connection reset by {peer}')
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _process_message(self, msg, reader, writer):
        mtype = msg.get('type')
        if mtype == MessageType.CHAT:
            # client message received at this server
            await self._handle_chat(msg, writer)
        elif mtype == MessageType.FORWARD and self.mode == 'coordinator':
            # worker forwarded a chat to coordinator
            await self._handle_chat(msg, writer, forwarded=True)
        elif mtype == MessageType.BROADCAST:
            # inbound broadcast (coordinator -> workers) or coordinator's own delivery
            await self._deliver_to_local_clients(msg)
        elif mtype == MessageType.SYNC_REQ and self.mode == 'coordinator':
            since = msg.get('since_idx', 0)
            msgs = self.state.get_since_index(since)
            resp = {'type': MessageType.SYNC_RESP, 'messages': msgs}
            writer.write(encode_message(resp))
            await writer.drain()
        elif mtype == MessageType.HEARTBEAT:
            # respond optionally
            pass
        else:
            # ignore or log other messages
            logging.debug(f'Unknown message type: {mtype}')

    async def _handle_chat(self, msg, writer, forwarded=False):
        # Append to local state (coordinator is authoritative)
        if self.mode == 'worker' and not forwarded:
            # forward to coordinator
            if not self.coordinator_writer:
                logging.warning('No coordinator connection; cannot forward')
                return
            fmsg = dict(msg)
            fmsg['type'] = MessageType.FORWARD
            self.coordinator_writer.write(encode_message(fmsg))
            await self.coordinator_writer.drain()
            return
        # if coordinator or forwarded message at coordinator:
        idx = self.state.append(msg)
        bmsg = dict(msg)
        bmsg['type'] = MessageType.BROADCAST
        bmsg['index'] = idx
        # broadcast to workers and local clients
        await self._broadcast_to_workers(bmsg)
        await self._deliver_to_local_clients(bmsg)

    async def _broadcast_to_workers(self, msg):
        # coordinator broadcasts to connected workers
        if self.mode != 'coordinator':
            return
        to_remove = []
        for addr, w in list(self.workers.items()):
            try:
                w.write(encode_message(msg))
                await w.drain()
            except Exception as e:
                logging.warning(f'Error sending to worker {addr}: {e}')
                to_remove.append(addr)
        for addr in to_remove:
            del self.workers[addr]

    async def _deliver_to_local_clients(self, msg):
        # send BROADCAST message to directly connected clients
        to_remove = []
        for w in list(self.clients):
            try:
                w.write(encode_message(msg))
                await w.drain()
            except Exception as e:
                logging.warning(f'Error delivering to client: {e}')
                to_remove.append(w)
        for w in to_remove:
            self.clients.discard(w)

    async def _connect_to_coordinator(self):
        # persistent connection to coordinator for workers
        host, port = self.coordinator.split(':')
        port = int(port)
        while True:
            try:
                reader, writer = await asyncio.open_connection(host, port)
                self.coordinator_writer = writer
                logging.info(f'Connected to coordinator at {host}:{port}')
                # request full sync (index 0)
                req = {'type': MessageType.SYNC_REQ, 'since_idx': 0}
                writer.write(encode_message(req))
                await writer.drain()
                # read loop for coordinator responses
                while not reader.at_eof():
                    line = await reader.readline()
                    if not line:
                        break
                    msg = decode_message(line.decode().strip())
                    if not msg:
                        continue
                    mtype = msg.get('type')
                    if mtype == MessageType.BROADCAST:
                        await self._deliver_to_local_clients(msg)
                        self.state.append(msg)  # keep local copy
                    elif mtype == MessageType.SYNC_RESP:
                        for m in msg.get('messages', []):
                            self.state.append(m)
                    # other message handling
                logging.info('Coordinator connection closed, reconnecting...')
            except Exception as e:
                logging.warning(f'Failed to connect to coordinator: {e}')
            await asyncio.sleep(2)

    async def _heartbeat_loop(self):
        while True:
            # simple heartbeat placeholder
            await asyncio.sleep(5)
            # coordinator could broadcast heartbeat; workers could detect absence
            try:
                if self.mode == 'coordinator':
                    # no-op or log
                    pass
                else:
                    # if worker, optionally send heartbeat to coordinator
                    if self.coordinator_writer:
                        hb = {'type': MessageType.HEARTBEAT, 'ts': time.time()}
                        try:
                            self.coordinator_writer.write(encode_message(hb))
                            await self.coordinator_writer.drain()
                        except Exception:
                            self.coordinator_writer = None
            except Exception:
                pass
