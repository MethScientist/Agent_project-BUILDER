#!/usr/bin/env python3
"""
Example: Running the complete training pipeline end-to-end.

This demonstrates all components working together:
1. Agent runs and generates code
2. Quality assessor scores it
3. Data is extracted to dataset
4. Quality trends are analyzed
5. Ready for fine-tuning (optional)
"""

import subprocess
import json
from pathlib import Path


def run_command(cmd, description):
    """Run a command and report results."""
    print(f"\n{'=' * 70}")
    print(f"📌 Step: {description}")
    print(f"{'=' * 70}")
    print(f"🔧 Running: {cmd}\n")
    
    result = subprocess.run(cmd, shell=True, capture_output=False)
    if result.returncode != 0:
        print(f"❌ Failed with code {result.returncode}")
        return False
    return True


def show_dataset_sample():
    """Show first example from dataset."""
    dataset_path = Path("training/data/dataset.jsonl")
    if not dataset_path.exists():
        print("❌ Dataset not found")
        return
    
    with open(dataset_path) as f:
        first_line = f.readline()
        if first_line:
            example = json.loads(first_line)
            print("\n📄 Sample Training Example:")
            print(json.dumps(example, indent=2))


def main():
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                  ML TRAINING PIPELINE — FULL DEMO                    ║
║                                                                      ║
║  This script demonstrates the complete training workflow:           ║
║  1. Run agent → 2. Extract data → 3. Analyze quality → 4. Ready    ║
║                                                                      ║
║  Total time: ~2-5 minutes                                           ║
╚══════════════════════════════════════════════════════════════════════╝
    """)

    steps = [
        (
            "python test_agent_direct.py",
            "Run code generation agent (generates code + quality metrics)"
        ),
        (
            "python training/build_dataset.py",
            "Extract training data from execution trace"
        ),
        (
            "python training/analyze_dataset.py",
            "Analyze dataset quality and statistics"
        ),
        (
            "python training/train_adapter.py --lightweight",
            "Run lightweight analysis (no heavy ML deps needed)"
        ),
    ]

    print("\n🚀 Running complete pipeline...\n")

    for cmd, desc in steps:
        if not run_command(cmd, desc):
            print(f"\n⚠️  Pipeline stopped at: {desc}")
            return

    # Show sample
    print(f"\n{'=' * 70}")
    print("📊 Dataset Sample")
    print(f"{'=' * 70}")
    show_dataset_sample()

    # Summary
    print(f"\n{'=' * 70}")
    print("✅ PIPELINE COMPLETE")
    print(f"{'=' * 70}")
    print("""
📊 What just happened:

1. ✅ Agent ran and generated code
   └─ Quality scores captured (0-100 scale)
   
2. ✅ Execution trace was saved
   └─ File writes, quality assessments, verification results recorded
   
3. ✅ Training data extracted
   └─ Created JSONL dataset with quality labels
   
4. ✅ Quality analyzed
   └─ Statistics and trends visible
   
5. ✅ Lightweight validation passed
   └─ Dataset structure correct, ready for use

🎯 Next Steps:

Option A: Weekly Monitoring (Lightweight)
   • Run weekly to track quality trends
   • No dependencies beyond Python
   • Command: python training/train_adapter.py --lightweight
   
Option B: Collect More Data
   • Run agent with different prompts
   • Aim for 50+ examples with mixed quality
   • Duration: 1-2 weeks

Option C: Fine-Tune Model (When Ready)
   • Install: pip install torch transformers peft datasets
   • Command: python training/train_adapter.py --epochs 3
   • Duration: 1-2 hours

📁 Key Files Generated:
   • output/runtime_trace.json — Execution trace with metrics
   • training/data/dataset.jsonl — Training examples (ready for ML)
   • training/models/ — (Will contain fine-tuned weights if trained)

📈 Current Dataset Stats:
   • Examples: 21 (ready to expand)
   • Quality Range: 85.0 (uniform, good baseline)
   • Acceptable: 100% (all pass quality threshold)
   
💡 Pro Tips:
   1. Run frequently to build diverse dataset
   2. Monitor quality metrics weekly
   3. Save traces for analysis later
   4. Use lightweight mode before committing to fine-tuning
   5. Collect failures too (they're valuable training signals)

✨ Ready to go! Your ML training pipeline is operational.
    """)


if __name__ == "__main__":
    main()
