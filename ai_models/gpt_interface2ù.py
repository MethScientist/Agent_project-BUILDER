import os
import json
from openai import OpenAI
from config.settings import SETTINGS, get_model_config
from utils.logger import log_info

CACHE_PATH = "cache/gpt_cache.json"

class GPTInterface:
    def __init__(self, model_id=None, role="default"):
        self.client = OpenAI(api_key=SETTINGS["openai_api_key"])
        self.cache = {}
        self._load_cache()

        # Grab model config
        self.model_cfg = get_model_config(role)
        self.model_id = model_id or self.model_cfg.get("model", "gpt-5-nano")
        self.temperature = self.model_cfg.get("temperature", 0.0)
        self.tools = self.model_cfg.get("tools", []) if isinstance(self.model_cfg, dict) else []

    def _load_cache(self):
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
                log_info(f"💾 Loaded GPT cache from file ({len(self.cache)} entries)")
            except Exception as e:
                log_info(f"⚠️ Failed to load GPT cache: {e}")

    def _save_cache(self):
        try:
            os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
            log_info("💽 GPT cache saved to file.")
        except Exception as e:
            log_info(f"⚠️ Failed to save GPT cache: {e}")

    def ask_gpt(self, prompt, system_role="You are an expert software engineer.", max_retries=3):
        log_info("🧠 Asking GPT for help...")

        # Check cache
        if prompt in self.cache:
            log_info("⚡ Using cached GPT response.")
            return self.cache[prompt]

        for attempt in range(max_retries):
            try:
                kwargs = dict(
                    model=self.model_id,
                    messages=[
                        {"role": "system", "content": system_role},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=self.temperature,
                )

                # ✅ Only include tools if defined
                if self.tools:
                    kwargs["tools"] = self.tools

                response = self.client.chat.completions.create(**kwargs)

                # ✅ Handle both plain text and tool calls
                msg = response.choices[0].message
                if msg.content:
                    content = msg.content
                elif msg.tool_calls:
                    content = json.dumps([t.to_dict() for t in msg.tool_calls], indent=2)
                else:
                    content = ""

                self.cache[prompt] = content
                self._save_cache()
                return content

            except Exception as e:
                log_info(f"⚠️ GPT attempt {attempt + 1} failed: {e}")

        raise RuntimeError("❌ All GPT attempts failed.")
