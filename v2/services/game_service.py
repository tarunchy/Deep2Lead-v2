"""PathoHunt game service — sessions, attacks, scoring."""
import json
import os
from datetime import datetime, timezone

from models.db_models import db
from models.game_models import GameSession, GameAttack
import services.target_service as target_service
import services.molecule_generator as molecule_generator
import services.property_calculator as property_calculator
import services.xp_service as xp_service

_GAME_LEVELS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "game_levels.json")
_game_levels_cache = None


DIFFICULTY_CONFIG = {
    "junior": {
        "win_threshold_override": None,  # use game_levels.json value
        "max_attempts": 999,
        "xp_event": "game_boss_defeated_easy",
        "noise": 0.2,
        "n_molecules": 5,
    },
    "fellow": {
        "win_threshold_override": None,
        "max_attempts": 10,
        "xp_event": "game_boss_defeated_medium",
        "noise": 0.35,
        "n_molecules": 5,
    },
    "pi": {
        "win_threshold_override": None,
        "max_attempts": 5,
        "xp_event": "game_boss_defeated_hard",
        "noise": 0.45,
        "n_molecules": 8,
    },
    "nobel": {
        "win_threshold_override": None,
        "max_attempts": 3,
        "xp_event": "game_boss_defeated_expert",
        "noise": 0.5,
        "n_molecules": 10,
    },
}

LEVEL_BADGE_MAP = {
    "influenza_na": "flu_slayer",
    "covid19_mpro": "covid_crusher",
    "hiv_protease": "hiv_vanquisher",
    "egfr_kinase": "cancer_fighter",
    "braf_v600e": "resistance_breaker",
    "sirt1": "longevity_seeker",
    "cdk2": "cycle_stopper",
}


def _load_game_levels() -> list:
    global _game_levels_cache
    if _game_levels_cache is None:
        with open(_GAME_LEVELS_PATH) as f:
            _game_levels_cache = json.load(f)
    return _game_levels_cache


def _level_meta(target_id: str) -> dict | None:
    return next((lvl for lvl in _load_game_levels() if lvl["target_id"] == target_id), None)


def get_all_bosses() -> list:
    """Return all curated targets that have a game level, merged with game metadata."""
    levels = _load_game_levels()
    level_index = {lvl["target_id"]: lvl for lvl in levels}
    all_targets = target_service.get_curated_targets()
    bosses = []
    for t in all_targets:
        tid = t.get("id")
        if tid in level_index:
            bosses.append({**t, **level_index[tid]})
    bosses.sort(key=lambda b: b.get("game_level", 99))
    return bosses


def get_boss(target_id: str) -> dict | None:
    meta = _level_meta(target_id)
    if not meta:
        return None
    t = target_service.get_curated_target(target_id)
    if not t:
        return None
    return {**t, **meta}


def start_session(user_id, target_id: str, mode: str = "quick_battle", difficulty: str = "junior") -> GameSession:
    meta = _level_meta(target_id)
    if not meta:
        raise ValueError(f"Target '{target_id}' is not a game boss")

    known_score = meta.get("known_drug_score", 0.60)
    boss_initial_hp = round(100.0 - known_score * 100.0, 1)
    win_threshold = meta.get("win_threshold_easy", 0.72)

    session = GameSession(
        user_id=user_id,
        target_id=target_id,
        mode=mode,
        difficulty=difficulty,
        boss_initial_hp=boss_initial_hp,
        boss_current_hp=boss_initial_hp,
        win_threshold=win_threshold,
    )
    db.session.add(session)
    db.session.commit()
    xp_service.award_xp(user_id, "game_battle_started")
    return session


