# test_planner_debug.py
import asyncio
import json
import os
import traceback

# -----------------------------
# Set project root to 'output' folder
# -----------------------------
PROJECT_ROOT = os.path.join(os.getcwd(), "output")
os.makedirs(PROJECT_ROOT, exist_ok=True)
print(f"[INFO] Project root set to: {PROJECT_ROOT}")

# -----------------------------
# Mock dependencies BEFORE importing Planner
# -----------------------------
import executor.code_writer
import ai_models.unity_generator
import executor.agents.unity_agent

# -----------------------------
# Mocks with proper context_manager/project_root
# -----------------------------
class MockCodeWriter:
    def __init__(self, project_root=None, context_manager=None, **kwargs):
        self.project_root = project_root or PROJECT_ROOT
        self.context_manager = context_manager
        print(f"[MOCK] CodeWriter initialized at: {self.project_root}, kwargs: {kwargs}")

    async def write_file(self, path, content):
        full_path = os.path.join(self.project_root, path)
        print(f"[MOCK] write_file called: {full_path}")

    def insert_code_if_missing(self, path, code, identifier=None):
        full_path = os.path.join(self.project_root, path)
        print(f"[MOCK] insert_code_if_missing called: {full_path}")

class MockUnityGenerator:
    def __init__(self, project_root=None, context_manager=None, **kwargs):
        self.writer = MockCodeWriter(project_root=project_root, context_manager=context_manager)
        print("[MOCK] UnityGenerator initialized")

    def generate_script(self, class_name, logic=""):
        print(f"[MOCK] generate_script called: {class_name}")

class MockUnityAgent:
    def __init__(self, project_root=None, context_manager=None, **kwargs):
        self.generator = MockUnityGenerator(project_root=project_root, context_manager=context_manager)
        print("[MOCK] UnityAgent initialized")

class MockMemoryManager:
    def __init__(self):
        self.storage = {}
        print("[MOCK] MemoryManager initialized")

    def save_plan(self, plan):
        print("[MOCK] Plan saved:", json.dumps(plan, indent=2))

class MockContextManager:
    def __init__(self):
        self.files = {}
        print("[MOCK] ContextManager initialized")

    def load_context(self):
        print("[MOCK] Context loaded")

    def add_file(self, path, role="code"):
        print(f"[MOCK] File added: {path} (role={role})")
        self.files[path] = role

    def save_context(self):
        print("[MOCK] Context saved")

# -----------------------------
# Patch modules
# -----------------------------
executor.code_writer.CodeWriter = MockCodeWriter
ai_models.unity_generator.UnityGenerator = MockUnityGenerator
executor.agents.unity_agent.UnityAgent = MockUnityAgent

# -----------------------------
# Import Planner after patching
# -----------------------------
from planner.planner import Planner

# -----------------------------
# Mock GPT
# -----------------------------
async def mock_call_gpt(prompt):
    print("[MOCK GPT] Called with prompt (truncated):", prompt[:100])

    steps = [
        {
            "description": "Create utils.py file with helper functions",
            "type": "create_file",
            "target_path": "utils.py",
            "agent": "default",
            "id": "utils.py"
        }
    ]

    # Wrap in dict with "steps" key
    return {"steps": steps}

# -----------------------------
# Debug Test Runner
# -----------------------------
async def main():
    debug_stats = {
        "init": {},
        "plan_steps": 0,
        "context_files": 0,
        "execution_result": None,
        "errors": []
    }

    # Create mocks
    try:
        memory = MockMemoryManager()
        context = MockContextManager()
        debug_stats["init"]["MemoryManager"] = True
        debug_stats["init"]["ContextManager"] = True
    except Exception as e:
        debug_stats["errors"].append(f"Init mocks failed: {e}")

    # Initialize Planner
    try:
        planner = Planner(memory_manager=memory, context_manager=context, project_root=PROJECT_ROOT)
        planner._call_gpt = mock_call_gpt
        debug_stats["init"]["Planner"] = True
    except Exception as e:
        debug_stats["errors"].append(f"Planner init failed: {traceback.format_exc()}")

    # -----------------------------
    # Create plan
    # -----------------------------
    try:
        plan = await planner.create_plan("Add helper functions file")
        # Normalize plan to always be dict with 'steps'
        if isinstance(plan, list):
            plan = {"steps": plan}
        debug_stats["plan_steps"] = len(plan.get("steps", []))
    except Exception as e:
        debug_stats["errors"].append(f"create_plan failed: {traceback.format_exc()}")
        plan = {"steps": []}

    # Count context files
    try:
        debug_stats["context_files"] = len(context.files)
    except Exception as e:
        debug_stats["errors"].append(f"Counting context files failed: {e}")

    # Execute plan
    try:
        result = await planner.execute_plan(plan)
        debug_stats["execution_result"] = result
    except Exception as e:
        debug_stats["errors"].append(f"execute_plan failed: {traceback.format_exc()}")

    # Print summary
    print("\n===== DEBUG STATS =====")
    print(json.dumps(debug_stats, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
