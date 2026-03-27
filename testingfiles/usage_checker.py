import os
import ast
from collections import defaultdict



ENTRY_POINT_NAMES = {"main", "__init__"}

def find_all_python_files(root_dir):
    python_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".py") and filename != os.path.basename(__file__):
                full_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(full_path, root_dir).replace("\\", "/")
                module_name = rel_path[:-3].replace("/", ".")  # convert to package.module
                python_files.append((full_path, module_name))
    return python_files

def get_imports_from_file(file_path):
    imports = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except SyntaxError:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports

def get_entities_from_file(file_path):
    entities = {"functions": set(), "classes": set()}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
    except SyntaxError:
        return entities

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            entities["functions"].add(node.name)
        elif isinstance(node, ast.ClassDef):
            entities["classes"].add(node.name)
    return entities

def build_project_map(root_dir):
    files = find_all_python_files(root_dir)
    file_map = {module: path for path, module in files}

    imports_map = defaultdict(list)
    imported_by_map = defaultdict(list)
    entities_map = {}

    for file_path, module_name in files:
        imports = get_imports_from_file(file_path)
        entities_map[file_path] = get_entities_from_file(file_path)

        for imp in imports:
            for mod, mod_path in file_map.items():
                if imp == mod or imp.startswith(mod + "."):
                    imports_map[file_path].append(mod_path)
                    imported_by_map[mod_path].append(file_path)

    return imports_map, imported_by_map, entities_map

def print_project_map(imports_map, imported_by_map, entities_map):
    for file_path in sorted(entities_map.keys()):
        print(f"\n📄 {file_path}")
        print("   ├─ Imports:")
        if imports_map[file_path]:
            for imp in imports_map[file_path]:
                print(f"   │    → {imp}")
        else:
            print("   │    (none)")

        print("   ├─ Imported by:")
        if imported_by_map[file_path]:
            for user in imported_by_map[file_path]:
                print(f"   │    ← {user}")
        else:
            print("   │    (none)")

        print("   ├─ Classes:")
        if entities_map[file_path]["classes"]:
            for cls in entities_map[file_path]["classes"]:
                print(f"   │    🏷 {cls}")
        else:
            print("   │    (none)")

        print("   ├─ Functions:")
        if entities_map[file_path]["functions"]:
            for func in entities_map[file_path]["functions"]:
                print(f"   │    ⚙ {func}")
        else:
            print("   │    (none)")

if __name__ == "__main__":
    project_root = r"C:\Users\Hp\3D Objects\hope last"
    imports_map, imported_by_map, entities_map = build_project_map(project_root)
    print("\n📌 PROJECT ARCHITECTURE MAP")
    print_project_map(imports_map, imported_by_map, entities_map)
