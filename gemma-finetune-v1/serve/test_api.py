#!/usr/bin/env python3
"""
Quick test for the fine-tuned E2B API from Mac or local machine.
Usage:
    python3 serve/test_api.py [--host dgx1] [--port 9002]
"""

import argparse
import json
import sys
import time

try:
    import requests
except ImportError:
    print("pip install requests")
    sys.exit(1)

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="dgx1")
parser.add_argument("--port", type=int, default=9002)
args = parser.parse_args()

BASE = f"http://{args.host}:{args.port}"

TEST_PROMPTS = [
    "Generate 5 novel drug-like SMILES that inhibit SARS-CoV-2 Main Protease. MW 250-450, QED>0.5.",
    "Generate 3 Influenza Neuraminidase inhibitor candidates inspired by Oseltamivir. Explain each in simple terms.",
    "Generate 4 molecules with MW 200-400, LogP 1-4, QED > 0.5, passing Lipinski rule of 5.",
]


def check_health():
    try:
        r = requests.get(f"{BASE}/health", timeout=5)
        data = r.json()
        print(f"Health: {data.get('status')} | GPU: {data.get('gpu')} | VRAM free: {data.get('vram_free_gb')} GB")
        return data.get("status") == "ready"
    except Exception as e:
        print(f"Health check failed: {e}")
        return False


def run_test(prompt: str):
    payload = {"prompt": prompt, "max_new_tokens": 400, "temperature": 0.8}
    t0 = time.time()
    try:
        r = requests.post(f"{BASE}/v1/text", json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        elapsed = time.time() - t0
        print(f"\n[PROMPT] {prompt[:80]}...")
        print(f"[RESPONSE] {data.get('response', '')[:600]}")
        print(f"[STATS] {data.get('tokens_generated')} tokens | {data.get('tokens_per_second')} tok/s | {elapsed:.1f}s")
    except Exception as e:
        print(f"Request failed: {e}")


if __name__ == "__main__":
    print(f"Testing fine-tuned E2B API at {BASE}\n")
    if not check_health():
        print("Server not ready. Start it first:")
        print("  python3 serve/serve_finetuned.py --port 9002")
        sys.exit(1)

    for prompt in TEST_PROMPTS:
        run_test(prompt)

    print("\nDone.")
