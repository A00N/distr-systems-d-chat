import asyncio
import json
import argparse

async def handle(reader, writer, clients):
    addr = writer.get_extra_info('peername')
    clients.add(writer)
    print("Client connected:", addr)
    print(clients)
    try:
        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                # pass through whatever JSON line the client sends
                obj = json.loads(line.decode().strip())
            except Exception:
                # ignore non-json lines
                continue
            # Broadcast the exact line to all connected clients (with newline)
            for w in set(clients):
                try:
                    w.write((json.dumps(obj) + "\n").encode())
                    await w.drain()
                except Exception:
                    clients.discard(w)
    finally:
        clients.discard(writer)
        writer.close()
        await writer.wait_closed()
        print("Client disconnected:", addr)

async def main(host, port):
    clients = set()
    server = await asyncio.start_server(lambda r, w: handle(r, w, clients), host, port)
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    print(f"Serving on {addrs}")
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=9001)
    args = p.parse_args()
    asyncio.run(main(args.host, args.port))