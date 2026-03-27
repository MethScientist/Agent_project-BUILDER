# ML Training Pipeline: Next Steps

## What We've Built

1. **QualityAssessor** (`core/quality_assessor.py`)
   - Detects undefined names, stubs, fragile patterns
   - Scores code 0-100
   - Emits `quality_assessment` events during step execution

2. **Integration** (`executor/step_executor.py` lines 911-929)
   - After verification, runs quality assessment
   - Emits event with score + issues
   - Events logged to WebSocket and can be captured in traces

3. **Training Scaffold** (`training/`)
   - `extract_episodes.py`: Extract JSONL dataset from traces
   - `train_adapter.py`: Fine-tune model with LoRA (placeholder)
   - `train_all.py`: Orchestrate extraction + training

---

## Quick Start: Generate Training Data (5 min)

### Step 1: Run agent to generate traces with quality scores

```bash
# Run the agent (generates output/runtime_trace.json with quality events)
python test_agent_direct.py 2>&1 | tee test_run.log
```

This will execute the agent and emit `quality_assessment` events.

### Step 2: Extract training episodes

```bash
python training/extract_episodes.py \
  --trace output/runtime_trace.json \
  --out training/data/episodes.jsonl
```

This produces JSONL like:
```json
{"user_prompt": "Build...", "step": "...", "generated_code": "...", "quality_score": 75, ...}
```

### Step 3: Inspect the dataset

```bash
head -3 training/data/episodes.jsonl | python -m json.tool
```

---

## Next: Implement Real Training (Optional Advanced)

If you want to fine-tune a model, fill in `training/train_adapter.py` with:

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from datasets import load_dataset

def train():
    # Load dataset
    dataset = load_dataset("json", data_files="training/data/episodes.jsonl")
    
    # Load base model
    model = AutoModelForCausalLM.from_pretrained("meta-llama/Llama-2-7b")
    tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-2-7b")
    
    # Apply LoRA
    config = LoraConfig(r=16, lora_alpha=32, target_modules=["q_proj", "v_proj"])
    model = get_peft_model(model, config)
    
    # Train on examples with quality_score as signal
    # (Your training loop here)
```

But **start with Step 1-3 above first** to see what training data looks like.

---

## Recommended Flow

1. ✅ Quick test: `python test_quality_assessor.py` (done)
2. ⏭️ **Next**: Run `python test_agent_direct.py` to generate traces
3. Extract: `python training/extract_episodes.py`
4. Inspect: `head training/data/episodes.jsonl`
5. Train (optional): Fill in `training/train_adapter.py` and run

---

## What You'll See

After running the pipeline, you'll have:

```
training/data/episodes.jsonl  ← 100+ training examples like:
{
  "user_prompt": "Create a REST API endpoint",
  "target_path": "api.py",
  "generated_code": "def get_user():\n    return db.query(...)",
  "quality_score": 82,
  "is_acceptable": true,
  "critical_issues": 0,
  "high_issues": 1,
  "issues": [{"type": "undefined_name", "line": 5, "message": "..."}]
}
```

These examples label **good vs bad code**. Train on them to improve the model.

---

**Ready?** Run: `python test_agent_direct.py 2>&1 | tee test_run.log`

That will generate traces. Then extract and inspect the dataset.
