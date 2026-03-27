# Fine-Tuning Your Agent: Major Steps

This covers both **agent tuning** (prompt/tool/memory/verification) and **model fine-tuning** (training the model). Most teams start with agent tuning, and only fine-tune the model if needed.

## 1) Define Goals
- Specify target behaviors and failure cases.
- Decide metrics: accuracy, format adherence, latency, cost.

## 2) Build a Test Set
- Collect 20–200 real prompts representative of your use cases.
- Create expected outputs or success criteria.

## 3) Establish a Baseline
- Run the agent on the test set.
- Record outputs, errors, and key metrics.

## 4) Improve the Agent (Most Impact)
- Tighten system prompts and output format rules.
- Improve tool usage and guardrails.
- Add context retrieval and relevant project files.
- Add verification checks and auto-fix loops.

## 5) Evaluate and Iterate
- Re-run the test set after each change.
- Track improvements and regressions.

## 6) Decide if Model Fine-Tuning Is Needed
- Only if prompt/tool changes are not enough.
- Requires a dataset of high-quality input→output pairs.

## 7) Prepare Fine-Tune Data (If Needed)
- Curate and clean training examples.
- Ensure consistent structure and formatting.
- Split into train/validation sets.

## 8) Train and Validate
- Train the model with the dataset.
- Validate on held-out data.

## 9) Deploy and Monitor
- Roll out gradually.
- Track drift, failures, and cost.
- Refresh data periodically.

## 10) Continuous Improvement
- Add new examples from real failures.
- Keep test set up to date.

