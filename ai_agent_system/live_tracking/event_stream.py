# ai_agent_system/live_tracking/event_stream.py

import asyncio
import json
from typing import Dict, Any, List
from sockets.agent_ws import connected_clients
from ai_agent_system.tracking.LiveTracker import payload

connected_clients: List[Any] = []

async def broadcast_event(event: Dict[str, Any]):
    """
    Sends an event to all connected frontend clients.
    """
    if not connected_clients:
        return

    message = json.dumps(event)
    disconnected = []
    for ws in connected_clients:
        try:
            await ws.send(message)
        except Exception:
            disconnected.append(ws)

    for ws in disconnected:
        connected_clients.remove(ws)


async def emit_event(event_type: str, payload: Dict[str, Any]):
    """
    Called by AI agent components (Executor, Planner, etc.) to push live events.
    """
    event = {
        "event": event_type,
        **payload
    }
    await broadcast_event(event)


def register_client(ws):
    connected_clients.append(ws)


def unregister_client(ws):
    if ws in connected_clients:
        connected_clients.remove(ws)  
