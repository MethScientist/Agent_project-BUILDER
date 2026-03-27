# sockets/agent_ws.py

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter()

connected_clients = set()

@router.websocket("/ws/agent")
async def agent_activity_stream(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep connection open
    except WebSocketDisconnect:
        connected_clients.remove(websocket)

# Helper function to broadcast event
async def emit_event(event: dict):
    living_clients = set()
    for ws in connected_clients:
        try:
            await ws.send_json(event)
            living_clients.add(ws)
        except:
            pass
    connected_clients.clear()
    connected_clients.update(living_clients)
