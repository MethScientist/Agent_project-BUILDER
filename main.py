# main.py
import os
import asyncio
from dotenv import load_dotenv
from fastapi.responses import HTMLResponse, Response, FileResponse, RedirectResponse


from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.templating import Jinja2Templates
from starlette.routing import Route

# Internal imports
from account.models import Base
from account.database import engine
from auth.auth import router as auth_router
from routes import user 
from planner.planner import Planner
from executor.step_executor import StepExecutor
from memory.memory_manager import MemoryManager
from ai_agent_system.tracking.LiveTracker import LiveTracker
from utils.logger import log_info
from utils.error_handler import handle_error
from sockets.agent_ws import router as agent_ws_router
from routes.prompt import router as prompt_router
from templates import router as templates_router
from api_diff import router as diff_router


# Load .env
load_dotenv()

# Initialize app
app = FastAPI()

# Static and Templates
app.mount("/static", StaticFiles(directory="web/static"), name="static")
templates = Jinja2Templates(directory="web/templates")

# DB setup
Base.metadata.create_all(bind=engine)

# Middleware
origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",  # ✅ correct
]
app.add_middleware(SessionMiddleware, secret_key="your_secret_key")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ only for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth_router)
app.include_router(user.router)
app.include_router(prompt_router)
app.include_router(agent_ws_router)
app.include_router(templates_router)
app.include_router(diff_router)

@app.get("/")
async def home(request: Request):
    user_email = request.cookies.get("user_email")
    if user_email:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("index.html", {"request": request})



@app.on_event("startup")
def list_routes():
    for route in app.router.routes:
        if isinstance(route, Route):
            print(f"{route.path} -> {route.endpoint}")
        else:
            print(f"{route.path} -> (non-standard route, type: {type(route).__name__})")

@app.options("/{path:path}")
async def preflight_handler():
    return Response(status_code=200)


# WebSocket Test (Optional)
@app.websocket("/ws/test")
async def test_websocket(websocket: WebSocket):
    await websocket.accept()
    for i in range(3):
        await websocket.send_text(f"[TEST EVENT {i}] Hello from WebSocket")
        await asyncio.sleep(1)
    await websocket.close()

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            print("Received:", data)
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print("WebSocket error:", e)

# CLI prompt runner (optional)
async def run_agent_prompt():
    log_info("🧠 AI Agent Booting...")
    await LiveTracker.log("🧠 AI Agent Booting...")

    try:
        memory = MemoryManager()
        planner = Planner(memory)
        executor = StepExecutor(memory)

        user_prompt = input("💬 What do you want to build? ")
        await LiveTracker.log(f"💬 Prompt received: {user_prompt}")

        plan = await planner.create_plan(user_prompt)
        memory.save_plan(plan)

        for step in plan:
            if not memory.is_step_done(step):
                log_info(f"🚧 Executing: {step['description']}")
                await LiveTracker.task_started(
                    step_id=step.get("id", step['description']),
                    description=step["description"],
                    agent=step.get("agent", "default")
                )
                await executor.execute_step(step)
                memory.mark_step_done(step)

        await LiveTracker.log("✅ All steps completed!")
        log_info("✅ All steps completed!")

    except Exception as e:
        handle_error(e)
        await LiveTracker.log(f"❌ Agent failed: {str(e)}")

# Main entrypoint
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
