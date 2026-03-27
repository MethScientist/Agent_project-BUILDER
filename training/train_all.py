"""train_all.py

Orchestrator to run extraction and module-level training scripts.
This is a thin wrapper to run the other utilities in this folder.
"""
import subprocess
import sys
from pathlib import Path


def run(cmd):
    print(f"$ {cmd}")
    rc = subprocess.call(cmd, shell=True)
    if rc != 0:
        print(f"Command failed: {cmd}")
        sys.exit(rc)


def main():
    data_out = 'training/data/episodes.jsonl'
    Path('training/data').mkdir(parents=True, exist_ok=True)

    run(f"python training/extract_episodes.py --out {data_out}")
    run(f"python training/train_adapter.py --data {data_out} --out training/models/adapter")


if __name__ == '__main__':
    main()
