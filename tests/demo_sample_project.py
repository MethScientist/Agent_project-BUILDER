# ===== file: tests/demo_sample_project.py =====
"""
Small demo that shows how the pieces work together.
Run it as a script to create a small sample project and auto-inject imports.
"""
import shutil
from pathlib import Path
from core.project_map import build_project_map
from core.dependency_resolver import DependencyResolver


def make_demo(tmpdir: Path):
    # create files that reference each other without imports
    (tmpdir / 'models').mkdir(parents=True, exist_ok=True)
    (tmpdir / 'services').mkdir(parents=True, exist_ok=True)

    models_user = """
class User:
    def __init__(self, id):
        self.id = id
"""
    (tmpdir / 'models' / 'user.py').write_text(models_user)

    auth_code = """

def login(user_id):
    u = User(user_id)
    return u.id
"""
    (tmpdir / 'services' / 'auth.py').write_text(auth_code)

    pm = build_project_map(str(tmpdir))
    print('project_map:', pm)
    resolver = DependencyResolver(pm, str(tmpdir))
    source = (tmpdir / 'services' / 'auth.py').read_text()
    patched = resolver.inject_imports('services/auth.py', source)
    print('patched source:\n', patched)


if __name__ == '__main__':
    import tempfile
    t = Path(tempfile.mkdtemp())
    try:
        make_demo(t)
    finally:
        # cleanup for repeated runs
        shutil.rmtree(str(t))