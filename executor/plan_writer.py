# executor/plan_writer.py

import os
from config.settings import SETTINGS
from utils.logger import log_info


class PlanWriter:
    def __init__(self):
        self.project_root = os.path.abspath(SETTINGS["project_root"])
        os.makedirs(self.project_root, exist_ok=True)

    # write plan to file means write the code into file before some other stuff
    def write_plan_to_files(self, plan):
        """
        plan format example:
        [
            {"path": "templates/index.html", "content": "<!DOCTYPE html>..."},
            {"path": "static/style.css", "content": "body { ... }"},
            {"path": "scripts/main.js", "content": "console.log('Hello');"}
        ]
        """
        for item in plan:
            rel_path = item["path"].lstrip("/\\")  # remove leading slashes
            full_path = os.path.join(self.project_root, rel_path)
            folder = os.path.dirname(full_path)
            os.makedirs(folder, exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(item.get("content", ""))

            log_info(f"✅ Wrote file: {full_path}")

