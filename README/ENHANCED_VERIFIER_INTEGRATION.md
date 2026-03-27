# ENHANCED VERIFIER INTEGRATION GUIDE

## What Was Implemented

The `Verifier` class in [core/verifier.py](core/verifier.py) has been enhanced with:

### ✅ NEW METHODS ADDED:

1. **`set_context()`** - Configure Verifier with project awareness
   ```python
   verifier.set_context(
       project_root="/path/to/project",
       project_map={...},
       dependency_resolver=resolver,
       context_manager=context_mgr
   )
   ```

2. **`verify_imports()`** - Semantic error detection
   ```python
   result = verifier.verify_imports("main.py")
   # Returns: {"status": "ok"} or {"status": "semantic_error", "issues": [...]}
   ```

3. **`auto_fix_with_context()`** - Smart fixing with project context
   ```python
   verifier.auto_fix_with_context("main.py", issues)
   # Fixes imports using full project knowledge
   ```

4. **`extract_import_block()`** - Snippet extraction
   ```python
   imports = verifier.extract_import_block(content, lang="py")
   # Returns list of (line_no, import_statement) tuples
   ```

5. **Helper Methods**:
   - `_check_python_imports()` - Parse Python imports
   - `_check_js_imports()` - Parse JavaScript imports
   - `_module_exists_in_project()` - Validate module exists
   - `_is_stdlib()` - Check if module is standard library
   - `_suggest_module()` - Suggest correction for wrong module
   - `_build_context_for_gpt()` - Create context summary for GPT

---

## How to Integrate into StepExecutor

### Step 1: Update StepExecutor.__init__()

In [executor/step_executor.py](executor/step_executor.py), modify the initialization:

```python
from core.project_map import build_project_map

class StepExecutor:
    def __init__(self, project_root=None, ...):
        # ... existing code ...
        
        # Build project map for Verifier context
        self.project_map = build_project_map(str(self.project_root))
        
        # Initialize Verifier (already exists)
        self.verifier = Verifier(model=self.gpt)
        
        # NEW: Configure Verifier with context
        self.verifier.set_context(
            project_root=str(self.project_root),
            project_map=self.project_map,
            dependency_resolver=self.resolver,  # if available
            context_manager=self.context_manager
        )
```

### Step 2: Update execute_step() with Two-Layer Verification

In the `execute_step()` method, after file writing (around line 796):

```python
# --- Run verifier and autotester for any modified file ---
if modified_rel_path:
    abs_modified = self._abs_path(modified_rel_path)
    try:
        print(f"[VERIFY] start {modified_rel_path}", flush=True)
        
        # ✅ LAYER 1: Syntax Verification
        verify_result = await asyncio.get_running_loop().run_in_executor(
            None, self.verifier.verify_file, abs_modified
        )
        
        if verify_result and verify_result.get("status") == "error":
            log_warning(f"🔍 Syntax error in {modified_rel_path}")
            try:
                # Try simple auto-fix
                fixed_code = await asyncio.get_running_loop().run_in_executor(
                    None, self.verifier.auto_fix, abs_modified, verify_result.get("error", "")
                )
                log_info(f"✅ Syntax auto-fix applied")
                
                # Re-verify syntax
                verify_result = await asyncio.get_running_loop().run_in_executor(
                    None, self.verifier.verify_file, abs_modified
                )
            except Exception as e_fix:
                log_error(f"❌ Syntax auto-fix failed: {e_fix}")
        
        # ✅ LAYER 2: Semantic Verification (NEW)
        if verify_result and verify_result.get("status") == "ok":
            semantic_result = await asyncio.get_running_loop().run_in_executor(
                None, self.verifier.verify_imports, abs_modified
            )
            
            if semantic_result and semantic_result.get("status") == "semantic_error":
                log_warning(f"🔍 Semantic error in {modified_rel_path}")
                try:
                    # Fix with context
                    fixed_code = await asyncio.get_running_loop().run_in_executor(
                        None, 
                        self.verifier.auto_fix_with_context,
                        abs_modified,
                        semantic_result.get("issues", [])
                    )
                    log_info(f"✅ Semantic auto-fix applied (with context)")
                    
                    # Re-verify imports
                    semantic_result = await asyncio.get_running_loop().run_in_executor(
                        None, self.verifier.verify_imports, abs_modified
                    )
                    
                    if semantic_result and semantic_result.get("status") == "ok":
                        log_info(f"✅ Semantic verification passed after fix")
                    else:
                        log_error(f"❌ Semantic verification still failing")
                        result = {"status": "fail", "reason": "semantic_error", "details": semantic_result}
                        
                except Exception as e_sem:
                    log_error(f"❌ Semantic auto-fix failed: {e_sem}")
                    result = {"status": "fail", "reason": "semantic_fix_failed", "error": str(e_sem)}
        
        print(f"[VERIFY] end {modified_rel_path}", flush=True)
        
    except Exception as e:
        log_error(f"❌ Verifier failed for {modified_rel_path}: {e}")
        result = {"status": "fail", "reason": "verifier_exception", "error": str(e)}
```

