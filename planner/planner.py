# planner/planner.py
print("[START] planner.planner module loaded", flush=True)

import os
import json
import asyncio
import re
import uuid
from typing import Any, Dict, List, Callable 
from utils.logger import log_info, log_warning, log_error
from planner.creative_enhancer import CreativeEnhancer
from planner.reasoning_chain import ReasoningChain
from planner.topological_sort import topological_sort_steps
from ai_agent_system.tracking.LiveTracker import LiveTracker
from ai_models.gpt_interface import GPTInterface
from executor.file_creator import FileCreator
from core.code_scanner import CodeScanner
from config.settings import SETTINGS
from core.project_map import build_project_map
from core.final_linker import FinalLinker
from context_awareness.manager import ContextManager
from executor.step_executor import StepExecutor

GPT_CALL_TIMEOUT=1200


def _extract_json_like(text: str) -> str:
    if not isinstance(text, str):
        return text

    # remove code fences and any whitespace/newlines before/after
    text = re.sub(r"```(?:json|text|javascript|python)?\n?", "", text, flags=re.IGNORECASE)
    text = text.strip()  # remove leading/trailing whitespace

    arr_match = re.search(r"(\[\s*\{.*\}\s*\])", text, flags=re.DOTALL)
    if arr_match:
        return arr_match.group(1)
    obj_match = re.search(r"(\{\s*\".*\}\s*\})", text, flags=re.DOTALL)
    if obj_match:
        return obj_match.group(1)
    bracket_match = re.search(r"(\[.*\])", text, flags=re.DOTALL)
    if bracket_match:
        return bracket_match.group(1)

    return text

def _plan_issues_to_fix(plan):
    """
    Scan plan steps for obvious issues and return a list of 'issues' suitable
    for auto_fix_with_context.
    Each issue should include:
      - 'line': index in the serialized plan JSON or related file
      - 'description': short note about the problem
      - other fields if needed
    """
    issues = []
    for idx, step in enumerate(plan):
        if not step.get("description") or not step.get("type") or not step.get("target_path"):
            issues.append({
                "line": idx + 1,  # for auto_fix_with_context, could map to plan snippet line
                "step_index": idx,
                "issue": "Missing description/type/target_path",
                "step": step
            })
    return issues


def _ensure_list_of_dicts(plan_candidate: Any) -> List[Dict]:
    if isinstance(plan_candidate, str):
        raw = _extract_json_like(plan_candidate)
        parsed = json.loads(raw)
    else:
        parsed = plan_candidate

    if isinstance(parsed, dict):
        for key in ("steps", "plan", "tasks"):
            if key in parsed and isinstance(parsed[key], list):
                parsed = parsed[key]
                break
        else:
            parsed = [parsed]

    if not isinstance(parsed, list):
        raise ValueError("Parsed plan is not a list.")

    normalized = []
    for i, item in enumerate(parsed):
        if not isinstance(item, dict):
            if isinstance(item, str):
                item = {"description": item}
            else:
                raise ValueError(f"Plan step at index {i} is not an object: {item!r}")

        item.setdefault("description", f"step {i}")
        item.setdefault("type", "implement_feature")
        item.setdefault("target_path", "")
        item.setdefault("agent", "default")
        if "id" not in item or not item.get("id"):
            item["id"] = item.get("target_path") or f"step-{i}-{uuid.uuid4().hex[:6]}"
        normalized.append(item)
    return normalized


