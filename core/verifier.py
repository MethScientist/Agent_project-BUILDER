import subprocess, os, tempfile, json, re
import runtime_trace as trace


class Verifier:
    def __init__(self, model):
        self.model = model

    def verify_file(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        res = {"status": "skipped", "reason": f"unsupported type: {ext}"}

        match ext:
            case ".py": res = self._verify_python(file_path)
            case ".js": res = self._verify_js(file_path)
            case ".ts": res = self._verify_ts(file_path)
            case ".html" | ".css": res = self._verify_html_css(file_path)
            case ".json": res = self._verify_json(file_path)
            case ".cpp": res = self._verify_cpp(file_path)
            case ".java": res = self._verify_java(file_path)
            case ".sh": res = self._verify_bash(file_path)
            case ".php": res = self._verify_php(file_path)

        try:
            trace.log_verification(file_path, res)
        except Exception:
            pass

        # RETURN ONLY REPORT, never modify file
        return res

    # ================= Basic verifiers =================
    def _verify_python(self, path):
        try:
            subprocess.run(["python", "-m", "py_compile", path], capture_output=True, text=True, check=True)
            return {"status": "ok"}
        except FileNotFoundError as e:
            return {"status": "skipped", "reason": f"python not found: {e}"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "error": e.stderr}

    def _verify_js(self, path):
        try:
            subprocess.run(["node", "--check", path], capture_output=True, text=True, check=True)
            return {"status": "ok"}
        except FileNotFoundError as e:
            return {"status": "skipped", "reason": f"node not found: {e}"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "error": e.stderr}

    def _verify_ts(self, path):
        try:
            subprocess.run(["tsc", "--noEmit", path], capture_output=True, text=True, check=True)
            return {"status": "ok"}
        except FileNotFoundError as e:
            return {"status": "skipped", "reason": f"tsc not found: {e}"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "error": e.stderr}

    def _verify_html_css(self, path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if "<html" in content or "{" in content:
            return {"status": "ok"}
        return {"status": "error", "error": "Invalid HTML/CSS syntax"}

    def _verify_css(self, path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        if content.count("{") == content.count("}") and content.count("{") > 0:
            return {"status": "ok"}
        return {"status": "error", "error": "Mismatched or missing CSS braces"}

    def _verify_json(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                json.load(f)
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _verify_cpp(self, path):
        try:
            subprocess.run(["g++", "-fsyntax-only", path], capture_output=True, text=True, check=True)
            return {"status": "ok"}
        except FileNotFoundError as e:
            return {"status": "skipped", "reason": f"g++ not found: {e}"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "error": e.stderr}

    def _verify_java(self, path):
        try:
            subprocess.run(["javac", "-Xlint", path], capture_output=True, text=True, check=True)
            return {"status": "ok"}
        except FileNotFoundError as e:
            return {"status": "skipped", "reason": f"javac not found: {e}"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "error": e.stderr}

    def _verify_bash(self, path):
        try:
            subprocess.run(["bash", "-n", path], capture_output=True, text=True, check=True)
            return {"status": "ok"}
        except FileNotFoundError as e:
            return {"status": "skipped", "reason": f"bash not found: {e}"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "error": e.stderr}

    def _verify_php(self, path):
        try:
            subprocess.run(["php", "-l", path], capture_output=True, text=True, check=True)
            return {"status": "ok"}
        except subprocess.CalledProcessError as e:
            return {"status": "error", "error": e.stderr}
    # ================= detect_issues =================
    def _extract_issues(self, file_path: str, error_text: str, lang: str = None) -> list:
        """
        Extract structured issues from verification output.
        
        Returns a list of dicts:
        {
            "line": int,
            "type": str,        # "syntax", "indentation", "runtime", "import", etc.
            "message": str,
            "snippet": str      # nearby code context
        }
        """
        issues = []
        if not error_text:
            return issues

        # Auto-detect language from file extension if not provided
        if not lang:
            ext = os.path.splitext(file_path)[1].lower()
            lang = {
                ".py": "py", ".js": "js", ".ts": "ts", ".jsx": "js", ".tsx": "ts",
                ".cpp": "cpp", ".c": "cpp", ".java": "java", ".html": "html",
                ".css": "css", ".json": "json", ".sh": "bash", ".php": "php"
            }.get(ext, "unknown")

        # Read file lines for context
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            lines = []

        # Helper to get snippet
        def get_snippet(line_no, context=2):
            start = max(0, line_no - context - 1)
            end = min(len(lines), line_no + context)
            return "".join(lines[start:end]).rstrip("\n")

        # 1️⃣ Python-specific errors
        if lang == "py":
            patterns = [
                (r"SyntaxError: (.+) \(line (\d+)\)", "syntax"),
                (r"IndentationError: (.+) \(line (\d+)\)", "indentation"),
                (r"(NameError|AttributeError|TypeError|ZeroDivisionError|KeyError|IndexError): (.+)", "runtime"),
                (r"ImportError: (.+)", "import")
            ]
            for pattern, err_type in patterns:
                for match in re.finditer(pattern, error_text):
                    if err_type in ["syntax", "indentation"]:
                        line_no = int(match.group(2))
                        msg = match.group(1).strip()
                    elif err_type == "runtime":
                        # Try to find line number from traceback
                        m_line = re.search(r"line (\d+)", error_text)
                        line_no = int(m_line.group(1)) if m_line else 1
                        msg = f"{match.group(1)}: {match.group(2)}"
                    else:  # import
                        line_no = 1
                        msg = match.group(1).strip()
                    issues.append({
                        "line": line_no,
                        "type": err_type,
                        "message": msg,
                        "snippet": get_snippet(line_no)
                    })

        # 2️⃣ JS/TS errors
        elif lang in ["js", "ts"]:
            # Syntax, reference, type errors
            patterns = [
                (r"SyntaxError: (.+) at line (\d+)", "syntax"),
                (r"ReferenceError: (.+) at line (\d+)", "runtime"),
                (r"TypeError: (.+) at line (\d+)", "runtime"),
                (r"Cannot find module ['\"](.+)['\"]", "import")
            ]
            for pattern, err_type in patterns:
                for match in re.finditer(pattern, error_text):
                    line_no = int(match.group(2)) if len(match.groups()) > 1 else 1
                    msg = match.group(1).strip()
                    issues.append({
                        "line": line_no,
                        "type": err_type,
                        "message": msg,
                        "snippet": get_snippet(line_no)
                    })

        # 3️⃣ C/C++ errors
        elif lang == "cpp":
            pattern = r"^(.*):(\d+):(\d+): (error|warning): (.+)$"
            for match in re.finditer(pattern, error_text, re.MULTILINE):
                line_no = int(match.group(2))
                msg_type = "error" if match.group(4) == "error" else "warning"
                msg = match.group(5).strip()
                issues.append({
                    "line": line_no,
                    "type": msg_type,
                    "message": msg,
                    "snippet": get_snippet(line_no)
                })

        # 4️⃣ Java errors
        elif lang == "java":
            pattern = r"^(.+\.java):(\d+): error: (.+)$"
            for match in re.finditer(pattern, error_text, re.MULTILINE):
                line_no = int(match.group(2))
                msg = match.group(3).strip()
                issues.append({
                    "line": line_no,
                    "type": "error",
                    "message": msg,
                    "snippet": get_snippet(line_no)
                })

        # 5️⃣ JSON errors
        elif lang == "json":
            pattern = r"line (\d+) column (\d+)"
            m = re.search(pattern, error_text)
            if m:
                line_no = int(m.group(1))
                issues.append({
                    "line": line_no,
                    "type": "json",
                    "message": error_text.strip(),
                    "snippet": get_snippet(line_no)
                })

        # 6️⃣ HTML/CSS
        elif lang in ["html", "css"]:
            issues.append({
                "line": 1,
                "type": lang,
                "message": error_text.strip(),
                "snippet": "".join(lines[:5]).rstrip("\n")
            })

        # 7️⃣ Fallback: generic error
        if not issues and error_text:
            issues.append({
                "line": 1,
                "type": "unknown",
                "message": error_text.strip(),
                "snippet": "".join(lines[:5]).rstrip("\n")
            })

        return issues

    def _read(self, file_path):
        """Return file content as string."""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    # ================= Auto-fix =================
    def auto_fix_with_context(self, file_path, max_rounds: int = 5):
        """
        Auto-fix a file using GPT context-aware line fixes and import fixes.
        Loops until the file passes verification or max_rounds reached.
        """
        if max_rounds < 1:
            max_rounds = 5

        for round_no in range(max_rounds):
            # 1️⃣ Run syntax / runtime verification
            result = self.verify_file(file_path)
            syntax_ok = result.get("status") == "ok"

            # 2️⃣ Run semantic/import verification
            imports_result = self.verify_imports(file_path)
            imports_ok = imports_result.get("status") in ["ok", "skipped"]

            if syntax_ok and imports_ok:
                # File fully fixed
                return self._read(file_path)

            # 3️⃣ Collect issues to fix
            issues = []

            # Syntax/runtime issues
            if result.get("status") == "error":
                issues.extend(self._extract_issues(file_path, result.get("error", "")))

            # Import/semantic issues
            if imports_result.get("status") == "semantic_error":
                issues.extend(imports_result.get("issues", []))

            if not issues:
                # Nothing to fix, exit
                break

            # 4️⃣ Read current file
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # 5️⃣ Fix each issue using GPT
            for issue in issues:
                line_no = max(issue.get("line", 1) - 1, 0)
                broken_line = lines[line_no].rstrip("\n") if line_no < len(lines) else ""

                prompt = f"""
    You are a code fixer.

    Project context: {self._build_context_for_gpt(file_path)}

    Broken code line (line {line_no+1}):
    {broken_line}

    Issue: {issue}

    Instructions:
    - Fix only this line.
    - Return only valid code lines, split by newline if multiple.
    - If line should be deleted, return only: # DELETE LINE
    - Do NOT add comments or explanations.
    """

                fixed_output = self.model.ask_gpt(prompt, system_role="You are an expert code fixer.").strip()
                fixed_lines = fixed_output.splitlines()

                # Apply GPT fix
                if fixed_lines == ["# DELETE LINE"]:
                    if line_no < len(lines):
                        lines[line_no] = ""
                elif fixed_lines:
                    lines[line_no] = fixed_lines[0] + "\n"
                    for extra in fixed_lines[1:]:
                        line_no += 1
                        lines.insert(line_no, extra + "\n")

            # 6️⃣ Write updated file
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(lines)

        # Return final file content
        return self._read(file_path)




    # ========================================================================
    # ENHANCED SEMANTIC ERROR DETECTION & FIXING
    # ========================================================================

    def set_context(self, project_root=None, project_map=None, dependency_resolver=None, context_manager=None):
        """
        Set project context for semantic error detection.
        
        Args:
            project_root: Root directory of project
            project_map: Dict of {rel_path: {"lang": lang, "exports": [...]}}
            dependency_resolver: DependencyResolver instance
            context_manager: ContextManager instance
        """
        self.project_root = project_root
        self.project_map = project_map or {}
        self.resolver = dependency_resolver
        self.context_manager = context_manager

    def verify_imports(self, file_path):
        """
        SEMANTIC ERROR DETECTION: Verify imports match project structure.
        
        Returns:
            {"status": "ok"} - All imports valid
            {"status": "semantic_error", "issues": [...]} - Import issues found
            {"status": "skipped"} - No context available
        """
        if not self.project_map or not self.project_root:
            return {"status": "skipped", "reason": "No project context"}
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Detect language
            ext = os.path.splitext(file_path)[1].lower()
            
            # Check imports based on language
            if ext == ".py":
                issues = self._check_python_imports(content, file_path)
            elif ext in [".ts", ".js", ".jsx", ".tsx"]:
                issues = self._check_js_imports(content, file_path)
            else:
                return {"status": "skipped", "reason": f"Import checking not supported for {ext}"}
            
            if issues:
                return {
                    "status": "semantic_error",
                    "issues": issues,
                    "message": f"Found {len(issues)} semantic issue(s)"
                }
            
            return {"status": "ok"}
            
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _check_python_imports(self, content, file_path):
        """Check Python import statements for validity."""
        issues = []
        
        # Pattern for: from X import Y or import X
        from_pattern = r'from\s+([\w\.]+)\s+import\s+([\w\s,]+)'
        import_pattern = r'import\s+([\w\.]+)'
        
        # Check 'from ... import ...' statements
        for match in re.finditer(from_pattern, content):
            module_name = match.group(1)
            imports = match.group(2)
            line_no = content[:match.start()].count('\n') + 1
            
            if not self._module_exists_in_project(module_name, file_path):
                suggestion = self._suggest_module(module_name)
                issues.append({
                    "type": "missing_module",
                    "module": module_name,
                    "imports": imports.split(',')[0].strip(),
                    "line": line_no,
                    "suggestion": suggestion
                })
        
        # Check 'import ...' statements
        for match in re.finditer(import_pattern, content):
            module_name = match.group(1).split('.')[0]
            line_no = content[:match.start()].count('\n') + 1
            
            # Skip standard library
            if not self._is_stdlib(module_name) and not self._module_exists_in_project(module_name, file_path):
                suggestion = self._suggest_module(module_name)
                issues.append({
                    "type": "missing_module",
                    "module": module_name,
                    "line": line_no,
                    "suggestion": suggestion
                })
        
        return issues

    def _check_js_imports(self, content, file_path):
        """Check JavaScript/TypeScript import statements for validity."""
        issues = []
        
        # Pattern for: import X from 'path' or import X from "path"
        import_pattern = r'import\s+(?:{[^}]*}|[\w*\s,]+)\s+from\s+[\'"]([^\'"]+)[\'"]'
        
        for match in re.finditer(import_pattern, content):
            import_path = match.group(1)
            line_no = content[:match.start()].count('\n') + 1
            
            if not self._js_module_exists(import_path, file_path):
                suggestion = self._suggest_js_path(import_path, file_path)
                issues.append({
                    "type": "missing_import_path",
                    "path": import_path,
                    "line": line_no,
                    "suggestion": suggestion
                })
        
        return issues

    def _module_exists_in_project(self, module_name, file_path):
        """Check if a Python module exists in the project."""
        # Check if it's in project_map
        module_path = module_name.replace('.', os.sep) + '.py'
        
        for rel_path in self.project_map.keys():
            if module_path in rel_path or rel_path.endswith(module_path):
                return True
        
        return False

    def _js_module_exists(self, import_path, file_path):
        """Check if a JavaScript module exists in the project."""
        if import_path.startswith('.'):
            # Relative import
            file_dir = os.path.dirname(file_path)
            resolved = os.path.normpath(os.path.join(file_dir, import_path))
            
            # Check with various extensions
            for ext in ['.ts', '.js', '.tsx', '.jsx', '']:
                check_path = resolved + ext if ext else resolved
                check_rel = os.path.relpath(check_path, self.project_root)
                check_rel = check_rel.replace('\\', '/')
                
                if check_rel in self.project_map:
                    return True
        
        return False

    def _is_stdlib(self, module_name):
        """Check if module is Python standard library."""
        stdlib_modules = {
            'os', 'sys', 're', 'json', 'math', 'random', 'datetime', 'time',
            'collections', 'itertools', 'functools', 'operator', 'string',
            'io', 'pathlib', 'subprocess', 'threading', 'multiprocessing',
            'asyncio', 'logging', 'unittest', 'doctest', 'pdb', 'trace',
            'typing', 'abc', 'inspect', 'types', 'copy', 'pickle', 'csv',
            'sqlite3', 'urllib', 'http', 'socket', 'email', 'html', 'xml'
        }
        return module_name in stdlib_modules

    def _suggest_module(self, wrong_module):
        """Suggest a correction for wrong module name."""
        # Find best matching module in project
        best_match = None
        best_score = 0
        
        for rel_path in self.project_map.keys():
            # Simple matching: if wrong_module appears in path
            if wrong_module.lower() in rel_path.lower():
                best_match = rel_path
                best_score = len(wrong_module)
                break
        
        if best_match:
            # Convert path to module name
            module_name = best_match.replace(os.sep, '.').replace('.py', '')
            return module_name
        
        return None

    def _suggest_js_path(self, wrong_path, file_path):
        """Suggest correction for wrong JavaScript import path."""
        # Find similar file names in project
        wrong_name = os.path.basename(wrong_path)
        
        for rel_path in self.project_map.keys():
            if wrong_name in os.path.basename(rel_path):
                # Convert to relative path
                file_dir = os.path.dirname(file_path)
                try:
                    rel = os.path.relpath(rel_path, file_dir)
                    rel = rel.replace('\\', '/')
                    if not rel.startswith('.'):
                        rel = './' + rel
                    rel = rel.replace('.ts', '').replace('.js', '')
                    return rel
                except ValueError:
                    pass
        
        return None


    def _build_context_for_gpt(self, file_path):
        """Build project context summary for GPT."""
        lines = []
        
        rel_path = os.path.relpath(file_path, self.project_root) if self.project_root else "unknown"
        lines.append(f"Current file: {rel_path}")
        
        # List available modules/exports
        lines.append("\nAvailable modules in project:")
        count = 0
        for mod_path, meta in self.project_map.items():
            if count >= 15:  # Limit for token budget
                lines.append(f"  ... and {len(self.project_map) - count} more modules")
                break
            
            exports = meta.get("exports", [])
            exports_str = ", ".join(str(e)[:20] for e in exports[:3])
            if len(exports) > 3:
                exports_str += f", ... ({len(exports)} total)"
            
            lines.append(f"  - {mod_path} exports: {exports_str}")
            count += 1
        
        return "\n".join(lines)

    def extract_import_block(self, content, lang="py"):
        """
        Extract import section from file.
        
        Returns:
            List of (line_no, import_statement) tuples
        """
        lines = content.split('\n')
        imports = []
        
        if lang == "py":
            for i, line in enumerate(lines):
                if line.strip().startswith(('import ', 'from ')):
                    imports.append((i + 1, line))
        
        elif lang in ["js", "ts"]:
            for i, line in enumerate(lines):
                if 'import ' in line and ' from ' in line:
                    imports.append((i + 1, line))
        
        return imports

    def fix_single_import(self, import_stmt, suggested_fix):
        """Fix a single import statement."""
        # Simple replacement: replace module name with suggested one
        # In real use, GPT would handle complex transformations
        return suggested_fix

