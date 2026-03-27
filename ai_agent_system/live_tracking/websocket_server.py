# ai_agent_system/live_tracking/websocket_server.py

import asyncio
import websockets
import logging

from .event_stream import register_client, unregister_client

logging.basicConfig(level=logging.INFO)

HOST = "127.0.0.1"
PORT = 8000

async def handler(websocket, path):
    logging.info(f"Client connected: {websocket.remote_address}")
    register_client(websocket)

    try:
        await websocket.send("{\"event\":\"connected\"}")
        async for _ in websocket:
            # No incoming messages expected for now.
            pass
    except websockets.exceptions.ConnectionClosed:
        logging.info(f"Client disconnected: {websocket.remote_address}")
    finally:
        unregister_client(websocket)


def start_websocket_server():
    logging.info(f"Starting WebSocket server at ws://{HOST}:{PORT}/ws/live")
    start_server = websockets.serve(handler, HOST, PORT, path="/ws/live")
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__":
    start_websocket_server()
