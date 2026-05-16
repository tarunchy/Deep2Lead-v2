import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from config.settings import (
    DGX_BASE_URL, DGX_TIMEOUT,
    FINETUNED_BASE_URL, FINETUNED_TIMEOUT,
    FINETUNED_V2_BASE_URL, FINETUNED_V2_TIMEOUT,
    MAX_RETRY_ATTEMPTS,
)
from services.molecule_validator import filter_candidates
from utils.mol_utils import canonicalize


def _build_prompt(seed_smile: str, amino_acid_seq: str, noise: float, n: int) -> str:
    aa_preview = amino_acid_seq[:80] + ("..." if len(amino_acid_seq) > 80 else "")
    return (
        f"You are a computational chemistry assistant specializing in drug discovery.\n"
        f"Generate novel drug-like SMILES strings structurally similar to the seed molecule.\n\n"
        f"Seed SMILES: {seed_smile}\n"
        f"Target protein (first 80 AA): {aa_preview}\n"
        f"Diversity level: {noise:.2f} (0=minimal change, 1=large structural variation)\n\n"
        f"Rules:\n"
        f"- Output ONLY valid SMILES strings, one per line, no numbering or explanation\n"
        f"- Each molecule must differ from the seed (substitute atoms, add/remove groups)\n"
        f"- Follow Lipinski's Rule of Five: MW<500, LogP<5, HBD<=5, HBA<=10\n"
        f"- Do not repeat molecules\n\n"
        f"Generate exactly {n} SMILES strings:"
    )


def _parse_smiles_from_text(text: str) -> list[str]:
    lines = text.strip().split("\n")
    smiles_pattern = re.compile(r"^[A-Za-z0-9@+\-\[\]()=#$/.\\%]+$")
    candidates = []
    for line in lines:
        line = line.strip().strip(".,;\"'`")
        line = re.sub(r"^\d+[\.\)]\s*", "", line)
        if line and smiles_pattern.match(line):
            candidates.append(line)
    return candidates


def _call_production(prompt: str) -> tuple[str, float]:
    """Call production model (dlyog04:9000, OpenAI-compatible)."""
    t0 = time.time()
    resp = requests.post(
        f"{DGX_BASE_URL}/v1/chat/completions",
        json={
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 512,
            "temperature": 0.8,
        },
        timeout=DGX_TIMEOUT,
    )
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    return text, time.time() - t0


def _call_finetuned(prompt: str) -> tuple[str, float]:
    """Call fine-tuned model v1 (dgx1:9002, FastAPI /v1/text)."""
    t0 = time.time()
    resp = requests.post(
        f"{FINETUNED_BASE_URL}/v1/text",
        json={"prompt": prompt, "temperature": 0.85, "max_new_tokens": 512},
        timeout=FINETUNED_TIMEOUT,
    )
    resp.raise_for_status()
    text = resp.json()["response"]
    return text, time.time() - t0


def _call_finetuned_v2(prompt: str) -> tuple[str, float]:
    """Call fine-tuned model v2 (dgx1:9003, FastAPI /v1/text)."""
    t0 = time.time()
    resp = requests.post(
        f"{FINETUNED_V2_BASE_URL}/v1/text",
        json={"prompt": prompt, "temperature": 0.85, "max_new_tokens": 512},
        timeout=FINETUNED_V2_TIMEOUT,
    )
    resp.raise_for_status()
    text = resp.json()["response"]
    return text, time.time() - t0


def _run_model(caller, prompt: str, canon_seed: str, n: int) -> dict:
    """Run one model, parse and filter results."""
    collected: list[str] = []
    latency_ms = 0
    error = None

    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            raw, elapsed = caller(prompt)
            latency_ms = int(elapsed * 1000)
        except requests.exceptions.RequestException as e:
            if attempt == MAX_RETRY_ATTEMPTS - 1:
                error = str(e)
            continue

        parsed = _parse_smiles_from_text(raw)
        valid = filter_candidates(parsed, canon_seed)
        collected.extend(valid)
        collected = list(dict.fromkeys(collected))
        if len(collected) >= n:
            break

    return {
        "smiles": collected[:n],
        "total_generated": len(collected),
        "latency_ms": latency_ms,
        "error": error,
    }


def generate(
    seed_smile: str,
    amino_acid_seq: str,
    noise: float = 0.5,
    n: int = 10,
    model_backend: str = "production",
) -> dict:
    canon_seed = canonicalize(seed_smile)
    if canon_seed is None:
        raise ValueError("Invalid seed SMILES")

    prompt = _build_prompt(canon_seed, amino_acid_seq, noise, n)
    if model_backend == "finetuned":
        caller = _call_finetuned
    elif model_backend == "finetuned_v2":
        caller = _call_finetuned_v2
    else:
        caller = _call_production
    result = _run_model(caller, prompt, canon_seed, n)

    if result["error"] and not result["smiles"]:
        raise RuntimeError(f"Model API unreachable: {result['error']}")

    return result


def generate_both(
    seed_smile: str,
    amino_acid_seq: str,
    noise: float = 0.5,
    n: int = 10,
) -> dict:
    """Call production and fine-tuned models in parallel."""
    canon_seed = canonicalize(seed_smile)
    if canon_seed is None:
        raise ValueError("Invalid seed SMILES")

    prompt = _build_prompt(canon_seed, amino_acid_seq, noise, n)

    with ThreadPoolExecutor(max_workers=3) as pool:
        fut_prod  = pool.submit(_run_model, _call_production,   prompt, canon_seed, n)
        fut_ft    = pool.submit(_run_model, _call_finetuned,    prompt, canon_seed, n)
        fut_ft_v2 = pool.submit(_run_model, _call_finetuned_v2, prompt, canon_seed, n)
        prod_res  = fut_prod.result()
        ft_res    = fut_ft.result()
        ft_v2_res = fut_ft_v2.result()

    return {"production": prod_res, "finetuned": ft_res, "finetuned_v2": ft_v2_res}


def check_dgx_health() -> bool:
    try:
        resp = requests.get(f"{DGX_BASE_URL}/health", timeout=5)
        return resp.status_code == 200 and resp.json().get("status") == "healthy"
    except Exception:
        return False


def check_finetuned_health() -> bool:
    try:
        resp = requests.get(f"{FINETUNED_BASE_URL}/health", timeout=5)
        return resp.status_code == 200 and resp.json().get("status") in ("ready", "healthy")
    except Exception:
        return False


def check_finetuned_v2_health() -> bool:
    try:
        resp = requests.get(f"{FINETUNED_V2_BASE_URL}/health", timeout=5)
        return resp.status_code == 200 and resp.json().get("status") in ("ready", "healthy")
    except Exception:
        return False
