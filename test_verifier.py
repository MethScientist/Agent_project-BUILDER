import json
from core.verifier import Verifier
from ai_models.gpt_interface import GPTInterface

model = GPTInterface(role="default")
verifier = Verifier(model)

with open("project_map.json") as f:
    project_map = json.load(f)

verifier.set_context(
    project_root=".",
    project_map=project_map,
    context_manager=None,
    dependency_resolver=None,
)

files = [
    "bad_project/main.py",
    "bad_project/math_ops.py",
    "bad_project/utils.py",
]

for f in files:
    result = verifier.verify_file(f)
    print(f"Verification report for {f}:", result)

    if result["status"] == "error":
        verifier.auto_fix_with_context(f)            # uses default max_rounds=5
        # or explicitly:

