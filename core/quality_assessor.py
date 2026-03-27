"""
core/quality_assessor.py

Quality assessment engine that evaluates generated code beyond syntax
checks—detects undefined names, fragile patterns, missing error handling,
stubs and stylistic issues. Produces a structured QualityReport usable as
training signal and for emit events.
"""
from __future__ import annotations
import ast
import re
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
from typing import List, Dict, Any, Optional


class SeverityLevel(Enum):
    CRITICAL = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    INFO = 1


@dataclass
class QualityIssue:
    type: str
    severity: SeverityLevel
    line: int
    column: int
    message: str
    code_snippet: str
    suggestion: Optional[str] = None
    auto_fixable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.name
        return d


@dataclass
class QualityReport:
    file_path: str
    language: str
    overall_score: float
    total_issues: int
    critical_issues: int
    high_issues: int
    medium_issues: int
    low_issues: int
    issues: List[QualityIssue]
    metrics: Dict[str, Any]
    recommendations: List[str]
    is_acceptable: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "language": self.language,
            "overall_score": round(self.overall_score, 2),
            "total_issues": self.total_issues,
            "critical_issues": self.critical_issues,
            "high_issues": self.high_issues,
            "medium_issues": self.medium_issues,
            "low_issues": self.low_issues,
            "is_acceptable": self.is_acceptable,
            "issues": [i.to_dict() for i in self.issues],
            "metrics": self.metrics,
            "recommendations": self.recommendations,
        }


