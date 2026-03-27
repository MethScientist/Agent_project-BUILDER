# core/lang_js.py
import re
from typing import List


# simple ES export detection (function/class/const/let/var)
EXPORT_RE = re.compile(r"\bexport\s+(?:default\s+)?(?:function|class|const|let|var)?\s*([A-Za-z_$][\w$]*)", re.M)
# CommonJS module.exports = { a: ..., b: ... }
MODULE_EXPORTS_RE = re.compile(r"module\.exports\s*=\s*{([^}]+)}", re.S)
# exports.name = ...
ASSIGN_EXPORT_RE = re.compile(r"exports\.([A-Za-z_$][\w$]*)\s*=")

# naive used-identifier finder
IDENT_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\b")

JS_GLOBALS = {
    "window", "document", "console", "module", "exports", "require",
    "setTimeout", "setInterval", "clearTimeout", "Math", "JSON", "Array",
    "Object", "String", "Number", "Boolean", "Promise", "fetch"
}

def extract_js_exports(source: str) -> List[str]:
    names = set()
    for m in EXPORT_RE.finditer(source):
        if m.group(1):
            names.add(m.group(1))
    for m in MODULE_EXPORTS_RE.finditer(source):
        body = m.group(1)
        for nm in re.findall(r"([A-Za-z_$][\w$]*)\s*:", body):
            names.add(nm)
    for m in ASSIGN_EXPORT_RE.finditer(source):
        names.add(m.group(1))
    return sorted(names)

def find_js_used_identifiers(source: str) -> List[str]:
    toks = set(IDENT_RE.findall(source))
    used = [t for t in toks if t not in JS_GLOBALS and not t.isdigit()]
    return sorted(used)
