# core/dependency_resolver.py
import os
import re
from typing import Dict, List, Optional, Any
from pathlib import PurePosixPath
from utils.ast_utils import find_undefined_names, get_imported_symbols, get_defined_symbols


# For JS heuristics
from core.lang_js import find_js_used_identifiers
from core.lang_cs import extract_cs_namespace

def posix_relpath(from_rel: str, to_rel: str) -> str:
    """Return a posix-style relative path from from_rel to to_rel."""
    a = PurePosixPath(from_rel).parent
    b = PurePosixPath(to_rel)
    rel = os.path.relpath(str(b), str(a))
    rel = PurePosixPath(rel).as_posix()
    if not rel.startswith("."):
        rel = "./" + rel
    return rel

class DependencyResolver:
    def __init__(self, project_map: Dict[str, Any], project_root: str):
        """
        project_map: {rel: {"lang": lang, "exports": [...]} }
        """
        self.project_map = project_map
        self.project_root = project_root
        self.symbol_index = self._build_index(project_map)

    def _build_index(self, pm):
        idx = {}  # symbol -> list of (module_rel, lang, extra)
        for rel, meta in pm.items():
            lang = meta.get("lang")
            exports = meta.get("exports", [])
            if lang == "cs":
                # exports may be [{"types": {"Type": "Namespace"}}]
                for item in exports:
                    types_map = item.get("types", {})
                    for t, ns in types_map.items():
                        idx.setdefault(t, []).append({"module": rel, "lang": "cs", "namespace": ns})
            else:
                for s in exports:
                    idx.setdefault(s, []).append({"module": rel, "lang": lang})
        return idx

    def choose_provider(self, symbol: str, preferred_langs: Optional[List[str]] = None) -> Optional[Dict]:
        cand = self.symbol_index.get(symbol)
        if not cand:
            return None
        if not preferred_langs:
            preferred_langs = ["py", "js", "cs", "css"]
        # simple scoring by language preference then shortest module path
        cand.sort(key=lambda x: (preferred_langs.index(x["lang"]) if x["lang"] in preferred_langs else len(preferred_langs), len(x["module"])))
        return cand[0]

    # ---------- Python injection ----------
    def _already_has_py_import(self, source: str, module: str, symbol: str) -> bool:
        if f"from {module} import {symbol}" in source:
            return True
        if f"import {module}" in source:
            return True
        return False

    def _inject_py_import(self, source: str, from_rel: str, module_rel: str, symbol: str) -> str:
        module = module_rel.replace("/", ".").replace(".py", "")
        if self._already_has_py_import(source, module, symbol):
            return source
        imp_line = f"from {module} import {symbol}\n"
        # attempt to keep module docstring at top
        m = re.match(r"^(\\s*(['\"]{3})).*?(['\"]{3})", source, flags=re.S)
        if m:
            # naive: insert after docstring
            doc_end = m.end()
            return source[:doc_end] + "\n" + imp_line + source[doc_end:]
        # else try to find existing imports block
        m2 = re.search(r"(^\s*(?:from\s+[^\n]+\n|import\s+[^\n]+\n)+)", source, flags=re.M)
        if m2:
            end = m2.end(1)
            return source[:end] + imp_line + source[end:]
        return imp_line + source

    # ---------- JS injection ----------
    def _already_has_js_import(self, source: str, rel_path: str, symbol: str) -> bool:
        # check named imports and default imports
        pattern = rf"import\s+.*\b{re.escape(symbol)}\b.*from\s+['\"]{re.escape(rel_path)}['\"]"
        if re.search(pattern, source):
            return True
        # require() style?
        if re.search(rf"\b{re.escape(symbol)}\b\s*=", source) and rel_path in source:
            return True
        return False

    def _inject_js_import(self, source: str, from_rel: str, module_rel: str, symbol: str) -> str:
        imp_path = posix_relpath(from_rel, module_rel)
        # add extension for clarity if module has .js or .ts
        if not (imp_path.endswith(".js") or imp_path.endswith(".mjs") or imp_path.endswith(".cjs") or imp_path.endswith(".ts")):
            # try to append module extension from module_rel
            if module_rel.endswith(".js") or module_rel.endswith(".mjs") or module_rel.endswith(".cjs") or module_rel.endswith(".ts"):
                imp_path = imp_path + PathSuffix(module_rel)
        if self._already_has_js_import(source, imp_path, symbol):
            return source
        import_line = f"import {{ {symbol} }} from '{imp_path}';\n"
        # insert after existing import block if any
        m = re.search(r"(^\s*(?:import .+\n)+)", source, flags=re.M)
        if m:
            end = m.end(1)
            return source[:end] + import_line + source[end:]
        else:
            return import_line + source

    # ---------- HTML injection ----------
    def _inject_html_asset(self, html: str, asset_rel: str, asset_type: str) -> str:
        # asset_type: 'script' or 'css'; asset_rel should be posix relative path
        if asset_type == "script":
            tag = f"<script src=\"{asset_rel}\"></script>"
        else:
            tag = f"<link rel=\"stylesheet\" href=\"{asset_rel}\">"
        if tag in html:
            return html
        if "</head>" in html:
            return html.replace("</head>", f"{tag}\n</head>", 1)
        # else prepend at top
        return tag + "\n" + html

    # ---------- CSS injection ----------
    def _inject_css_import(self, source: str, from_rel: str, module_rel: str) -> str:
        relp = posix_relpath(from_rel, module_rel)
        imp_line = f"@import '{relp}';\n"
        if imp_line in source:
            return source
        # insert at top
        return imp_line + source

    # ---------- C# injection ----------
    def _inject_cs_using(self, source: str, namespace: str) -> str:
        if not namespace:
            return source
        if re.search(rf"\busing\s+{re.escape(namespace)}\s*;", source):
            return source
        # append after existing using block
        m = re.search(r"(^\s*(?:using .+;\n)+)", source, flags=re.M)
        if m:
            return source[:m.end(1)] + f"using {namespace};\n" + source[m.end(1):]
        return f"using {namespace};\n\n" + source

    # ---------- Top-level injection API ----------
    def inject_imports(self, rel_path: str, source: str) -> str:
        """
        rel_path: path relative to project root (posix style)
        source: file content
        returns patched source
        """
        # decide language by rel_path extension
        ext = os.path.splitext(rel_path)[1].lower()
        lang = "py" if ext == ".py" else ("js" if ext in (".js", ".mjs", ".cjs", ".ts") else ("css" if ext == ".css" else ("html" if ext in (".html", ".htm") else ("cs" if ext == ".cs" else "text"))))

        try:
            if lang == "py":
                undefined = find_undefined_names(source)
                for name in sorted(undefined):
                    prov = self.choose_provider(name, preferred_langs=["py"])
                    if not prov:
                        continue
                    module = prov["module"]
                    # don't import from same file
                    if module == rel_path:
                        continue
                    source = self._inject_py_import(source, rel_path, module, name)
                return source

            if lang == "js":
                used = find_js_used_identifiers(source)
                # skip identifiers already defined in this file
                defined = get_defined_symbols(source)
                imported = get_imported_symbols(source)
                for name in used:
                    if name in defined or name in imported:
                        continue
                    prov = self.choose_provider(name, preferred_langs=["js", "py"])
                    if not prov:
                        continue
                    module = prov["module"]
                    if module == rel_path:
                        continue
                    source = self._inject_js_import(source, rel_path, module, name)
                return source

            if lang == "html":
                # for HTML, look up referenced JS/CSS by used identifiers in embedded scripts (quick heuristic)
                # find inline <script> content and used ids
                # simple strategy: for every provider module that is js or css, if its exported symbol appears in the HTML, inject corresponding tag
                for mod, meta in self.project_map.items():
                    mlang = meta.get("lang")
                    exports = meta.get("exports", [])
                    if not exports:
                        continue
                    if mlang == "js":
                        for sym in exports:
                            if re.search(rf"\b{re.escape(sym)}\b", source):
                                asset_rel = posix_relpath(rel_path, mod)
                                source = self._inject_html_asset(source, asset_rel, "script")
                    elif mlang == "css":
                        for cls in exports:
                            # if class name referenced in HTML, inject link
                            if re.search(rf'class=["\'][^"\']*\b{re.escape(cls)}\b', source):
                                asset_rel = posix_relpath(rel_path, mod)
                                source = self._inject_html_asset(source, asset_rel, "css")
                return source

            if lang == "css":
                # find class names used (naive: nothing to find inside css itself), but if css references @apply etc. we could import
                # Instead: if this css file references variables or uses classes not defined here, skip for now.
                return source

            if lang == "cs":
                # find undefined type names (naive) and add using for their namespace if available
                idents = re.findall(r"\b([A-Z][A-Za-z0-9_]+)\b", source)
                for ident in idents:
                    prov = self.choose_provider(ident, preferred_langs=["cs"])
                    if not prov:
                        continue
                    ns = prov.get("namespace") or prov.get("namespace", None)
                    if ns:
                        source = self._inject_cs_using(source, ns)
                return source

            return source
        except Exception:
            # fail-safe: return original source on unexpected errors
            return source

# helper to grab suffix char sequence of module (for js extension detection)
def PathSuffix(rel):
    return os.path.splitext(rel)[1] or ""