class QualityAssessor:
    def __init__(self, project_root: str = ".", project_map: Optional[Dict] = None):
        self.project_root = Path(project_root).resolve()
        self.project_map = project_map or {}

    def assess_file(self, file_path: str) -> QualityReport:
        p = Path(file_path)
        if not p.exists():
            issue = QualityIssue(
                type="file_missing",
                severity=SeverityLevel.CRITICAL,
                line=0,
                column=0,
                message=f"File not found: {file_path}",
                code_snippet="",
            )
            return QualityReport(
                file_path=str(file_path),
                language="unknown",
                overall_score=0.0,
                total_issues=1,
                critical_issues=1,
                high_issues=0,
                medium_issues=0,
                low_issues=0,
                issues=[issue],
                metrics={},
                recommendations=["Check file path"],
                is_acceptable=False,
            )

        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            issue = QualityIssue(
                type="read_error",
                severity=SeverityLevel.CRITICAL,
                line=0,
                column=0,
                message=f"Could not read file: {e}",
                code_snippet="",
            )
            return QualityReport(
                file_path=str(file_path),
                language="unknown",
                overall_score=0.0,
                total_issues=1,
                critical_issues=1,
                high_issues=0,
                medium_issues=0,
                low_issues=0,
                issues=[issue],
                metrics={},
                recommendations=["Fix file permissions"],
                is_acceptable=False,
            )

        ext = p.suffix.lower()
        language = self._detect_language(ext)

        issues: List[QualityIssue] = []
        metrics: Dict[str, Any] = {}

        if language == "python":
            issues.extend(self._assess_python(content))
            metrics.update(self._python_metrics(content))
        else:
            # Minimal checks for other languages
            issues.extend(self._assess_universal(content))

        counts = self._count_by_severity(issues)
        score = self._compute_score(counts, len(content.splitlines()))
        is_ok = counts["critical"] == 0 and counts["high"] <= 1
        recs = self._generate_recommendations(issues, metrics)

        return QualityReport(
            file_path=str(file_path),
            language=language,
            overall_score=score,
            total_issues=len(issues),
            critical_issues=counts["critical"],
            high_issues=counts["high"],
            medium_issues=counts["medium"],
            low_issues=counts["low"],
            issues=issues,
            metrics=metrics,
            recommendations=recs,
            is_acceptable=is_ok,
        )

    # ------------------------- python checks -------------------------
    def _assess_python(self, content: str) -> List[QualityIssue]:
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            return [QualityIssue(
                type="syntax_error",
                severity=SeverityLevel.CRITICAL,
                line=e.lineno or 0,
                column=e.offset or 0,
                message=f"Syntax error: {e.msg}",
                code_snippet=(content.splitlines()[e.lineno-1] if e.lineno and e.lineno <= len(content.splitlines()) else ""),
            )]

        issues: List[QualityIssue] = []
        lines = content.split('\n')

        defined = self._extract_defs(tree)
        imports = self._extract_imports(tree)

        issues.extend(self._find_undefined_names(tree, defined, imports, lines))
        issues.extend(self._find_stub_functions(tree, lines))
        issues.extend(self._find_bare_excepts(tree, lines))
        issues.extend(self._find_unused_imports(tree, lines))
        issues.extend(self._assess_universal(content))

        return issues

    def _extract_defs(self, tree: ast.AST) -> set:
        names = {'__name__', '__file__'}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        names.add(t.id)
        return names

    def _extract_imports(self, tree: ast.AST) -> set:
        result = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    result.add(a.asname or a.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    result.add(a.asname or a.name)
        return result

    def _find_undefined_names(self, tree, defined, imports, lines) -> List[QualityIssue]:
        issues = []
        builtins = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))
        ok = defined | imports | builtins | {"self", "cls"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
                if node.id not in ok and not node.id.startswith('_'):
                    ln = getattr(node, 'lineno', 0)
                    snippet = lines[ln-1].strip() if ln and ln <= len(lines) else ''
                    issues.append(QualityIssue(
                        type="undefined_name",
                        severity=SeverityLevel.HIGH,
                        line=ln,
                        column=getattr(node, 'col_offset', 0),
                        message=f"Name '{node.id}' is not defined",
                        code_snippet=snippet,
                        suggestion=f"Define or import '{node.id}'",
                    ))
        return issues

    def _find_stub_functions(self, tree, lines) -> List[QualityIssue]:
        issues = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                body = node.body or []
                if len(body) == 0 or all(isinstance(n, (ast.Pass, ast.Expr)) and (not isinstance(n, ast.Expr) or isinstance(n.value, ast.Constant)) for n in body):
                    if not node.name.startswith('_'):
                        ln = node.lineno
                        snippet = lines[ln-1].strip() if ln and ln <= len(lines) else ''
                        issues.append(QualityIssue(
                            type="stub_function",
                            severity=SeverityLevel.HIGH,
                            line=ln,
                            column=0,
                            message=f"Function '{node.name}' appears to be a stub",
                            code_snippet=snippet,
                        ))
        return issues

    def _find_bare_excepts(self, tree, lines) -> List[QualityIssue]:
        issues = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                ln = getattr(node, 'lineno', 0)
                snippet = lines[ln-1].strip() if ln and ln <= len(lines) else ''
                issues.append(QualityIssue(
                    type="bare_except",
                    severity=SeverityLevel.MEDIUM,
                    line=ln,
                    column=0,
                    message="Bare except catches all exceptions",
                    code_snippet=snippet,
                    suggestion="Catch specific exception types",
                    auto_fixable=True,
                ))
        return issues

    def _find_unused_imports(self, tree, lines) -> List[QualityIssue]:
        issues = []
        used = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                used.add(node.value.id)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                ln = getattr(node, 'lineno', 0)
                for a in node.names:
                    name = a.asname or a.name.split('.')[0]
                    if name not in used and not name.startswith('_'):
                        snippet = lines[ln-1].strip() if ln and ln <= len(lines) else ''
                        issues.append(QualityIssue(
                            type="unused_import",
                            severity=SeverityLevel.LOW,
                            line=ln,
                            column=0,
                            message=f"Unused import: {name}",
                            code_snippet=snippet,
                            auto_fixable=True,
                        ))
        return issues

    # ------------------------- universal checks -------------------------
    def _assess_universal(self, content: str) -> List[QualityIssue]:
        issues = []
        for i, line in enumerate(content.split('\n'), 1):
            if len(line) > 120:
                issues.append(QualityIssue(
                    type="line_too_long",
                    severity=SeverityLevel.LOW,
                    line=i,
                    column=120,
                    message=f"Line length {len(line)} > 120",
                    code_snippet=line[:120] + '...',
                ))
        return issues

    def _python_metrics(self, content: str) -> Dict[str, Any]:
        try:
            tree = ast.parse(content)
        except Exception:
            return {}
        return {
            'lines': len(content.split('\n')),
            'functions': sum(1 for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))),
            'classes': sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef)),
            'imports': sum(1 for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)))
        }

    def _detect_language(self, ext: str) -> str:
        m = {'.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.cs': 'csharp'}
        return m.get(ext, 'unknown')

    def _count_by_severity(self, issues: List[QualityIssue]) -> Dict[str, int]:
        counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        for it in issues:
            name = it.severity.name.lower()
            if name in counts:
                counts[name] += 1
        return counts

    def _compute_score(self, counts: Dict[str, int], lines: int) -> float:
        score = 100.0
        score -= counts['critical'] * 20
        score -= counts['high'] * 10
        score -= counts['medium'] * 5
        score -= counts['low'] * 2
        if lines < 10:
            score -= 15
        elif lines < 30:
            score -= 5
        return max(0.0, min(100.0, score))

    def _generate_recommendations(self, issues: List[QualityIssue], metrics: Dict, ) -> List[str]:
        recs = []
        types = {}
        for it in issues:
            types[it.type] = types.get(it.type, 0) + 1
        if types.get('undefined_name'):
            recs.append('Fix undefined names by adding definitions or imports')
        if types.get('stub_function'):
            recs.append('Implement stub functions')
        if types.get('bare_except'):
            recs.append('Avoid bare except; catch specific exceptions')
        if types.get('unused_import'):
            recs.append('Remove unused imports')
        if not recs:
            recs.append('No major issues found')
        return recs
