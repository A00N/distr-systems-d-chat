"""Simple Tkinter GUI client for D-Chat.

Usage: python3 client/main.py --host <server-ip> --port 9001 --user alice
"""
import argparse, asyncio, threading, json, logging
from message_handler import ClientProtocol
from ui import ChatUI

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

def start_async_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=9001)
    parser.add_argument('--user', default='anon')
    args = parser.parse_args()

    loop = asyncio.new_event_loop()
    t = threading.Thread(target=start_async_loop, args=(loop,), daemon=True)
    t.start()

    protocol = ClientProtocol(loop, args.host, args.port, args.user)
    ui = ChatUI(username=args.user, send_callback=protocol.send_chat)
    protocol.set_ui(ui)
    loop.create_task(protocol.connect())

    ui.run()
