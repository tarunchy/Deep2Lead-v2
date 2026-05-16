#!/usr/bin/env python3
"""
FastAPI server for the v2 fine-tuned Gemma4-E2B drug discovery model.
Port: 9003  (v1 fine-tune runs at 9002, production at 9001)

Key v2 changes vs serve_finetuned.py (v1):
  - Port 9003
  - Model path points to v2 adapter (gemma4_e2b_drug_v2)
  - System prompt enforces rationale-first output format
  - Default temperature=0.85, repetition_penalty=1.3

Usage:
    python3 serve/serve_v2.py [--port 9003] [--model-path ./drug_discovery/lora/gemma4_e2b_drug_v2]
"""

import argparse
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Optional

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import MAX_SEQ_LENGTH, OUTPUT_DIR, FINETUNED_API_PORT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("gemma4-drug-api-v2")

parser = argparse.ArgumentParser()
parser.add_argument("--port",       type=int, default=FINETUNED_API_PORT)
parser.add_argument("--host",       default="0.0.0.0")
parser.add_argument("--model-path", default=OUTPUT_DIR)
args, _ = parser.parse_known_args()

MODEL     = None
PROCESSOR = None
READY     = False

SYSTEM_PROMPT_V2 = (
    "You are Deep2Lead's drug discovery AI v2. When given a protein target or biological context, "
    "first reason about the binding pocket geometry, key residues, and desired physicochemical profile "
    "(2-3 sentences labelled 'Rationale:'), then output novel drug-like SMILES molecules labelled 'SMILES:'. "
    "Explain choices in plain English suitable for high school students."
)


def load_model():
    global MODEL, PROCESSOR, READY
    from unsloth import FastModel

    log.info(f"Loading v2 fine-tuned model from: {args.model_path}")
    MODEL, PROCESSOR = FastModel.from_pretrained(
        model_name=args.model_path,
        max_seq_length=MAX_SEQ_LENGTH,
        load_in_4bit=True,
        dtype=None,
        full_finetuning=False,
    )
    FastModel.for_inference(MODEL)
    READY = True
    free_gb = torch.cuda.mem_get_info()[0] / 1e9 if torch.cuda.is_available() else 0
    log.info(f"v2 fine-tuned model ready. VRAM free: {free_gb:.1f} GB")


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model()
    yield


app = FastAPI(
    title="Deep2Lead Drug Discovery API (Fine-tuned Gemma4-E2B v2)",
    version="2.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class TextRequest(BaseModel):
    prompt: str
    system: Optional[str] = None
    max_new_tokens: int = 512
    temperature: float = 0.85
    top_p: float = 0.92
    top_k: int = 50
    repetition_penalty: float = 1.3


class GenerateResponse(BaseModel):
    response: str
    tokens_generated: int
    time_seconds: float
    tokens_per_second: float
    model: str = "gemma4-e2b-drug-v2"


@app.get("/health")
def health():
    return {
        "status":       "ready" if READY else "loading",
        "model":        args.model_path,
        "version":      "v2",
        "port":         args.port,
        "gpu":          torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none",
        "vram_free_gb": round(torch.cuda.mem_get_info()[0] / 1e9, 1) if torch.cuda.is_available() else 0,
    }


@app.get("/v1/params")
def generation_params():
    """Return current default generation parameters."""
    defaults = TextRequest.model_fields
    return {k: v.default for k, v in defaults.items() if k not in ("prompt", "system")}


@app.post("/v1/text", response_model=GenerateResponse)
def generate_text(req: TextRequest):
    if not READY:
        raise HTTPException(503, "Model still loading")

    system = req.system or SYSTEM_PROMPT_V2
    messages = [
        {"role": "system",    "content": [{"type": "text", "text": system}]},
        {"role": "user",      "content": [{"type": "text", "text": req.prompt}]},
    ]

    inputs = PROCESSOR.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=True,
        return_dict=True,
        return_tensors="pt",
    ).to("cuda")

    input_len = inputs["input_ids"].shape[-1]
    t0 = time.time()

    with torch.no_grad():
        outputs = MODEL.generate(
            **inputs,
            max_new_tokens=req.max_new_tokens,
            do_sample=True,
            temperature=req.temperature,
            top_p=req.top_p,
            top_k=req.top_k,
            repetition_penalty=req.repetition_penalty,
            use_cache=True,
        )

    generated = outputs[0][input_len:]
    response  = PROCESSOR.decode(generated, skip_special_tokens=True).strip()
    elapsed   = time.time() - t0
    n_tokens  = len(generated)

    return GenerateResponse(
        response=response,
        tokens_generated=n_tokens,
        time_seconds=round(elapsed, 2),
        tokens_per_second=round(n_tokens / max(elapsed, 0.001), 1),
    )


@app.post("/v1/generate")
def generate_compat(req: TextRequest):
    """Mirror v1 API shape for zero-code-change comparisons."""
    return generate_text(req)


if __name__ == "__main__":
    log.info(f"Starting v2 Gemma4-E2B API on {args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
