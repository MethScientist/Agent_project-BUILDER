import asyncio
from executor.executor import Executor

async def test_executor():
    print("[TEST] Starting executor test")
    try:
        executor = Executor(project_root="C:/Users/Hp/3D Objects/hope last")
        print("[TEST] Executor initialized")
        await executor.execute_from_prompt("Test prompt")
        print("[TEST] Execution finished")
    except Exception as e:
        print("[ERROR] Exception during executor test:", e)

asyncio.run(test_executor())
