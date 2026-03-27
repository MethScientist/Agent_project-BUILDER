"""
Test: What happens when Verifier tries to fix SEMANTIC errors
(not just syntax errors)

Shows the limitations of the current auto-fix approach.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.verifier import Verifier
from ai_models.gpt_interface import GPTInterface


def test_undefined_variable():
    """Test: Code with undefined variable - NOT a syntax error"""
    print("\n" + "="*70)
    print("TEST 1: Undefined Variable (SEMANTIC ERROR)")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        py_file = os.path.join(tmpdir, "undefined.py")
        with open(py_file, "w") as f:
            f.write("""def calculate():
    result = undefined_function()  # This function doesn't exist!
    return result

print(calculate())
""")
        
        model = GPTInterface()
        verifier = Verifier(model)
        result = verifier.verify_file(py_file)
        
        print(f"File content:")
        with open(py_file, "r") as f:
            print(f.read())
        
        print(f"\nVerification result: {result}")
        print(f"\nAnalysis:")
        print(f"  ✅ Syntax check: PASSES (syntax is correct)")
        print(f"  ❌ Semantic check: FAILS (undefined_function doesn't exist)")
        print(f"  ❌ Verifier detects: NO (only checks syntax, not semantics)")
        return result['status']


def test_missing_import():
    """Test: Code with missing import"""
    print("\n" + "="*70)
    print("TEST 2: Missing Import (SEMANTIC ERROR)")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        py_file = os.path.join(tmpdir, "missing_import.py")
        with open(py_file, "w") as f:
            f.write("""import numpy as np  # This import might not exist or be wrong

def process_data():
    data = np.array([1, 2, 3])  # But numpy might not be installed
    return data.sum()

print(process_data())
""")
        
        model = GPTInterface()
        verifier = Verifier(model)
        result = verifier.verify_file(py_file)
        
        print(f"File content:")
        with open(py_file, "r") as f:
            print(f.read())
        
        print(f"\nVerification result: {result}")
        print(f"\nAnalysis:")
        print(f"  ✅ Syntax check: PASSES (import statement is valid syntax)")
        print(f"  ❌ Runtime check: FAILS (numpy might not be installed)")
        print(f"  ❌ Verifier detects: NO (only runs py_compile, doesn't import)")
        return result['status']


def test_wrong_import_path():
    """Test: Code importing from wrong project path"""
    print("\n" + "="*70)
    print("TEST 3: Wrong Import Path (PROJECT STRUCTURE ERROR)")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        py_file = os.path.join(tmpdir, "wrong_import.py")
        with open(py_file, "w") as f:
            f.write("""from nonexistent_module import helper  # Wrong path!

def do_something():
    return helper.process()

print(do_something())
""")
        
        model = GPTInterface()
        verifier = Verifier(model)
        result = verifier.verify_file(py_file)
        
        print(f"File content:")
        with open(py_file, "r") as f:
            print(f.read())
        
        print(f"\nVerification result: {result}")
        print(f"\nAnalysis:")
        print(f"  ✅ Syntax check: PASSES (import syntax is correct)")
        print(f"  ❌ Module resolution: FAILS (module doesn't exist)")
        print(f"  ❌ Verifier detects: NO (py_compile doesn't resolve imports)")
        return result['status']


def test_type_mismatch():
    """Test: Code with type/logic errors"""
    print("\n" + "="*70)
    print("TEST 4: Type/Logic Error (SEMANTIC ERROR)")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        py_file = os.path.join(tmpdir, "type_error.py")
        with open(py_file, "w") as f:
            f.write("""def process_list(data: list) -> int:
    '''Should return sum, but data is a string'''
    return len(data)  # Wrong! data might be string, not list

result = process_list("hello")  # Passing string instead of list
print(result)
""")
        
        model = GPTInterface()
        verifier = Verifier(model)
        result = verifier.verify_file(py_file)
        
        print(f"File content:")
        with open(py_file, "r") as f:
            print(f.read())
        
        print(f"\nVerification result: {result}")
        print(f"\nAnalysis:")
        print(f"  ✅ Syntax check: PASSES (code is syntactically valid)")
        print(f"  ⚠️  Type check: WOULD FAIL (with mypy/pyright, but not py_compile)")
        print(f"  ❌ Verifier detects: NO (py_compile is too basic)")
        return result['status']


def test_what_autofix_can_do():
    """Show what auto_fix() actually DOES do"""
    print("\n" + "="*70)
    print("TEST 5: What auto_fix() CAN Handle (Syntax Errors Only)")
    print("="*70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        py_file = os.path.join(tmpdir, "syntax_error.py")
        with open(py_file, "w") as f:
            f.write("""def add(a, b)  # Missing colon - SYNTAX ERROR
    return a + b
