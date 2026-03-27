# executor/code_writer.py
import os
import re
import time
import asyncio
import importlib.util
from pathlib import Path 
from typing import Optional
from pathlib import Path       # <-- must be here
import runtime_trace as trace

from config.settings import SETTINGS, get_model_id
from utils.logger import log_info, log_warning, log_error
from server.tracker import emit_event
from ai_agent_system.tracking.LiveTracker import LiveTracker
from core.code_scanner import CodeScanner
from core.code_generator import CodeGenerator  # may be sync or async
from core.project_map import build_project_map, detect_lang_by_ext
from core.lang_js import extract_js_exports
from core.lang_css import extract_css_class_names
from core.lang_cs import cs_exports
from core.dependency_resolver import DependencyResolver
from utils.ast_utils import get_defined_symbols
from executor.granular import GranularFileEditor
from context_awareness.manager import ContextManager  # or wherever it lives

def _sanitize_diff_name(s: str) -> str:
    # Replace path separators and other problematic chars for filenames
    sanitized = re.sub(r"[\\/:\*\?\"<>\|]", "_", s)
    sanitized = re.sub(r"\s+", "_", sanitized)
    return sanitized


class CodeWriter:
    def __init__(
        self,
        context_manager: ContextManager,
        project_root: Optional[str] = None,
        model: Optional[str] = None
    ):
        print(f"[DEBUG] CodeWriter.__init__ start, project_root={project_root}, context_manager={context_manager}", flush=True)

        if context_manager is None:
            raise ValueError("CodeWriter requires a ContextManager instance")

        raw_root = project_root or SETTINGS.get("project_root")
        print(f"[DEBUG] Resolved project_root = {raw_root}", flush=True)
        if not raw_root:
            raise ValueError("SETTINGS['project_root'] is not set; CodeWriter cannot initialize.")

        self.project_root = Path(raw_root).resolve()
        print(f"[DEBUG] Resolved Path(project_root) = {self.project_root}", flush=True)


        if not self.project_root.exists():
            print(f"[DEBUG] Creating project root folder: {self.project_root}", flush=True)
            self.project_root.mkdir(parents=True, exist_ok=True)
        print("[DEBUG] Calling build_project_map...", flush=True)
        self.project_map = build_project_map(str(self.project_root))
        print(f"[DEBUG] project_map keys: {list(self.project_map.keys())}", flush=True)

        self.resolver = DependencyResolver(self.project_map, str(self.project_root))
        print(f"[DEBUG] DependencyResolver created: {self.resolver}", flush=True)
        try:
            log_info("🧭 DependencyResolver enabled for CodeWriter")
        except Exception:
            pass
        resolved_model = model or get_model_id("code_writer")
        self.generator = CodeGenerator(model=resolved_model)
        self.tracker = LiveTracker()
        self.scanner = CodeScanner(self.project_root)
        log_info(f"🛠 CodeWriter initialized for project root: {self.project_root}")
        self.editor = GranularFileEditor(self.project_root)

        self.context_manager = context_manager

        self.context_manager.load_context()
        
        log_info("🧠 ContextManager initialized for CodeWriter")

    def _strip_code_fences(self, text: str) -> str:
        if not isinstance(text, str):
            return text
        # Remove leading/trailing fenced code blocks
        stripped = text.strip()
        if stripped.startswith("```"):
            # drop first fence line
            stripped = re.sub(r"^```[a-zA-Z0-9_-]*\s*\n", "", stripped)
            # drop trailing fence
            stripped = re.sub(r"\n```$", "", stripped)
        return stripped

    def _normalize_relative_path(self, path: str) -> str:
        """
        Normalize a path to be project-root relative and avoid double-prefixing.
        Accepts absolute or relative inputs.
        """
        if not path:
            return path
        p = Path(path)
        if p.is_absolute():
            try:
                return p.resolve().relative_to(self.project_root).as_posix()
            except Exception:
                return p.name

        norm = path.replace("\\", "/").lstrip("./")
        try:
            rel_root = os.path.relpath(self.project_root, os.getcwd()).replace("\\", "/")
        except Exception:
            rel_root = None
        if rel_root:
            if norm == rel_root:
                return "."
            if norm.startswith(rel_root + "/"):
                return norm[len(rel_root) + 1:]
        return norm

    # -------------------------
    # Import pruning (Python)
    # -------------------------
    def _python_valid_modules(self):
        """
        Build a set of valid python module names derived from project files.
        Example: 'pkg/util.py' -> 'pkg.util'
        """
        mods = set()
        for rel in self.project_map.keys():
            if not rel.endswith(".py"):
                continue
            parts = rel[:-3].split("/")  # drop .py
            if parts[-1] == "__init__":
                # package name is the folder
                pkg = ".".join(parts[:-1])
                if pkg:
                    mods.add(pkg)
            mod = ".".join(parts)
            if mod:
                mods.add(mod)
        return mods

    def _js_import_exists(self, rel_key: str, import_path: str) -> bool:
        if not import_path:
            return True
        # strip query/hash
        base_path = import_path.split("?", 1)[0].split("#", 1)[0]
        # package import -> keep
        if not (base_path.startswith(".") or base_path.startswith("/")):
            return True

        base_dir = Path(rel_key).parent
        if base_path.startswith("/"):
            candidate = (self.project_root / base_path.lstrip("/")).resolve()
        else:
            candidate = (self.project_root / base_dir / base_path).resolve()

        # if path has extension, check directly
        if candidate.suffix:
            return candidate.exists()

        # try common extensions and index files
        exts = [".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"]
        for ext in exts:
            if (candidate.with_suffix(ext)).exists():
                return True
        # directory index
        if candidate.is_dir():
            for ext in exts:
                if (candidate / f"index{ext}").exists():
                    return True
        return False

    def _cs_known_namespaces(self):
        namespaces = set()
        for rel, meta in self.project_map.items():
            if meta.get("lang") != "cs":
                continue
            exports = meta.get("exports") or []
            for item in exports:
                if isinstance(item, dict) and "types" in item:
                    for ns in item.get("types", {}).values():
                        if ns:
                            namespaces.add(ns)
        return namespaces

    def _prune_invalid_imports(self, rel_key: str, code: str) -> str:
        """
        Remove import lines that refer to non-existent project-local modules
        and are not importable via Python.
        Applies to .py, .js/.ts, and .cs files.
        """
        if not (rel_key.endswith(".py") or rel_key.endswith(".js") or rel_key.endswith(".ts") or rel_key.endswith(".jsx") or rel_key.endswith(".tsx") or rel_key.endswith(".mjs") or rel_key.endswith(".cjs") or rel_key.endswith(".cs")):
            return code

        valid_modules = self._python_valid_modules()
        known_namespaces = self._cs_known_namespaces()

        def is_importable(mod: str) -> bool:
            if not mod:
                return True
            # local module?
            if mod in valid_modules:
                return True
            # try importlib spec (stdlib or installed)
            return importlib.util.find_spec(mod) is not None

        def is_relative_import_valid(mod: str) -> bool:
            # Resolve relative imports against rel_key
            dots = len(mod) - len(mod.lstrip("."))
            module_part = mod[dots:].strip()
            base = Path(rel_key).parent
            if dots > 1:
                for _ in range(dots - 1):
                    base = base.parent
            if module_part:
                rel_mod = Path(*module_part.split("."))
                base = base / rel_mod
            # check module file or package
            cand_file = self.project_root / (base.as_posix() + ".py")
            cand_pkg = self.project_root / base / "__init__.py"
            return cand_file.exists() or cand_pkg.exists()

        pruned_lines = []
        for line in code.splitlines():
            stripped = line.strip()
            # Python: Simple single-line imports only
            m_from = re.match(r"from\s+([\w\.]+)\s+import\s+", stripped)
            m_imp = re.match(r"import\s+([\w\.]+)", stripped)

            mod = None
            if m_from:
                mod = m_from.group(1)
            elif m_imp:
                # handle multiple imports separated by comma: import a, b
                mods = [part.strip() for part in m_imp.group(1).split(",")]
                # if any module in list is invalid, drop only those and keep others
                valid_mods = [m for m in mods if is_importable(m)]
                if valid_mods:
                    # rebuild the import line with valid modules
                    pruned_lines.append("import " + ", ".join(valid_mods))
                # skip adding the line if none valid
                continue

            if mod:
                # keep relative imports as-is
                if mod.startswith("."):
                    if is_relative_import_valid(mod):
                        pruned_lines.append(line)
                    # else drop invalid relative import
                    continue
                if is_importable(mod):
                    pruned_lines.append(line)
                # else skip the line
                continue

            # JS/TS: remove local import lines that point to missing files
            if rel_key.endswith((".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs")):
                m_js = re.match(r"import\s+.*?\s+from\s+['\"]([^'\"]+)['\"]", stripped)
                m_side = re.match(r"import\s+['\"]([^'\"]+)['\"]", stripped)
                m_req = re.match(r".*require\(\s*['\"]([^'\"]+)['\"]\s*\)", stripped)
                js_path = None
                if m_js:
                    js_path = m_js.group(1)
                elif m_side:
                    js_path = m_side.group(1)
                elif m_req:
                    js_path = m_req.group(1)

                if js_path:
                    if self._js_import_exists(rel_key, js_path):
                        pruned_lines.append(line)
                    # else drop the line
                    continue

            # C#: remove using lines with unknown namespaces (keep System/Microsoft)
            if rel_key.endswith(".cs"):
                m_using = re.match(r"using\s+([A-Za-z0-9_.]+)\s*;", stripped)
                if m_using:
                    ns = m_using.group(1)
                    if ns.startswith("System") or ns.startswith("Microsoft"):
                        pruned_lines.append(line)
                    elif ns in known_namespaces:
                        pruned_lines.append(line)
                    # else drop
                    continue

            # non-import line
            pruned_lines.append(line)

        return "\n".join(pruned_lines)

    def _full_path(self, relative_path: str) -> Path:
        """
        Resolve a relative path into an absolute path inside project_root.
        Prevent path traversal outside project root.
        """
        rel = self._normalize_relative_path(relative_path)
        log_info(f"📁 Resolving full path: {rel}")

        candidate = (self.project_root / rel).resolve()
        try:
            # Ensure candidate is inside project_root
            if self.project_root not in candidate.parents and candidate != self.project_root:
                raise ValueError(f"Attempted to write outside project root: {candidate}")
        except Exception:
            # On some systems candidate.parents might be empty; fallback to commonpath check
            rp = str(self.project_root)
            cp = str(candidate)
            if not cp.startswith(rp):
                raise ValueError(f"Attempted to write outside project root: {candidate}")
        return candidate

    def _backup_file(self, path: Path):
        """Create a timestamped backup of the file (if exists)."""
        if not path.exists():
            return
        backup_dir = self.project_root / ".backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        backup_name = f"{path.name}.{ts}.bak"
        backup_path = backup_dir / backup_name
        try:
            backup_path.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
            log_info(f"📦 Backup created: {backup_path}")
        except Exception as e:
            log_error(f"❌ Failed to create backup for {path}: {e}")

    async def _store_diff_file(self, relative_path: str, diff_text: str):
        """Write the unified diff into .diffs/ with a sanitized filename."""
        diff_dir = self.project_root / ".diffs"
        diff_dir.mkdir(parents=True, exist_ok=True)
        safe_name = _sanitize_diff_name(relative_path)
        diff_path = diff_dir / (safe_name + f".{int(time.time())}.diff")
        try:
            diff_path.write_text(diff_text, encoding="utf-8")
            log_info(f"📝 Diff stored: {diff_path}")
        except Exception as e:
            log_error(f"❌ Failed to write diff for {relative_path}: {e}")

    def _generate_diff_text(self, old: str, new: str, filename: str) -> str:
        import difflib
        return "\n".join(difflib.unified_diff(
            old.splitlines(),
            new.splitlines(),
            fromfile=f"{filename} (old)",
            tofile=f"{filename} (new)",
            lineterm=""
        ))
    def modify_file(self, rel_path, action, **kwargs):
        """
        Modify an existing file with granular precision.
        action options:
        - 'replace' → overwrite file with new content
        - 'insert_after' → insert code after pattern
        - 'insert_before' → insert code before pattern
        - 'insert_in_function' → insert inside Python function
        """
        try:
            if action == "replace":
                content = kwargs["content"]
                self.editor.write(rel_path, content)

            elif action == "insert_after":
                pattern = kwargs["pattern"]
                code = kwargs["code"]
                self.editor.insert_after_pattern(rel_path, pattern, code)

            elif action == "insert_before":
                pattern = kwargs["pattern"]
                code = kwargs["code"]
                self.editor.insert_before_pattern(rel_path, pattern, code)

            elif action == "insert_in_function":
                func_name = kwargs["func_name"]
                code = kwargs["code"]
                after_line = kwargs.get("after_line")
                self.editor.insert_in_function(rel_path, func_name, code, after_line)

            else:
                raise ValueError(f"Unknown modification action: {action}")

            log_info(f"✅ File modified: {rel_path} ({action})")
            return True

        except Exception as e:
            log_info(f"❌ File modification failed for {rel_path}: {e}")
            return False

    # -------------------------
    # Generator helpers
    # -------------------------
    async def _maybe_await_generator(self, *args, **kwargs):
        """Call generator and await if it returns a coroutine."""
        try:
            if hasattr(self.generator, "generate_code_async"):
                res = self.generator.generate_code_async(*args, **kwargs)
            else:
                res = self.generator.generate_code(*args, **kwargs)
        except TypeError:
            # fallback if signature mismatch
            if hasattr(self.generator, "generate_code_async"):
                res = self.generator.generate_code_async(args[0], args[1] if len(args) > 1 else "")
            else:
                res = self.generator.generate_code(args[0], args[1] if len(args) > 1 else "")

        if asyncio.iscoroutine(res):
            res = await res

        # Now res is defined — safe to log
        log_info(f"🔍 Generator returned type: {type(res)}, content length: {len(str(res))}")

        return res


    # -------------------------
    # Primary API
    # -------------------------
    async def generate_and_write_file(self, relative_path: str, description: str, dependency_context: str | None = None):
        """
        Uses CodeGenerator to create new file content and writes it to disk.
        Works whether CodeGenerator.generate_code is sync or async.
        """

        try:
            rel_path = self._normalize_relative_path(relative_path)
            new_code = await self._maybe_await_generator(rel_path, description, dependency_context)
        except Exception as e:
            log_error(f"❌ Code generation failed for {relative_path}: {e}")
            await emit_event({"type": "task_failed", "file": relative_path, "error": str(e)})
            return

        await self.write_file(rel_path, new_code)


    async def write_file(self, relative_path: str, new_code: str):
        """
        Write a full file, injecting imports, creating backups, diffs, and using context awareness.
        """
        # normalize path for keys and safety
        rel_key = self._normalize_relative_path(relative_path).replace("\\", "/").lstrip("/")

        # validate path and get absolute path


        try:
            full = self._full_path(rel_key)
        except Exception as e:
            log_error(f"❌ Invalid path for write_file({relative_path}): {e}")
            await emit_event({"type": "file_write_failed", "file": relative_path, "error": str(e)})
            return

        full.parent.mkdir(parents=True, exist_ok=True)

        # --- CONTEXT CHECK: skip if file already exists in context ---
        if self.context_manager.get_file_info(rel_key):
            log_info(f"⚡ Context shows {rel_key} already exists; will update if needed.")
            existing_info = self.context_manager.get_file_info(rel_key)
        else:
            existing_info = None

        old_code = ""
        if full.exists():
            try:
                old_code = full.read_text(encoding="utf-8")
            except Exception as e:
                log_error(f"❌ Failed to read existing file {full}: {e}")

        if not isinstance(new_code, str):
            new_code = str(new_code)
        new_code = self._strip_code_fences(new_code)

        if not new_code.strip():
            log_warning(f"⚠️ Attempted to write empty content to {relative_path}; skipping.")
            await emit_event({"type": "file_skipped", "file": relative_path, "reason": "empty_content"})
            return

        # --- PRUNE invalid imports before injection (so undefined symbols can be detected) ---
        try:
            pruned_code = self._prune_invalid_imports(rel_key, new_code)
        except Exception as e:
            log_warning(f"⚠️ Import pruning failed for {relative_path}: {e}; using unpruned code.")
            pruned_code = new_code

        # --- INJECT imports after pruning ---
        try:
            patched_code = self.resolver.inject_imports(rel_key, pruned_code)
        except Exception as e:
            log_warning(f"⚠️ Dependency injection failed for {relative_path}: {e}; falling back to original content.")
            patched_code = pruned_code

        # --- PRUNE again in case injection added invalid entries ---
        try:
            cleaned_code = self._prune_invalid_imports(rel_key, patched_code)
        except Exception as e:
            log_warning(f"⚠️ Import pruning failed for {relative_path}: {e}; using unpruned code.")
            cleaned_code = patched_code

        # --- CREATE DIFF ---
        diff_text = self._generate_diff_text(old_code, cleaned_code, rel_key)
        if diff_text.strip():
            # backup existing file if present and store diff
            if old_code:
                self._backup_file(full)
            await self._store_diff_file(rel_key, diff_text)
        else:
            log_info(f"ℹ️ No content changes detected for {relative_path}; skipping write.")
            await emit_event({"type": "file_skipped", "file": relative_path, "reason": "no_changes"})
            return

        # --- WRITE FILE ---
        try:
            full.write_text(cleaned_code, encoding="utf-8")
            log_info(f"✅ Wrote file: {full}")
            try:
                trace.log_file_write(str(full), rel_key)
            except Exception:
                pass
            await emit_event({"type": "file_written", "file": rel_key})
        except Exception as e:
            log_error(f"❌ Failed to write file {full}: {e}")
            await emit_event({"type": "file_write_failed", "file": rel_key, "error": str(e)})
            return

        # --- UPDATE PROJECT MAP AND RESOLVER ---
        try:
            lang = detect_lang_by_ext(Path(rel_key))
            exports = []
            if lang == "py":
                exports = sorted(list(get_defined_symbols(patched_code)))
            elif lang == "js":
                exports = extract_js_exports(patched_code)
            elif lang == "css":
                exports = extract_css_class_names(patched_code)
            elif lang == "cs":
                mapping = cs_exports(patched_code)
                if mapping:
                    exports = [{"types": mapping}]
            # Validate rel_key before inserting into project_map to avoid malformed keys
            try:
                if not rel_key or rel_key.startswith("/"):
                    raise ValueError("empty or absolute path")
                if ":" in rel_key:
                    # catch drive letters or other colon-delimited tokens
                    raise ValueError("contains colon")
                if ".." in rel_key:
                    raise ValueError("path traversal detected")

                # Ensure the resolved candidate is inside project_root
                candidate = (self.project_root / rel_key).resolve()
                if self.project_root not in candidate.parents and candidate != self.project_root:
                    raise ValueError(f"resolves outside project root: {candidate}")

            except Exception as e:
                log_warning(f"⚠️ Not updating project_map for '{rel_key}': {e}")
            else:
                self.project_map[rel_key] = {"lang": lang, "exports": exports}
                self.resolver = DependencyResolver(self.project_map, str(self.project_root))
        except Exception as e:
            log_warning(f"⚠️ Failed updating project_map after writing {rel_key}: {e}")

        # --- CONTEXT UPDATE ---
        self.context_manager.add_file(rel_key, role="code")  # role can be dynamic
        self.context_manager.save_context()
        log_info(f"🧠 Context updated for {rel_key}")

    async def write_or_replace_block(self, relative_path: str, identifier: str, new_block: str):
        """
        Replace a code block wrapped with:
            # BEGIN <identifier>
            ...
            # END <identifier>
        while preserving the markers. If no block exists, append the block (with markers).
        Integrates context tracking.
        """
        relative_path = self._normalize_relative_path(relative_path)
        log_info(f"🖋 write_or_replace_block called for {relative_path} with identifier {identifier}")

        try:
            full = self._full_path(relative_path)
        except Exception as e:
            log_error(f"❌ Invalid path for write_or_replace_block({relative_path}): {e}")
            await emit_event({"type": "code_write_failed", "file": relative_path, "identifier": identifier, "error": str(e)})
            return

        full.parent.mkdir(parents=True, exist_ok=True)

        new_block = self._strip_code_fences(new_block)
        new_block_text = new_block.strip() + "\n"

        # --- CONTEXT CHECK ---
        context_info = self.context_manager.get_file_info(relative_path)
        if context_info and identifier in context_info.get("blocks", []):
            log_info(f"⚡ Context shows block '{identifier}' exists in {relative_path}.")

        if not full.exists():
            # Create new file with markers + block
            initial = f"# BEGIN {identifier}\n{new_block_text}# END {identifier}\n"
            try:
                full.write_text(initial, encoding="utf-8")
                log_info(f"🆕 Created file and wrote block: {full}")
                try:
                    trace.log_file_write(str(full), relative_path)
                except Exception:
                    pass
                await emit_event({"type": "code_written", "file": relative_path, "identifier": identifier, "action": "created"})
            except Exception as e:
                log_error(f"❌ Failed to create {full}: {e}")
                await emit_event({"type": "code_write_failed", "file": relative_path, "identifier": identifier, "error": str(e)})
            # --- CONTEXT UPDATE ---
            self.context_manager.add_file_block(relative_path, identifier)
            self.context_manager.save_context()
            return

        try:
            content = full.read_text(encoding="utf-8")
        except Exception as e:
            log_error(f"❌ Failed to read {full}: {e}")
            await emit_event({"type": "code_write_failed", "file": relative_path, "identifier": identifier, "error": str(e)})
            return

        # Pattern to capture BEGIN marker, inner content, and END marker separately
        esc_id = re.escape(identifier)
        pattern = re.compile(rf"(?s)(#\s*BEGIN\s+{esc_id}\s*\n)(.*?)(\n#\s*END\s+{esc_id})")

        if pattern.search(content):
            # Replace inner content while preserving markers
            updated_content = pattern.sub(rf"\1{new_block_text}\3", content)
            diff_text = self._generate_diff_text(content, updated_content, relative_path)
            if diff_text.strip():
                self._backup_file(full)
                await self._store_diff_file(relative_path, diff_text)
                try:
                    full.write_text(updated_content, encoding="utf-8")
                    log_info(f"♻️ Replaced block '{identifier}' in {relative_path}")
                    try:
                        trace.log_file_write(str(full), relative_path)
                    except Exception:
                        pass
                    await emit_event({"type": "code_written", "file": relative_path, "identifier": identifier, "action": "replaced"})
                except Exception as e:
                    log_error(f"❌ Failed to write replaced block to {full}: {e}")
                    await emit_event({"type": "code_write_failed", "file": relative_path, "identifier": identifier, "error": str(e)})
            else:
                log_info(f"ℹ️ Replacement produced no changes for '{identifier}' in {relative_path}")
                await emit_event({"type": "code_skipped", "file": relative_path, "identifier": identifier, "reason": "no_changes"})
        else:
            # Append block with markers
            appended = content + "\n" + f"# BEGIN {identifier}\n{new_block_text}# END {identifier}\n"
            diff_text = self._generate_diff_text(content, appended, relative_path)
            if diff_text.strip():
                self._backup_file(full)
                await self._store_diff_file(relative_path, diff_text)
                try:
                    full.write_text(appended, encoding="utf-8")
                    log_info(f"➕ Appended block '{identifier}' to {relative_path}")
                    try:
                        trace.log_file_write(str(full), relative_path)
                    except Exception:
                        pass
                    await emit_event({"type": "code_written", "file": relative_path, "identifier": identifier, "action": "appended"})
                except Exception as e:
                    log_error(f"❌ Failed to append block to {full}: {e}")
                    await emit_event({"type": "code_write_failed", "file": relative_path, "identifier": identifier, "error": str(e)})
            else:
                log_info(f"ℹ️ Append produced no changes for '{identifier}' in {relative_path}")
                await emit_event({"type": "code_skipped", "file": relative_path, "identifier": identifier, "reason": "no_changes"})

        # --- CONTEXT UPDATE ---
        self.context_manager.add_file_block(relative_path, identifier)
        self.context_manager.save_context()
        log_info(f"🧠 Context updated for block '{identifier}' in {relative_path}")

    async def append_code(self, relative_path: str, code: str):


        relative_path = self._normalize_relative_path(relative_path)
        try:
            full = self._full_path(relative_path)
        except Exception as e:
            log_error(f"❌ Invalid path for append_code({relative_path}): {e}")
            await emit_event({"type": "file_append_failed", "file": relative_path, "error": str(e)})
            return

        full.parent.mkdir(parents=True, exist_ok=True)

        if not isinstance(code, str):
            code = str(code)
        if not code.strip():
            log_warning(f"⚠️ Attempted to append empty content to {relative_path}; skipping.")
            await emit_event({"type": "file_skipped", "file": relative_path, "reason": "empty_append"})
            return

        old_content = ""
        if full.exists():
            try:
                old_content = full.read_text(encoding="utf-8")
            except Exception as e:
                log_error(f"❌ Failed to read {full} before append: {e}")

        new_content = old_content + "\n" + code.strip() + "\n"
        diff_text = self._generate_diff_text(old_content, new_content, relative_path)

        if diff_text.strip():
            self._backup_file(full)
            await self._store_diff_file(relative_path, diff_text)
            try:
                full.write_text(new_content, encoding="utf-8")
                log_info(f"📎 Appended code to {relative_path}")
                try:
                    trace.log_file_write(str(full), relative_path)
                except Exception:
                    pass
                await emit_event({"type": "file_appended", "file": relative_path})
            except Exception as e:
                log_error(f"❌ Failed to append to {full}: {e}")
                await emit_event({"type": "file_append_failed", "file": relative_path, "error": str(e)})

            # --- CONTEXT UPDATE ---
            self.context_manager.add_file_code(relative_path, code)
            self.context_manager.save_context()
            log_info(f"🧠 Context updated for appended code in {relative_path}")

        else:
            log_info(f"ℹ️ Append produced no changes for {relative_path}")
            await emit_event({"type": "file_skipped", "file": relative_path, "reason": "no_changes"})

    async def edit_file_with_ai(self, relative_path: str, instructions: str):
        """Edits a file using CodeGenerator; works with sync or async generator."""


        relative_path = self._normalize_relative_path(relative_path)
        try:
            full = self._full_path(relative_path)
        except Exception as e:
            log_error(f"❌ Invalid path for edit_file_with_ai({relative_path}): {e}")
            await emit_event({"type": "file_edit_failed", "file": relative_path, "reason": "invalid_path", "error": str(e)})
            return

        if not full.exists():
            log_error(f"❌ Cannot edit {relative_path} — file does not exist.")
            await emit_event({"type": "file_edit_failed", "file": relative_path, "reason": "not_found"})
            return

        try:
            old_content = full.read_text(encoding="utf-8")
        except Exception as e:
            log_error(f"❌ Failed to read {full}: {e}")
            await emit_event({"type": "file_edit_failed", "file": relative_path, "reason": "read_error", "error": str(e)})
            return

        description = f"Edit this file to follow these instructions:\n{instructions}\nThe current content is:\n{old_content}"

        try:
            new_content = await self._maybe_await_generator(relative_path, description)
        except Exception as e:
            log_error(f"❌ AI edit generation failed for {relative_path}: {e}")
            await emit_event({"type": "file_edit_failed", "file": relative_path, "reason": "generation_failed", "error": str(e)})
            return

        if not isinstance(new_content, str):
            new_content = str(new_content)

        if not new_content.strip():
            log_warning(f"⚠️ AI returned empty content for {relative_path}; skipping.")
            await emit_event({"type": "file_skipped", "file": relative_path, "reason": "empty_ai_output"})
            return

        diff_text = self._generate_diff_text(old_content, new_content, relative_path)
        if not diff_text.strip():
            log_info(f"ℹ️ AI edit produced no changes for {relative_path}; skipping write.")
            await emit_event({"type": "file_skipped", "file": relative_path, "reason": "no_changes"})
            return

        self._backup_file(full)
        await self._store_diff_file(relative_path, diff_text)
        try:
            full.write_text(new_content, encoding="utf-8")
            log_info(f"🤖 Edited file with AI: {relative_path}")
            await emit_event({"type": "file_edited", "file": relative_path})
        except Exception as e:
            log_error(f"❌ Failed to write AI-edited content to {full}: {e}")
            await emit_event({"type": "file_edit_failed", "file": relative_path, "reason": "write_failed", "error": str(e)})