### Step 3: Update Project Map Building

Ensure project map is built and available:

```python
# In StepExecutor or Executor class
def _init_project_structures(self):
    """Initialize project-related structures"""
    from core.project_map import build_project_map
    from core.dependency_resolver import DependencyResolver
    
    self.project_map = build_project_map(str(self.project_root))
    self.resolver = DependencyResolver(self.project_map, str(self.project_root))
    
    # Pass to Verifier
    self.verifier.set_context(
        project_root=str(self.project_root),
        project_map=self.project_map,
        dependency_resolver=self.resolver,
        context_manager=getattr(self, 'context_manager', None)
    )
```

---

## What Gets Fixed Now

### BEFORE Enhancement:
```
File: main.py
─────────────
from wrong_path import helper  # ❌ ERROR: Module doesn't exist
def run():
    return helper(5)

Verifier: ✅ Syntax is OK (passes py_compile)
Result: ❌ BROKEN at runtime - imports don't work
```

### AFTER Enhancement:
```
File: main.py
─────────────
from wrong_path import helper  # ❌ ERROR: Module doesn't exist
def run():
    return helper(5)

Layer 1 - Syntax Check: ✅ Passes
Layer 2 - Semantic Check: ❌ Detects: wrong_path doesn't exist
Auto-Fix with Context: 
  1. Looks at project map
  2. Finds helper() is exported from utils.py
  3. Fixes to: from utils import helper
Result: ✅ WORKING - imports are correct
```

---

## Verification Flow Diagram

```
┌─ FILE GENERATED ──────────────────────────────────┐
│ main.py with wrong imports or broken syntax      │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌─ LAYER 1: SYNTAX CHECK ───────────────────────┐
│ verifier.verify_file(main.py)                 │
│  - Runs py_compile                            │
│  - Runs tsc/node for JS/TS                    │
└──────────────┬──────────────────────────────────┘
               │
         ┌─────┴─────┐
         ▼           ▼
    SYNTAX ERROR   OK → Continue
    │
    ├─→ verifier.auto_fix()  (simple fix)
    └─→ re-verify
         │
         ├─→ Still error? ❌ FAIL
         └─→ Fixed? → Continue
               │
               ▼
┌─ LAYER 2: SEMANTIC CHECK (NEW) ──────────────┐
│ verifier.verify_imports(main.py)             │
│  - Checks imports against project map        │
│  - Validates modules exist                   │
│  - Checks exports are available              │
└──────────────┬──────────────────────────────────┘
               │
         ┌─────┴─────┐
         ▼           ▼
   SEMANTIC ERROR   OK
    │              │
    ├─→ verifier.auto_fix_with_context()    ✅ DONE
    │   (fix with full project knowledge)    File is ready!
    └─→ re-verify
         │
         ├─→ Still error? ❌ FAIL
         └─→ Fixed? ✅ DONE
```

---

## Testing the Integration

After integration, test with:

```python
# Test in your agent execution:
print("[INFO] Testing enhanced verifier with project context...")

result = executor.execute_step(step)
# Should show:
# [VERIFY] start path/to/file.py
# 🔍 Semantic error in path/to/file.py: wrong_module
# ✅ Semantic auto-fix applied (with context)
# ✅ Semantic verification passed after fix
# [VERIFY] end path/to/file.py
```

---

## Performance Considerations

- **Async Execution**: Both layers run in executor pool (non-blocking)
- **Token Usage**: Context is limited (top 15 modules) to save tokens
- **Caching**: GPT responses are cached by GPTInterface
- **Skip Conditions**: Unsupported file types are skipped gracefully

---

## Error Handling

If semantic checking is not available:
- Gracefully skips (returns `{"status": "skipped"}`)
- Falls back to syntax-only checking
- Won't break existing functionality

---

## Next Steps

1. ✅ Enhanced Verifier ready ([core/verifier.py](core/verifier.py))
2. ✅ Tests passing ([tests/test_enhanced_verifier_complete.py](tests/test_enhanced_verifier_complete.py))
3. 🔄 **TODO**: Integrate into [executor/step_executor.py](executor/step_executor.py)
4. 🔄 **TODO**: Test with real project generation
5. 🔄 **TODO**: Monitor and optimize based on token usage

---

## Summary

The Enhanced Verifier now provides:
- ✅ Syntax error detection (existing)
- ✅ Semantic error detection (new) - detects wrong imports
- ✅ Context-aware auto-fixing (new) - fixes with project knowledge
- ✅ File-by-file verification (new) - each file independently checked
- ✅ Snippet-based fixing (new) - only fixes broken parts

This means generated code will be **automatically verified and fixed** at both syntax and semantic levels! 🚀