def _simple_plan_from_prompt(user_prompt: str) -> List[Dict]:
    """
    Best-effort parser for very simple prompts like:
    "Create a file called hello.txt and write: Hello"
    Returns a minimal create_file plan with content if detected.
    """
    if not user_prompt:
        return []

    # filename
    m_file = re.search(r"file called\s+([^\s\"'`]+)", user_prompt, re.IGNORECASE)
    filename = m_file.group(1).strip() if m_file else None

    # content (prefer backticks)
    m_content = re.search(r"write(?: the text)?\s*:?\s*`([^`]+)`", user_prompt, re.IGNORECASE)
    if m_content:
        content = m_content.group(1).strip()
    else:
        m_content = re.search(r"write\s*:?\s*(.+)$", user_prompt, re.IGNORECASE | re.DOTALL)
        content = m_content.group(1).strip() if m_content else None

    if filename:
        return [{
            "description": f"Create a file named `{filename}` and write the provided text into it.",
            "type": "create_file",
            "target_path": filename,
            "content": content or "",
            "agent": "default",
            "id": filename
        }]
    return []


def _extract_file_spec_from_prompt(user_prompt: str, rel_path: str) -> str | None:
    """
    Best-effort extraction of a file-specific requirement line from the user prompt.
    Looks for lines like: - `path/to/file.ext`: do something...
    """
    if not user_prompt or not rel_path:
        return None

    text = user_prompt.replace("\r\n", "\n")
    rel_norm = rel_path.replace("\\", "/").lstrip("./")
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
        # backticked pattern
        m = re.search(rf"`{re.escape(cand)}`\s*:\s*(.+)", text)
        if m:
            return m.group(1).strip()
        # fallback without backticks
        m = re.search(rf"{re.escape(cand)}\s*:\s*(.+)", text)
        if m:
            return m.group(1).strip()

    return None

def gather_project_state(project_root="."):
    state = {}

    # List existing files
    files = []
    for root, dirs, fs in os.walk(project_root):
        for f in fs:
            files.append(os.path.relpath(os.path.join(root, f), project_root))

    state["files"] = files

    # Add memory progress
    try:
        from memory.memory_manager import MemoryManager
        mm = MemoryManager()
        state["done_steps"] = mm.memory.get("done_steps", [])
    except:
        state["done_steps"] = []

    return state

