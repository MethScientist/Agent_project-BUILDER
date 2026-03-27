import asyncio
import os
import tempfile
import shutil

from planner.planner import Planner
from memory.memory_manager import MemoryManager
from config import settings
from executor.file_creator import FileCreator


def run_planner_check():
    tmp = tempfile.mkdtemp()
    try:
        planner = Planner(memory_manager=MemoryManager(), context_manager=None, project_root=tmp)

        async def fake_call_gpt(self, prompt):
            return '[{"description": "Create index", "type":"create_file", "target_path":"index.html", "content":"<html>hi</html>"}]'

        # Monkeypatch Planner._call_gpt
        Planner._call_gpt = fake_call_gpt

        plan = asyncio.run(planner.create_plan("Create an index.html file"))
        print("plan:", plan)

        assert isinstance(plan, list)
        step = plan[0]
        assert step["type"] == "create_file"
        assert step.get("content") == "<html>hi</html>"
        assert not os.path.exists(os.path.join(tmp, "index.html"))
        print("Planner check passed")
    finally:
        shutil.rmtree(tmp)


def run_file_creator_check():
    tmp = tempfile.mkdtemp()
    try:
        settings.SETTINGS["project_root"] = tmp
        fc = FileCreator()
        target = os.path.join(fc.project_root, "a.txt")
        with open(target, "w", encoding="utf-8") as f:
            f.write("original content")
        fc.create_file("a.txt", content=None)
        with open(target, "r", encoding="utf-8") as f:
            data = f.read()
        assert data == "original content"
        print("FileCreator check passed")
    finally:
        shutil.rmtree(tmp)


if __name__ == '__main__':
    run_planner_check()
    run_file_creator_check()
