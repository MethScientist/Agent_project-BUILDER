import sys
import os
import shutil
from pathlib import Path
import tempfile
from dotenv import dotenv

# Ensure repository root is importable when running test directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from context_awareness.manager import ContextManager
from memory.memory_manager import MemoryManager
from executor.step_executor import StepExecutor
from config import settings


def test_ensure_folder_and_change_directory(tmp_path):
    # Setup
    settings.SETTINGS["project_root"] = str(tmp_path)
    cm = ContextManager(save_path=str(Path(tmp_path) / "context_awareness" / "context.json"))
    cm.load_context()
    se = StepExecutor(memory_manager=MemoryManager(), context_manager=cm, project_root=str(tmp_path))

    # ensure_folder step with absolute path
    folder = tmp_path / "sub" / "project"
    step = {"type": "ensure_folder", "target_path": str(folder), "description": "Ensure nested folder"}
    res = None
    try:
        import asyncio
        res = asyncio.run(se.execute_step(step))
    except Exception as e:
        raise
    assert os.path.isdir(folder)

    # change_directory to that folder
    step_cd = {"type": "change_directory", "target_path": str(folder), "description": "Change root"}
    try:
        import asyncio
        asyncio.run(se.execute_step(step_cd))
    except Exception as e:
        raise

    assert os.path.abspath(se.project_root) == os.path.abspath(str(folder))

    # create_file within new root
    step_cf = {"type": "create_file", "target_path": "hello.txt", "content": "Hi", "description": "create file in new root"}
    import asyncio
    asyncio.run(se.execute_step(step_cf))
    assert (folder / "hello.txt").exists()
    with open(folder / "hello.txt", "r", encoding="utf-8") as f:
        assert "Hi" in f.read()
