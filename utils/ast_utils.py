# ===== file: utils/ast_utils.py =====
"""
Small helpers to extract symbols from Python source using ast.
"""
import ast
import builtins
from typing import Set 


BUILTINS = set(dir(builtins))


def get_defined_symbols(source: str) -> Set[str]:
    tree = ast.parse(source)
    defs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef) or isinstance(node, ast.ClassDef):
            defs.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defs.add(target.id)
    return defs


def get_imported_symbols(source: str) -> Set[str]:
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                # import module as m  -> we consider module name
                name = n.asname or n.name.split(".")[0]
                imported.add(name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for n in node.names:
                asname = n.asname or n.name
                imported.add(asname)
    return imported


def get_used_names(source: str) -> Set[str]:
    tree = ast.parse(source)
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            used.add(node.id)
    return used


def find_undefined_names(source: str) -> Set[str]:
    defined = get_defined_symbols(source)
    imported = get_imported_symbols(source)
    used = get_used_names(source)
    # exclude builtins and private names
    candidates = set()
    for name in used:
        if name in BUILTINS:
            continue
        if name.startswith("_"):
            continue
        if name in defined:
            continue
        if name in imported:
            continue
        candidates.add(name)
    return candidates
