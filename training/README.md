Training scaffolding for the project-agent

Overview
--------
This folder contains utilities to extract training data from agent runs and to run training pipelines for module-level improvements (planner, code generator, verifier adapter).

Files
-----
- `extract_episodes.py`: scan runtime traces and logs to produce JSONL training examples.
- `train_adapter.py`: example script to fine-tune a model adapter (LoRA) if `transformers`+`peft` are available.
- `train_all.py`: orchestrator that runs extraction then per-module training scripts.

Quick start
-----------
1. Extract episodes:

```bash
python training/extract_episodes.py --out training/data/episodes.jsonl
```

2. Train adapter (requires `transformers`, `peft`):

```bash
python training/train_adapter.py --data training/data/episodes.jsonl --out training/models/adapter
```

Notes
-----
- These scripts are intentionally lightweight and provide a reproducible starting point. They will print helpful instructions if heavy ML dependencies are missing.
- You should review and adapt `extract_episodes.py` to read whichever runtime trace/log format you use (e.g. `output/runtime_trace.json`).
