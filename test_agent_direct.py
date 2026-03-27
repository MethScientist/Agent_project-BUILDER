import argparse
import asyncio
import os
import sys

# Runtime instrumentation
import runtime_trace as trace
trace.install()

import ollama

from ai_models.gpt_interface import GPTInterface
from executor.executor import Executor
from config import settings
from config.settings import set_project_root
from memory.memory_manager import MemoryManager

PROJECT_ROOT = os.path.abspath("test_project/dependency2_demo")
CLEAN_PROJECT_ROOT = True

EXPECTED_FILES = [
    "py_app/utils/math_utils.py",
    "py_app/main.py",
    "web/utils/format.ts",
    "web/app.ts",
    "UnityGame/Scripts/Health.cs",
    "UnityGame/Scripts/Player.cs",
]

EXPECTED_SNIPPETS = {
    "py_app/utils/math_utils.py": [
        "def add",
        "class Greeter",
        "def greet",
    ],
    "py_app/main.py": [
        "math_utils",
        "add(",
        "Greeter(",
    ],
    "web/utils/format.ts": [
        "export function titleCase",
    ],
    "web/app.ts": [
        "./utils/format",
        "formatMessage",
        "titleCase",
    ],
    "UnityGame/Scripts/Health.cs": [
        "namespace Game.Core",
        "class Health",
        "TakeDamage",
        "Current",
    ],
    "UnityGame/Scripts/Player.cs": [
        "using Game.Core;",
        "namespace Game",
        "class Player",
        "Health",
        "Hit",
    ],
}


def _ensure_ollama_ready(model_id: str, pull_if_missing: bool) -> str | None:
    try:
        resp = ollama.list()
        if isinstance(resp, dict):
            models = resp.get("models", [])
        else:
            models = getattr(resp, "models", [])
    except Exception as exc:
        print(f"[ERROR] Ollama server not reachable: {exc}")
        return None

    def _model_name(m):
        if isinstance(m, dict):
            return m.get("name") or m.get("model")
        return getattr(m, "name", None) or getattr(m, "model", None)

    available = {n for n in (_model_name(m) for m in models) if n}
    if not available:
        if pull_if_missing:
            print(f"[INFO] No local models found. Pulling '{model_id}'...")
            try:
                ollama.pull(model_id)
            except Exception as exc:
                print(f"[ERROR] Failed to pull model '{model_id}': {exc}")
                return None
            resp = ollama.list()
            if isinstance(resp, dict):
                models = resp.get("models", [])
            else:
                models = getattr(resp, "models", [])
            available = {n for n in (_model_name(m) for m in models) if n}
        else:
            print("[ERROR] No local Ollama models found. Pull one with: `ollama pull <model>`.")
            return None

    if model_id not in available:
        if pull_if_missing:
            print(f"[INFO] Pulling missing model '{model_id}'...")
            try:
                ollama.pull(model_id)
            except Exception as exc:
                print(f"[ERROR] Failed to pull model '{model_id}': {exc}")
            else:
                resp = ollama.list()
                if isinstance(resp, dict):
                    models = resp.get("models", [])
                else:
                    models = getattr(resp, "models", [])
                available = {n for n in (_model_name(m) for m in models) if n}

        fallback = sorted(available)[0]
        print(
            f"[WARN] Model '{model_id}' not found in local Ollama models. "
            f"Falling back to '{fallback}'."
        )
        model_id = fallback

    print(f"[OK] Using Ollama model: {model_id}")
    return model_id


def _smoke_test_gpt(model_id: str):
    print("[TEST] Ollama GPTInterface smoke test")
    gpt = GPTInterface(model_id=model_id)
    # Use a unique prompt to avoid cache hits and force a real call.
    response = gpt.ask_gpt(f"Say only the word: OK (nonce={os.urandom(4).hex()})")
    print("[TEST] Response:", response.strip())
    if "OK" not in response:
        print("[WARN] Smoke test response did not include OK.")

def _force_model_settings(model_id: str):
    roles = [
        "default",
        "planner",
        "executor",
        "code_writer",
        "reasoner",
        "verifier",
    ]
    for role in roles:
        if role in settings.SETTINGS["models"]:
            settings.SETTINGS["models"][role]["model"] = model_id


async def main(model_id: str, pull_if_missing: bool):
    if CLEAN_PROJECT_ROOT and "test_project/dependency_demo" in PROJECT_ROOT.replace("\\", "/"):
        import shutil
        if os.path.exists(PROJECT_ROOT):
            shutil.rmtree(PROJECT_ROOT)
    os.makedirs(PROJECT_ROOT, exist_ok=True)
    set_project_root(PROJECT_ROOT)
    os.environ["SKIP_PLAN_POSTPROCESS"] = "1"

    # Clear done_steps so repeated runs don't skip work
    try:
        mm = MemoryManager()
        mm.memory["done_steps"] = []
        mm._save()
    except Exception:
        pass

    actual_model = _ensure_ollama_ready(model_id, pull_if_missing)
    if not actual_model:
        sys.exit(1)
    _force_model_settings(actual_model)

    _smoke_test_gpt(actual_model)

    executor = Executor(project_root=PROJECT_ROOT)
    prompt = """
Create a small multi-language mini-project under `test_project/dependency_demo` with exactly these files and make them depend on each other:

Python:
- `py_app/utils/math_utils.py`: define function `add(a, b)` and class `Greeter(name)` with method `greet()` returning "Hello, {name}".
- `py_app/main.py`: import `add` and `Greeter` from `py_app.utils.math_utils`, then in a `main()` function call `add(2, 3)` and `Greeter("Hope").greet()` and print results.

JavaScript/TypeScript:
- `web/utils/format.ts`: export function `titleCase(s: string)` that capitalizes each word.
- `web/app.ts`: import `titleCase` from `./utils/format` and export function `formatMessage(msg: string)` that returns titleCase(msg).

C#:
- `UnityGame/Scripts/Health.cs`: namespace `Game.Core` with class `Health` and method `TakeDamage(int amount)` that reduces an `int Current` property.
- `UnityGame/Scripts/Player.cs`: namespace `Game` and use `using Game.Core;` then create a `Health` field and method `Hit(int dmg)` that calls `TakeDamage`.

Rules:
- Each file must import or use the correct project-local file(s).
- Do not invent files or imports.
- Keep code short and readable.
""".strip()

    print("=== EXECUTION START ===")
    await executor.execute_from_prompt(prompt)
    print("=== EXECUTION END ===")

    # Verify results
    missing = []
    for rel in EXPECTED_FILES:
        path = os.path.join(PROJECT_ROOT, rel)
        if not os.path.exists(path):
            missing.append(rel)
    if missing:
        raise RuntimeError(f"Missing expected files: {missing}")

    for rel, snippets in EXPECTED_SNIPPETS.items():
        path = os.path.join(PROJECT_ROOT, rel)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        for s in snippets:
            if s not in content:
                raise RuntimeError(f"Missing snippet '{s}' in {rel}")

    print("[PASS] Dependency demo files created and verified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Hope Agent against Ollama.")
    parser.add_argument(
        "--model",
        default=os.getenv("OLLAMA_MODEL_DEFAULT", "gpt-oss:120b-cloud"),
        help="Ollama model id (default: env OLLAMA_MODEL_DEFAULT or gpt-oss:120b-cloud).",
    )
    parser.add_argument(
        "--pull",
        action="store_true",
        help="Pull the model if it's missing locally.",
    )
    args = parser.parse_args()

    asyncio.run(main(args.model, args.pull))
