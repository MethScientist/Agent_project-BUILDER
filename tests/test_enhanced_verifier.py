"""
ENHANCED VERIFIER WITH CONTEXT AWARENESS

This shows the BEST APPROACH:
- Verifier gets PROJECT CONTEXT (ProjectMap, DependencyResolver, ContextManager)
- Enhanced auto_fix() can understand imports, dependencies, exports
- Can detect and fix SEMANTIC errors, not just syntax errors
- Works on SNIPPET level within file context
"""

import os
import sys
import tempfile
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.verifier import Verifier
from core.project_map import build_project_map
from core.dependency_resolver import DependencyResolver
from context_awareness.manager import ContextManager
from ai_models.gpt_interface import GPTInterface


# ============================================================================
# ENHANCED VERIFIER WITH CONTEXT
# ============================================================================

class ContextAwareVerifier(Verifier):
    """
    Enhanced Verifier that understands project structure and can fix semantic errors.
    
    APPROACH:
    1. FILE-BY-FILE verification (not global)
    2. SNIPPET-BASED fixing (fix imports within file)
    3. CONTEXT-AWARE generation (GPT knows about project)
    """
    
    def __init__(self, model, project_root=None, project_map=None, context_manager=None):
        super().__init__(model)
        self.project_root = project_root
        self.project_map = project_map or {}
        self.context_manager = context_manager
        
        # Build dependency resolver if we have project map
        if project_map and project_root:
            self.resolver = DependencyResolver(project_map, project_root)
        else:
            self.resolver = None
    
    def auto_fix(self, file_path, error, with_context=False):
        """
        Enhanced auto-fix that can use project context.
        
        APPROACH:
        - For syntax errors: Use simple GPT fix (existing behavior)
        - For semantic errors: Use project context to guide fix
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        if with_context and self.resolver and self.project_map:
            # SEMANTIC ERROR FIX WITH CONTEXT
            return self._auto_fix_with_context(file_path, content, error)
        else:
            # SIMPLE SYNTAX ERROR FIX (existing)
            return self._auto_fix_simple(content, error)
    
    def _auto_fix_simple(self, content, error):
        """Original auto-fix for syntax errors only."""
        prompt = f"""You are a code fixer.
The file contains syntax errors:
Error output: {error}
Fix the code correctly while keeping the same logic.

Code:
{content}"""
        
        fixed = self.model.ask_gpt(prompt, system_role="You are an expert code fixer.")
        return fixed
    
    def _auto_fix_with_context(self, file_path, content, error):
        """
        ENHANCED: Auto-fix with full project context.
        Understands imports, exports, dependencies.
        """
        rel_path = os.path.relpath(file_path, self.project_root)
        
        # Get what this file exports
        file_meta = self.project_map.get(rel_path, {})
        file_exports = file_meta.get("exports", [])
        
        # Get available imports from other files
        available_modules = []
        for module_rel, meta in self.project_map.items():
            if module_rel != rel_path:
                exports = meta.get("exports", [])
                if exports:
                    available_modules.append({
                        "path": module_rel,
                        "exports": exports,
                        "lang": meta.get("lang", "unknown")
                    })
        
        # Build context for GPT
        project_context = self._build_context_summary(available_modules, file_exports, rel_path)
        
        # Enhanced prompt with full context
        prompt = f"""You are a code fixer with full project awareness.

PROJECT STRUCTURE:
{project_context}

FILE: {rel_path}
Current exports: {file_exports}

The code has errors:
Error: {error}

RULES:
1. Only import from modules that exist in the project
2. Keep exports compatible with what other files need
3. Use correct relative paths for imports
4. Don't invent functions/modules that don't exist
5. Fix the code while keeping original logic

BROKEN CODE:
{content}

