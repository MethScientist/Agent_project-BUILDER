import os
import ast
import sys
import json
from collections import defaultdict

from planner.topological_sort import graph

from usage_checker import files

from usage_checker import imports
from core.lang_cs import m
from planner.topological_sort import node
from templates import root

PROJECT_ROOT = sys.argv[1] if len(sys.argv) > 1 else "."

REPORT = {
    "stats": {},
    "syntax_errors": [],
    "import_errors": [],
    "circular_imports": [],
    "missing_modules": set(),
    "unused_files": [],
    "entry_points": [],
}

py_files = []
imports_map = defaultdict(set)
defined_modules = set()

# --------------------------------------------------
# Scan files
# --------------------------------------------------
for root, _, files in os.walk(PROJECT_ROOT):
    for file in files:
        if file.endswith(".py"):
            full_path = os.path.join(root, file)
            py_files.append(full_path)
            module_name = os.path.relpath(full_path, PROJECT_ROOT).replace(os.sep, ".").replace(".py", "")
            defined_modules.add(module_name)

REPORT["stats"]["total_python_files"] = len(py_files)

# --------------------------------------------------
# Analyze each file
# --------------------------------------------------
for file in py_files:
    try:
        with open(file, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)
        module_name = os.path.relpath(file, PROJECT_ROOT).replace(os.sep, ".").replace(".py", "")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    imports_map[module_name].add(n.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports_map[module_name].add(node.module.split(".")[0])

        # Detect entry points
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                if isinstance(node.test, ast.Compare):
                    REPORT["entry_points"].append(module_name)

    except SyntaxError as e:
        REPORT["syntax_errors"].append({
            "file": file,
            "line": e.lineno,
            "error": str(e)
        })
    except Exception as e:
        REPORT["import_errors"].append({
            "file": file,
            "error": str(e)
        })

# --------------------------------------------------
# Missing modules
# --------------------------------------------------
for mod, imports in imports_map.items():
    for imp in imports:
        if imp not in defined_modules:
            try:
                __import__(imp)
            except Exception:
                REPORT["missing_modules"].add(imp)

REPORT["missing_modules"] = list(REPORT["missing_modules"])

# --------------------------------------------------
# Circular imports
# --------------------------------------------------
def detect_cycles(graph):
    visited = set()
    stack = set()
    cycles = []

    def visit(node):
        if node in stack:
            cycles.append(node)
            return
        if node in visited:
            return
        visited.add(node)
        stack.add(node)
        for neigh in graph[node]:
            if neigh in graph:
                visit(neigh)
        stack.remove(node)

    for node in graph:
        visit(node)
    return cycles

REPORT["circular_imports"] = detect_cycles(imports_map)

# --------------------------------------------------
# Unused files
# --------------------------------------------------
used = set()
for imports in imports_map.values():
    used |= imports

for mod in defined_modules:
    if mod.split(".")[0] not in used and "main" not in mod:
        REPORT["unused_files"].append(mod)

# --------------------------------------------------
# Output report
# --------------------------------------------------
print("\n====== PROJECT DIAGNOSTIC REPORT ======\n")

print("📊 Stats")
for k, v in REPORT["stats"].items():
    print(f" - {k}: {v}")

print("\n❌ Syntax Errors:")
for e in REPORT["syntax_errors"]:
    print(e)

print("\n📦 Missing Modules:")
for m in REPORT["missing_modules"]:
    print(" -", m)

print("\n🔁 Circular Imports:")
for c in REPORT["circular_imports"]:
    print(" -", c)

print("\n🧹 Unused Files:")
for u in REPORT["unused_files"]:
    print(" -", u)

with open("diagnostic_report.json", "w", encoding="utf-8") as f:
    json.dump(REPORT, f, indent=2)

print("\n✅ Full report saved to diagnostic_report.json")
