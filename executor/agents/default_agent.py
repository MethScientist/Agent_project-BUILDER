# executor/agents/default_agent.py
import os
import asyncio
from ai_agent_system.live_tracking import LiveTracker
from executor.code_writer import write_file
from utils.logger import log_info



class DefaultAgent:
    async def run_step(self, step: dict):
        description = step.get("description", "")
        step_type = step.get("type")
        target_path = step.get("target_path")

        try:
            await LiveTracker.log(f"⚙️ [default] Starting: {description}")
            log_info(f"[default] ➤ {step_type}: {target_path}")

            if step_type == "create_folder":
                await self.create_folder(target_path)

            elif step_type == "create_file":
                await self.create_file(target_path)

            elif step_type == "implement_feature":
                await self.implement_feature(target_path, step)

            else:
                await LiveTracker.log(f"⚠️ Unknown step type: {step_type}")
                log_info(f"[default] ⚠️ Unknown step type: {step_type}")

            await LiveTracker.log(f"✅ [default] Completed: {description}")

        except Exception as e:
            await LiveTracker.log(f"❌ [default] Failed: {description} — {e}")
            log_info(f"[default] ❌ Failed: {e}")

    async def create_folder(self, path: str):
        os.makedirs(path, exist_ok=True)
        await LiveTracker.log(f"📁 Folder created: {path}")

    async def create_file(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # Do not write empty file; let CodeWriter write actual content during execution
        await LiveTracker.log(f"📄 File scheduled (dir ensured): {path}")

    async def implement_feature(self, path: str, step: dict):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        content = await self.generate_code(step)
        await write_file(path, content)
        await LiveTracker.log(f"💡 Feature implemented: {path}")

    async def generate_code(self, step: dict) -> str:
        # Use GPT or static stub for now
        return f"# {step['description']}\n\n# TODO: Implement this feature"
