from core.project_map import build_project_map


def test_project_map_extracts_json_yaml_and_other(tmp_path):
    proj = tmp_path
    # create sample JSON
    fjson = proj / "data.json"
    fjson.write_text('{"alpha": 1, "beta": 2}', encoding="utf-8")

    # YAML (simple keys)
    fyaml = proj / "config.yaml"
    fyaml.write_text("alpha: 1\nbeta: 2\n", encoding="utf-8")

    # PHP
    fphp = proj / "lib.php"
    fphp.write_text("<?php\nfunction greet() { echo 'hi'; }\nclass Helper {}\n?>", encoding="utf-8")

    # Java
    fjava = proj / "Main.java"
    fjava.write_text("public class Main { public static void main(String[] args) {} public void helper(){} }", encoding="utf-8")

    # C
    fc = proj / "util.c"
    fc.write_text("int add(int a,int b){return a+b;} static void helper(){ }", encoding="utf-8")

    # Go
    fgo = proj / "util.go"
    fgo.write_text("package main\nfunc DoThing(){}", encoding="utf-8")

    # Rust
    frs = proj / "lib.rs"
    frs.write_text("pub fn do_it() {}", encoding="utf-8")

    # XML
    fxml = proj / "layout.xml"
    fxml.write_text("<root><item/></root>", encoding="utf-8")

    # JSX (treated as JS)
    fjx = proj / "comp.jsx"
    fjx.write_text("export function Comp(){}", encoding="utf-8")

    pm = build_project_map(str(proj))

    assert "data.json" in pm and pm["data.json"]["lang"] == "json"
    assert "alpha" in pm["data.json"]["exports"]

    assert "config.yaml" in pm and pm["config.yaml"]["lang"] == "yaml"
    assert "alpha" in pm["config.yaml"]["exports"]

    assert "lib.php" in pm and pm["lib.php"]["lang"] == "php"
    assert "greet" in pm["lib.php"]["exports"]
    assert any(isinstance(e, str) and e == "Helper" for e in pm["lib.php"]["exports"]) 

    assert "Main.java" in pm and pm["Main.java"]["lang"] == "java"
    assert "Main" in pm["Main.java"]["exports"]

    assert "util.c" in pm and pm["util.c"]["lang"] == "c"
    assert "add" in pm["util.c"]["exports"]

    assert "util.go" in pm and pm["util.go"]["lang"] == "go"
    assert "DoThing" in pm["util.go"]["exports"]

    assert "lib.rs" in pm and pm["lib.rs"]["lang"] == "rust"
    assert "do_it" in pm["lib.rs"]["exports"]

    assert "layout.xml" in pm and pm["layout.xml"]["lang"] == "xml"
    assert "root" in pm["layout.xml"]["exports"]

    assert "comp.jsx" in pm and pm["comp.jsx"]["lang"] == "js"
    assert "Comp" in pm["comp.jsx"]["exports"]
