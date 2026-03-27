import os
from dotenv import load_dotenv


load_dotenv()  # Load environment variables from .env


def _env_model(name: str, default: str) -> str:
    return os.getenv(name, default)


SETTINGS = {
    "openai_api_key": os.getenv("OPENAI_API_KEY"),
    "memory_file": "memory/memory_store.json",
    "log_file": "logs/execution.log",
    "runtime_log_file": "runtime_agent/runtime.log",
    "default_language": "python",
    "project_root": "output",

    # Ollama models by role. Override with env vars as needed.
    "models": {
        "default": {
            "model": _env_model("OLLAMA_MODEL_DEFAULT", "gpt-oss:120b-cloud"),
            "temperature": float(os.getenv("OLLAMA_TEMP_DEFAULT", "0.2")),
            "options": {}
        },
        "planner": {
            "model": _env_model("OLLAMA_MODEL_PLANNER", _env_model("OLLAMA_MODEL_DEFAULT", "gpt-oss:120b-cloud")),
            "temperature": float(os.getenv("OLLAMA_TEMP_PLANNER", "0.2")),
            "options": {}
        },
        "reasoner": {
            "model": _env_model("OLLAMA_MODEL_REASONER", _env_model("OLLAMA_MODEL_DEFAULT", "gpt-oss:120b-cloud")),
            "temperature": float(os.getenv("OLLAMA_TEMP_REASONER", "0.2")),
            "options": {}
        },
        "executor": {
            "model": _env_model("OLLAMA_MODEL_EXECUTOR", _env_model("OLLAMA_MODEL_DEFAULT", "gpt-oss:120b-cloud")),
            "temperature": float(os.getenv("OLLAMA_TEMP_EXECUTOR", "0.2")),
            "options": {}
        },
        "language_detector": {
            "model": _env_model("OLLAMA_MODEL_LANG_DETECTOR", _env_model("OLLAMA_MODEL_DEFAULT", "gpt-oss:120b-cloud")),
            "temperature": float(os.getenv("OLLAMA_TEMP_LANG_DETECTOR", "0.0")),
            "options": {}
        },
        "code_writer": {
            "model": _env_model("OLLAMA_MODEL_CODE_WRITER", _env_model("OLLAMA_MODEL_DEFAULT", "gpt-oss:120b-cloud")),
            "temperature": float(os.getenv("OLLAMA_TEMP_CODE_WRITER", "0.2")),
            "options": {}
        },
        "code_orchestrator": {
            "model": _env_model("OLLAMA_MODEL_CODE_ORCH", _env_model("OLLAMA_MODEL_DEFAULT", "gpt-oss:120b-cloud")),
            "temperature": float(os.getenv("OLLAMA_TEMP_CODE_ORCH", "0.2")),
            "options": {}
        },
        "code_generator": {
            "model": _env_model("OLLAMA_MODEL_CODE_GEN", _env_model("OLLAMA_MODEL_DEFAULT", "gpt-oss:120b-cloud")),
            "temperature": float(os.getenv("OLLAMA_TEMP_CODE_GEN", "0.2")),
            "options": {}
        },
        "plugin_code_generator": {
            "model": _env_model("OLLAMA_MODEL_PLUGIN_CODE_GEN", _env_model("OLLAMA_MODEL_DEFAULT", "gpt-oss:120b-cloud")),
            "temperature": float(os.getenv("OLLAMA_TEMP_PLUGIN_CODE_GEN", "0.2")),
            "options": {}
        },
        "verifier": {
            "model": _env_model("OLLAMA_MODEL_VERIFIER", _env_model("OLLAMA_MODEL_DEFAULT", "gpt-oss:120b-cloud")),
            "temperature": float(os.getenv("OLLAMA_TEMP_VERIFIER", "0.0")),
            "options": {}
        }
    }
}


def get_model_config(role: str, fallback_role: str = "default") -> dict:
    models = SETTINGS.get("models", {}) or {}
    return models.get(role) or models.get(fallback_role) or {}


def get_model_id(role: str, fallback_role: str = "default") -> str:
    return get_model_config(role, fallback_role).get("model")


def set_project_root(path: str):
    from config import settings
    settings.SETTINGS["project_root"] = path
