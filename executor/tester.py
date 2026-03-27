

import subprocess, time
import os
class AutoTester:
    def __init__(self, verifier, max_attempts=3):
        self.verifier = verifier
        self.max_attempts = max_attempts

    def test_and_fix(self, file_path):
        for attempt in range(self.max_attempts):
            verify_result = self.verifier.verify_file(file_path)
            if verify_result["status"] == "ok":
                run_result = self._run_file(file_path)
                if run_result["status"] == "ok":
                    return {"status": "ok", "message": "Code verified and executed successfully."}
                else:
                    fixed_code = self.verifier.auto_fix(file_path, run_result["error"])
            else:
                fixed_code = self.verifier.auto_fix(file_path, verify_result["error"])
            time.sleep(1)
        return {"status": "failed", "message": f"Could not fix {file_path} after {self.max_attempts} attempts."}

    def _run_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".py":
                subprocess.run(["python", path], capture_output=True, text=True, check=True)
            elif ext == ".js":
                subprocess.run(["node", path], capture_output=True, text=True, check=True)
            else:
                return {"status": "skipped", "error": "Unsupported file type for runtime test."}
            return {"status": "ok"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "error": e.stderr}