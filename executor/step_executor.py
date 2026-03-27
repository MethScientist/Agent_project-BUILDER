# File: executor/step_executor.py
print("[START] executor.step_executor module loaded", flush=True)

import os
import re
import asyncio
import inspect
import runtime_trace as trace
from pathlib import Path



from executor.file_creator import FileCreator
from executor.code_writer import CodeWriter
from executor.language_detector import LanguageDetector  # ✅ use GPT detector
from ai_models.gpt_interface import GPTInterface
from ai_models.unity_generator import UnityGenerator
from utils.logger import log_info, log_warning, log_error
from executor.agents.unity_agent import UnityAgent
from ai_agent_system.tracking.LiveTracker import LiveTracker
from server.tracker import emit_event  # ensure we can emit directly to WS
from config.settings import SETTINGS
from core.code_scanner import CodeScanner
from core.verifier import Verifier
from core.quality_assessor import QualityAssessor
from context_awareness.manager import ContextManager
from executor.code_orchestrator import CodeOrchestrator
from core.project_map import build_project_map
from core.dependency_resolver import DependencyResolver

class StepExecutor:
    def __init__(self, memory_manager, context_manager=None, project_root=None):
        print("[INIT] StepExecutor.__init__ start", flush=True)

        # ---- Context Manager ----
        print("[DEBUG] Initializing ContextManager...", flush=True)
        if context_manager:
            self.context_manager = context_manager
            print(f"[DEBUG] ContextManager passed in: {self.context_manager}", flush=True)
        else:
            context_path = os.path.join(self.project_root, "context_awareness", "context.json")
            print(f"[DEBUG] ContextManager will be created at: {context_path}", flush=True)
            self.context_manager = ContextManager(save_path=context_path)
            print(f"[DEBUG] ContextManager instance created: {self.context_manager}", flush=True)
            try:
                self.context_manager.load_context()
                print("[DEBUG] ContextManager.load_context() completed", flush=True)
            except Exception as e:
                print(f"[ERROR] ContextManager.load_context() failed: {e}", flush=True)
                raise

        self.memory = memory_manager

        self.creator = FileCreator()
        self.detector = LanguageDetector()
        self.gpt = GPTInterface(role="executor")

        self.subagents = {"unity": UnityAgent(context_manager=self.context_manager)}

        self.project_root = os.path.abspath(
            project_root or SETTINGS.get("project_root") or "."
        )

        self.verifier = Verifier(model=self.gpt)


        # ---- CodeWriter ----
        print("[DEBUG] Initializing CodeWriter...", flush=True)
        try:
            self.writer = CodeWriter(
                context_manager=self.context_manager,
                project_root=self.project_root
            )
            print(f"[DEBUG] CodeWriter initialized: {self.writer}", flush=True)
            print(f"[DEBUG] CodeWriter.project_root = {self.writer.project_root}", flush=True)
            print(f"[DEBUG] CodeWriter.context_manager = {self.writer.context_manager}", flush=True)
        except Exception as e:
            print(f"[ERROR] CodeWriter initialization failed: {e}", flush=True)
            raise

        # ---- Verifier context (initial) ----
        try:
            project_map = build_project_map(self.project_root)
            resolver = DependencyResolver(project_map, self.project_root)
            # Attach project map/resolver to writer for reuse
            try:
                self.writer.project_map = project_map
                self.writer.resolver = resolver
            except Exception:
                pass
            # Provide the verifier with the initial project view
            try:
                self.verifier.set_context(
                    project_root=self.project_root,
                    project_map=project_map,
                    dependency_resolver=resolver,
                    context_manager=self.context_manager,
                )
                print("[DEBUG] Verifier context initialized", flush=True)
                try:
                    # instantiate quality assessor for training signals
                    self.quality_assessor = QualityAssessor(self.project_root, project_map)
                    print("[DEBUG] QualityAssessor initialized", flush=True)
                except Exception:
                    self.quality_assessor = QualityAssessor(self.project_root, None)
                    print("[WARN] QualityAssessor initialization fallback", flush=True)
            except Exception as e:
                print(f"[WARN] Failed to set verifier context: {e}", flush=True)
        except Exception as e:
            print(f"[WARN] Failed to build initial project_map for verifier: {e}", flush=True)


        # ---- CodeOrchestrator (KEY FIX) ----
        self.code_orchestrator = CodeOrchestrator(
            context_manager=self.context_manager,
            project_root=self.project_root
        )

        print("[INIT] StepExecutor.__init__ end", flush=True)


    def _abs_path(self, path: str) -> str:
        if not path:
            res = os.path.abspath(self.project_root or ".")
            try:
                trace.log_path(path, res)
            except Exception:
                pass
            return res
        if os.path.isabs(path):
            res = path
            try:
                trace.log_path(path, res)
            except Exception:
                pass
            return res
        project_root = self.project_root or "."
        try:
            rel_root = os.path.relpath(project_root, os.getcwd()).replace("\\", "/")
        except Exception:
            rel_root = None
        norm = path.replace("\\", "/")
        # Normalize planner-provided repo-relative paths so they map inside the
        # configured `project_root` instead of being nested under it. Common planner
        # behavior includes returning paths like `test_project/dependency_demo/...`.
        # We drop a leading repo top-level folder (e.g. `test_project`) and then
        # drop the following segment if it is not part of the current project_root
        # (this maps `test_project/dependency_demo/...` -> `...` under project_root).
        if rel_root:
            # quick return when path exactly equals rel_root
            if norm == rel_root:
                return os.path.abspath(project_root)

            rel_parts = rel_root.split("/")
            norm_parts = norm.split("/")

            # If the first segment matches the repo top-level folder, drop it
            if rel_parts and norm_parts and norm_parts[0] == rel_parts[0]:
                norm_parts = norm_parts[1:]

                # If the next segment is not part of the project_root relative parts,
                # also drop it to avoid creating nested sibling folders.
                proj_parts = rel_parts
                if norm_parts and norm_parts[0] not in proj_parts:
                    norm_parts = norm_parts[1:]

            # Rebuild normalized path
            norm = "/".join(p for p in norm_parts if p)
            # If the path still begins with rel_root, strip that prefix
            if norm.startswith(rel_root + "/"):
                norm = norm[len(rel_root) + 1 :]
        res = os.path.abspath(os.path.join(project_root, norm))
        try:
            trace.log_path(path, res)
        except Exception:
            pass
        return res

    def _rel_path(self, abs_or_rel_path: str) -> str:
        """Return a path relative to project_root suitable for CodeWriter.
        If path is already relative, return as-is."""
        if os.path.isabs(abs_or_rel_path):
            try:
                rel = os.path.relpath(abs_or_rel_path, self.project_root)
            except Exception:
                rel = abs_or_rel_path
            res = rel.replace("\\", "/")
            try:
                trace.log_path(abs_or_rel_path, res)
            except Exception:
                pass
            return res
        res = abs_or_rel_path.replace("\\", "/")
        try:
            trace.log_path(abs_or_rel_path, res)
        except Exception:
            pass
        return res
        
    def _build_dependency_context(self, step: dict) -> str:
        """
        Build a detailed context string from all dependency files.
        Includes relative paths, file types, and cleanly delimited content.
        """
        deps = step.get("depends_on", [])
        if not deps:
            # Auto-include a few same-extension files in the project for context
            target_path = step.get("target_path") or ""
            ext = os.path.splitext(target_path)[1].lower()
            if ext:
                auto = []
                for root, _, files in os.walk(self.project_root):
                    if "/.diffs" in root.replace("\\", "/") or "/.backups" in root.replace("\\", "/"):
                        continue
                    for f in files:
                        if not f.lower().endswith(ext):
                            continue
                        abs_f = os.path.join(root, f)
                        rel_f = os.path.relpath(abs_f, self.project_root).replace("\\", "/")
                        if rel_f == target_path.replace("\\", "/"):
                            continue
                        auto.append(rel_f)
                        if len(auto) >= 4:
                            break
                    if len(auto) >= 4:
                        break
                deps = auto
            if not deps:
                return ""

        context_parts = []
        target_path = step.get("target_path") or ""
        base_dir = os.path.dirname(target_path).replace("\\", "/")

        for dep in deps:
            abs_dep = self._abs_path(dep)
            if not os.path.exists(abs_dep) and base_dir and not os.path.isabs(dep):
                # try resolving relative to target directory
                abs_dep = self._abs_path(os.path.join(base_dir, dep))
            try:
                if os.path.exists(abs_dep) and os.path.isfile(abs_dep):
                    ext = os.path.splitext(abs_dep)[1].lower()
                    lang_hint = {
                        ".py": "python",
                        ".js": "javascript",
                        ".ts": "typescript",
                        ".html": "html",
                        ".css": "css",
                        ".json": "json",
                    }.get(ext, "text")

                    with open(abs_dep, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    # wrap each dependency with labeled boundaries
                    context_parts.append(
                        f"\n# BEGIN DEPENDENCY [{lang_hint}] :: {dep}\n"
                        f"{content.strip()}\n"
                        f"# END DEPENDENCY :: {dep}\n"
                    )
                else:
                    log_warning(f"⚠ Dependency path invalid or missing: {abs_dep}")
            except Exception as e:
                log_error(f"❌ Failed reading dependency {abs_dep}: {e}")

        return "\n".join(context_parts)

    def _infer_language_from_path(self, path: str) -> str:
        if not path:
            return "text"
        ext = os.path.splitext(path)[1].lower()
        if ext == ".py":
            return "python"
        if ext == ".cs":
            return "c#"
        if ext in (".html", ".htm"):
            return "html"
        if ext in (".js", ".ts"):
            return "javascript"
        return "text"

    def _extract_literal_write_content(self, description: str) -> str | None:
        if not description:
            return None
        # Prefer backtick-delimited content: write ... `content`
        m = re.search(r"write(?: the text)?\s*:?\s*`([^`]+)`", description, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        # Fallback: "write: <content>" until end of line
        m = re.search(r"write\s*:?\s*(.+)$", description, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return None

    def _should_overwrite_file(self, abs_path: str) -> bool:
        if not abs_path or not os.path.exists(abs_path):
            return True
        try:
            content = open(abs_path, "r", encoding="utf-8", errors="ignore").read()
        except Exception:
            return False
        stripped = content.strip()
        if not stripped:
            return True
        # If file is mostly markers or placeholders, overwrite with full content
        if "# BEGIN" in stripped and "# END" in stripped:
            return True
        if len(stripped.splitlines()) < 5:
            return True
        return False

    def _extract_file_refs(self, text: str) -> list[str]:
        if not text:
            return []
        # Capture common filename patterns with extensions
        pattern = r"([A-Za-z0-9_./\\-]+\.(?:py|js|ts|jsx|tsx|mjs|cjs|cs|json|html|htm|css))"
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        # normalize slashes and de-dupe while preserving order
        seen = set()
        refs = []
        for m in matches:
            ref = m.replace("\\", "/")
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)
        return refs

    def _extract_file_spec(self, user_prompt: str, target_path: str) -> str | None:
        """
        Best-effort extraction of a file-specific requirement line from the user prompt.
        Looks for lines like: - `path/to/file.ext`: do something...
        """
        if not user_prompt or not target_path:
            return None
        try:
            rel = self._rel_path(self._abs_path(target_path))
        except Exception:
            rel = target_path
        text = user_prompt.replace("\r\n", "\n")
        rel_norm = rel.replace("\\", "/").lstrip("./")
        if not rel_norm or rel_norm == ".":
            return None

        candidates = [rel_norm]
        if rel_norm.startswith("./"):
            candidates.append(rel_norm[2:])
        if rel_norm.startswith("/"):
            candidates.append(rel_norm.lstrip("/"))

        for cand in candidates:
            if not cand:
                continue
            m = re.search(rf"`{re.escape(cand)}`\s*:\s*(.+)", text)
            if m:
                return m.group(1).strip()
            m = re.search(rf"{re.escape(cand)}\s*:\s*(.+)", text)
            if m:
                return m.group(1).strip()
        return None

    def _extract_required_namespace(self, text: str) -> str | None:
        if not text:
            return None
        clean = text.replace("`", "")
        m = re.search(r"namespace\s+([A-Za-z0-9_.]+)", clean)
        return m.group(1) if m else None

    def _extract_required_usings(self, text: str) -> list[str]:
        if not text:
            return []
        clean = text.replace("`", "")
        found = re.findall(r"using\s+([A-Za-z0-9_.]+)", clean)
        # de-dupe, preserve order
        seen = set()
        ordered = []
        for ns in found:
            if ns in seen:
                continue
            seen.add(ns)
            ordered.append(ns)
        return ordered

    def _ensure_cs_usings(self, code: str, required: list[str]) -> str:
        if not required:
            return code
        existing = set(re.findall(r"^\s*using\s+([A-Za-z0-9_.]+)\s*;", code, flags=re.M))
        missing = [ns for ns in required if ns and ns not in existing]
        if not missing:
            return code
        insert_block = "".join([f"using {ns};\n" for ns in missing])
        m = re.search(r"(^\s*(?:using\s+[^;]+;\s*\n)+)", code, flags=re.M)
        if m:
            return code[:m.end(1)] + insert_block + code[m.end(1):]
        return insert_block + "\n" + code

    def _wrap_cs_namespace(self, code: str, namespace: str) -> str:
        if not namespace:
            return code
        lines = code.splitlines()
        i = 0
        while i < len(lines) and lines[i].strip().startswith("using "):
            i += 1
        using_block = "\n".join(lines[:i]).strip()
        rest = "\n".join(lines[i:]).strip()
        if rest:
            indented = "\n".join(("    " + line if line.strip() else "") for line in rest.splitlines())
        else:
            indented = ""
        body = f"namespace {namespace}\n{{\n{indented}\n}}\n"
        if using_block:
            return using_block + "\n\n" + body
        return body

    def _enforce_cs_contract(self, code: str, spec_text: str | None) -> str:
        if not spec_text:
            return code
        required_ns = self._extract_required_namespace(spec_text)
        required_usings = self._extract_required_usings(spec_text)
        updated = code
        if required_ns:
            if re.search(r"namespace\s+[A-Za-z0-9_.]+", updated):
                updated = re.sub(r"namespace\s+[A-Za-z0-9_.]+", f"namespace {required_ns}", updated, count=1)
            else:
                updated = self._wrap_cs_namespace(updated, required_ns)
        if required_usings:
            updated = self._ensure_cs_usings(updated, required_usings)
        return updated

    def _merge_dependencies(self, step: dict, description: str) -> None:
        deps = step.get("depends_on") or []
        if not isinstance(deps, list):
            deps = []
        deps.extend(self._extract_file_refs(description))
        # de-dupe, preserve order
        seen = set()
        merged = []
        for d in deps:
            if not d:
                continue
            if d in seen:
                continue
            seen.add(d)
            merged.append(d)
        if merged:
            step["depends_on"] = merged

    def _gpt_generate_code(self, step: dict, description: str, target_path: str, language: str) -> str:
        """
        Synchronous helper to build prompt and call GPT (intended to run in executor).
        Returns generated code text (string).
        """
        dep_context = self._build_dependency_context(step)
        user_prompt = step.get("user_prompt") or ""
        file_spec = step.get("file_spec") or self._extract_file_spec(user_prompt, target_path)

        lang_rules = ""
        lang_lower = (language or "").lower()
        path_lower = (target_path or "").lower()
        if lang_lower in ("c#", "cs", "csharp") or path_lower.endswith(".cs"):
            lang_rules = """C# rules:
- If the spec mentions a namespace, use it exactly.
- If the spec mentions a using directive, include it exactly.
- Do not add framework base classes or attributes unless explicitly required.
"""
        elif lang_lower in ("javascript", "typescript") or path_lower.endswith((".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs")):
            lang_rules = """JS/TS rules:
- If the spec says to export a function, define and export it in this file.
- Do not re-export identifiers without defining them unless the spec says so.
- Use correct relative import paths for project-local files.
"""
        elif lang_lower == "python" or path_lower.endswith(".py"):
            lang_rules = """Python rules:
- Use explicit imports for project-local modules when referenced.
- Match function/class names exactly as described.
"""

        prompt = f"""
You are the project's main coding agent.

Global project spec (read for exact file requirements):
{user_prompt or "(none)"}

File-specific requirements (must follow exactly; do not omit):
{file_spec or "(none found)"}

Task: Implement the following feature for the target file only.
Description: {description}

Target file: {target_path}
Language: {language}

Here are all related dependency files to ensure consistency:
{dep_context or "(no dependencies provided)"}

Rules:
- Only implement the target file. Do not create or reference other files unless required by the spec.
- Do not invent imports, classes, or functions.
- Keep code short and readable.
{lang_rules}

Return only the complete file content, no markdown.
"""
        generated = self.gpt.ask_gpt(prompt)
        if path_lower.endswith(".cs") or lang_lower in ("c#", "cs", "csharp"):
            generated = self._enforce_cs_contract(generated, file_spec)
        return generated

    async def execute_step(self, step, max_retries=3):
        print("[ASYNC ENTER] execute_step", flush=True)

        step_type = step.get("type")
        path = step.get("target_path")
        description = step.get("description") or ""
        # set current tracing step early so all activities are attributed
        step_id = step.get("id") or description
        try:
            trace.set_current_step(step_id)
        except Exception:
            pass
        agent_name = (step.get("agent") or "default").lower()
        # Force C# or UnityGame/Scripts steps through default agent to honor target paths
        if agent_name == "unity":
            p = (path or "").replace("\\", "/")
            if p.endswith(".cs") or "UnityGame" in p:
                agent_name = "default"

        log_info(f"▶ execute_step called for: id={step.get('id') or 'no-id'} type={step_type} target={path} agent={agent_name}")

        attempt = 0

        if self.memory.is_step_done(step):
            log_info(f"⏭️ Step already completed: {description}")
            await emit_event({"type": "task_skipped", "description": description, "target_path": path})
            await asyncio.sleep(0)
            try:
                trace.clear_current_step()
            except Exception:
                pass
            return {"status": "skipped", "step": step}

        # Emit step started
        step_id = step.get("id") or description
        await emit_event({
            "type": "task_started",
            "step_id": step_id,
            "description": description,
            "agent": agent_name,
            "target_path": path
        })
        await asyncio.sleep(0)

        while attempt < max_retries:
            try:
                log_info(f"⚙️ Attempt {attempt + 1}/{max_retries} → Executing: {description}")

                # ------------- Sub-agent routing -------------
                print(f"[ROUTE] agent={agent_name}", flush=True)

                if agent_name != "default" and agent_name in self.subagents:
                    log_info(f"🤖 Routing step to sub-agent: {agent_name}")
                    sub = self.subagents[agent_name]
                    # sub.execute_step may be sync or async
                    if asyncio.iscoroutinefunction(getattr(sub, "execute_step", None)):
                        result = await sub.execute_step(step)
                    else:
                        result = await asyncio.get_running_loop().run_in_executor(None, sub.execute_step, step)

                else:
                    # Normalize path handling
                    abs_path = self._abs_path(path) if path else None
                    rel_path = self._rel_path(abs_path) if abs_path else None

                    # Merge any inferred dependencies (file refs in description)
                    self._merge_dependencies(step, description)

                    # Track which file (if any) was created/modified during this step
                    modified_rel_path = None

                    # Ensure file/folder creation happens when appropriate
                    if step_type == "create_folder":
                        # Prefer creator API for consistent logging
                        self.creator.create_folder(rel_path)
                        await LiveTracker.folder_created(self._abs_path(rel_path))
                        await emit_event({"type": "file_system", "action": "folder_created", "path": self._abs_path(rel_path)})
                        result = {"status": "success"}
                        modified_rel_path = None

                    elif step_type == "ensure_folder":
                        # Planner may emit absolute paths; ensure the folder exists.
                        abs_target = self._abs_path(path)
                        os.makedirs(abs_target, exist_ok=True)
                        log_info(f"📁 Ensured folder (ensure_folder): {abs_target}")
                        await LiveTracker.folder_created(abs_target)
                        await emit_event({"type": "file_system", "action": "folder_ensured", "path": abs_target})
                        result = {"status": "success"}
                        modified_rel_path = None

                    elif step_type == "change_directory":
                        # Change executor's project root so subsequent steps operate in the new context.
                        new_root = self._abs_path(path)
                        if not os.path.isdir(new_root):
                            os.makedirs(new_root, exist_ok=True)
                        # Update executor/project components to use new root
                        old_root = self.project_root
                        self.project_root = os.path.abspath(new_root)
                        try:
                            from config import settings as _settings
                            _settings.SETTINGS["project_root"] = self.project_root
                        except Exception:
                            pass

                        # Update writer, creator, and scanner to reflect new project root
                        try:
                            self.writer.project_root = Path(self.project_root).resolve()
                            # rebuild maps and resolver
                            self.writer.project_map = build_project_map(str(self.writer.project_root))
                            self.writer.resolver = DependencyResolver(self.writer.project_map, str(self.writer.project_root))
                            self.writer.scanner = CodeScanner(self.writer.project_root)
                            # Update verifier with new project context after changing root
                            try:
                                self.verifier.set_context(
                                    project_root=self.project_root,
                                    project_map=self.writer.project_map,
                                    dependency_resolver=self.writer.resolver,
                                    context_manager=self.context_manager,
                                )
                            except Exception as e:
                                log_warning(f"⚠️ Failed setting verifier context after change_directory: {e}")
                        except Exception as e:
                            log_warning(f"⚠️ Failed updating CodeWriter project root: {e}")

                        try:
                            self.creator.project_root = os.path.abspath(self.project_root)
                        except Exception:
                            pass

                        # reload context from new location
                        try:
                            self.context_manager.load_context()
                        except Exception:
                            pass

                        log_info(f"📂 Changed execution project root from {old_root} to {self.project_root}")
                        await LiveTracker.log(f"📂 Changed working project root to: {self.project_root}")
                        await emit_event({"type": "file_system", "action": "changed_root", "path": self.project_root})
                        result = {"status": "success"}
                        modified_rel_path = None

                    elif step_type in ("create_file", "create_class", "create_function", "implement_feature"):
                        # Always ensure the file exists first (create empty if missing)
                        if rel_path:
                            try:
                                # ensure directory exists without writing empty files (defer actual write to CodeWriter)
                                self.creator.create_file(rel_path, content=None)
                            except Exception as e:
                                log_error(f"❌ Failed to ensure file exists {rel_path}: {e}")
                                raise

                        if step_type == "create_file":
                            # Special-case create_file: write literal content if described
                            content = step.get("content")
                            if not content:
                                content = self._extract_literal_write_content(description)
                            if content:
                                await self.writer.write_file(rel_path, content)
                            else:
                                dep_context = self._build_dependency_context(step)
                                await self.writer.generate_and_write_file(rel_path, description, dep_context)
                            result = {"status": "success"}
                            modified_rel_path = rel_path

                        else:
                            dep_context = self._build_dependency_context(step)
                            # Decide the language and use the most specific path available
                            # Prefer explicit detection, fall back to extension-based inference
                            detected_lang = None
                            try:
                                detected_lang = (self.detector.detect_language(path, description) or "").strip().lower()
                            except Exception:
                                detected_lang = None

                            if not detected_lang and rel_path:
                                detected_lang = self._infer_language_from_path(rel_path)

                            # Default write target (may be overwritten for implement_feature)
                            write_rel = rel_path

                            # If it's an implement_feature step, generate code (GPT path) and write to the target file
                            if step_type == "implement_feature":
                                language = detected_lang or "python"

                                # Use explicit target path when available; otherwise build one
                                if not write_rel:
                                    write_rel = self._rel_path(self._abs_path(self._get_code_path(description, language)))

                                # Unity/C# special-casing when target is .cs or description mentions unity
                                if agent_name == "unity" and (language.lower() == "c#" or "unity" in description.lower() or (write_rel and write_rel.endswith('.cs'))):
                                    # call Unity generator on executor thread
                                    def sync_unity():
                                        generator = UnityGenerator()
                                        # use a simple heuristic to choose what to generate
                                        desc_l = description.lower()
                                        if "player" in desc_l:
                                            generator.generate_player_controller()
                                        elif "camera" in desc_l:
                                            generator.generate_camera_follow()
                                        elif "game manager" in desc_l or "manager" in desc_l:
                                            generator.generate_game_manager()
                                        else:
                                            # fallback: generate a named script file using the target name
                                            base_name = os.path.splitext(os.path.basename(write_rel))[0]
                                            generator.generate_script(base_name, logic="// Unity logic here")

                                    await asyncio.get_running_loop().run_in_executor(None, sync_unity)
                                    log_info("🧩 Unity logic generated")
                                    await emit_event({"type": "unity", "action": "generated", "feature": description, "path": write_rel})
                                    result = {"status": "success"}
                                    modified_rel_path = write_rel

                                else:
                                    await emit_event({
                                        "type": "dependency_context",
                                        "message": f"Using {len(step.get('depends_on', []))} dependency files for {path}",
                                        "target_path": path
                                    })

                                    # Generate code via GPT in threadpool
                                    print(f"[GPT] generating code for {write_rel}", flush=True)

                                    generated_code = await asyncio.get_running_loop().run_in_executor(
                                        None, self._gpt_generate_code, step, description, path, language
                                    )

                                    if not generated_code or not str(generated_code).strip():
                                        raise RuntimeError("GPT returned empty code")

                                    abs_target = self._abs_path(write_rel)
                                    if self._should_overwrite_file(abs_target):
                                        await self.writer.write_file(write_rel, generated_code)
                                        print(f"[WRITE OK] {write_rel}", flush=True)
                                        result = {"status": "success"}
                                        modified_rel_path = write_rel
                                    else:
                                        # Decide identifier (function/class) heuristically
                                        identifier = None
                                        m_func = re.search(r"def\s+([A-Za-z_]\w*)\s*\(", generated_code)
                                        m_class = re.search(r"class\s+([A-Za-z_]\w*)\s*[:\(]", generated_code)
                                        if m_func:
                                            identifier = f"def {m_func.group(1)}"
                                        elif m_class:
                                            identifier = f"class {m_class.group(1)}"
                                        else:
                                            identifier = description.split('\n', 1)[0][:120]

                                        # Use writer API to replace or append block inside the target file
                                        await self.writer.write_or_replace_block(write_rel, identifier, generated_code)
                                        print(f"[WRITE OK] {write_rel}", flush=True)
                                        result = {"status": "success"}
                                        modified_rel_path = write_rel
                                        await emit_event({"type": "task_progress", "message": f"Code written to {write_rel}", "path": write_rel})

                            else:
                                # For create_class/create_function: prefer to ask CodeOrchestrator (existing helper)
                                # but guarantee it writes into the planned target path
                                def sync_task():
                                    agent = self.code_orchestrator
                                    if step_type == "create_class":
                                        agent.generate_and_insert_class(rel_path, description, dep_context)
                                    else:
                                        agent.generate_and_insert_function(rel_path, description, dep_context)

                                await asyncio.get_running_loop().run_in_executor(None, sync_task)
                                result = {"status": "success"}
                                modified_rel_path = rel_path

                    elif step_type == "scan_and_fix_project":
                        # Run the project-wide scanner/fixer (safe by default: dry_run=True)
                        params = step.get("params", {}) or {}
                        dry_run = params.get("dry_run", True)
                        max_passes = params.get("max_passes", 2)
                        backup_root = params.get("backup_root", None)

                        # Emit explicit event
                        await emit_event({
                            "type": "scan_started",
                            "step_id": step_id,
                            "description": description or "Scan & fix project",
                            "dry_run": dry_run,
                            "max_passes": max_passes
                        })

                        def sync_scan():
                            scanner = CodeScanner(project_root=self.project_root, backup_root=backup_root, gpt=self.gpt)
                            return scanner.fix_project(dry_run=dry_run, max_passes=max_passes)

                        # run in threadpool because scanner does file IO + cpu work
                        scan_result = await asyncio.get_running_loop().run_in_executor(None, sync_scan)

                        # emit scan completed with details
                        await emit_event({
                            "type": "scan_completed",
                            "step_id": step_id,
                            "result": scan_result
                        })

                        # Decide how to mark the step: if dry_run just mark "skipped" (or success depending on desired semantics).
                        if dry_run:
                            # do not apply changes—just report
                            result = {"status": "dry_run", "scan_result": scan_result}
                        else:
                            # If not dry_run, treat as success if scanner reports changed_files or no errors
                            # You can tighten logic (e.g., check for validation errors)
                            result = {"status": "success", "scan_result": scan_result}
                        modified_rel_path = None

                    elif step_type == "modify_file":
                        params = step.get("params", {}) or {}
                        rel_path = self._rel_path(self._abs_path(path))
                        try:
                            self.writer.modify_file(rel_path, **params)
                            await emit_event({
                                "type": "task_progress",
                                "message": f"Modified file {rel_path}",
                                "path": rel_path
                            })
                            result = {"status": "success"}
                            modified_rel_path = rel_path
                        except Exception as e:
                            log_error(f"❌ the_file failed for {rel_path}: {e}")
                            result = {"status": "fail", "reason": str(e)}
                            modified_rel_path = None

                    else:
                        log_warning(f"⚠️ Unknown step type reached: {step_type}")
                        result = {"status": "fail", "reason": "Unknown step type", "step": step}
                        modified_rel_path = None

                    # --- Run verifier and autotester for any modified file ---
                    if modified_rel_path:
                        abs_modified = self._abs_path(modified_rel_path)
                        try:
                            # Run verifier.verify_file in threadpool
                            print(f"[VERIFY] start {modified_rel_path}", flush=True)

                            # Ensure verifier has an up-to-date project context before running
                            try:
                                pm = getattr(self.writer, "project_map", None)
                                if not pm:
                                    pm = build_project_map(self.project_root)
                                    try:
                                        self.writer.project_map = pm
                                    except Exception:
                                        pass
                                resolver = getattr(self.writer, "resolver", None)
                                if not resolver:
                                    resolver = DependencyResolver(self.writer.project_map, self.project_root)
                                    try:
                                        self.writer.resolver = resolver
                                    except Exception:
                                        pass
                                try:
                                    self.verifier.set_context(
                                        project_root=self.project_root,
                                        project_map=self.writer.project_map,
                                        dependency_resolver=self.writer.resolver,
                                        context_manager=self.context_manager,
                                    )
                                except Exception as e:
                                    log_warning(f"⚠️ Failed updating verifier context before verification: {e}")
                            except Exception as e:
                                log_warning(f"⚠️ Error while preparing verifier context: {e}")

                            verify_result = await asyncio.get_running_loop().run_in_executor(
                                None, self.verifier.verify_file, abs_modified
                            )

                            # If verification reported an error, attempt auto-fix then re-verify
                            if verify_result and verify_result.get("status") == "error":
                                log_warning(f"🔍 Verification failed for {modified_rel_path}: {verify_result.get('error', '')[:200]}")
                                try:
                                    # auto_fix may modify the file on disk
                                    fixed_code = await asyncio.get_running_loop().run_in_executor(
                                        None, self.verifier.auto_fix, abs_modified, verify_result.get("error", "")
                                    )
                                    await emit_event({
                                        "type": "auto_fix_applied",
                                        "path": modified_rel_path,
                                        "message": "Verifier attempted auto-fix"
                                    })
                                    log_info(f"✅ Auto-fix attempted for {modified_rel_path}")

                                    # re-run verification after auto-fix
                                    verify_result = await asyncio.get_running_loop().run_in_executor(
                                        None, self.verifier.verify_file, abs_modified
                                    )
                                    if verify_result and verify_result.get("status") == "ok":
                                        log_info(f"✅ Verification passed after auto-fix for {modified_rel_path}")
                                    else:
                                        log_error(f"❌ Verification still failing for {modified_rel_path}: {verify_result}")
                                        result = {"status": "fail", "reason": "verification_failed", "verify_result": verify_result}

                                except Exception as e_fix:
                                    log_error(f"❌ Auto-fix failed for {modified_rel_path}: {e_fix}")
                                    result = {"status": "fail", "reason": "auto_fix_failed", "error": str(e_fix)}

                        except Exception as e:
                            log_error(f"❌ Verifier failed for {modified_rel_path}: {e}")
                            # treat verifier failures as non-fatal but surface them
                            result = {"status": "fail", "reason": "verifier_exception", "error": str(e)}
                        print(f"[VERIFY] end {modified_rel_path}", flush=True)
                            # --- Quality assessment for training signal ---
                        try:
                            if not hasattr(self, 'quality_assessor') or self.quality_assessor is None:
                                self.quality_assessor = QualityAssessor(self.project_root, getattr(self.writer, 'project_map', None))
                            qa_report = await asyncio.get_running_loop().run_in_executor(
                                None, self.quality_assessor.assess_file, abs_modified
                            )
                            await emit_event({
                                "type": "quality_assessment",
                                "path": modified_rel_path,
                                "quality_report": qa_report.to_dict(),
                                "quality_score": qa_report.overall_score,
                                "is_acceptable": qa_report.is_acceptable,
                            })
                            if not qa_report.is_acceptable:
                                log_warning(f"⚠️ Low quality detected for {modified_rel_path}: score={qa_report.overall_score}")
                        except Exception as _qa_e:
                            log_warning(f"⚠️ Quality assessment failed for {modified_rel_path}: {_qa_e}")


                # Mark done and emit completion/failure events
                if result.get("status") == "success":
                    self.memory.mark_step_done(step)
                    await emit_event({
                        "type": "task_completed",
                        "step_id": step_id,
                        "description": description,
                        "target_path": path
                    })
                    await asyncio.sleep(0)
                else:
                    await emit_event({
                        "type": "task_failed",
                        "step_id": step_id,
                        "description": description,
                        "error": result.get("reason", "Unknown error")
                    })
                    await asyncio.sleep(0)

                print(f"[STEP DONE] {step_id}", flush=True)
                try:
                    trace.clear_current_step()
                except Exception:
                    pass
                return result

            except Exception as e:
                print(f"[STEP ERROR] attempt={attempt+1} id={step_id}", flush=True)

                log_error(f"❌ Step failed (attempt {attempt + 1}): {e}")
                # emit failure for this attempt
                await emit_event({
                    "type": "task_failed",
                    "step_id": step_id,
                    "description": description,
                    "error": str(e),
                    "attempt": attempt + 1
                })
                await asyncio.sleep(0)
                attempt += 1

        # All retries failed
        log_info(f"🛑 All {max_retries} attempts failed for step: {description}")
        await emit_event({
            "type": "task_failed",
            "step_id": step_id,
            "description": description,
            "error": f"All {max_retries} attempts failed"
        })
        await asyncio.sleep(0)
        print(f"[STEP FAIL] all retries exhausted id={step_id}", flush=True)
        try:
            trace.clear_current_step()
        except Exception:
            pass

        return {"status": "fail", "retries": attempt, "step": step}


    def _get_code_path(self, description, language):
        # sanitize description to filename safe string (simple)
        base = re.sub(r"[^\w\-_. ]", "", description).replace(" ", "_").lower()
        if language.lower() == "python":
            return f"backend/features/{base}.py"
        elif language.lower() == "html":
            return f"web/ui/{base}.html"
        elif language.lower() == "c#":
            return f"UnityGame/Scripts/{base}.cs"
        else:
            return f"features/{base}.txt"

    # keep sync unity helper if any existing code expects it
    def _handle_unity_logic(self, feature):
        try:
            generator = UnityGenerator()
            if "player" in feature.lower():
                generator.generate_player_controller()
            elif "camera" in feature.lower():
                generator.generate_camera_follow()
            elif "game manager" in feature.lower() or "manager" in feature.lower():
                generator.generate_game_manager()
            else:
                generator.generate_script(feature.replace(" ", ""), logic="// Unity logic here")
            log_info("🧩 Unity logic generated (sync)")
        except Exception as e:
            log_info(f"⚠️ Unity generation failed: {e}")
