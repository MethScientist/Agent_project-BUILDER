"""
core/code_scanner.py

Orchestrator that:
- discovers files under project_root
- runs python_fixer for safe deterministic fixes
- optionally asks GPT (ai_models.gpt_interface.GPTInterface) for deeper fixes (full-file replacement)
- validates Python files (py_compile)
- backups originals before applying changes
- supports dry-run and multiple passes
"""
import ast
import os
import re
import shutil
import time
import json
import py_compile
import tempfile
from pathlib import Path
from typing import List, Dict, Optional
from collections import Counter


# try to use your project's logger if available
try:
    from utils.logger import log_info, log_warning, log_error
except Exception:
    def log_info(msg): print("[INFO]", msg)
    def log_warning(msg): print("[WARN]", msg)
    def log_error(msg): print("[ERROR]", msg)

# import python fixer
from core.python_fixer import analyze_and_fix

# import GPT glue (tries to use your ai_models.gpt_interface.GPTInterface)
try:
    from ai_models.gpt_interface import GPTInterface
except Exception:
    # fallback stub if your project doesn't have GPTInterface defined yet
    class GPTInterface:
        def __init__(self):
            pass

        def fix_file_content(self, file_path: str, content: str, instruction: str) -> Optional[str]:
            # Default: no change (safe)
            return None


TIMESTAMP = time.strftime("%Y%m%d-%H%M%S")


