import os
import runtime_trace as trace
from config.settings import SETTINGS
from utils.logger import log_info, log_error



class FileCreator:
    def __init__(self):
        raw_root = SETTINGS.get("project_root")
        if not raw_root:
            log_error("❌ Project root not set in SETTINGS.")
            raise ValueError("Project root not set in SETTINGS.")
        self.project_root = os.path.abspath(raw_root)
        log_info(f"🛠 Project root set to: {self.project_root}")

    def _normalize_path(self, path: str) -> str:
        if os.path.isabs(path):
            return path
        try:
            rel_root = os.path.relpath(self.project_root, os.getcwd()).replace("\\", "/")
        except Exception:
            rel_root = None
        norm = path.replace("\\", "/")
        if rel_root:
            if norm == rel_root:
                return self.project_root
            if norm.startswith(rel_root + "/"):
                stripped = norm[len(rel_root) + 1:]
                return os.path.join(self.project_root, stripped)
        return os.path.join(self.project_root, path)

    def create_folder(self, path):
        if not path:
            log_error("❌ Folder path not provided.")
            raise ValueError("Folder path cannot be empty.")
        full_path = self._normalize_path(path)
        os.makedirs(full_path, exist_ok=True)
        log_info(f"📁 Folder ensured: {full_path}")
        try:
            trace.log_file_write(full_path, full_path)
        except Exception:
            pass
        return full_path

    def create_file(self, path, content=None):
        if not path:
            log_error("❌ File path not provided.")
            raise ValueError("File path cannot be empty.")
        full_path = self._normalize_path(path)
        folder = os.path.dirname(full_path)
        os.makedirs(folder, exist_ok=True)

        # Do not write if content is None — only ensure directories. Actual file write will
        # be performed by CodeWriter during execution to avoid overwrite races.
        if content is None:
            log_info(f"📄 File ensured (no content written): {full_path}")
            return full_path

        try:
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            log_info(f"📄 File written: {full_path}")
            try:
                trace.log_file_write(full_path, full_path)
            except Exception:
                pass
            return full_path
        except Exception as e:
            log_error(f"❌ Failed to write file {full_path}: {e}")
            raise

from executor.plan_writer import PlanWriter

def execute_gpt_plan(gpt_plan_with_code):
    if not gpt_plan_with_code:
        log_error("❌ GPT plan is empty or None.")
        raise ValueError("GPT plan cannot be empty.")
    writer = PlanWriter()
    writer.write_plan_to_files(gpt_plan_with_code)
