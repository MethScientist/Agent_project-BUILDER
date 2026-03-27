"""
core/python_fixer.py

Conservative, AST-based "safe" python fixer:
- Parses a file's AST
- Collects defined names (functions, classes, imports, assignments)
- Collects used names (Name nodes)
- For names that are used but not defined/imported/builtins, create small stubs:
    - If used as a call -> function stub
    - Otherwise -> class stub (conservative)
- Inserts stubs after top-level import block.

Returns modified content and a list of inserted stubs (for reporting).
"""

import ast
from typing import Tuple, List, Set
import builtins




def _collect_defined_names(tree: ast.AST) -> Set[str]:
    defined = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defined.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    defined.add(t.id)
        elif isinstance(node, ast.AnnAssign):
            t = node.target
            if isinstance(t, ast.Name):
                defined.add(t.id)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            # import a as b -> alias.asname or alias.name
            for alias in getattr(node, 'names', []):
                if alias.asname:
                    defined.add(alias.asname)
                else:
                    # import x.y -> name 'x' becomes defined at top-level
                    root = alias.name.split('.')[0]
                    defined.add(root)
    return defined


def _collect_used_names_and_calls(tree: ast.AST) -> Tuple[Set[str], Set[str]]:
    used = set()
    called = set()

    # We want to detect Name nodes that are loaded (used)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # function can be ast.Name or ast.Attribute; try to detect simple ast.Name calls
            func = node.func
            if isinstance(func, ast.Name):
                called.add(func.id)
            # else if Attribute (mod.func) we skip (can't stub reliably)
        elif isinstance(node, ast.Name):
            # Only consider usages in Load context
            if isinstance(getattr(node, "ctx", None), ast.Load):
                used.add(node.id)
    return used, called


def _find_insertion_line_for_stubs(tree: ast.AST, src_lines: List[str]) -> int:
    """
    Determine line number to insert stubs: after the last top-level import/encoding/comment block.
    Return index into src_lines (0-based) where insertion should happen.
    """
    last_import_lineno = -1
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            # lineno is 1-based
            last_import_lineno = max(last_import_lineno, getattr(node, "lineno", 0))
        else:
            # stop on first non-import top-level node
            break

    if last_import_lineno <= 0:
        # try to skip module docstring if present
        if (len(src_lines) > 0 and src_lines[0].strip().startswith(('"""', "'''"))):
            # find closing docstring
            for i in range(1, len(src_lines)):
                if src_lines[i].strip().endswith(('"""', "'''")):
                    return i + 1
        return 0
    return last_import_lineno  # insertion index (1-based), we'll convert to 0-based usage


def make_stub_for_name(name: str, assume_function: bool = True) -> str:
    if assume_function:
        return (
            f"\n\ndef {name}(*args, **kwargs):\n"
            f"    \"\"\"Auto-generated stub for missing function `{name}`.\"\"\"\n"
            f"    raise NotImplementedError('Stub: function {name} created by python_fixer')\n"
        )
    else:
        return (
            f"\n\nclass {name}:\n"
            f"    \"\"\"Auto-generated stub for missing class `{name}`.\"\"\"\n"
            f"    def __init__(self, *args, **kwargs):\n"
            f"        raise NotImplementedError('Stub: class {name} created by python_fixer')\n"
        )


def analyze_and_fix(content: str) -> Tuple[str, List[str]]:
    """
    Analyze Python source and insert minimal stubs for undefined names.
    Returns: (new_content, list_of_inserted_stub_names)
    """
    src_lines = content.splitlines()
    try:
        tree = ast.parse(content)
    except SyntaxError:
        # Don't attempt structural fixes for files with syntax errors here.
        # Higher-level GPT or human review should handle complex syntax errors.
        return content, []

    defined = _collect_defined_names(tree)
    used, called = _collect_used_names_and_calls(tree)

    builtins_set = set(dir(builtins))
    # also exclude common names likely from typing or kwargs
    excluded = builtins_set.union({"self", "__name__", "__file__", "__doc__"})

    # Names we might need to add (used but not defined/imported)
    missing = sorted(name for name in (used - defined - excluded) if not name.startswith("_"))

    if not missing:
        return content, []

    # Decide for each missing whether to assume function (if it appeared in calls)
    stubs = []
    for name in missing:
        is_call = name in called
        # Conservative decision: if it's called -> function stub, else class stub.
        stub_text = make_stub_for_name(name, assume_function=is_call)
        stubs.append((name, stub_text))

    # Find insertion point
    insert_after = _find_insertion_line_for_stubs(tree, src_lines)  # returns line number (1-based or 0)
    # convert to 0-based index
    insert_idx = max(0, insert_after)

    # Build new content by inserting stubs after top-level import block
    insertion_block = "\n".join(st for (_, st) in stubs).lstrip("\n")
    # If insertion_idx equals 0, put at start
    new_lines = src_lines[:insert_idx] + [insertion_block] + src_lines[insert_idx:]
    new_content = "\n".join(new_lines).rstrip() + "\n"

    inserted_names = [name for (name, _) in stubs]
    return new_content, inserted_names


# For quick testing
if __name__ == "__main__":
    sample = """
import os

def foo():
    print(bar())
"""
    new, names = analyze_and_fix(sample)
    print("Inserted:", names)
    print("New content:\n", new)
