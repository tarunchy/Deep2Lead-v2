import re
import time
import requests
from config.settings import DGX_BASE_URL, DGX_TIMEOUT, MAX_RETRY_ATTEMPTS
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
        # Strip leading numbering like "1.", "1)"
        line = re.sub(r"^\d+[\.\)]\s*", "", line)
        if line and smiles_pattern.match(line):
            candidates.append(line)
    return candidates


def _call_gemma4(prompt: str) -> str:
    resp = requests.post(
        f"{DGX_BASE_URL}/v1/text",
        json={"prompt": prompt, "max_new_tokens": 512, "temperature": 0.8},
        timeout=DGX_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("response", "")


def generate(
    seed_smile: str,
    amino_acid_seq: str,
    noise: float = 0.5,
    n: int = 10,
) -> dict:
    canon_seed = canonicalize(seed_smile)
    if canon_seed is None:
        raise ValueError("Invalid seed SMILES")

    prompt = _build_prompt(canon_seed, amino_acid_seq, noise, n)
    collected: list[str] = []
    latency_ms = 0

    for attempt in range(MAX_RETRY_ATTEMPTS):
        try:
            t0 = time.time()
            raw = _call_gemma4(prompt)
            latency_ms = int((time.time() - t0) * 1000)
        except requests.exceptions.RequestException as e:
            if attempt == MAX_RETRY_ATTEMPTS - 1:
                raise RuntimeError(f"Gemma4 API unreachable: {e}") from e
            continue

        parsed = _parse_smiles_from_text(raw)
        valid = filter_candidates(parsed, canon_seed)
        collected.extend(valid)
        collected = list(dict.fromkeys(collected))  # deduplicate, preserve order
        if len(collected) >= n:
            break

    return {
        "smiles": collected[:n],
        "total_generated": len(collected),
        "latency_ms": latency_ms,
    }


def check_dgx_health() -> bool:
    try:
        resp = requests.get(f"{DGX_BASE_URL}/health", timeout=5)
        return resp.status_code == 200 and resp.json().get("status") == "ready"
    except Exception:
        return False