def execute_attack(session_id, smiles: str, user_id) -> dict:
    session = GameSession.query.get(session_id)
    if not session:
        raise ValueError("Session not found")
    if str(session.user_id) != str(user_id):
        raise ValueError("Unauthorised")
    if session.status != "active":
        raise ValueError("Session is not active")

    target = target_service.get_curated_target(session.target_id)
    if not target:
        raise ValueError("Target data missing")

    seed = smiles.strip() if smiles else target.get("starter_smiles", "")
    if not seed:
        raise ValueError("No seed SMILES provided")

    config = DIFFICULTY_CONFIG.get(session.difficulty, DIFFICULTY_CONFIG["junior"])

    # Generate candidate molecules via Gemma4
    gen_result = molecule_generator.generate(
        seed_smile=seed,
        amino_acid_seq=target.get("amino_acid_seq", ""),
        noise=config["noise"],
        n=config["n_molecules"],
    )
    candidates = gen_result.get("smiles", [])
    if not candidates:
        candidates = [seed]

    # Score all candidates, pick best composite
    best_smiles, best_props = _pick_best(candidates, seed)

    # Fallback if all candidates fail scoring
    if best_smiles is None:
        best_smiles = seed
        props = property_calculator.compute_all(seed, seed)
        composite = _compute_composite(props) if props else 0.30
        best_props = {**(props or {}), "composite_score": composite}

    previous_best = session.best_score
    composite = best_props.get("composite_score", 0.0)
    damage = _calculate_damage(composite, previous_best)
    new_hp = max(0.0, round(session.boss_current_hp - damage, 2))

    is_new_best = composite > session.best_score
    if is_new_best:
        session.best_score = composite

    session.boss_current_hp = new_hp
    session.attacks_count += 1

    # Check win/lose
    meta = _level_meta(session.target_id)
    win_threshold = meta.get("win_threshold_easy", 0.72) if meta else 0.72
    won = new_hp <= 0.0 or session.best_score >= win_threshold
    max_attempts = config["max_attempts"]
    lost = not won and session.attacks_count >= max_attempts

    if won:
        session.status = "won"
        session.time_ended = datetime.now(timezone.utc)
        xp_service.award_xp(user_id, config["xp_event"])
        xp_service.award_badge(user_id, "game_first_hunt")
        badge_slug = LEVEL_BADGE_MAP.get(session.target_id)
        if badge_slug:
            xp_service.award_badge(user_id, badge_slug)
    elif lost:
        session.status = "lost"
        session.time_ended = datetime.now(timezone.utc)

    attack = GameAttack(
        session_id=session.id,
        smiles=best_smiles,
        composite_score=composite,
        qed=best_props.get("qed"),
        sas=best_props.get("sas"),
        logp=best_props.get("logp"),
        mw=best_props.get("mw"),
        damage_dealt=damage,
        boss_hp_after=new_hp,
        lipinski_pass=bool(best_props.get("lipinski_pass", False)),
        is_best=is_new_best,
        attack_number=session.attacks_count,
    )
    db.session.add(attack)

    if session.attacks_count == 1:
        xp_service.award_xp(user_id, "game_first_attack")
    if damage > 0:
        xp_service.award_xp(user_id, "game_boss_damaged")

    db.session.commit()

    return {
        "session": session.to_dict(),
        "attack": attack.to_dict(),
        "best_smiles": best_smiles,
        "best_props": best_props,
        "all_candidates": candidates[:5],
        "damage": round(damage, 2),
        "new_hp": new_hp,
        "won": won,
        "lost": lost,
        "is_new_best": is_new_best,
        "latency_ms": gen_result.get("latency_ms", 0),
    }


def get_session_state(session_id, user_id) -> dict | None:
    session = GameSession.query.get(session_id)
    if not session or str(session.user_id) != str(user_id):
        return None
    attacks = [a.to_dict() for a in session.attacks]
    return {"session": session.to_dict(), "attacks": attacks}


def abandon_session(session_id, user_id) -> bool:
    session = GameSession.query.get(session_id)
    if not session or str(session.user_id) != str(user_id):
        return False
    if session.status in ("won", "lost", "abandoned"):
        return False  # already in terminal state
    session.status = "abandoned"
    session.time_ended = datetime.now(timezone.utc)
    db.session.commit()
    return True


def get_history(user_id, limit: int = 20) -> list:
    sessions = (
        GameSession.query.filter_by(user_id=user_id)
        .order_by(GameSession.time_started.desc())
        .limit(limit)
        .all()
    )
    return [s.to_dict() for s in sessions]


# ─── scoring helpers ──────────────────────────────────────────────────────────