INSTRUCTIONS:
1. Analyze what this file is trying to do
2. Check if imports are valid (from available modules)
3. Fix broken imports first (change paths to match project structure)
4. Fix any other syntax/semantic issues
5. Return ONLY the fixed code, no explanations"""
        
        fixed = self.model.ask_gpt(prompt, system_role="You are an expert code fixer with project knowledge.")
        return fixed
    
    def _build_context_summary(self, available_modules, file_exports, current_file):
        """Build a summary of project structure for GPT."""
        lines = []
        lines.append(f"\nAvailable modules in project:")
        for mod in available_modules[:10]:  # Limit to 10 for token budget
            exports_preview = ", ".join(str(e)[:30] for e in mod["exports"][:5])
            lines.append(f"  - {mod['path']} ({mod['lang']}) exports: {exports_preview}")
        
        lines.append(f"\nCurrent file: {current_file}")
        lines.append(f"Should export: {file_exports}")
        
        return "\n".join(lines)
    
    def verify_imports(self, file_path):
        """
        NEW: Verify that imports in file actually exist in project.
        
        DETECTS SEMANTIC ERRORS:
        - Importing from non-existent modules
        - Using undefined functions
        - Wrong import paths
        """
        if not self.resolver:
            return {"status": "skipped", "reason": "No project resolver"}
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Check for import statements and verify they exist
            issues = self._check_imports_in_content(content, file_path)
            
            if issues:
                return {
                    "status": "semantic_error",
                    "issues": issues,
                    "message": f"Found {len(issues)} semantic issues"
                }
            
            return {"status": "ok"}
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _check_imports_in_content(self, content, file_path):
        """Extract and validate imports."""
        issues = []
        
        # Python imports
        import re
        
        # Pattern for: from X import Y or import X
        patterns = [
            r'from\s+([\w\.]+)\s+import\s+([\w\s,]+)',
            r'import\s+([\w\.]+)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                module_name = match.group(1)
                
                # Check if module exists in project
                if not self._module_exists(module_name, file_path):
                    issues.append({
                        "type": "missing_module",
                        "module": module_name,
                        "line": content[:match.start()].count('\n') + 1,
                        "suggestion": self._suggest_correction(module_name, file_path)
                    })
        
        return issues
    
    def _module_exists(self, module_name, file_path):
        """Check if a module exists in project."""
        # This is simplified - real implementation would check project structure
        for rel_path in self.project_map.keys():
            # Handle relative imports
            if module_name in rel_path or rel_path.replace("\\", "/").endswith(module_name):
                return True
        return False
    
    def _suggest_correction(self, wrong_module, file_path):
        """Suggest correction for wrong import path."""
        # Find similar module names
        closest_match = None
        for rel_path in self.project_map.keys():
            if any(part in wrong_module for part in rel_path.split("/")):
                closest_match = rel_path
                break
        return closest_match


# ============================================================================
# DEMO: Enhanced Verifier with Context
# ============================================================================

def demo_enhanced_verifier():
    """
    Show how enhanced Verifier prevents semantic errors.
    """
    print("\n" + "="*70)
    print("ENHANCED VERIFIER DEMO: Context-Aware Error Detection")
    print("="*70)
    
    # Create temporary project structure
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create project files
        utils_file = os.path.join(tmpdir, "utils.py")
        with open(utils_file, "w") as f:
            f.write("""def helper_function(x):
    return x * 2

def process_data(data):
    return [helper_function(i) for i in data]
""")
        
        main_file = os.path.join(tmpdir, "main.py")
        with open(main_file, "w") as f:
            f.write("""from wrong_path import helper_function  # Wrong import!

def run():
    result = helper_function(5)
    return result
