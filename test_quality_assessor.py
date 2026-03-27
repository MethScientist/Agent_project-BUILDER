#!/usr/bin/env python3
"""Quick smoke test of QualityAssessor on sample code files."""

import sys
from pathlib import Path

# Test imports
try:
    from core.quality_assessor import QualityAssessor, QualityReport
    print("✅ QualityAssessor imported successfully")
except Exception as e:
    print(f"❌ Failed to import QualityAssessor: {e}")
    sys.exit(1)

# Create a sample Python file with known issues
sample_code = '''
def incomplete_function():
    pass

def another_function():
    try:
        x = undefined_variable
    except:
        print("error")

unused_import = None
'''

sample_file = Path("test_sample.py")
sample_file.write_text(sample_code)

try:
    # Test the assessor
    assessor = QualityAssessor(project_root=".")
    report = assessor.assess_file(str(sample_file))
    
    print(f"\n📊 Quality Report for {sample_file}:")
    print(f"  Overall Score: {report.overall_score}/100")
    print(f"  Language: {report.language}")
    print(f"  Total Issues: {report.total_issues}")
    print(f"    - Critical: {report.critical_issues}")
    print(f"    - High: {report.high_issues}")
    print(f"    - Medium: {report.medium_issues}")
    print(f"    - Low: {report.low_issues}")
    print(f"  Is Acceptable: {report.is_acceptable}")
    
    print(f"\n  Issues found:")
    for i, issue in enumerate(report.issues[:5], 1):
        print(f"    {i}. [{issue.severity.name}] {issue.type} @ line {issue.line}: {issue.message}")
    
    print(f"\n  Recommendations:")
    for rec in report.recommendations:
        print(f"    - {rec}")
    
    print("\n✅ QualityAssessor smoke test PASSED")
    
finally:
    sample_file.unlink(missing_ok=True)
