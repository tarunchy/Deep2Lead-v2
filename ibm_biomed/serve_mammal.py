#!/usr/bin/env python3
"""
IBM MAMMAL DTI Binding Affinity API — corrected implementation.

Uses the task-specific fine-tuned model:
  ibm/biomed.omics.bl.sm.ma-ted-458m.dti_bindingdb_pkd

Key corrections vs v1:
  - Uses DtiBindingdbKdTask.data_preprocessing() for correct prompt format
  - Uses nn_model.forward_encoder_only() not generate()
  - Uses DtiBindingdbKdTask.process_model_output() for pKd denormalization
  - Output is pKd (higher = stronger binding), mapped to [0,1] score:
      score = min(pKd / 10, 1.0)
      is_binder = pKd >= 7.0  (= Kd/IC50 <= 100 nM)

pKd reference:
  pKd 9 → Kd = 1 nM   (excellent binder)
  pKd 7 → Kd = 100 nM (good binder, our threshold)
  pKd 5 → Kd = 10 µM  (weak binder)
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mammal-api")

PORT       = int(os.getenv("MAMMAL_PORT", "8090"))
MODEL_ID   = "ibm/biomed.omics.bl.sm.ma-ted-458m.dti_bindingdb_pkd"
DEVICE     = "cuda" if torch.cuda.is_available() else "cpu"
MAX_FASTA  = int(os.getenv("MAMMAL_MAX_FASTA", "600"))
MAX_BATCH  = int(os.getenv("MAMMAL_MAX_BATCH", "50"))

# BindingDB Kd normalization constants (from MAMMAL training)
NORM_Y_MEAN = 5.79384684128215
NORM_Y_STD  = 1.33808027428196

# pKd threshold for "is_binder": pKd >= 7.0 = Kd <= 100 nM
PKD_BINDER_THRESHOLD = 7.0

MODEL     = None
TOK       = None
TASK      = None
READY     = False


def _pkd_to_score(pkd: float) -> float:
    """Map pKd to [0,1] score. pKd=7 → 0.70, pKd=10 → 1.0, pKd=5 → 0.50."""
    return min(max(pkd / 10.0, 0.0), 1.0)


def _predict_one(fasta: str, smiles: str) -> dict:
    fasta_trimmed = fasta[:MAX_FASTA]
    sample = {"target_seq": fasta_trimmed, "drug_seq": smiles}

    sample = TASK.data_preprocessing(
        sample_dict=sample,
        tokenizer_op=TOK,
        target_sequence_key="target_seq",
        drug_sequence_key="drug_seq",
        norm_y_mean=None,
        norm_y_std=None,
        device=torch.device(DEVICE),
    )

    batch_dict = MODEL.forward_encoder_only([sample])

    batch_dict = TASK.process_model_output(
        batch_dict,
        scalars_preds_processed_key="model.out.dti_bindingdb_kd",
        norm_y_mean=NORM_Y_MEAN,
        norm_y_std=NORM_Y_STD,
    )

    pkd   = float(batch_dict["model.out.dti_bindingdb_kd"][0])
    score = _pkd_to_score(pkd)
    return {
        "pkd":       round(pkd, 4),
        "score":     round(score, 4),
        "is_binder": pkd >= PKD_BINDER_THRESHOLD,
        "raw_output": f"pKd={pkd:.3f}",
    }


def load_model():
    global MODEL, TOK, TASK, READY
    from mammal.model import Mammal
    from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp
    from mammal.examples.dti_bindingdb_kd.task import DtiBindingdbKdTask

    log.info(f"Loading MAMMAL DTI model: {MODEL_ID}")
    t0 = time.time()

    TOK   = ModularTokenizerOp.from_pretrained(MODEL_ID)
    MODEL = Mammal.from_pretrained(MODEL_ID)
    MODEL.eval()
    MODEL.to(device=torch.device(DEVICE))
    TASK  = DtiBindingdbKdTask

    READY = True
    elapsed  = time.time() - t0
    vram_used = round(torch.cuda.memory_allocated() / 1e9, 2) if DEVICE == "cuda" else 0
    log.info(f"MAMMAL DTI model ready in {elapsed:.1f}s. VRAM used: {vram_used} GB")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    yield


app = FastAPI(
    title="IBM MAMMAL DTI pKd API",
    version="2.0.0",
    description=(
        "Serves ibm/biomed.omics.bl.sm.ma-ted-458m.dti_bindingdb_pkd "
        "for drug-target binding affinity (pKd) prediction."
    ),
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class BindingRequest(BaseModel):
    fasta:  str = Field(..., min_length=5)
    smiles: str = Field(..., min_length=2)


class BindingResponse(BaseModel):
    pkd:        float   # predicted pKd (higher = stronger binding)
    score:      float   # pkd / 10, clamped to [0,1]
    is_binder:  bool    # pkd >= 7.0 (Kd <= 100 nM)
    raw_output: str
    latency_ms: int


class BatchRequest(BaseModel):
    pairs: list[BindingRequest] = Field(..., max_length=MAX_BATCH)


class BatchResponse(BaseModel):
    results:       list[BindingResponse]
    total:         int
    passed_filter: int
    latency_ms:    int


@app.get("/health")
def health():
    vram_free = round(torch.cuda.mem_get_info()[0] / 1e9, 1) if DEVICE == "cuda" else 0
    vram_used = round(torch.cuda.memory_allocated() / 1e9, 1) if DEVICE == "cuda" else 0
    return {
        "status":       "ready" if READY else "loading",
        "model":        MODEL_ID,
        "device":       DEVICE,
        "gpu":          torch.cuda.get_device_name(0) if DEVICE == "cuda" else "none",
        "vram_used_gb": vram_used,
        "vram_free_gb": vram_free,
        "port":         PORT,
        "pkd_threshold": PKD_BINDER_THRESHOLD,
    }


@app.get("/model-info")
def model_info():
    return {
        "model_id":    MODEL_ID,
        "task":        "DTI pKd prediction (BindingDB Kd)",
        "parameters":  "458M",
        "output":      "pKd = -log10(Kd[M])",
        "is_binder_threshold": f"pKd >= {PKD_BINDER_THRESHOLD} (Kd <= 100 nM)",
        "score_mapping": "score = pKd / 10, clamped to [0,1]",
        "norm_y_mean": NORM_Y_MEAN,
        "norm_y_std":  NORM_Y_STD,
        "license":     "Apache 2.0",
        "paper":       "https://arxiv.org/abs/2410.22367",
    }


@app.post("/predict-binding", response_model=BindingResponse)
def predict_binding(req: BindingRequest):
    if not READY:
        raise HTTPException(503, "Model still loading")
    t0 = time.time()
    try:
        result = _predict_one(req.fasta, req.smiles)
    except Exception as e:
        log.error(f"Prediction error: {e}", exc_info=True)
        raise HTTPException(500, f"Prediction failed: {e}")
    return BindingResponse(
        pkd=result["pkd"],
        score=result["score"],
        is_binder=result["is_binder"],
        raw_output=result["raw_output"],
        latency_ms=int((time.time() - t0) * 1000),
    )


@app.post("/predict-batch", response_model=BatchResponse)
def predict_batch(req: BatchRequest):
    if not READY:
        raise HTTPException(503, "Model still loading")

    t0 = time.time()
    results = []
    for pair in req.pairs:
        try:
            r = _predict_one(pair.fasta, pair.smiles)
            results.append(BindingResponse(
                pkd=r["pkd"], score=r["score"],
                is_binder=r["is_binder"], raw_output=r["raw_output"], latency_ms=0,
            ))
        except Exception as e:
            log.warning(f"Pair error (skipping): {e}")
            results.append(BindingResponse(pkd=0.0, score=0.0, is_binder=False,
                                           raw_output="error", latency_ms=0))

    total_ms = int((time.time() - t0) * 1000)
    per_ms   = total_ms // max(len(results), 1)
    for r in results:
        r.latency_ms = per_ms

    return BatchResponse(
        results=results,
        total=len(results),
        passed_filter=sum(1 for r in results if r.is_binder),
        latency_ms=total_ms,
    )


if __name__ == "__main__":
    log.info(f"Starting IBM MAMMAL DTI API on 0.0.0.0:{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
