# context_awareness/representation.py

from typing import List, Dict


class FileContext:
    def __init__(self, name: str, role: str, dependencies: List[str] = None):
        self.name = name
        self.role = role
        self.dependencies = dependencies or []
        self.blocks: List[str] = []        # Track named code blocks
        self.code_snippets: List[str] = [] # Track appended code snippets
        
class ProjectContext:
    def __init__(self):
        self.project_files: Dict[str, FileContext] = {}  # key: filename
        self.active_file: str = None
        self.current_goal: str = ""
        self.history: List[str] = []

    def to_dict(self):
        return {
            "project_files": {f: vars(fc) for f, fc in self.project_files.items()},
            "active_file": self.active_file,
            "current_goal": self.current_goal,
            "history": self.history
        }
