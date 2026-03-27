# test_gpt_interface.py

import os
import shutil
from ai_models.gpt_interface import GPTInterface

# ---- helpers -------------------------------------------------

def reset_cache():
    """Remove cache file to force a real Ollama call."""
    cache_dir = "cache"
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
        print("[TEST] Cache cleared")

# ---- tests ---------------------------------------------------

def test_basic_prompt():
    print("\n[TEST] test_basic_prompt")
    gpt = GPTInterface()

    prompt = "Say only the word: OK"
    response = gpt.ask_gpt(prompt)

    assert isinstance(response, str), "Response is not a string"
    assert len(response.strip()) > 0, "Empty response from Ollama"

    print("[PASS] Received response:", response.strip())


def test_cache_hit():
    print("\n[TEST] test_cache_hit")
    gpt = GPTInterface()

    prompt = "Cache test prompt"
    first = gpt.ask_gpt(prompt)
    second = gpt.ask_gpt(prompt)

    assert first == second, "Cached response does not match"
    print("[PASS] Cache hit confirmed")


def test_system_role():
    print("\n[TEST] test_system_role")
    gpt = GPTInterface()

    prompt = "Respond with only your role."
    response = gpt.ask_gpt(
        prompt,
        system_role="You are a QA tester."
    )

    assert isinstance(response, str)
    print("[PASS] System role respected:", response.strip())


def test_retry_logic():
    print("\n[TEST] test_retry_logic (simulated)")

    gpt = GPTInterface()
    original_model = gpt.model_id

    try:
        # Force failure by using invalid model
        gpt.model_id = "invalid-model-name"
        gpt.ask_gpt("This should fail", max_retries=2)
        raise AssertionError("Expected RuntimeError not raised")
    except RuntimeError:
        print("[PASS] Retry logic triggered RuntimeError")
    finally:
        gpt.model_id = original_model


# ---- main ----------------------------------------------------

if __name__ == "__main__":
    print("=== GPTInterface TEST SUITE START ===")

    reset_cache()
    test_basic_prompt()
    test_cache_hit()
    test_system_role()
    test_retry_logic()

    print("=== GPTInterface TEST SUITE END ===")
