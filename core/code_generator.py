# core/code_generator.py
import asyncio
from pathlib import Path

import ollama

from utils.logger import log_info
from config.settings import SETTINGS, get_model_config
from core.project_map import build_project_map


class CodeGenerator:
    def __init__(self, model=None, role="code_generator"):
        cfg = get_model_config(role)
        self.model = model or cfg.get("model") or "llama3.1:8b"
        self.temperature = cfg.get("temperature", None)
        self.options = cfg.get("options", {}) or {}
        self.project_root = Path(SETTINGS.get("project_root") or ".").resolve()

    def _project_context_summary(self, limit_files: int = 40, limit_exports: int = 6) -> str:
        """
        Build a concise list of existing project files and their exported symbols.
        Used to nudge the model to import real project-local code instead of inventing.
        """
        try:
            pm = build_project_map(str(self.project_root))
        except Exception:
            return ""

        lines = []
        for i, (rel, meta) in enumerate(pm.items()):
            if i >= limit_files:
                break
            lang = meta.get("lang") or "text"
            exports = meta.get("exports") or []
            exp_preview = ", ".join(map(str, exports[:limit_exports])) if exports else "(no exports detected)"
            lines.append(f"- {rel} [{lang}] exports: {exp_preview}")
        return "\n".join(lines)

    async def generate_code_async(self, file_path: str, description: str, dependency_context: str | None = None) -> str:
        """
        Async: Generates complete code for a specific file using Ollama OSS.
        """
        project_summary = self._project_context_summary()
        ext = Path(file_path).suffix.lower()
        if ext in {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}:
            lang_rules = (
                "JS/TS import rules:\n"
                "- Use relative imports (./ or ../) for project files.\n"
                "- Do NOT import a local path unless it exists in the project list above.\n"
                "- Keep package imports only if they are real external deps.\n"
            )
        elif ext == ".cs":
            lang_rules = (
                "C# import rules:\n"
                "- Use `using` only for namespaces that exist in the project list above or System/Microsoft.\n"
                "- Do NOT invent namespaces.\n"
            )
        elif ext == ".py":
            lang_rules = (
                "Python import rules:\n"
                "- Import project-local modules only if they exist in the project list above.\n"
                "- Do NOT invent module names.\n"
            )
        else:
            lang_rules = ""

        prompt = f"""
You are a professional software engineer.
Your task is to write the FULL content for the following file:

File path: {file_path}
Task: {description}

Existing project files (only import from these when needed; do NOT invent modules):
{project_summary or "(none detected)"}
{lang_rules}

Dependency context (use these files if relevant; do NOT invent new modules):
{dependency_context or "(none)"}

Requirements:
- Write clean, production-ready code.
- Follow best practices for the language and framework.
- Include all imports and necessary setup.
- Prefer project-local modules from the list above when referencing shared code.
- Do NOT add imports for modules that are not in standard library or the list above.
- If no local dependency is needed, keep imports minimal.
- Do not write explanations or comments unless they are code comments.
- Return only the complete file content.
"""

        log_info(f"[Async] Generating code for: {file_path}")

        options = dict(self.options) if self.options else {}
        if self.temperature is not None:
            options["temperature"] = self.temperature

        result = ollama.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a professional code generator."},
                {"role": "user", "content": prompt.strip()},
            ],
            options=options or None
        )

        # Extract content
        content = result.get("message", {}).get("content", "")
        return content.strip()

    def generate_code(self, file_path: str, description: str, dependency_context: str | None = None) -> str:
        """
        Sync wrapper around async function.
        """
        return asyncio.run(self.generate_code_async(file_path, description, dependency_context))
