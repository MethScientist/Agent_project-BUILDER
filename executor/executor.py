# executor/executor.py
print("[START] executor.executor module loaded", flush=True)

import os
import asyncio
from context_awareness.manager import ContextManager
from ai_agent_system.tracking.LiveTracker import LiveTracker
from planner.planner import Planner
from executor.step_executor import StepExecutor
from memory.memory_manager import MemoryManager
from utils.logger import log_info
from server.tracker import emit_event  # important for live WebSocket updates

class Executor:
    def __init__(self, project_root: str):
        print("[INIT] Executor.__init__ start", flush=True)

        self.project_root = project_root

        # Memory
        self.memory = MemoryManager()

        # Context awareness
        self.context_manager = ContextManager()
        # Preload existing project files into context
        self._preload_project_files()
        # Load any previously saved context (merge with preloaded files)
        self.context_manager.load_context()

        # Planner now uses executor's context
        self.planner = Planner(
            memory_manager=self.memory,
            context_manager=self.context_manager,
            project_root=self.project_root
        )

        # Step executor also uses the same context manager
        self.step_executor = StepExecutor(
            memory_manager=self.memory,
            context_manager=self.context_manager
        )

        print("[INIT] Executor.__init__ end", flush=True)
        
    def _preload_project_files(self):
        """Scan project root and add all existing files to context."""
        for root, _, files in os.walk(self.project_root):
            for f in files:
                filepath = os.path.relpath(os.path.join(root, f), self.project_root)
                self.context_manager.add_file(filepath, role="code")

    async def execute_from_prompt(self, prompt: str):
        """Plan and execute steps from a user prompt, with live tracking and context updates."""
        print("[ASYNC ENTER] execute_from_prompt", flush=True)
        log_info("🧠 Starting execution from user prompt.")

        # Step 1: Generate plan via Planner
        plan = await self.planner.create_plan(prompt)
        print(f"[PLAN] Created {len(plan)} steps", flush=True)

        # Save plan to memory
        self.memory.save_plan(plan)

        # Step 2: Execute steps one by one
        for index, step in enumerate(plan):
            step_id = step.get("id", f"step-{index}")
            description = step.get("description", "<no description>")
            target_path = step.get("target_path", "")
            agent = step.get("agent", "default")

            # Emit: step started
            await LiveTracker.task_started(step_id, description, agent)
            await emit_event({
                "type": "task_started",
                "step_id": step_id,
                "description": description,
                "agent": agent,
                "target_path": target_path
            })

            # Progress update
            await LiveTracker.task_progress(step_id, "Starting step...")
            await emit_event({
                "type": "task_progress",
                "step_id": step_id,
                "message": "Starting step",
                "progress": 0.0
            })

            try:
                print(f"[EXEC] Running step {step_id}", flush=True)

                # Execute the step
                await self.step_executor.execute_step(step)

                # Update context if new files are created
                if target_path and step.get("type") in ("create_file", "create_class", "create_function"):
                    self.context_manager.add_file(target_path, role=step.get("type"))

                # Save context after each step
                self.context_manager.save_context()

                # Mark step done in memory
                self.memory.mark_step_done(step)

                # Emit: step completed
                result_msg = f"Completed: {target_path or description}"
                await LiveTracker.task_completed(step_id, result_msg)
                await emit_event({
                    "type": "task_completed",
                    "step_id": step_id,
                    "result": result_msg
                })

                print(f"[EXEC OK] Step {step_id} completed", flush=True)

            except Exception as e:
                print(f"[EXEC ERROR] Step {step_id}: {e}", flush=True)
                err = str(e)

                # Emit: step failed
                await LiveTracker.task_failed(step_id, err)
                await emit_event({
                    "type": "task_failed",
                    "step_id": step_id,
                    "error": err
                })

        print("[EXEC] All steps finished", flush=True)
        log_info("✅ Execution complete.")

        # Optionally emit a final summary
        await LiveTracker.log("All steps finished.", "info")
        await emit_event({"type": "summary", "detail": {"status": "done"}})
