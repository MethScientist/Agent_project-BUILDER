from pathlib import Path
import tempfile
from memory.memory_manager import MemoryManager
from planner.planner import Planner


def test_planner_normalizes_absolute_targets(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    planner = Planner(memory_manager=MemoryManager(), context_manager=None, project_root=str(proj))

    # Simulate a plan with absolute paths under project_root
    abs_path = str((proj / "subdir" / "file.txt").resolve())
    plan = [{"description": "Create file", "type": "create_file", "target_path": abs_path}]

    # Use top-level normalization used by planner
    for s in plan:
        if s.get("target_path"):
            s["target_path"] = planner._normalize_target_path(s.get("target_path"))

    assert not s["target_path"].startswith(str(proj))
    assert s["target_path"].startswith("subdir") or s["target_path"].startswith(".")
