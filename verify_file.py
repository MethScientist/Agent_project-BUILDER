import subprocess
import sys
import traceback
from pathlib import Path



def verify_python_file(file_path: str) -> dict:
    path = Path(file_path).resolve()

    if not path.exists():
        return {
            "success": False,
            "error": f"File not found: {path}",
            "traceback": None,
        }

    try:
        process = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True,
            text=True,
        )

        if process.returncode != 0:
            return {
                "success": False,
                "error": process.stderr.strip(),
                "traceback": process.stderr,
            }

        return {
            "success": True,
            "error": None,
            "traceback": None,
        }

    except Exception:
        return {
            "success": False,
            "error": "Execution failed",
            "traceback": traceback.format_exc(),
        }
