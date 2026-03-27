#!/usr/bin/env python3
"""
Quick dataset analysis without external dependencies.
"""
import json
from pathlib import Path
from collections import defaultdict


def main():
    dataset_path = Path("training/data/dataset.jsonl")
    if not dataset_path.exists():
        print(f"❌ Dataset not found: {dataset_path}")
        print("   Run: python training/build_dataset.py")
        return

    examples = []
    with open(dataset_path) as f:
        for line in f:
            if line.strip():
                examples.append(json.loads(line))

    print(f"\n📊 Dataset Analysis ({len(examples)} examples)")
    print("=" * 60)

    # Basic stats
    scores = [e.get("quality_score", 0) for e in examples]
    acceptable = [e for e in examples if e.get("is_acceptable")]
    unacceptable = [e for e in examples if not e.get("is_acceptable")]

    print(f"\n✅ Summary:")
    print(f"  Total examples:        {len(examples)}")
    print(f"  Acceptable:            {len(acceptable)} ({100*len(acceptable)//len(examples)}%)")
    print(f"  Unacceptable:          {len(unacceptable)} ({100*len(unacceptable)//len(examples)}%)")

    print(f"\n📈 Quality Scores:")
    print(f"  Min:    {min(scores):.1f}")
    print(f"  Max:    {max(scores):.1f}")
    print(f"  Mean:   {sum(scores)/len(scores):.1f}")
    print(f"  Median: {sorted(scores)[len(scores)//2]:.1f}")

    # Distribution
    score_bins = defaultdict(int)
    for score in scores:
        bin_key = int(score // 10) * 10
        score_bins[bin_key] += 1

    print(f"\n📊 Score Distribution:")
    for bin_start in sorted(score_bins.keys()):
        count = score_bins[bin_start]
        bar = "█" * (count * 2)
        print(f"  {bin_start:3d}-{bin_start+9:3d}:  {bar} ({count})")

    # By status
    status_counts = defaultdict(int)
    for ex in examples:
        status = ex.get("verifier_status", "unknown")
        if status is None:
            status = "unknown"
        status_counts[status] += 1

    print(f"\n✔️ Verifier Status:")
    for status, count in sorted(status_counts.items()):
        print(f"  {str(status):15s}: {count:3d}")

    # Files with issues
    print(f"\n📁 Generated Files:")
    files = set(e.get("file_path", "").split("/")[-1] for e in examples)
    for f in sorted(files)[:10]:
        print(f"  • {f}")
    if len(files) > 10:
        print(f"  ... and {len(files) - 10} more")

    # Recommendations
    print(f"\n💡 Recommendations:")
    if all(e.get("is_acceptable") for e in examples):
        print("  ✅ All examples acceptable — dataset quality is good!")
        print("     Next: Collect more examples for diversity")
    else:
        print(f"  ⚠️  {len(unacceptable)} unacceptable examples")
        print("     Review them to improve generation:")
        for ex in unacceptable[:3]:
            print(f"       - {ex.get('file_path', 'unknown')}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
