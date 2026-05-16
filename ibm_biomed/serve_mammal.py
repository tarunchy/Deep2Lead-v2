#!/usr/bin/env python3
"""
IBM MAMMAL DTI Binding Affinity API
Serves ibm/biomed.omics.bl.sm.ma-ted-458m on dlyog03 port 8090.

Endpoints:
  GET  /health              — status + GPU info
  GET  /model-info          — model card summary
  POST /predict-binding     — single (fasta, smiles) → score
  POST /predict-batch       — list of pairs → list of scores (max 100 per call)

Called by dgx1 during Gemma v2 training data filtering.
Model: 458M params, ~2GB VRAM on RTX 3060 Ti (float32) or ~1GB (float16)
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("mammal-api")

PORT      = int(os.getenv("MAMMAL_PORT", "8090"))
MODEL_ID  = os.getenv("MAMMAL_MODEL_ID", "ibm/biomed.omics.bl.sm.ma-ted-458m")
DEVICE    = "cuda" if torch.cuda.is_available() else "cpu"
MAX_FASTA = int(os.getenv("MAMMAL_MAX_FASTA", "600"))   # cap for VRAM safety
MAX_BATCH = int(os.getenv("MAMMAL_MAX_BATCH", "100"))

MODEL   = None
TOK     = None
READY   = False


def _build_dti_prompt(fasta: str, smiles: str) -> str:
    """Build MAMMAL DTI encoder prompt string."""
    return (
        f"<@TOKENIZER-TYPE=AA><BINDING_AFFINITY_CLASS><SENTINEL_ID_0>"
        f"<MOLECULAR_ENTITY><MOLECULAR_ENTITY_GENERAL_PROTEIN>"
        f"<SEQUENCE_NATURAL_START>{fasta}<SEQUENCE_NATURAL_END>"
        f"<MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
        f"<SEQUENCE_NATURAL_START>{smiles}<SEQUENCE_NATURAL_END><EOS>"
    )


def _decode_score(raw: str) -> float:
    """
    Convert MAMMAL raw output to a float score in [0, 1].
    MAMMAL outputs vary by task version — handle both numeric and label forms.
    """
    text = raw.strip().lower()
    # Numeric probability output (ideal)
    try:
        val = float(text)
        return max(0.0, min(1.0, val))
    except ValueError:
        pass
    # Class label output
    if any(k in text for k in ("high", "active", "binder", "1", "positive")):
        return 0.85
    if any(k in text for k in ("low", "inactive", "non", "0", "negative")):
        return 0.20
    # Unknown — conservative middle score
    log.warning(f"Unknown MAMMAL output: '{raw}' — returning 0.50")
    return 0.50


def _predict_one(fasta: str, smiles: str) -> dict:
    from mammal.keys import (
        ENCODER_INPUTS_STR, ENCODER_INPUTS_TOKENS,
        ENCODER_INPUTS_ATTENTION_MASK, CLS_PRED,
    )
    fasta_trimmed = fasta[:MAX_FASTA]
    prompt        = _build_dti_prompt(fasta_trimmed, smiles)

    sample = {ENCODER_INPUTS_STR: prompt}
    TOK(
        sample_dict=sample,
        key_in=ENCODER_INPUTS_STR,
        key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
        key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK,
    )
    sample[ENCODER_INPUTS_TOKENS]         = torch.tensor(sample[ENCODER_INPUTS_TOKENS]).to(DEVICE)
    sample[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sample[ENCODER_INPUTS_ATTENTION_MASK]).to(DEVICE)

    with torch.no_grad():
        batch = MODEL.generate(
            [sample],
            output_scores=True,
            return_dict_in_generate=True,
            max_new_tokens=5,
        )

    raw   = TOK._tokenizer.decode(batch[CLS_PRED][0])
    score = _decode_score(raw)
    return {"score": score, "raw_output": raw.strip(), "is_binder": score >= 0.70}


def load_model():
    global MODEL, TOK, READY
    log.info(f"Loading IBM MAMMAL from '{MODEL_ID}' on {DEVICE} ...")
    t0 = time.time()

    from mammal.model import Mammal
    from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp

    MODEL = Mammal.from_pretrained(MODEL_ID)
    MODEL.eval()
    if DEVICE == "cuda":
        MODEL = MODEL.cuda()

    TOK = ModularTokenizerOp.from_pretrained(MODEL_ID)

    READY = True
    elapsed = time.time() - t0
    vram_used = round(torch.cuda.memory_allocated() / 1e9, 2) if DEVICE == "cuda" else 0
    log.info(f"MAMMAL ready in {elapsed:.1f}s. VRAM used: {vram_used} GB")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    yield


app = FastAPI(
    title="IBM MAMMAL DTI Binding Affinity API",
    version="1.0.0",
    description="Serves ibm/biomed.omics.bl.sm.ma-ted-458m for drug-target interaction scoring.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ──────────────────────────────────────────────────

class BindingRequest(BaseModel):
    fasta:  str = Field(..., min_length=5,  description="Protein sequence (amino acids)")
    smiles: str = Field(..., min_length=2,  description="Small molecule SMILES string")


class BindingResponse(BaseModel):
    score:      float   # affinity probability [0, 1]
    is_binder:  bool    # score >= 0.70
    raw_output: str     # raw model token string
    latency_ms: int


class BatchRequest(BaseModel):
    pairs: list[BindingRequest] = Field(..., max_length=MAX_BATCH)


class BatchResponse(BaseModel):
    results:        list[BindingResponse]
    total:          int
    passed_filter:  int   # count with is_binder=True
    latency_ms:     int


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    vram_free = round(torch.cuda.mem_get_info()[0] / 1e9, 1) if DEVICE == "cuda" else 0
    vram_used = round(torch.cuda.memory_allocated() / 1e9, 1) if DEVICE == "cuda" else 0
    return {
        "status":    "ready" if READY else "loading",
        "model":     MODEL_ID,
        "device":    DEVICE,
        "gpu":       torch.cuda.get_device_name(0) if DEVICE == "cuda" else "none",
        "vram_used_gb": vram_used,
        "vram_free_gb": vram_free,
        "port":      PORT,
    }


@app.get("/model-info")
def model_info():
    return {
        "model_id":    MODEL_ID,
        "parameters":  "458M",
        "architecture": "MAMMAL (encoder-decoder, multimodal)",
        "tasks":        ["DTI", "protein-protein binding", "molecular property prediction"],
        "license":      "Apache 2.0",
        "paper":        "https://arxiv.org/abs/2410.22367",
        "threshold_recommendation": 0.70,
    }


@app.post("/predict-binding", response_model=BindingResponse)
def predict_binding(req: BindingRequest):
    if not READY:
        raise HTTPException(503, "Model still loading")
    t0 = time.time()
    try:
        result = _predict_one(req.fasta, req.smiles)
    except Exception as e:
        log.error(f"Prediction error: {e}")
        raise HTTPException(500, f"Prediction failed: {e}")
    return BindingResponse(
        score=result["score"],
        is_binder=result["is_binder"],
        raw_output=result["raw_output"],
        latency_ms=int((time.time() - t0) * 1000),
    )


@app.post("/predict-batch", response_model=BatchResponse)
def predict_batch(req: BatchRequest):
    if not READY:
        raise HTTPException(503, "Model still loading")
    if len(req.pairs) > MAX_BATCH:
        raise HTTPException(400, f"Max {MAX_BATCH} pairs per batch request")

    t0 = time.time()
    results = []
    for pair in req.pairs:
        try:
            r = _predict_one(pair.fasta, pair.smiles)
            results.append(BindingResponse(
                score=r["score"],
                is_binder=r["is_binder"],
                raw_output=r["raw_output"],
                latency_ms=0,
            ))
        except Exception as e:
            log.warning(f"Pair prediction error (skipping): {e}")
            results.append(BindingResponse(score=0.0, is_binder=False, raw_output="error", latency_ms=0))

    total_ms = int((time.time() - t0) * 1000)
    for r in results:
        r.latency_ms = total_ms // max(len(results), 1)

    return BatchResponse(
        results=results,
        total=len(results),
        passed_filter=sum(1 for r in results if r.is_binder),
        latency_ms=total_ms,
    )


if __name__ == "__main__":
    log.info(f"Starting IBM MAMMAL API on 0.0.0.0:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
