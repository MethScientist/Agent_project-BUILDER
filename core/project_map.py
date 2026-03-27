# core/project_map.py
from pathlib import Path
from typing import Dict, Any



from utils.ast_utils import get_defined_symbols
from core.lang_js import extract_js_exports
from core.lang_css import extract_css_class_names
from core.lang_cs import cs_exports
import json
import re

# optional YAML support; we try to import PyYAML if available
try:
    import yaml
except Exception:
    yaml = None

EXT_LANG_MAP = {
    ".py": "py",
    ".js": "js",
    ".mjs": "js",
    ".cjs": "js",
    ".ts": "js",
    ".jsx": "js",
    ".tsx": "js",
    ".css": "css",
    ".html": "html",
    ".htm": "html",
    ".json": "json",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".xml": "xml",
    ".php": "php",
    ".java": "java",
    ".c": "c",
    ".cpp": "c",
    ".h": "c",
    ".hpp": "c",
    ".go": "go",
    ".rs": "rust",
    ".cs": "cs",
}


def detect_lang_by_ext(path: Path) -> str:
    return EXT_LANG_MAP.get(path.suffix.lower(), "text")


def build_project_map(project_root: str) -> Dict[str, Any]:
    """
    Returns project_map: { "rel/path": {"lang": lang, "exports": [...], "raw": False} }
    `exports` is a list of exported symbols (or dicts for cs).
    """
    project_root = Path(project_root)
    out = {}
    for p in project_root.rglob("*"):
        if not p.is_file():
            continue
        # skip venvs
        path_str = str(p)
        if "site-packages" in path_str or "/.venv" in path_str or "/venv" in path_str:
            continue
        if "/.diffs/" in path_str or "/.backups/" in path_str or "/__pycache__/" in path_str:
            continue
        if "\\.diffs\\" in path_str or "\\.backups\\" in path_str or "\\__pycache__\\" in path_str:
            continue
        rel = p.relative_to(project_root).as_posix()
        lang = detect_lang_by_ext(p)
        exports = []
        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            continue
        try:
            if lang == "py":
                exports = sorted(list(get_defined_symbols(content)))

            elif lang == "js":
                exports = extract_js_exports(content)

            elif lang == "css":
                exports = extract_css_class_names(content)

            elif lang == "json":
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, dict):
                        exports = sorted(list(parsed.keys()))
                    else:
                        exports = []
                except Exception:
                    exports = []

            elif lang == "yaml":
                if yaml:
                    try:
                        parsed = yaml.safe_load(content)
                        if isinstance(parsed, dict):
                            exports = sorted(list(parsed.keys()))
                        else:
                            exports = []
                    except Exception:
                        exports = []
                else:
                    # simple fallback: top-level YAML keys
                    keys = re.findall(r'^\s*([A-Za-z0-9_.-]+)\s*:', content, re.M)
                    exports = sorted(set(keys))

            elif lang == "xml":
                tags = set(re.findall(r'<([A-Za-z0-9_:-]+)', content))
                exports = sorted(tags)

            elif lang == "php":
                classes = re.findall(r'class\s+([A-Za-z_]\w*)', content)
                funcs = re.findall(r'function\s+&?\s*([A-Za-z_]\w*)', content)
                exports = sorted(set(classes + funcs))

            elif lang == "java":
                classes = re.findall(r'\bclass\s+([A-Za-z_]\w*)', content)
                methods = re.findall(r'public\s+(?:static\s+)?[A-Za-z0-9_<>,\[\]]+\s+([A-Za-z_]\w*)\s*\(', content)
                exports = sorted(set(classes + methods))

            elif lang == "c":
                funcs = re.findall(r'\b([A-Za-z_]\w*)\s*\([^;{]*\)\s*\{', content)
                # filter out common keywords
                keywords = {"if", "for", "while", "switch", "return", "sizeof", "typedef"}
                funcs = [f for f in funcs if f not in keywords]
                exports = sorted(set(funcs))

            elif lang == "go":
                funcs = re.findall(r'\bfunc\s+([A-Za-z_]\w*)', content)
                exports = sorted(set(funcs))

            elif lang == "rust":
                funcs = re.findall(r'\bfn\s+([A-Za-z_]\w*)', content)
                exports = sorted(set(funcs))

            elif lang == "cs":
                # cs_exports returns mapping type -> namespace; store as list of dicts for lookup
                mapping = cs_exports(content)
                if mapping:
                    exports = [{"types": mapping}]  # structure: list with one dict

            else:
                exports = []
        except Exception:
            # non-fatal parsing errors; skip exports
            exports = []
        out[rel] = {"lang": lang, "exports": exports}
    return out

# ------------------ JSON helpers ------------------

def save_project_map(project_map: Dict[str, Any], path: str):
    """Save project map to JSON file"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(project_map, f, indent=2)
    print(f"[INFO] Project map saved to {path}")


def load_project_map(path: str) -> Dict[str, Any]:
    """Load project map from JSON file"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"[WARN] Project map file not found: {path}")
        return {}