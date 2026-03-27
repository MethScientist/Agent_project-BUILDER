import sys
import asyncio
import os
import tempfile
import shutil
from pathlib import Path

# ensure repo root is on sys.path for local imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from executor.step_executor import StepExecutor
from memory.memory_manager import MemoryManager
from config import settings
from context_awareness.manager import ContextManager


def run_executor_create_file_check():
    tmp = tempfile.mkdtemp()
    try:
        settings.SETTINGS["project_root"] = tmp
        cm = ContextManager(save_path=str(Path(tmp) / "context_awareness" / "context.json"))
        cm.load_context()
        se = StepExecutor(memory_manager=MemoryManager(), context_manager=cm, project_root=tmp)
        step = {"type": "create_file", "target_path": "index.html", "content": "<html>hello</html>", "description": "Create homepage"}
        asyncio.run(se.execute_step(step))
        path = os.path.join(tmp, "index.html")
        assert os.path.exists(path)
        with open(path, "r", encoding="utf-8") as f:
            data = f.read()
        assert "<html>hello</html>" in data
        print("Executor create_file check passed")
    finally:
        shutil.rmtree(tmp)


if __name__ == '__main__':
    run_executor_create_file_check()