class Planner:
    def __init__(self, memory_manager, context_manager: ContextManager = None, project_root: str = None):
        print("[INIT] Planner.__init__ start", flush=True)

        self.memory = memory_manager
        self.reasoner = ReasoningChain()
        self.gpt = GPTInterface(role="planner")


        # Project root
        self.project_root = project_root or getattr(SETTINGS, "project_root", None) or "."

        # ✅ 1. Context manager FIRST
        if context_manager:
            self.context_manager = context_manager
        else:
            self.context_manager = ContextManager()
            self.context_manager.load_context()
            self._preload_project_files(self.project_root)

        # ✅ 2. Executor AFTER context exists
        self.executor = StepExecutor(
            memory_manager=self.memory,
            context_manager=self.context_manager
        )

        # Scanner and enhancer
        self.scanner = CodeScanner(self.project_root)
        self.enhancer = CreativeEnhancer()

        print("[INIT] Planner.__init__ end", flush=True)

    def _preload_project_files(self, project_root=None):
        project_root = project_root or self.project_root
        import os
        for root, dirs, files in os.walk(project_root):
            for f in files:
                rel_path = os.path.relpath(os.path.join(root, f), project_root)
                self.context_manager.add_file(rel_path, role="code")

    def _normalize_target_path(self, target: str) -> str:
        if not target:
            return target
        if os.path.isabs(target):
            return os.path.relpath(target, self.project_root).replace("\\", "/")
        norm = target.replace("\\", "/")
        proj_abs = os.path.abspath(self.project_root).replace("\\", "/")
        if norm.startswith(proj_abs):
            rel = os.path.relpath(norm, proj_abs).replace("\\", "/")
            return rel
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
    async def _maybe_call(self, fn: Callable, *args, **kwargs):
        """
        Call fn whether it's async or sync. If sync, run in executor so it doesn't block.
        Returns the result or raises.
        """
        try:
            if asyncio.iscoroutinefunction(fn):
                return await fn(*args, **kwargs)
            else:
                loop = asyncio.get_running_loop()
                return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))
        except Exception as e:
            # Propagate so caller can log context
            raise

    async def _run_steps(self, plan: dict) -> dict:
        """
        Execute planner steps sequentially using StepExecutor.
        """
        steps = plan.get("steps", [])

        if not isinstance(steps, list):
            raise ValueError("Plan.steps must be a list")

        results = []

        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                raise ValueError(f"Invalid step at index {index}")

            try:
                result = await self.executor.execute_step(step)
                results.append({
                    "step": index,
                    "status": "ok",
                    "result": result
                })
            except Exception as e:
                return {
                    "status": "failed",
                    "failed_step": index,
                    "error": str(e),
                    "results": results
                }

        return {
            "status": "success",
            "results": results
        }

    async def _call_gpt(self, prompt: str):
        """Call GPT with a timeout and catch/annotate exceptions."""
        print("[ASYNC ENTER] _call_gpt", flush=True)

        try:
            coro = asyncio.to_thread(self.gpt.ask_gpt, prompt)
            return await asyncio.wait_for(coro, timeout=GPT_CALL_TIMEOUT)
        except asyncio.TimeoutError as te:
            log_error(f"GPT call timed out after {GPT_CALL_TIMEOUT}s")
            raise RuntimeError(f"GPT call timed out after {GPT_CALL_TIMEOUT}s") from te
        except Exception as e:
            log_error(f"GPT call failed: {e}")
            raise

    async def create_plan(self, user_prompt: str):
        log_info(f"📋 Planning based on prompt: {user_prompt}")
        print("[ASYNC ENTER] create_plan", flush=True)

        # best-effort notify tracker
        try:
            await self._maybe_call(LiveTracker.log, f"📋 Planning started for: {user_prompt}")
        except Exception as e:
            log_warning(f"LiveTracker.log failed (non-fatal): {e}")

        # Step 1 — Scan (use scanner API if available, otherwise build compact summary)
        try:
            print("[SCAN] Starting project scan...", flush=True)
            # prefer a dedicated summarizer API if CodeScanner exposes it
            if hasattr(self.scanner, "scan_project_summary"):
                scan_summary = await self._maybe_call(self.scanner.scan_project_summary)
            else:
                # fallback: run a light discovery and build a compact summary
                try:
                    files = await self._maybe_call(self.scanner.discover_files)
                    # build counts by extension
                    counts = {}
                    top_files = []
                    for f in files:
                        ext = f.suffix.lower()
                        counts[ext] = counts.get(ext, 0) + 1
                        if len(top_files) < 12:
                            try:
                                top_files.append(str(f.relative_to(self.scanner.project_root)))
                            except Exception:
                                top_files.append(str(f))
                    counts_str = ", ".join([f"{k or '[no-ext]'}:{v}" for k, v in sorted(counts.items(), key=lambda x: -x[1])])
                    scan_summary = f"files={len(files)}, counts={{ {counts_str} }}, top_files={top_files}"
                except Exception as e_scan:
                    log_warning(f"Light scan failed: {e_scan}")
                    scan_summary = ""
            await self._maybe_call(LiveTracker.log, "📂 Project scan completed.")
        except Exception as e:
            scan_summary = ""
            log_info(f"⚠️ Project scan failed: {e}")
            try:
                await self._maybe_call(LiveTracker.log, "📂 Project scan failed.")
            except Exception:
                pass

        # Step 2 — Chained reasoning
        log_info("▶ Running chained reasoner...")
        try:
            thoughts = await self._maybe_call(self.reasoner.reason_through_prompt, user_prompt)
        except Exception as e:
            log_error(f"❌ Reasoner failed: {e}")
            thoughts = ""
        log_info(f"🧩 Chained reasoning result (truncated): {str(thoughts)[:300]}")
        # safe tracker call
        try:
            await self._maybe_call(LiveTracker.thoughts, thoughts)
        except Exception as e:
            log_warning(f"LiveTracker.thoughts failed (non-fatal): {e}")

        # Step 3 — Enhance prompt
        log_info("▶ Enhancing prompt (creative enhancer)...")
        try:
            # run enhancer in thread if sync to avoid blocking
            enhanced_prompt = await self._maybe_call(self.enhancer.enhance_prompt, user_prompt)
            log_info(f"✨ Enhanced prompt (truncated): {str(enhanced_prompt)[:300]}")
            try:
                await self._maybe_call(LiveTracker.log, "✨ Prompt enhanced.")
            except Exception:
                pass
        except Exception as e:
            enhanced_prompt = user_prompt
            log_warning(f"CreativeEnhancer.enhance failed; continuing with original prompt: {e}")

        # Step 4 — Build instruction (same as before), but limit the size of scan_summary and thoughts to avoid huge prompts
        # truncate helpers
        def _truncate_for_prompt(s: str, limit: int = 8000) -> str:
            if not s:
                return ""
            s = str(s)
            if len(s) <= limit:
                return s
            return s[:limit] + "\n\n...[truncated]"

        ts_scan_summary = _truncate_for_prompt(scan_summary, limit=3000)
        ts_thoughts = _truncate_for_prompt(thoughts, limit=4000)
        ts_enhanced = _truncate_for_prompt(enhanced_prompt, limit=2000)

        # Step 4 — Gather project state (reader of the project to give its state)
        project_state = gather_project_state(self.project_root)
        project_state_json = json.dumps(project_state, indent=2)

        instruction = (
            "You're planning a software project.\n"
            f"Current project context:\n{project_state_json}\n\n"
            "Based on this context, generate a JSON list of execution steps..."
            "that break down the prompt into logical subgoals.\n\n"
            "Based on these thoughts and the current project state below, generate a JSON list of execution steps.\n\n"
            "Each step must include:\n"
            "- description: a clear summary of what to implement.\n"
            "- type: choose from [create_folder, create_file, create_class, create_function, implement_feature].\n"
            "- target_path: the exact file or folder path where this should go.\n"
            "- agent: choose 'unity' for Unity/C# tasks, or 'default' otherwise.\n\n"
            f"Project scan summary (compact):\n{ts_scan_summary}\n\n"
            "Use `implement_feature` for core logic, scripts, components, or smart behaviors.\n\n"
            f"Reasoning Steps (compact):\n{ts_thoughts}\n\n"
            f"Enhanced Prompt (compact):\n{ts_enhanced}"
        )

        # Step 5 — Generate initial plan (with robust parsing)
        MAX_RETRIES = 3
        retries = 0
        plan = []

        while retries < MAX_RETRIES:
            print(f"[GPT] plan generation attempt {retries+1}", flush=True)

            try:
                log_info(f"▶ Asking GPT to generate plan (attempt {retries+1})...")
                if retries == 0:
                    prompt_for_plan = instruction
                else:
                    prompt_for_plan = instruction + f"\n\n# retry {retries} {uuid.uuid4().hex}"
                raw_response = await self._call_gpt(prompt_for_plan)
                # log raw response for debugging (including empty responses)
                try:
                    with open("planner_gpt_debug.txt", "a", encoding="utf-8") as dbg:
                        dbg.write(f"--- raw_response attempt {retries+1} ---\n")
                        dbg.write((raw_response or "<EMPTY RESPONSE>") + "\n\n")
                except Exception:
                    pass

                # handle empty/whitespace responses early
                if not raw_response or (isinstance(raw_response, str) and not raw_response.strip()):
                    raise RuntimeError("Empty response from GPT")

                # parse robustly
                # robust parsing with debug
                try:
                    # remove code fences, whitespace, etc.
                    raw_clean = _extract_json_like(raw_response) if isinstance(raw_response, str) else raw_response
                    raw_clean = raw_clean.strip()  # strip leading/trailing whitespace

                    # debug snippet
                    print("[DEBUG] raw_response snippet:", repr(raw_clean[:200]), flush=True)

                    # normalize to list of dicts
                    plan = _ensure_list_of_dicts(raw_clean)
                    print(f"[PLAN OK] steps={len(plan)}", flush=True)

                except Exception as e:
                    # fallback: try direct json.loads
                    try:
                        plan = json.loads(raw_response)
                        plan = _ensure_list_of_dicts(plan)
                        print(f"[PLAN OK] steps={len(plan)}", flush=True)
                    except Exception as e2:
                        snippet = (raw_response[:200] + '...') if isinstance(raw_response, str) else str(type(raw_response))
                        raise RuntimeError(f"Failed to parse plan: {e2} -- raw_response_snippet: {snippet}") from e2

                log_info("🚀 Plan successfully generated from GPT.")
                await self._maybe_call(LiveTracker.log, "🚀 Plan successfully generated.")
                break
            except Exception as e:
                # log raw response for debugging if available
                try:
                    log_warning(f"⚠️ Plan generation attempt {retries+1} failed: {e}")
                    await self._maybe_call(LiveTracker.log, f"⚠️ Plan attempt {retries+1} failed: {e}")
                except Exception:
                    pass
                # if we received a raw_response variable, save it to a debug file for inspection
                try:
                    if 'raw_response' in locals() and isinstance(raw_response, str):
                        with open("planner_gpt_debug.txt", "a", encoding="utf-8") as dbg:
                            dbg.write(f"--- attempt {retries+1} ---\n")
                            dbg.write(raw_response + "\n\n")
                except Exception:
                    pass
                retries += 1

        # Step 6 — Fallback
        if not plan:
            # Try a simple heuristic plan before falling back
            simple = _simple_plan_from_prompt(user_prompt)
            if simple:
                log_info("⚠️ GPT failed. Using simple heuristic plan.")
                try:
                    await self._maybe_call(LiveTracker.log, "⚠️ GPT failed. Using simple heuristic plan.")
                except Exception:
                    pass
                try:
                    self.memory.save_plan(simple)
                except Exception:
                    try:
                        self.memory.save_plan(json.dumps(simple))
                    except Exception:
                        log_warning("Could not save simple plan to memory.")
                return simple

            fallback = [{
                "description": "Create fallback file",
                "type": "create_file",
                "target_path": "fallback.txt",
                "agent": "default",
                "id": "fallback-0"
            }]
            log_info("❌ All GPT attempts failed. Using fallback plan.")
            try:
                await self._maybe_call(LiveTracker.log, "❌ GPT failed. Using fallback plan.")
            except Exception:
                pass
            try:
                self.memory.save_plan(fallback)
            except Exception:
                try:
                    self.memory.save_plan(json.dumps(fallback))
                except Exception:
                    log_warning("Could not save fallback plan to memory.")
            return fallback

        # Steps 7-9 — dependency, reflection, verify (defensive parse)
        async def _try_gpt_postprocess(prompt_text: str, stage_name: str):
            try:
                log_info(f"▶ GPT postprocess: {stage_name}")
                raw = await self._call_gpt(prompt_text)
                try:
                    candidate = _extract_json_like(raw) if isinstance(raw, str) else raw
                    return _ensure_list_of_dicts(candidate)
                except Exception as e:
                    log_warning(f"{stage_name} parse failed: {e}; will keep previous plan.")
                    # save raw for debugging
                    try:
                        if isinstance(raw, str):
                            with open("planner_gpt_debug.txt", "a", encoding="utf-8") as dbg:
                                dbg.write(f"--- {stage_name} raw ---\n")
                                dbg.write(raw + "\n\n")
                    except Exception:
                        pass
                    return None
            except Exception as e:
                log_warning(f"{stage_name} GPT call failed: {e}")
                return None

        # Dependency analysis
        dep_result = None
        if os.getenv("SKIP_PLAN_DEPENDENCY", "0") != "1":
            dependency_prompt = (
                "Analyze the following execution plan and identify dependencies between steps.\n"
                "Add a 'depends_on' field listing file names or modules that each step requires to exist or be executed first.\n"
                "Return the updated plan as a JSON list.\n\n"
                f"{plan}"
            )
            dep_result = await _try_gpt_postprocess(dependency_prompt, "DependencyAnalysis")
        if dep_result:
            plan = dep_result
            await self._maybe_call(LiveTracker.log, "🔗 Step dependencies added.")

        # Self-reflection
        reflection_prompt = (
            "Review this list of execution steps for building the software project:\n\n"
            f"{plan}\n\n"
            "Think like an expert software architect. Are any steps missing, redundant, or misordered?\n"
            "Return the revised plan as a valid JSON list, fixing any issues you detect."
        )
        refl_result = None
        if os.getenv("SKIP_PLAN_POSTPROCESS", "0") != "1":
            refl_result = await _try_gpt_postprocess(reflection_prompt, "SelfReflection")
        if refl_result:
            plan = refl_result
            await self._maybe_call(LiveTracker.log, "🔍 Plan reviewed via self-reflection.")

        # Verification
        # --- Incremental verification & fixes using auto_fix_with_context ---
        issues = _plan_issues_to_fix(plan)

        # map each issue to a "file" for auto_fix_with_context
        for issue in issues:
            step = issue["step"]
            file_path = os.path.join(self.project_root, step.get("target_path", ""))
            
            # Compose custom instructions for GPT to handle plan step
            issue["instructions"] = [
                "Fix missing description/type/target_path",
                "Keep rest of the step intact",
                "Use proper syntax and logical structure",
                "Return only the corrected snippet for this step"
            ]
            
            # Apply fix
            self.verifier.auto_fix_with_context(file_path)


        await self._maybe_call(LiveTracker.log, "✅ Plan verification applied incremental fixes.")

        # Step 10 — Sort topologically
        try:
            plan = topological_sort_steps(plan, autofix=True, debug=True)
            await self._maybe_call(LiveTracker.log, "✅ Topological sort completed.")
            print(f"[PLAN OK] steps={len(plan)}", flush=True)

        except Exception as e:
            log_warning(f"Topological sort failed: {e}")
            try:
                await self._maybe_call(LiveTracker.log, f"⚠️ Sorting plan failed: {e}")
            except Exception:
                pass

        # Normalize target paths to be project-root relative and avoid double-prefixing
        for step in plan:
            if not isinstance(step, dict):
                continue
            tpath = step.get("target_path") or ""
            if tpath:
                norm = self._normalize_target_path(tpath)
                if norm != tpath:
                    step["target_path"] = norm
                    if step.get("id") == tpath:
                        step["id"] = norm
            deps = step.get("depends_on")
            if isinstance(deps, list):
                normalized_deps = []
                for dep in deps:
                    if isinstance(dep, str):
                        normalized_deps.append(self._normalize_target_path(dep))
                    else:
                        normalized_deps.append(dep)
                step["depends_on"] = normalized_deps

        # Attach original prompt + per-file spec to each step (for stricter generation)
        for step in plan:
            if isinstance(step, dict):
                step["user_prompt"] = user_prompt
                tpath = step.get("target_path") or ""
                rel = self._normalize_target_path(tpath) if tpath else ""
                spec = _extract_file_spec_from_prompt(user_prompt, rel)
                if spec:
                    step["file_spec"] = spec

        # Step 11 - Emit plan and save
        try:
            await self._maybe_call(LiveTracker.plan, plan)
        except Exception:
            pass

        log_info(f"📊 Final Plan (len={len(plan)}). Preview (first 5): {plan[:5] if isinstance(plan, list) else plan}")
        
        for step in plan:
            desc = step.get("description", "<no description>")
            tpath = step.get("target_path", "<no path>")
            step_type = step.get("type", "implement_feature")
            role = step.get("role", step_type)  # use type as default role

            log_info(f" - {desc} -> {tpath}")

            # --- NEW: update context ---
            if tpath and step_type in ("create_file", "create_class", "create_function"):
                # add file to context manager
                self.context_manager.add_file(tpath, role)
            
            # --- existing LiveTracker call ---
            try:
                await self._maybe_call(LiveTracker.step_created, step)
            except Exception:
                pass

        # --- NEW: save context after all steps ---
        self.context_manager.save_context()


        # Save plan to memory defensively and add provenance
        plan_meta = {
            "generated_by": "gpt",
            "attempts": retries + 1,
            "timestamp": asyncio.get_event_loop().time()
        }
        try:
            self.memory.save_plan({"plan": plan, "meta": plan_meta})
            log_info("💾 Plan saved to memory (object).")
        except Exception as e:
            log_warning(f"Could not save plan object to memory: {e}; trying JSON string.")
            try:
                self.memory.save_plan(json.dumps({"plan": plan, "meta": plan_meta}))
                log_info("💾 Plan saved to memory (json string).")
            except Exception as e2:
                log_warning(f"Could not save plan to memory as JSON string either: {e2}")

        # Normalize all target paths to project-relative where possible
        for s in plan:
            if s.get("target_path"):
                try:
                    s["target_path"] = self._normalize_target_path(s.get("target_path"))
                except Exception:
                    pass

        # Step 12 — Planner immediate file/folder creation (unchanged, defensive)
        from executor.code_writer import CodeWriter

        file_creator = FileCreator()
        code_writer = CodeWriter(
            project_root=self.project_root,
            context_manager=self.context_manager
        )
        print("[PLANNER IO] starting immediate file/folder creation", flush=True)

        for step in plan:
            t = step.get("type")
            target = step.get("target_path")
            try:
                if t == "create_folder":
                    log_info(f"Planner creating folder (planner immediate): {target}")
                    # use FileCreator just for folder creation (it should be lightweight)
                    file_creator.create_folder(self._normalize_target_path(target))
                elif t == "create_file":
                    content = step.get("content", "")
                    if not isinstance(content, str):
                        content = str(content)

                    if not content.strip():
                        log_info(f"⚠️ No content found for {target}, generating code via GPT...")
                        await self._maybe_call(LiveTracker.log, f"⚠️ No content in plan for {target}, generating now.")
                        code_prompt = (
                            f"Generate the full content for the following file:\n"
                            f"File path: {target}\n"
                            f"Description: {step.get('description', '')}\n\n"
                            f"Provide the complete code with no explanations, just the code."
                        )
                        try:
                            generated_code = await self._call_gpt(code_prompt)
                            if isinstance(generated_code, dict) and "content" in generated_code:
                                content = generated_code["content"]
                            else:
                                content = generated_code
                        except Exception as e:
                            log_warning(f"Failed to generate code for {target}: {e}")
                            content = f"# Error generating code: {e}"

                    log_info(f"Planner generated content for {target}; deferring write to executor.")
                    # Attach generated content to the plan step so the Executor writes it during execution
                    step["content"] = content

            except Exception as e:
                log_warning(f"❌ Planner failed to create {t} {target}: {e}")
                try:
                    await self._maybe_call(LiveTracker.log, f"❌ Planner failed to create {target}: {e}")
                except Exception:
                    pass

        return plan

    async def execute_plan(self, plan):  # or run(), or build_project(), etc.
        # existing logic that routes steps to the executor / CodeWriter
        print("[ASYNC ENTER] execute_plan", flush=True)

        result = await self._run_steps(plan)

        # FinalLinker disabled (generation-time imports only)

        return result
