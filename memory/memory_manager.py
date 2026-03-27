# memory/memory_manager.py
print("[START] memory.memory_manager module loaded", flush=True)
import os
import json
from config.settings import SETTINGS
from utils.logger import log_info


class MemoryManager:
    def __init__(self):
        print("[INIT] MemoryManager.__init__ start", flush=True)

        self.memory_path = SETTINGS["memory_file"]
        self.memory = {"plan": [], "done_steps": []}

        try:
            # Check file exists
            if not os.path.exists(self.memory_path):
                raise FileNotFoundError

            # Read file safely
            with open(self.memory_path, "r", encoding="utf-8") as f:
                content = f.read().strip()

            # Empty file? reinitialize
            if not content:
                raise ValueError("Memory file empty")

            # Parse JSON
            self.memory = json.loads(content)
            print("[MEMORY] loaded from disk", flush=True)

        except Exception as e:
            print(f"[MEMORY] failed to load memory, initializing new memory: {e}", flush=True)
            self.memory = {"plan": [], "done_steps": []}
            self._save()

        # Ensure required keys exist
        if not isinstance(self.memory, dict):
            self.memory = {}
        self.memory.setdefault("plan", [])
        self.memory.setdefault("done_steps", [])

    def _save(self):
        print("[MEMORY] _save writing to disk", flush=True)
        with open(self.memory_path, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, indent=4)
        log_info("💾 Memory updated.")
            
    def save_plan(self, plan):
        print("[MEMORY] save_plan called", flush=True)

        self.memory["plan"] = plan
        self._save()

    def is_step_done(self, step):
        print("[MEMORY] is_step_done called", flush=True)

        done = self.memory.get("done_steps", [])
        return step.get('description') in done

    def mark_step_done(self, step):
        print("[MEMORY] mark_step_done called", flush=True)

        self.memory.setdefault("done_steps", [])
        self.memory["done_steps"].append(step.get('description'))
        self._save()



