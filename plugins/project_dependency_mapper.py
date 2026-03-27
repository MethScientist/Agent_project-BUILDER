import os
import ast
import networkx as nx
import matplotlib.pyplot as plt
from pyvis.network import Network

from core.final_linker import src



# ----------------------------
# CONFIG
# ----------------------------
OUTPUT_PNG = "project_dependencies.png"
OUTPUT_HTML = "project_dependencies.html"

# ----------------------------
# FILE SCAN
# ----------------------------
def scan_imports(project_path):
    dependencies = []
    for root, _, files in os.walk(project_path):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read(), filename=filepath)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                dependencies.append((file, alias.name))
                        elif isinstance(node, ast.ImportFrom) and node.module:
                            dependencies.append((file, node.module))
                except Exception:
                    pass
    return dependencies

# ----------------------------
# PROBLEM DETECTION
# ----------------------------
def detect_problem_areas(G):
    cycles = list(nx.simple_cycles(G.to_directed()))
    high_conn = [node for node, degree in G.degree() if degree > 5]
    isolated = list(nx.isolates(G))
    return cycles, high_conn, isolated

# ----------------------------
# PNG DRAW
# ----------------------------
def save_png(G, cycles, high_conn, isolated):
    pos = nx.spring_layout(G, seed=42)
    plt.figure(figsize=(12, 8), facecolor="black")
    node_colors = []
    for node in G.nodes():
        if any(node in cycle for cycle in cycles):
            node_colors.append("red")
        elif node in high_conn:
            node_colors.append("orange")
        elif node in isolated:
            node_colors.append("gray")
        else:
            node_colors.append("skyblue")
    nx.draw(G, pos, with_labels=True, node_color=node_colors, font_color="white", edge_color="white")
    plt.title("Project Dependency Map", color="white")
    plt.savefig(OUTPUT_PNG, facecolor="black", dpi=300)
    plt.close()

# ----------------------------
# INTERACTIVE HTML
# ----------------------------
def save_html(G, cycles, high_conn, isolated, output_path):
    net = Network(height="100%", width="100%", bgcolor="#111", font_color="white", directed=True)
    net.barnes_hut(gravity=-30000, central_gravity=0.3, spring_length=150)

    for node in G.nodes():
        color = "skyblue"
        if any(node in cycle for cycle in cycles):
            color = "red"
        elif node in high_conn:
            color = "orange"
        elif node in isolated:
            color = "gray"
        net.add_node(node, label=node, color=color)

    for source, target in G.edges():
        net.add_edge(source, target)

    # Save base HTML
    net.save_graph(output_path)

    # Inject layout switcher JS
    with open(output_path, "r", encoding="utf-8") as f:
        html_data = f.read()

    layout_buttons = """
    <div style="position: fixed; top: 10px; left: 10px; z-index: 9999;">
        <button onclick="setForce()" style="padding:5px;">Force Layout</button>
        <button onclick="setHierarchical()" style="padding:5px;">Hierarchical Layout</button>
    </div>
    <script type="text/javascript">
    function setForce(){
        network.setOptions({layout: {hierarchical: false}, physics: {enabled: true}});
    }
    function setHierarchical(){
        network.setOptions({
            layout: {hierarchical: {direction: 'LR', sortMethod: 'hubsize'}},
            physics: {enabled: false}
        });
    }
    </script>
    """

    html_data = html_data.replace("</body>", layout_buttons + "\n</body>")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_data)

# ----------------------------
# MAIN
# ----------------------------
if __name__ == "__main__":
    project_path = input("📂 Enter project folder path: ").strip()
    if not os.path.isdir(project_path):
        print("❌ Invalid path.")
        exit()

    print("🔍 Scanning project and building dependency graph...")
    imports = scan_imports(project_path)
    G = nx.DiGraph()
    for src, dst in imports:
        G.add_edge(src, dst)

    cycles, high_conn, isolated = detect_problem_areas(G)

    save_png(G, cycles, high_conn, isolated)
    save_html(G, cycles, high_conn, isolated, OUTPUT_HTML)

    print(f"✅ PNG saved as {OUTPUT_PNG}")
    print(f"✅ Interactive HTML saved as {OUTPUT_HTML}")

def analyze_project(project_path: str):
    imports = scan_imports(project_path)
    G = nx.DiGraph()
    for src, dst in imports:
        G.add_edge(src, dst)

    cycles, high_conn, isolated = detect_problem_areas(G)
    save_png(G, cycles, high_conn, isolated)
    save_html(G, cycles, high_conn, isolated, OUTPUT_HTML)

    return {
        "graph": G,
        "cycles": cycles,
        "highly_connected": high_conn,
        "isolated": isolated,
        "html": OUTPUT_HTML,
        "png": OUTPUT_PNG
    }