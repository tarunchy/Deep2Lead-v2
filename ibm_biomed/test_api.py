#!/usr/bin/env python3
"""
Test IBM MAMMAL API on dlyog03:8090.
Run from dlyog03 after start.sh:   python test_api.py
Run from dgx1 (same LAN):          python test_api.py --host 192.168.86.20
"""

import argparse
import json
import sys
import time
import requests

parser = argparse.ArgumentParser()
parser.add_argument("--host", default="localhost")
parser.add_argument("--port", type=int, default=8090)
args = parser.parse_args()

BASE = f"http://{args.host}:{args.port}"
print(f"\nTesting MAMMAL API at {BASE}\n{'='*50}")


def check(label: str, ok: bool, detail: str = ""):
    status = "PASS" if ok else "FAIL"
    print(f"  [{status}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


# ── 1. Health check ────────────────────────────────────────────────────────────
print("[1] Health check ...")
try:
    r = requests.get(f"{BASE}/health", timeout=10)
    r.raise_for_status()
    h = r.json()
    check("HTTP 200", True)
    check("Status = ready", h.get("status") == "ready", h.get("status"))
    check("Model ID present", "ibm" in h.get("model", "").lower(), h.get("model"))
    print(f"      GPU: {h.get('gpu')}")
    print(f"      VRAM used: {h.get('vram_used_gb')} GB  free: {h.get('vram_free_gb')} GB")
except Exception as e:
    check("Health endpoint reachable", False, str(e))

# ── 2. Model info ──────────────────────────────────────────────────────────────
print("\n[2] Model info ...")
r = requests.get(f"{BASE}/model-info", timeout=10)
info = r.json()
check("Parameters field", "458M" in info.get("parameters", ""), info.get("parameters"))
print(f"      License: {info.get('license')}")

# ── 3. Single binding prediction — known high-affinity pair ───────────────────
print("\n[3] Single binding prediction (known binder: SARS-CoV-2 MPro + Nirmatrelvir) ...")
t0 = time.time()
r = requests.post(f"{BASE}/predict-binding", json={
    "fasta":  "MESLVPGFNEKTHVQLSLPVLQVRDVLVRGFGDSVEEVLSEARQHLKDAGVNKEVPKGIYYVGENLRLNKKEGLEQLEKELAEK",
    "smiles": "CC1(C2CC2NC(=O)C(F)(F)F)C(=O)N[C@@H](Cc2ccc(C#N)cc2)C1=O",
}, timeout=120)
r.raise_for_status()
result = r.json()
elapsed = time.time() - t0
check("Score in [0,1]", 0.0 <= result["score"] <= 1.0, f"score={result['score']:.3f}")
print(f"      Score: {result['score']:.3f}  is_binder: {result['is_binder']}  raw: '{result['raw_output']}'")
print(f"      Latency: {elapsed:.2f}s")

# ── 4. Single prediction — known non-binder (random scaffold) ─────────────────
print("\n[4] Single binding prediction (random non-drug SMILES) ...")
r = requests.post(f"{BASE}/predict-binding", json={
    "fasta":  "MESLVPGFNEKTHVQLSLPVLQVRDVLVRGFGDSVEEVLSEARQHLKDAGVNKEVPKGIYYVGENLRLNKKEGLEQLEKELAEK",
    "smiles": "CCCCCCCCCC",   # decane — no drug-like features
}, timeout=120)
result2 = r.json()
check("Score in [0,1]", 0.0 <= result2["score"] <= 1.0, f"score={result2['score']:.3f}")
print(f"      Score: {result2['score']:.3f}  is_binder: {result2['is_binder']}  raw: '{result2['raw_output']}'")

# ── 5. Batch prediction ────────────────────────────────────────────────────────
print("\n[5] Batch prediction (3 pairs) ...")
fasta = "MESLVPGFNEKTHVQLSLPVLQVRDVLVRGFGDSVEEVLSEARQHLK"
batch_payload = {
    "pairs": [
        {"fasta": fasta, "smiles": "CC1(C2CC2NC(=O)C(F)(F)F)C(=O)N[C@@H](Cc2ccc(C#N)cc2)C1=O"},
        {"fasta": fasta, "smiles": "CC(C)Cc1ccc(cc1)[C@@H](C)C(=O)O"},   # Ibuprofen
        {"fasta": fasta, "smiles": "CC(=O)Oc1ccccc1C(=O)O"},              # Aspirin
    ]
}
t0 = time.time()
r = requests.post(f"{BASE}/predict-batch", json=batch_payload, timeout=300)
r.raise_for_status()
batch = r.json()
elapsed = time.time() - t0
check("Returned 3 results", batch["total"] == 3, f"got {batch['total']}")
print(f"      Passed filter: {batch['passed_filter']}/3")
for i, res in enumerate(batch["results"]):
    print(f"      Pair {i+1}: score={res['score']:.3f}  is_binder={res['is_binder']}")
print(f"      Batch latency: {elapsed:.2f}s")

# ── Summary ────────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(" All tests PASSED. MAMMAL API is ready for use by dgx1.")
print(f" Call from dgx1: http://192.168.86.20:{args.port}/predict-binding")
print(f"{'='*50}\n")