def _pick_best(candidates: list, seed: str) -> tuple:
    best_smiles = None
    best_props = None
    for smi in candidates:
        props = property_calculator.compute_all(smi, seed)
        if props is None:
            continue
        composite = _compute_composite(props)
        props["composite_score"] = composite
        if best_props is None or composite > best_props.get("composite_score", 0):
            best_smiles = smi
            best_props = props
    return best_smiles, best_props


def _compute_composite(props: dict | None) -> float:
    if not props:
        return 0.0
    qed = props.get("qed", 0.0)
    sas = props.get("sas", 10.0)
    sas_norm = 1.0 - (sas - 1.0) / 9.0  # 1=easiest → 1.0, 10=hardest → 0.0
    tanimoto = props.get("tanimoto", 0.0)
    lipinski_bonus = 0.10 if props.get("lipinski_pass") else 0.0
    composite = (0.45 * qed) + (0.30 * sas_norm) + (0.15 * tanimoto) + lipinski_bonus
    return round(min(1.0, max(0.0, composite)), 4)


def _calculate_damage(composite: float, previous_best: float) -> float:
    delta = composite - previous_best
    if delta <= 0:
        return 0.0
    return round(min(60.0, delta * 100.0), 2)


def get_candidates(session_id, user_id) -> list:
    session = GameSession.query.get(session_id)
    if not session or str(session.user_id) != str(user_id):
        return []
    target = target_service.get_curated_target(session.target_id)
    if not target:
        return []
    seed = target.get("starter_smiles", "")
    if not seed:
        return []
    candidates = []
    try:
        gen = molecule_generator.generate(seed_smile=seed, amino_acid_seq=target.get("amino_acid_seq",""), noise=0.25, n=3)
        candidates = gen.get("smiles", [])[:3]
    except Exception:
        pass
    if not candidates:
        candidates = [seed]
    result = []
    for smi in candidates[:3]:
        props = property_calculator.compute_all(smi, seed)
        composite = _compute_composite(props) if props else 0.30
        result.append({
            "smiles": smi,
            "name": _mol_codename(smi),
            "composite": round(composite, 3),
            "qed": round(props.get("qed", 0.0) if props else 0.0, 3),
            "sas": round(props.get("sas", 5.0) if props else 5.0, 2),
            "lipinski": bool(props.get("lipinski_pass", False) if props else False),
        })
    return result


def _mol_codename(smiles: str) -> str:
    import hashlib
    h = int(hashlib.md5(smiles.encode()).hexdigest(), 16)
    prefixes = ["CX", "DL", "VK", "MX", "BT", "ZR", "PH", "QL"]
    return f"{prefixes[h % len(prefixes)]}-{(h % 9000) + 1000}"


def validate_novelty(smiles: str) -> dict:
    import requests as _req
    from urllib.parse import quote
    from config.settings import CHEMBL_URL
    try:
        encoded = quote(smiles, safe='')
        url = f"{CHEMBL_URL}/similarity/{encoded}/70.json?limit=3"
        resp = _req.get(url, timeout=15)
        if resp.status_code != 200:
            return {"novel": True, "max_similarity": 0, "hits": [], "reason": "No match found in ChEMBL"}
        data = resp.json()
        molecules = data.get("molecules", [])
        hits = []
        for mol in molecules[:3]:
            hits.append({
                "chembl_id": mol.get("molecule_chembl_id", ""),
                "name": mol.get("pref_name") or mol.get("molecule_chembl_id", "Unknown"),
                "similarity": round(float(mol.get("similarity", 0)), 1),
                "smiles": mol.get("molecule_structures", {}).get("canonical_smiles", "")[:60],
            })
        max_sim = max((h["similarity"] for h in hits), default=0)
        return {
            "novel": max_sim < 80,
            "max_similarity": max_sim,
            "hits": hits,
            "reason": f"{'Potentially novel' if max_sim < 80 else 'Similar to known drug'}: {max_sim}% max similarity"
        }
    except Exception as e:
        return {"novel": True, "max_similarity": 0, "hits": [], "reason": "ChEMBL query failed", "error": str(e)}
