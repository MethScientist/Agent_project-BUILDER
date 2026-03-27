# core/code_generator.py
import ollama
from utils.logger import log_info
from config.settings import get_model_config


class CodeGenerator:
    def __init__(self, model=None, role="plugin_code_generator"):
        cfg = get_model_config(role)
        self.model = model or cfg.get("model") or "llama3.1:8b"
        self.temperature = cfg.get("temperature", None)
        self.options = cfg.get("options", {}) or {}

    def generate_code(self, prompt: str) -> str:
        """
        Sends a prompt to Ollama and returns generated code.
        """
        log_info(f"Generating code from prompt: {prompt}")

        messages = [
            {"role": "system", "content": "You are a professional code writer."},
            {"role": "user", "content": prompt}
        ]

        options = dict(self.options) if self.options else {}
        if self.temperature is not None:
            options["temperature"] = self.temperature

        result = ollama.chat(
            model=self.model,
            messages=messages,
            options=options or None
        )

        code = result.get("message", {}).get("content", "")
        return code.strip()
