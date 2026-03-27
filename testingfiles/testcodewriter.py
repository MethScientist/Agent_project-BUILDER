# test_class_versions.py
import inspect
from executor.step_executor import StepExecutor
from executor.code_writer import CodeWriter
from context_awareness.manager import ContextManager
from memory.memory_manager import MemoryManager

print("=== Checking StepExecutor.__init__ ===")
print(inspect.signature(StepExecutor.__init__))

print("\n=== Checking CodeWriter.__init__ ===")
print(inspect.signature(CodeWriter.__init__))

print("\n=== Testing creation with dummy objects ===")
mem = MemoryManager()
ctx = ContextManager()

try:
    step = StepExecutor(memory_manager=mem, context_manager=ctx)
    print("[OK] StepExecutor instantiated successfully")
except Exception as e:
    print("[ERROR] StepExecutor instantiation failed:", e)

try:
    writer = CodeWriter(context_manager=ctx, project_root="output")
    print("[OK] CodeWriter instantiated successfully")
except Exception as e:
    print("[ERROR] CodeWriter instantiation failed:", e)
