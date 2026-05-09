"""
Phase 1 DTI predictor — heuristic scoring.
Phase 2 will replace this with ESM-2 + ECFP MLP (see scripts/train_dti.py).
"""


def predict(props: dict, amino_acid_seq: str) -> float:
    """Return a heuristic DTI binding probability in [0, 1]."""
    score = 0.0

    # QED contribution (drug-likeness proxy)
    score += 0.35 * props.get("qed", 0.0)

    # Lipinski compliance
    score += 0.25 if props.get("lipinski_pass", False) else 0.0

    # LogP preference: penalize extremes (ideal 1–3)
    logp = props.get("logp", 0.0)
    if 0.0 <= logp <= 3.0:
        score += 0.20
    elif -1.0 <= logp < 0.0 or 3.0 < logp <= 5.0:
        score += 0.10

    # SAS contribution (easier synthesis → more likely to be known-active)
    sas = props.get("sas", 10.0)
    score += 0.20 * max(0.0, (10.0 - sas) / 9.0)

    return round(min(1.0, max(0.0, score)), 4)


def composite_score(props: dict, dti: float) -> float:
    from config.settings import SCORE_WEIGHTS as W
    qed = props.get("qed", 0.0)
    sas = props.get("sas", 10.0)
    tanimoto = props.get("tanimoto", 0.0)
    sas_norm = max(0.0, (10.0 - sas) / 9.0)
    return round(
        W["dti"] * dti
        + W["qed"] * qed
        + W["sas"] * sas_norm
        + W["tanimoto"] * tanimoto,
        4,
    )
