# core/final_linker.py (update run)
from pathlib import Path
from core.project_map import build_project_map
from core.dependency_resolver import DependencyResolver


class FinalLinker:
    def __init__(self, project_root: str, project_map=None):
        self.project_root = Path(project_root)
        self.project_map = project_map or build_project_map(str(self.project_root))

    def run(self):
        resolver = DependencyResolver(self.project_map, str(self.project_root))
        for p in self.project_root.rglob('*'):
            if not p.is_file(): continue
            rel = p.relative_to(self.project_root).as_posix()
            try:
                src = p.read_text(encoding='utf-8')
            except Exception:
                continue
            patched = resolver.inject_imports(rel, src)
            if patched != src:
                p.write_text(patched, encoding='utf-8')
                print(f"Patched imports/assets into: {rel}")
