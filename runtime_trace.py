import os
import atexit
import inspect
import threading
import json
from collections import defaultdict

_lock = threading.Lock()
_data = {
    "steps": {},  # step_id -> { files: {norm: {raws:set, write_count:int, verifier:status}}, paths: [] }
}

current = {"step": None}

def install():
    os.makedirs("output", exist_ok=True)
    atexit.register(_flush)

def set_current_step(step_id: str):
    with _lock:
        current["step"] = step_id
        if step_id not in _data["steps"]:
            _data["steps"][step_id] = {"files": {}, "paths": []}

def clear_current_step():
    with _lock:
        current["step"] = None

def _callsite_info():
    st = inspect.stack()
    # pick the first frame outside this module
    for frame in st[2:8]:
        fn = frame.filename
        if fn and not fn.endswith("runtime_trace.py"):
            return f"{os.path.relpath(fn)}:{frame.lineno} in {frame.function}"
    # fallback
    f = st[1]
    return f"{os.path.relpath(f.filename)}:{f.lineno} in {f.function}"

def log_path(raw: str, normalized: str):
    with _lock:
        sid = current.get("step") or "<no-step>"
        rec = _data["steps"].setdefault(sid, {"files": {}, "paths": []})
        rec["paths"].append({"raw": raw, "normalized": normalized, "callsite": _callsite_info()})

def log_file_write(path: str, normalized: str | None = None):
    with _lock:
        sid = current.get("step") or "<no-step>"
        rec = _data["steps"].setdefault(sid, {"files": {}, "paths": []})
        norm = normalized or path
        f = rec["files"].setdefault(norm, {"raws": set(), "write_count": 0, "verifier": None, "call_sites": []})
        f["raws"].add(path)
        f["write_count"] += 1
        f["call_sites"].append(_callsite_info())

def log_verification(path: str, result: dict):
    with _lock:
        sid = current.get("step") or "<no-step>"
        rec = _data["steps"].setdefault(sid, {"files": {}, "paths": []})
        norm = path
        f = rec["files"].setdefault(norm, {"raws": set(), "write_count": 0, "verifier": None, "call_sites": []})
        f["verifier"] = result

def _flush():
    try:
        out_json = os.path.join("output", "runtime_trace.json")
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(_data, f, indent=2, default=list)

        # also produce CSV-like table for quick inspection
        out_csv = os.path.join("output", "runtime_trace_table.csv")
        with open(out_csv, "w", encoding="utf-8") as f:
            f.write("step_id,raw_path,normalized_path,write_count,verifier_status\n")
            for sid, rec in _data["steps"].items():
                for norm, info in rec["files"].items():
                    raws = ";".join(sorted(info.get("raws", [])))
                    write_count = info.get("write_count", 0)
                    ver = info.get("verifier")
                    ver_status = ver.get("status") if isinstance(ver, dict) else (str(ver) if ver is not None else "")
                    f.write(f'"{sid}","{raws}","{norm}",{write_count},"{ver_status}"\n')
    except Exception:
        pass
