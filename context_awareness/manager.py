# context_awareness/manager.py

import json
from .representation import ProjectContext, FileContext


class ContextManager:
    def __init__(self, save_path="context_awareness/context.json"):
        self.context = ProjectContext()
        self.save_path = save_path

    def add_file(self, filename: str, role: str, dependencies=None):
        if filename not in self.context.project_files:
            self.context.project_files[filename] = FileContext(filename, role, dependencies)
        else:
            # update role or dependencies if needed
            fc = self.context.project_files[filename]
            fc.role = role
            fc.dependencies = dependencies or fc.dependencies

    def set_active_file(self, filename: str):
        self.context.active_file = filename

    def update_goal(self, goal: str):
        self.context.current_goal = goal

    def add_history(self, action: str):
        self.context.history.append(action)

    def save_context(self):
        import os
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)

        with open(self.save_path, "w") as f:
            json.dump(self.context.to_dict(), f, indent=2)


    def load_context(self):
        try:
            with open(self.save_path, "r") as f:
                data = json.load(f)

            self.context.project_files = {}

            for fname, fdata in data.get("project_files", {}).items():
                fc = FileContext(
                    name=fname,
                    role=fdata.get("role"),
                    dependencies=fdata.get("dependencies", [])
                )
                fc.blocks = fdata.get("blocks", [])
                fc.code_snippets = fdata.get("code_snippets", [])
                self.context.project_files[fname] = fc

            self.context.active_file = data.get("active_file")
            self.context.current_goal = data.get("current_goal", "")
            self.context.history = data.get("history", [])

        except FileNotFoundError:
            pass

    # --- New methods for CodeWriter ---
    def get_file_info(self, filename: str):
        """Return FileContext as dict or None"""
        fc = self.context.project_files.get(filename)
        if fc:
            return {
                "filename": fc.name,
                "role": fc.role,
                "dependencies": fc.dependencies,
                "blocks": fc.blocks,
                "code_snippets": fc.code_snippets
            }
        return None

    def add_file_block(self, filename: str, identifier: str):
        fc = self.context.project_files.get(filename)
        if not fc:
            fc = FileContext(filename, role="code")
            self.context.project_files[filename] = fc
        if identifier not in fc.blocks:
            fc.blocks.append(identifier)

    def add_file_code(self, filename: str, code: str):
        fc = self.context.project_files.get(filename)
        if not fc:
            fc = FileContext(filename, role="code")
            self.context.project_files[filename] = fc
        fc.code_snippets.append(code)