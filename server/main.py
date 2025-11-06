"""Entry point for server node (coordinator or worker).

Coordinator mode: holds the authoritative chat log and broadcasts to workers.
Worker mode: accepts clients, forwards client messages to coordinator and optionally to peers.
"""
import argparse
import asyncio
import json
import logging
from message_protocol import MessageType, encode_message, decode_message
from node_manager import ServerNode
from state_manager import ChatState
from utils import load_config

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(message)s')

async def main(args):
    config = {}
    if args.config:
        config = load_config(args.config)
    state = ChatState(storage_path=config.get('storage_path', f'chat_log_{args.port}.jsonl'))
    node = ServerNode(host=args.host, port=args.port, mode=args.mode,
                      coordinator=args.coordinator, peers=args.peers, state=state, config=config)
    await node.start()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['coordinator','worker'], required=True)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=9000)
    parser.add_argument('--config', help='path to config json', default=None)
    parser.add_argument('--coordinator', help='coordinator host:port', default=None)
    parser.add_argument('--peers', help='comma separated peer host:port', default='')
    args = parser.parse_args()

    # normalize peers
    if args.peers:
        args.peers = [p.strip() for p in args.peers.split(',') if p.strip()]
    else:
        args.peers = []
    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print('Shutting down...')