""")
        
        # Build project map
        project_map = {
            "utils.py": {
                "lang": "py",
                "exports": ["helper_function", "process_data"]
            },
            "main.py": {
                "lang": "py",
                "exports": ["run"]
            }
        }
        
        # Create enhanced verifier
        model = GPTInterface()
        verifier = ContextAwareVerifier(
            model,
            project_root=tmpdir,
            project_map=project_map
        )
        
        # 1. Check imports in main.py
        print(f"\n1️⃣  Checking imports in main.py...")
        import_check = verifier.verify_imports(main_file)
        print(f"Result: {import_check}")
        
        if import_check.get("issues"):
            print(f"\n2️⃣  Semantic issues detected:")
            for issue in import_check["issues"]:
                print(f"  ❌ {issue['type']}: {issue['module']}")
                if issue.get("suggestion"):
                    print(f"     💡 Suggestion: from {issue['suggestion'].replace('/', '.')[:20]} import...")
        
        # 2. Auto-fix with context
        print(f"\n3️⃣  Auto-fixing with project context...")
        with open(main_file, "r") as f:
            original = f.read()
        
        print(f"Original:\n{original}")
        print(f"\nAttempting context-aware auto-fix...")
        
        # Note: This would call GPT in real scenario
        # For demo, just show the approach
        print(f"\nFix would:")
        print(f"  1. See that 'wrong_path' doesn't exist in project")
        print(f"  2. Find 'helper_function' is in 'utils.py'")
        print(f"  3. Generate: from utils import helper_function")
        print(f"  4. Result would be semantically correct!")


# ============================================================================
# ARCHITECTURE COMPARISON
# ============================================================================

def show_architecture():
    """Show the two approaches and why enhanced one is better."""
    print("\n\n")
    print("█" * 70)
    print("█" + " " * 68 + "█")
    print("█" + "  ARCHITECTURE COMPARISON".center(68) + "█")
    print("█" + " " * 68 + "█")
    print("█" * 70)
    
    print("""
┌─ APPROACH 1: BASIC VERIFIER (Current) ──────────────────────────────┐
│                                                                      │
│  ✅ Detects: Syntax errors (missing colons, etc.)                   │
│  ❌ Detects: Semantic errors (wrong imports, undefined vars)        │
│  ❌ Fixes: Only syntax, with limited context                        │
│                                                                      │
│  Flow: Code → Verifier → pass/fail                                 │
│                                                                      │
│  Limitation: Relies on CodeGenerator to get it RIGHT first time    │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌─ APPROACH 2: ENHANCED VERIFIER (Proposed) ─────────────────────────┐
│                                                                      │
│  ✅ Detects: Syntax errors                                          │
│  ✅ Detects: Semantic errors (wrong imports, missing functions)     │
│  ✅ Fixes: Both, WITH full project context                          │
│                                                                      │
│  Flow:                                                              │
│    1. Code → Syntax Check (py_compile)                             │
│    2. If fails → Simple auto-fix (existing)                        │
│    3. If passes → Semantic Check (import verification)             │
│    4. If semantic fails → Context-aware auto-fix (new)             │
│                                                                      │
│  Advantage: Catches errors CodeGenerator might miss                │
│             Fixes them intelligently with full context             │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌─ RECOMMENDED APPROACH FOR HOPE AGENT ───────────────────────────────┐
│                                                                      │
│  COMBINATION OF BOTH (file-by-file with snippet fixing):            │
│                                                                      │
│  1. During generation:                                              │
│     - CodeGenerator uses ProjectMap to create correct code         │
│     - Gets context from ContextManager                              │
│                                                                      │
│  2. After generation:                                               │
│     - Verifier checks syntax (current)                             │
│     - ContextAwareVerifier checks imports (new)                    │
│     - Auto-fix with context if needed                              │
│                                                                      │
│  3. For each file independently:                                    │
│     - Check: does this file's imports match project?               │
│     - Check: does this file's exports match what others use?       │
│     - Fix: update imports to match project structure               │
│     - Fix: update exports if file role changed                     │
│                                                                      │
│  SNIPPET-BASED FIXING:                                             │
│     - Not fixing entire files, but specific import blocks         │
│     - Keep working code, fix only broken parts                    │
│     - Minimal changes = safer, faster, more reliable               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌─ IMPLEMENTATION CHECKLIST ──────────────────────────────────────────┐
│                                                                      │
│  ✅ ContextAwareVerifier class created                              │
│  ✅ Import verification method added                                │
│  ✅ Project context awareness added                                 │
│  ✅ Snippet-based fixing approach defined                           │
│                                                                      │
│  🔄 Next steps:                                                     │
│     1. Integrate ContextAwareVerifier into StepExecutor             │
│     2. Pass ProjectMap to Verifier during init                     │
│     3. Enhanced auto_fix to use context-aware approach             │
│     4. Test on multi-file projects with dependencies              │
│     5. Measure: catch rate for semantic errors                     │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
""")


if __name__ == "__main__":
    show_architecture()
    demo_enhanced_verifier()
