"""train_adapter.py

Fine-tuning adapter using Hugging Face transformers + peft LoRA.
Automatically falls back to lightweight analysis if heavy deps missing.

Usage:
  # Lightweight analysis only (default if no heavy deps)
  python training/train_adapter.py --data training/data/dataset.jsonl --lightweight
  
  # Full LoRA training (requires torch, transformers, peft)
  python training/train_adapter.py --data training/data/dataset.jsonl --epochs 3
"""
import argparse
import json
import sys
from pathlib import Path


def check_deps():
    """Check if heavy ML deps are installed."""
    missing = []
    for pkg in ["torch", "transformers", "peft", "datasets"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    return len(missing) == 0


def load_dataset(path: str):
    """Load JSONL training dataset."""
    examples = []
    with open(path) as f:
        for line in f:
            if line.strip():
                examples.append(json.loads(line))
    return examples


def train_lightweight(dataset_path: str, output_dir: str):
    """
    Lightweight training: analyze dataset and report statistics.
    No GPU/heavy deps required.
    """
    print("📊 Analyzing dataset (lightweight mode)...")

    examples = load_dataset(dataset_path)
    print(f"  ✓ Loaded {len(examples)} examples")

    # Group by quality
    high_quality = [e for e in examples if e.get("quality_score", 0) > 75]
    low_quality = [e for e in examples if e.get("quality_score", 0) <= 75]

    print(f"\n  Quality breakdown:")
    print(f"    High (>75):  {len(high_quality)} examples")
    print(f"    Low (≤75):   {len(low_quality)} examples")

    # Compute statistics
    scores = [e.get("quality_score", 0) for e in examples]
    if scores:
        print(f"\n  Score statistics:")
        print(f"    Min:  {min(scores):.1f}")
        print(f"    Max:  {max(scores):.1f}")
        print(f"    Mean: {sum(scores) / len(scores):.1f}")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    print(f"\n✅ Dataset ready. To enable full training, install:")
    print(f"   pip install torch transformers peft datasets")


def train_lora(
    dataset_path: str,
    output_dir: str,
    base_model: str = "meta-llama/Llama-2-7b-hf",
    num_epochs: int = 3,
    batch_size: int = 2,
):
    """
    Train LoRA adapter on dataset.
    Requires GPU and HuggingFace model access.
    """
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
        from peft import LoraConfig, get_peft_model
        from datasets import Dataset
        import torch
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        sys.exit(1)

    print(f"🚀 Starting LoRA training...")
    print(f"  Base model: {base_model}")
    print(f"  Epochs: {num_epochs}")
    print(f"  Batch size: {batch_size}")

    # Load dataset
    examples = load_dataset(dataset_path)
    print(f"  Dataset: {len(examples)} examples")

    # Create simple dataset format
    texts = []
    labels = []
    for ex in examples:
        text = f"Step: {ex.get('step', '')} File: {ex.get('file_path', '')}"
        label = ex.get("quality_score", 0)
        texts.append(text)
        labels.append(label)

    dataset = Dataset.from_dict({"text": texts, "label": labels})

    # Load model
    print(f"  Loading model {base_model}...")
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForCausalLM.from_pretrained(base_model, load_in_8bit=True, device_map="auto")

    # Apply LoRA
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "v_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora_config)
    print(f"  LoRA applied: {lora_config}")

    # Tokenize
    def tokenize(batch):
        return tokenizer(batch["text"], truncation=True, max_length=512, return_tensors="pt")

    dataset = dataset.map(tokenize, batched=True)

    # Train
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        save_steps=10,
        logging_steps=5,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
    )

    print(f"  Training...")
    trainer.train()
    print(f"✅ Training complete. Model saved to {output_dir}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--data", default="training/data/dataset.jsonl", help="Path to dataset JSONL")
    p.add_argument("--output_dir", default="training/models/agent_adapter", help="Output directory")
    p.add_argument("--base_model", default="meta-llama/Llama-2-7b-hf", help="Base LLM model")
    p.add_argument("--epochs", type=int, default=3, help="Training epochs")
    p.add_argument("--batch_size", type=int, default=2, help="Batch size")
    p.add_argument("--lightweight", action="store_true", help="Analyze only, no training")
    args = p.parse_args()

    data_path = Path(args.data)
    if not data_path.exists():
        print(f"❌ Dataset not found: {data_path}")
        print(f"   Run: python training/build_dataset.py")
        sys.exit(1)

    if args.lightweight or not check_deps():
        train_lightweight(str(data_path), args.output_dir)
    else:
        train_lora(
            str(data_path),
            args.output_dir,
            base_model=args.base_model,
            num_epochs=args.epochs,
            batch_size=args.batch_size,
        )


if __name__ == "__main__":
    main()
