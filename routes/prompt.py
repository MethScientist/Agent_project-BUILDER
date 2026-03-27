# server/routes/run_prompt_new.py
import os
import asyncio
import logging
import sys
import io
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

from config.settings import set_project_root
from ai_agent_system.tracking.LiveTracker import LiveTracker
from executor.executor import Executor

router = APIRouter()

# -------------------------
# Pydantic models
# -------------------------
class PromptRequest(BaseModel):
    prompt: str
    project_root: str

class PromptResponse(BaseModel):
    status: str
    logs: List[str]
    project_id: Optional[str] = None

class TaskStatusResponse(BaseModel):
    status: str
    logs: List[str]
    project_id: Optional[str] = None
    finished: bool = False

# -------------------------
# Task registry
# -------------------------
active_tasks = {}
last_task_status = {
    "project_id": None,
    "status": "idle",
    "logs": [],
    "finished": False
}

# -------------------------
# Logging setup
# -------------------------
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

def get_logger(task_id: str):
    logger = logging.getLogger(task_id)
    if not logger.handlers:
        # File handler with UTF-8 encoding to safely store emoji and unicode
        file_handler = logging.FileHandler(os.path.join(LOG_DIR, f"{task_id}.log"), encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Stream handler that wraps stdout with UTF-8 to avoid Windows cp1252 errors
        try:
            utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
            stream_handler = logging.StreamHandler(utf8_stdout)
        except Exception:
            # Fallback to default stream handler if wrapping fails
            stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

        # Prevent propagation to root handlers which may use a different encoding
        logger.propagate = False
        logger.setLevel(logging.INFO)
    return logger

# -------------------------
# Background task
# -------------------------
async def run_agent_task(task_id: str, request: PromptRequest):
    print("=== RUN_AGENT_TASK START ===")

    logger = get_logger(task_id)

    def log_info(msg: str):
        logger.info(msg)
        asyncio.create_task(LiveTracker.log(msg))

    try:
        log_info("Agent task started")
        log_info("[BOOT] AI Agent Booting...")
        last_task_status.update({
            "project_id": task_id,
            "status": "running",
            "logs": ["Agent task started"],
            "finished": False
        })

        # Validate project root
        if not os.path.isdir(request.project_root):
            msg = f"[ERROR] Invalid project root path: {request.project_root}"
            log_info(msg)
            last_task_status.update({
                "project_id": task_id,
                "status": "failed",
                "logs": [msg],
                "finished": True
            })
            return

        set_project_root(request.project_root)
        log_info(f"📁 Project root set to: {request.project_root}")

        # Executor with proper context management
        executor = Executor(project_root=request.project_root)
        log_info("✅ Executor created with context manager.")

        # Execute prompt safely
        print(">>> EXECUTOR START")

        await executor.execute_from_prompt(request.prompt)
        print(">>> EXECUTOR END")

        log_info("✅ All steps completed successfully!")
        last_task_status.update({
            "project_id": task_id,
            "status": "success",
            "logs": ["All steps completed successfully"],
            "finished": True
        })

        print("=== RUN_AGENT_TASK END ===")
    except Exception as e:
        msg = f"❌ Agent execution failed: {str(e)}"
        log_info(msg)
        last_task_status.update({
            "project_id": task_id,
            "status": "failed",
            "logs": [msg],
            "finished": True
        })

    finally:
        active_tasks.pop(task_id, None)
        log_info("[DONE] Task finished.")
        if last_task_status.get("project_id") == task_id:
            last_task_status["finished"] = True

# -------------------------
# API route
# -------------------------
@router.post("/run-prompt", response_model=PromptResponse)
async def run_prompt(request: PromptRequest):
    task_id = f"task-{len(active_tasks) + 1}"

    # Quick synchronous validation
    try:
        _ = request.dict()
    except Exception as e:
        return PromptResponse(
            status="failed",
            logs=[f"Initialization error: {str(e)}"],
            project_id=task_id
        )

    # Validate or create project root before starting background task
    try:
        if not os.path.isdir(request.project_root):
            os.makedirs(request.project_root, exist_ok=True)
        if not os.path.isdir(request.project_root):
            return PromptResponse(
                status="failed",
                logs=[f"Invalid project root path: {request.project_root}"],
                project_id=task_id
            )
    except Exception as e:
        return PromptResponse(
            status="failed",
            logs=[f"Project root error: {request.project_root} ({e})"],
            project_id=task_id
        )
    
    def task_done_callback(task: asyncio.Task):
        try:
            task.result()
        except Exception as e:
            print("❌ Background task crashed:", e)
    # Schedule background execution
    task = asyncio.create_task(run_agent_task(task_id, request))
    task.add_done_callback(task_done_callback)
    active_tasks[task_id] = task

    # Immediate response
    return PromptResponse(
        status="started",
        logs=["Agent started. Logs will be saved in the logs folder and streamed via LiveTracker."],
        project_id=task_id
    )


@router.get("/task-status/last", response_model=TaskStatusResponse)
async def last_task_status_endpoint():
    return TaskStatusResponse(**last_task_status)