class CodeScanner:
    def __init__(self, project_root: str, backup_root: Optional[str] = None, gpt: Optional[GPTInterface] = None):
        self.project_root = Path(project_root).resolve()
        self.backup_root = Path(backup_root or (self.project_root / f".backup/{TIMESTAMP}")).resolve()
        self.gpt = gpt or GPTInterface(role="executor")
        self.files: List[Path] = []
        self.file_langs: Dict[str, str] = {}

    def discover_files(self, include_exts: Optional[List[str]] = None):
        include_exts = include_exts or ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.html', '.css']
        self.files = [p for p in self.project_root.rglob('*') if p.is_file() and p.suffix.lower() in include_exts]
        for p in self.files:
            self.file_langs[str(p)] = self.detect_language(p)
        log_info(f"Discovered {len(self.files)} files under {self.project_root}")
        return self.files

    @staticmethod
    def detect_language(path: Path) -> str:
        ext = path.suffix.lower()
        if ext == '.py':
            return 'python'
        if ext in {'.js', '.jsx'}:
            return 'javascript'
        if ext in {'.ts', '.tsx'}:
            return 'typescript'
        if ext == '.java':
            return 'java'
        if ext in {'.html', '.htm'}:
            return 'html'
        return 'text'

    def scan_project_summary(self) -> str:
        """
        Produce a compact, informative summary of the project for planner prompts.
        Returns a string (multi-line) including:
          - total files, counts by extension
          - top N largest files (name, size_kb)
          - for top python files: function/class counts, syntax check, TODO/FIXME count
          - discovered dependency files (requirements.txt, pyproject.toml)
        This is intentionally compact and safe to include in prompts.
        """
        try:
            # Ensure files list is populated
            try:
                self.discover_files()
            except Exception:
                # fallback: try a light scan of project_root
                self.files = [p for p in Path(self.project_root).rglob('*') if p.is_file()]

            total_files = len(self.files)
            # counts by extension
            exts = [p.suffix.lower() or "[no-ext]" for p in self.files]
            counts = Counter(exts)

            # top largest files (by filesize)
            files_with_size = []
            for p in self.files:
                try:
                    size = p.stat().st_size
                except Exception:
                    size = 0
                files_with_size.append((p, size))
            files_with_size.sort(key=lambda x: x[1], reverse=True)
            TOP_N = 8
            top = files_with_size[:TOP_N]

            top_entries = []
            for p, size in top:
                size_kb = round(size / 1024, 1)
                info = {"path": str(p.relative_to(self.project_root)) if p.is_relative_to(self.project_root) else str(p),
                        "size_kb": size_kb}
                # extra python-specific info
                if p.suffix.lower() == ".py":
                    try:
                        text = p.read_text(encoding="utf-8", errors="ignore")
                        # count TODO/FIXME occurrences (first 300 lines to keep it cheap)
                        snippet = "\n".join(text.splitlines()[:300])
                        todos = len(re.findall(r"\b(TODO|FIXME)\b", snippet, flags=re.IGNORECASE))
                        # parse AST to count top-level defs
                        try:
                            tree = ast.parse(snippet)
                            func_count = sum(1 for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
                            class_count = sum(1 for n in tree.body if isinstance(n, ast.ClassDef))
                            syntax_ok = True
                        except SyntaxError:
                            func_count = 0
                            class_count = 0
                            syntax_ok = False
                        info.update({"py_funcs": func_count, "py_classes": class_count, "py_syntax_ok": syntax_ok, "todos": todos})
                    except Exception:
                        # be conservative if reading/parsing fails
                        info.update({"py_funcs": 0, "py_classes": 0, "py_syntax_ok": None, "todos": 0})
                top_entries.append(info)

            # try to read dependency files
            deps = []
            try:
                req = Path(self.project_root) / "requirements.txt"
                if req.exists():
                    lines = [ln.strip() for ln in req.read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip() and not ln.strip().startswith("#")]
                    deps.extend(lines[:20])
                pyproject = Path(self.project_root) / "pyproject.toml"
                if pyproject.exists():
                    # take first 30 lines as hint
                    deps.extend([ln.strip() for ln in pyproject.read_text(encoding="utf-8", errors="ignore").splitlines()[:30]])
            except Exception:
                pass

            # Compose a compact string
            counts_part = ", ".join(f"{ext or '[no-ext]'}:{cnt}" for ext, cnt in counts.most_common())
            top_part_lines = []
            for e in top_entries:
                line = f"- {e['path']} ({e['size_kb']} KB)"
                if e.get("path", "").endswith(".py"):
                    syntax = "ok" if e.get("py_syntax_ok") else ("err" if e.get("py_syntax_ok") is False else "unknown")
                    line += f" [py funcs:{e.get('py_funcs')} classes:{e.get('py_classes')} syntax:{syntax} todos:{e.get('todos')}]"
                top_part_lines.append(line)

            deps_snippet = ", ".join(deps[:20]) if deps else "(none found)"

            summary = [
                f"Project root: {self.project_root}",
                f"Total files: {total_files}",
                f"Counts by extension: {counts_part}",
                f"Top {len(top_entries)} largest files:",
            ]
            summary.extend(top_part_lines)
            summary.append(f"Dependencies (requirements/pyproject snippet): {deps_snippet}")

            # keep it short: join with newlines and return
            return "\n".join(summary)
        except Exception as e:
            # Never raise — return a short fallback string
            try:
                log_warning(f"scan_project_summary failed: {e}")
            except Exception:
                pass
            return "Project scan summary unavailable."

    def backup_file(self, file_path: Path):
        dest = self.backup_root / file_path.relative_to(self.project_root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, dest)
        log_info(f"Backed up {file_path} -> {dest}")

    def apply_fix(self, file_path: Path, new_content: str):
        self.backup_file(file_path)
        file_path.write_text(new_content, encoding='utf-8')
        log_info(f"Wrote fixed file {file_path}")

    def validate_python(self, file_path: Path) -> (bool, Optional[str]):
        try:
            py_compile.compile(str(file_path), doraise=True)
            return True, None
        except Exception as e:
            return False, str(e)

    def _ask_gpt_fix_python(self, file_path: Path, content: str, project_snapshot: Dict) -> Optional[str]:
        """
        Ask GPT to produce an updated version of this Python file.
        Model MUST return only the full file contents (no commentary).
        """
        instruction = (
            "You are an expert Python assistant. Given the file content and project context, "
            "return ONLY the full updated file content. Make minimal edits: fix imports, small missing helpers, "
            "obvious logic or syntax issues. Keep changes focused and minimal.\n\n"
            f"File path: {file_path}\n"
            f"Project snapshot: {json.dumps(project_snapshot)}\n\n"
            "---- CURRENT FILE -----\n"
            f"{content}\n"
            "---- END -----\n"
            "Return only the updated full file contents."
        )
        try:
            resp = self.gpt.fix_file_content(str(file_path), content, instruction)
            return resp
        except Exception as e:
            log_error(f"GPT fixer failed for {file_path}: {e}")
            return None

    def fix_project(self, dry_run: bool = True, max_passes: int = 2) -> Dict:
        self.discover_files()
        passes = 0
        changed_files: List[str] = []

        while passes < max_passes:
            passes += 1
            log_info(f"[CodeScanner] pass {passes}")
            any_change = False
            project_snapshot = {"root": str(self.project_root), "file_count": len(self.files)}

            # Simple ordering: python files first (you can improve with dependency graph later)
            ordered = sorted(self.files, key=lambda p: (p.suffix.lower() != '.py', str(p)))

            for fp in ordered:
                fp_str = str(fp)
                lang = self.file_langs.get(fp_str, 'text')
                try:
                    content = fp.read_text(encoding='utf-8', errors='ignore')
                except Exception as e:
                    log_warning(f"Failed reading {fp}: {e}")
                    continue

                new_content = None
                made_changes = False

                if lang == 'python':
                    # 1) deterministic AST-based safe fixes
                    fixed_content, inserted = analyze_and_fix(content)
                    if inserted:
                        made_changes = True
                        log_info(f"python_fixer: inserted stubs {inserted} into {fp}")
                        new_content = fixed_content
                    else:
                        new_content = content

                    # 2) then optionally ask GPT for deeper fixes (full-file replacement)
                    gpt_result = self._ask_gpt_fix_python(fp, new_content, project_snapshot)
                    if gpt_result and gpt_result.strip() != new_content.strip():
                        # GPT suggested changes
                        made_changes = True
                        log_info(f"GPT suggested changes for {fp}")
                        new_content = gpt_result

                    # If changes were proposed, validate then apply (unless dry-run)
                    if made_changes:
                        if dry_run:
                            log_info(f"[dry-run] would apply changes to {fp}")
                            changed_files.append(fp_str)
                            any_change = True
                        else:
                            # write to temp file and validate
                            tmp = Path(tempfile.mkstemp(suffix=".py")[1])
                            tmp.write_text(new_content, encoding='utf-8')
                            ok, err = self.validate_python(tmp)
                            tmp.unlink(missing_ok=True)
                            if ok:
                                self.apply_fix(fp, new_content)
                                changed_files.append(fp_str)
                                any_change = True
                            else:
                                log_warning(f"Validation failed for {fp}: {err}. Skipping write.")
                else:
                    # For non-python files: optionally ask GPT for fixes, but conservative here
                    # Add hooks here if you create language-specific fixers
                    continue

            if not any_change:
                log_info("[CodeScanner] No changes in this pass — finished.")
                break

        return {"passes": passes, "changed_files": changed_files, "backup_root": str(self.backup_root)}
