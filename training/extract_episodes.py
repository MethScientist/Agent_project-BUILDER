"""extract_episodes.py

Simple extractor that builds training examples from runtime traces.
It looks for `output/runtime_trace.json` or `test_run.log` and emits
JSONL lines with the following schema:

{ "user_prompt": ..., "plan": ..., "step": ..., "dependency_context": ..., "generated_code": ..., "verify_result": ..., "quality": {...} }

This is a starting point — adapt to your trace format as needed.
"""
import json
from pathlib import Path
import argparse


def load_runtime_trace(path: Path):
    if not path.exists():
        return []
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
        if isinstance(obj, list):
            return obj
        if isinstance(obj, dict) and obj.get('events'):
            return obj['events']
        return []
    except Exception:
        return []


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--trace', default='output/runtime_trace.json')
    p.add_argument('--out', default='training/data/episodes.jsonl')
    args = p.parse_args()

    trace_path = Path(args.trace)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    events = load_runtime_trace(trace_path)

    # Naive conversion: gather contiguous events that look like steps
    examples = []
    for ev in events:
        try:
            if ev.get('type') == 'step_completed' or ev.get('type') == 'task_completed' or ev.get('type') == 'task_failed':
                # try to find related fields
                ex = {
                    'user_prompt': ev.get('user_prompt') or ev.get('prompt') or '',
                    'plan': ev.get('plan') or ev.get('plan_summary') or None,
                    'step': ev.get('step') or ev.get('description') or None,
                    'target_path': ev.get('target_path') or ev.get('path') or None,
                    'generated_code': ev.get('generated_code') or ev.get('content') or None,
                    'verify_result': ev.get('verify_result') or ev.get('scan_result') or None,
                    'quality': ev.get('quality_report') or ev.get('quality') or None,
                }
                examples.append(ex)
        except Exception:
            continue

    # fallback: if no events, try reading test_run.log for simple patterns
    if not examples and Path('test_run.log').exists():
        txt = Path('test_run.log').read_text(encoding='utf-8', errors='ignore')
        # crude split by lines containing [STEP DONE]
        for line in txt.splitlines():
            if '[STEP DONE]' in line:
                examples.append({'user_prompt': '', 'step': line, 'generated_code': None})

    with out_path.open('w', encoding='utf-8') as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + '\n')

    print(f"Wrote {len(examples)} examples to {out_path}")


if __name__ == '__main__':
    main()
