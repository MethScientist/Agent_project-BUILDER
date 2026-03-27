# ai_agent_system/tracking/LiveTracker.py
import os
import asyncio
from typing import Optional, Dict, Any, List


# IMPORT: emit_event must be the async function in your tracker module that sends JSON to connected clients.
# Ensure server.tracker exports `emit_event(event: Dict[str, Any]) -> Coroutine`
from server.tracker import emit_event

# Config: maximum content size to send over WS (avoid huge payloads)
MAX_CONTENT_CHARS = 20_000

class LiveTracker:
    """Central place for agent to emit structured live events to the frontend via WebSocket.

    NOTE:
      - `emit_event` must be an async callable that sends JSON to connected websocket clients.
      - We `await` emit_event to preserve ordering. If you'd rather not block the agent,
        replace await emit_event(...) with asyncio.create_task(emit_event(...)) where ordering is not important.
    """

    @staticmethod
    async def _safe_emit(payload: Dict[str, Any], timeout: float = 2.0):
        """Call emit_event with basic timeout and error handling so the agent won't crash if WS is slow."""
        try:
            # wait up to `timeout` seconds for the emit to complete
            await asyncio.wait_for(emit_event(payload), timeout=timeout)
        except asyncio.TimeoutError:
            # emit timed out — don't raise to avoid breaking agent execution
            # You may optionally log locally here.
            try:
                # fallback: call without waiting (fire-and-forget)
                asyncio.create_task(emit_event(payload))
            except Exception:
                pass
        except Exception:
            # swallow to avoid propagation into agent flow, optionally log to local logger
            pass

    # --- Event methods that frontend expects ---

    @staticmethod
    async def log(message: str, level: str = "info"):
        """Generic textual log (info/warn/error)."""
        payload = {"type": "log", "level": level, "message": message}
        await LiveTracker._safe_emit(payload)

    @staticmethod
    async def thought(content: str):
        payload = {"type": "thought", "content": content}
        await LiveTracker._safe_emit(payload)

    @staticmethod
    async def thoughts(content: str):
        payload = {"type": "thoughts", "content": content}
        await LiveTracker._safe_emit(payload)

    @staticmethod
    async def plan(plan: List[Dict[str, Any]]):
        payload = {"type": "plan", "plan": plan}
        await LiveTracker._safe_emit(payload)

    @staticmethod
    async def step_created(step: Dict[str, Any]):
        payload = {"type": "step_created", "step": step}
        await LiveTracker._safe_emit(payload)

    @staticmethod
    async def file_created(path: str):
        payload = {"type": "file_created", "path": path}
        await LiveTracker._safe_emit(payload)

    @staticmethod
    async def folder_created(path: str):
        payload = {"type": "folder_created", "path": path}
        await LiveTracker._safe_emit(payload)

    @staticmethod
    async def code_written(path: str, content: str, language: Optional[str] = None):
        # Avoid sending extremely large payloads; truncate if needed and mark truncated
        truncated = False
        if content is None:
            content = ""
        if len(content) > MAX_CONTENT_CHARS:
            content = content[:MAX_CONTENT_CHARS]
            truncated = True
        payload = {
            "type": "code_written",
            "path": path,
            "content": content,
            "language": language or LiveTracker.detect_language(path),
            "truncated": truncated
        }
        await LiveTracker._safe_emit(payload)

    @staticmethod
    async def task_started(step_id: str, description: str, agent: str = "default"):
        payload = {
            "type": "task_started",
            "step_id": step_id,
            "description": description,
            "agent": agent
        }
        await LiveTracker._safe_emit(payload)

    @staticmethod
    async def task_progress(step_id: str, message: str, progress: Optional[float] = None):
        """Interim updates for a running step. progress (0..1) optional."""
        payload = {
            "type": "task_progress",
            "step_id": step_id,
            "message": message,
            "progress": progress
        }
        await LiveTracker._safe_emit(payload)

    @staticmethod
    async def task_completed(step_id: str, result: Optional[str] = None):
        payload = {
            "type": "task_completed",
            "step_id": step_id,
            "result": result
        }
        await LiveTracker._safe_emit(payload)

    @staticmethod
    async def task_failed(step_id: str, error: str):
        payload = {
            "type": "task_failed",
            "step_id": step_id,
            "error": error
        }
        await LiveTracker._safe_emit(payload)

    @staticmethod
    def detect_language(path: str) -> str:
        ext = os.path.splitext(path)[-1].lower()
        return {
            ".py": "python",
            ".tsx": "typescript",
            ".ts": "typescript",
            ".js": "javascript",
            ".html": "html",
            ".css": "css",
            ".json": "json",
            ".md": "markdown",
        }.get(ext, "text")
