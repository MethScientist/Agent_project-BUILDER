import asyncio
import os
import pytest

from planner.planner import Planner
from memory.memory_manager import MemoryManager


@pytest.mark.asyncio
async def test_planner_defers_writing(tmp_path, monkeypatch):
    proj = tmp_path / "proj"
    proj.mkdir()

    planner = Planner(memory_manager=MemoryManager(), context_manager=None, project_root=str(proj))

    # Fake GPT response returning a JSON plan with a create_file step that includes content
    plan_json = '[{"description": "Create index", "type":"create_file", "target_path":"index.html", "content":"<html>hi</html>"}]'

    async def fake_call_gpt(self, prompt):
        return plan_json

    monkeypatch.setattr(Planner, "_call_gpt", fake_call_gpt)

    plan = await planner.create_plan("Create an index.html file")

    # Ensure plan returned and that the step contains the content
    assert isinstance(plan, list)
    step = plan[0]
    assert step["type"] == "create_file"
    assert step.get("content") == "<html>hi</html>"

    # Planner should NOT have written the file to disk (deferred to executor)
    assert not (proj / "index.html").exists()
