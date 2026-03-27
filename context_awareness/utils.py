# context_awareness/utils.py

from .manager import ContextManager


def find_file_for_role(context_manager: ContextManager, role: str):
    """
    Return filename that matches the given role.
    If none found, return None.
    """
    for fname, fctx in context_manager.context.project_files.items():
        if fctx.role == role:
            return fname
    return None
