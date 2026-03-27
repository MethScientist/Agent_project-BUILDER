#!/usr/bin/env python3
"""
training/build_dataset.py

Builds training dataset from agent runs.
Collects episodes with quality labels for fine-tuning.
"""
import json
import sys
from pathlib import Path
from collections import defaultdict


def extract_from_runtime_trace(trace_path: Path):
    """Extract training examples from runtime_trace.json structure."""
    try:
        with open(trace_path) as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to load trace: {e}")
        return []

    examples = []

    # Parse steps structure
    if isinstance(data, dict) and "steps" in data:
        steps_data = data["steps"]
        for step_name, step_info in steps_data.items():
            if not isinstance(step_info, dict):
                continue

            # Extract file information
            files = step_info.get("files", {})
            for file_path, file_data in files.items():
                if not isinstance(file_data, dict):
                    continue

                # Collect what we know
                call_sites = file_data.get("call_sites", [])
                ex = {
                    "step": step_name,
                    "file_path": file_path,
                    "write_count": file_data.get("write_count", 0),
                    "verifier_result": file_data.get("verifier", None),
                    "call_site": call_sites[0] if call_sites else None,
                    "quality_score": None,  # Will be filled if available
                    "is_acceptable": None,
                }

                if ex["write_count"] > 0:
                    examples.append(ex)

    return examples


def extract_from_memory_logs(memory_path: Path):
    """Extract from memory_store.json if it contains quality signals."""
    if not memory_path.exists():
        return []

    try:
        data = json.load(open(memory_path))
        if isinstance(data, dict) and "quality_reports" in data:
            return data["quality_reports"]
    except Exception:
        pass

    return []


def synthesize_training_examples(runtime_examples):
    """
    Create synthetic training examples with quality labels.
    In a real scenario, these would come from actual generated code + quality assessments.
    """
    synthetic = []

    # For each file written, create a training example
    for ex in runtime_examples:
        if ex["write_count"] == 0:
            continue

        # Simulate quality scoring based on verifier result
        if ex["verifier_result"] is None:
            quality_score = 85.0
            is_acceptable = True
        elif ex["verifier_result"] == "error":
            quality_score = 35.0
            is_acceptable = False
        else:
            quality_score = 70.0
            is_acceptable = True

        training_ex = {
            "step": ex["step"],
            "file_path": ex["file_path"],
            "quality_score": quality_score,
            "is_acceptable": is_acceptable,
            "verifier_status": ex["verifier_result"],
            "dataset_split": "train" if quality_score > 60 else "eval",
        }

        synthetic.append(training_ex)

    return synthetic


def main():
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--trace", default="output/runtime_trace.json")
    p.add_argument("--memory", default="memory/memory_store.json")
    p.add_argument("--out", default="training/data/dataset.jsonl")
    args = p.parse_args()

    trace_path = Path(args.trace)
    memory_path = Path(args.memory)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"📊 Building training dataset...")

    # Collect examples from trace
    trace_examples = extract_from_runtime_trace(trace_path)
    print(f"  Found {len(trace_examples)} file writes in trace")

    # Optionally collect from memory
    memory_examples = extract_from_memory_logs(memory_path)
    print(f"  Found {len(memory_examples)} quality reports in memory")

    # Synthesize training examples with quality labels
    training_examples = synthesize_training_examples(trace_examples)
    print(f"  Synthesized {len(training_examples)} training examples")

    # Write JSONL
    with out_path.open("w", encoding="utf-8") as f:
        for ex in training_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"✅ Wrote {len(training_examples)} examples to {out_path}")

    # Show stats
    high_quality = sum(1 for ex in training_examples if ex.get("quality_score", 0) > 75)
    low_quality = len(training_examples) - high_quality
    print(f"\n  Stats:")
    print(f"    High quality (>75): {high_quality}")
    print(f"    Low quality (≤75):  {low_quality}")

    if training_examples:
        print(f"\n  Sample (first example):")
        print(f"    {json.dumps(training_examples[0], indent=6)}")


if __name__ == "__main__":
    main()
