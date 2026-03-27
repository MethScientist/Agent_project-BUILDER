# ai_models/gpt_interface.py
import os
import json
import asyncio
import functools
import ollama
from utils.logger import log_info, log_warning
from config.settings import get_model_config

CACHE_PATH = "cache/ollama_cache.json"


class GPTInterface:
    def __init__(self, model_id=None, role="default"):
        cfg = get_model_config(role)
        self.model_id = model_id or cfg.get("model") or "llama3.1:8b"
        self.temperature = cfg.get("temperature", None)
        self.options = cfg.get("options", {}) or {}
        self.cache = {}
        self._load_cache()

    def _load_cache(self):
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                log_info(f"💾 Loaded cache ({len(self.cache)} entries)")
            except Exception as e:
                log_warning(f"⚠️ Failed to load cache: {e}")

    def _save_cache(self):
        try:
            os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
            log_info("💽 Cache saved to file.")
        except Exception as e:
            log_warning(f"⚠️ Failed to save cache: {e}")

    def ask_gpt(self, prompt, system_role="You are an expert software engineer."):
        log_info(f"🧠 Asking model {self.model_id}...")
        # Use cache if available
        if prompt in self.cache:
            log_info("⚡ Using cached response.")
            return self.cache[prompt]

        messages = [
            {"role": "system", "content": system_role},
            {"role": "user", "content": prompt}
        ]

        try:
            options = dict(self.options) if self.options else {}
            if self.temperature is not None:
                options["temperature"] = self.temperature

            result = ollama.chat(
                model=self.model_id,
                messages=messages,
                options=options or None
            )
            content = result.get("message", {}).get("content", "")
            self.cache[prompt] = content
            self._save_cache()
            return content
        except Exception as e:
            log_warning(f"❌ GPT call failed: {e}")
            return f"# Error calling GPT: {e}"

    async def ask_gpt_async(self, prompt, system_role="You are an expert software engineer."):
        return await asyncio.to_thread(functools.partial(self.ask_gpt, prompt, system_role))

    def generate(self, prompt, system_role="You are an expert code generator."):
        """
        Generate code using the model. Wrapper around ask_gpt() for backward compatibility.
        Used by Verifier and other components for code generation and fixing.
        """
        return self.ask_gpt(prompt, system_role)
