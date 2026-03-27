# executor/core_orchestrator.py

from core.code_generator import CodeGenerator
from executor.code_writer import CodeWriter
from context_awareness.manager import ContextManager  # adjust import if needed
from config.settings import get_model_id


class CodeOrchestrator:
    def __init__(
        self,
        context_manager: ContextManager,
        project_root: str,
        model: str = None
    ):
        resolved_model = model or get_model_id("code_orchestrator")
        self.generator = CodeGenerator(model=resolved_model)
        self.writer = CodeWriter(
            context_manager=context_manager,
            project_root=project_root,
            model=resolved_model
        )

    def generate_and_insert_function(self, filepath: str, prompt: str, dependency_context: str | None = None):
        code = self.generator.generate_code(filepath, prompt, dependency_context)
        func_name = self.writer.extract_function_name(code)
        self.writer.safe_insert_function(filepath, func_name, code)

    def generate_and_insert_class(self, filepath: str, prompt: str, dependency_context: str | None = None):
        code = self.generator.generate_code(filepath, prompt, dependency_context)
        class_name = self.writer.extract_class_name(code)
        self.writer.safe_insert_class(filepath, class_name, code)
