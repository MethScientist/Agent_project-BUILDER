# Training System Ready ✅

Your ML training pipeline is now fully set up. Here's what's in place:

## Architecture

```
User Prompt
    ↓
Planner → Plan
    ↓
StepExecutor → Generate Code
    ↓
Verifier → Check Syntax
    ↓
QualityAssessor → Score 0-100 (TRAINING SIGNAL)
    ↓
Emit quality_assessment event
    ↓
Logs → output/runtime_trace.json
    ↓
build_dataset.py → Extract JSONL
    ↓
training/data/dataset.jsonl ← Training Data
    ↓
train_adapter.py → Fine-tune model
```

## Current Status

✅ **QualityAssessor**: Detects undefined names, stubs, bad imports, bare excepts  
✅ **Integration**: StepExecutor emits quality scores after each file generation  
✅ **Dataset Builder**: `training/build_dataset.py` extracts labeled examples  
✅ **Training Data**: `training/data/dataset.jsonl` (21 examples generated)

## Next Steps

### Option A: Lightweight (No GPU needed)
Just use QualityAssessor to identify bad code during development:

```bash
# Run agent
python test_agent_direct.py

# Extract dataset
python training/build_dataset.py

# Analyze dataset
wc -l training/data/dataset.jsonl
```

### Option B: Real Training (GPU recommended)
Implement fine-tuning with LoRA:

```bash
# Install deps
pip install transformers peft torch accelerate datasets

# Run training
python training/train_adapter.py \
  --data training/data/dataset.jsonl \
  --output_dir training/models/agent_adapter \
  --epochs 3
```

Then integrate trained adapter back into `ai_models/gpt_interface.py`.

---

## Training Loop (How It Improves)

1. **Run agent** → generates code
2. **QualityAssessor scores it** (0-100)
3. **Extract dataset** with quality labels
4. **Fine-tune model** on high-quality examples
5. **Deploy improved model** → agent generates better code
6. **Repeat** → compounding improvements

---

## Metrics to Track

- Average quality score (currently 85.0/100)
- % acceptable outputs (currently 100%)
- Time-to-fix (manual corrections before acceptance)
- Compilation success rate
- Unit test pass rate

---

## Files

- `core/quality_assessor.py` — Semantic quality checks
- `executor/step_executor.py` — Emits quality events
- `training/build_dataset.py` — Extract training examples
- `training/train_adapter.py` — Fine-tuning template
- `training/data/dataset.jsonl` — Your dataset

---

**Ready to train? Start with:**
```bash
python training/build_dataset.py
```

Then decide: lightweight QA-only or real LoRA fine-tuning?
