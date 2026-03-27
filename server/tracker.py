# server/tracker.py
print("[DEBUG] tracker module loaded")

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any
import uvicorn
import asyncio


app = FastAPI()

# Allow cross-origin for frontend testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store connected clients
clients: List[WebSocket] = []
clients_lock = asyncio.Lock()
@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    print("[DEBUG] websocket_endpoint entered")

    await websocket.accept()  # accept connection immediately

    async with clients_lock:
        clients.append(websocket)
        print("[DEBUG] Client added. Total:", len(clients))

    print("🔌 Client connected")

    try:
        while True:
            await asyncio.sleep(10)  # keep connection alive
    except WebSocketDisconnect:
        async with clients_lock:
            if websocket in clients:
                clients.remove(websocket)
        print("❌ Client disconnected")
    except Exception as e:
        print(f"❌ WebSocket error: {e}")
        async with clients_lock:
            if websocket in clients:
                clients.remove(websocket)
                
async def emit_event(event: Dict[str, Any]):
    print(f"[DEBUG] emit_event called: type={event.get('type')}, keys={list(event.keys())}")

    if not clients:
        return

    # Copy clients under lock (VERY important)
    async with clients_lock:
        current_clients = clients.copy()

    disconnected = []

    for client in current_clients:
        try:
            await client.send_json(event)
            print("[DEBUG] Sent event to client")
        except Exception as e:
            print(f"[DEBUG] Client send failed: {e}")
            disconnected.append(client)

    # Cleanup disconnected clients
    if disconnected:
        async with clients_lock:
            for client in disconnected:
                if client in clients:
                    clients.remove(client)

    # Yield control safely
    await asyncio.sleep(0)


@app.on_event("startup")
async def startup_event():
    print("[DEBUG] tracker startup_event triggered")

    """
    Test message on server startup to confirm WebSocket is alive.
    """
    async def test_emit():
        await asyncio.sleep(1)
        await emit_event({
            "type": "startup",
            "detail": {"message": "Tracker WebSocket is live!"}
        })
    asyncio.create_task(test_emit())

if __name__ == "__main__":
    print("🚀 Tracker running at ws://localhost:8000/ws")
    uvicorn.run("server.tracker:app", host="0.0.0.0", port=8000, reload=True)