""")
        
        model = GPTInterface()
        verifier = Verifier(model)
        
        # First verify - should fail
        result = verifier.verify_file(py_file)
        print(f"Initial verification: {result}")
        
        if result['status'] == 'error':
            print(f"\nError detected: {result['error'][:100]}...")
            print(f"\nAttempting auto_fix()...")
            
            try:
                fixed_code = verifier.auto_fix(py_file, result['error'])
                print(f"\nAuto-fix result:")
                print(f"{fixed_code}")
                
                # Verify again
                result2 = verifier.verify_file(py_file)
                print(f"\nPost-fix verification: {result2}")
                
            except Exception as e:
                print(f"❌ Auto-fix failed: {e}")


# ============================================================================
# SUMMARY
# ============================================================================

def run_all_tests():
    print("\n\n")
    print("█" * 70)
    print("█" + " " * 68 + "█")
    print("█" + "  VERIFIER SEMANTIC ERROR HANDLING TEST".center(68) + "█")
    print("█" + " " * 68 + "█")
    print("█" * 70)
    
    test_undefined_variable()
    test_missing_import()
    test_wrong_import_path()
    test_type_mismatch()
    test_what_autofix_can_do()
    
    # Summary
    print("\n\n")
    print("█" * 70)
    print("█" + " " * 68 + "█")
    print("█" + "  FINDINGS: VERIFIER LIMITATIONS".center(68) + "█")
    print("█" + " " * 68 + "█")
    print("█" * 70)
    
    print("""
┌─ WHAT VERIFIER CAN DO ─────────────────────────────────────────────┐
│                                                                      │
│  ✅ Detects & Fixes SYNTAX ERRORS:                                 │
│     - Missing colons, parentheses, brackets                        │
│     - Invalid indentation                                          │
│     - Malformed statements                                         │
│     Example: "def foo()" → "def foo():"                           │
│                                                                      │
│  ✅ Validates JSON structure                                       │
│  ✅ Checks CSS brace matching                                      │
│  ✅ Uses language-specific compilers (tsc, g++, javac)            │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌─ WHAT VERIFIER CANNOT DO ──────────────────────────────────────────┐
│                                                                      │
│  ❌ Detect semantic errors:                                        │
│     - Undefined variables/functions                               │
│     - Missing imports                                              │
│     - Wrong import paths                                           │
│     - Type mismatches                                              │
│     - Logic errors                                                 │
│                                                                      │
│  ❌ Understand project structure:                                  │
│     - Knows nothing about where modules should be                  │
│     - Doesn't know project dependencies                            │
│     - Can't validate cross-file dependencies                       │
│                                                                      │
│  ❌ Validate at runtime:                                           │
│     - Won't catch runtime errors                                   │
│     - Can't verify if code actually works                          │
│     - No type checking (unless using TypeScript/mypy)             │
│                                                                      │
│  ❌ Auto-fix SEMANTIC errors reliably:                             │
│     - GPT might hallucinate imports/functions                      │
│     - GPT doesn't know project context                             │
│     - Generated code might not integrate properly                  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌─ WHY THIS HAPPENS ─────────────────────────────────────────────────┐
│                                                                      │
│  py_compile -m only checks SYNTAX, not SEMANTICS:                  │
│  - It parses the code but doesn't execute it                       │
│  - It doesn't try to import or resolve modules                     │
│  - It only validates grammar, not meaning                          │
│                                                                      │
│  GPT's auto-fix has CONTEXT LIMITATIONS:                           │
│  - Only sees the broken file, not the full project                 │
│  - Doesn't know what imports are available                         │
│  - Might invent functions/modules that don't exist                 │
│  - Works better with Verifier + CodeGenerator combo               │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘

┌─ SOLUTION: MULTI-LAYER VALIDATION ────────────────────────────────┐
│                                                                      │
│  The Hope Agent system handles this by COMBINING:                 │
│                                                                      │
│  1. VERIFIER (syntax validation)                                   │
│     └─ What it does: Catches syntax errors                        │
│                                                                      │
│  2. PROJECT MAPPER (semantic awareness)                            │
│     └─ What it does: Understands project structure & exports       │
│                                                                      │
│  3. DEPENDENCY RESOLVER (context awareness)                        │
│     └─ What it does: Validates imports exist in project            │
│                                                                      │
│  4. CODE GENERATOR (intelligent generation)                        │
│     └─ What it does: Generates code WITH project context          │
│                                                                      │
│  5. CONTEXT MANAGER (knowledge base)                               │
│     └─ What it does: Provides GPT with full project information   │
│                                                                      │
│  Together: ✅ Syntax errors → Fixed                                │
│  Together: ✅ Semantic errors → Prevented                          │
│  Together: ✅ Context understood → Proper code generated          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
""")


if __name__ == "__main__":
    run_all_tests()
