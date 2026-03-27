import os
from config import settings
from executor.file_creator import FileCreator


def test_file_creator_ensure_does_not_overwrite(tmp_path):
    # Point SETTINGS to temporary project root
    settings.SETTINGS["project_root"] = str(tmp_path)

    fc = FileCreator()

    # Create a file with initial content
    target = tmp_path / "a.txt"
    with open(target, "w", encoding="utf-8") as f:
        f.write("original content")

    # Call create_file with content=None to ensure it does not overwrite
    fc.create_file("a.txt", content=None)

    with open(target, "r", encoding="utf-8") as f:
        assert f.read() == "original content"
