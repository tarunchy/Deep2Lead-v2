"""PathoHunt game service — sessions, attacks, scoring."""
import json
import os
import random
from datetime import datetime, timezone

from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.DataStructs import TanimotoSimilarity

from models.db_models import db, Experiment, Candidate
from models.game_models import GameSession, GameAttack
from models.game_progression import GameLeaderboard
import services.target_service as target_service
import services.molecule_generator as molecule_generator
import services.property_calculator as property_calculator
import services.xp_service as xp_service
import services.lab_service as lab_service

_GAME_LEVELS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "game_levels.json")
_game_levels_cache = None


DIFFICULTY_CONFIG = {
    "junior": {
        "win_threshold_override": None,
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

# Tracks first-win per target across process lifetime; augmented by DB check at runtime
_first_defeats_cache: set = set()


def _load_game_levels() -> list:
    global _game_levels_cache
    if _game_levels_cache is None:
        with open(_GAME_LEVELS_PATH) as f:
            _game_levels_cache = json.load(f)
    return _game_levels_cache


def _level_meta(target_id: str) -> dict | None:
    return next((lvl for lvl in _load_game_levels() if lvl["target_id"] == target_id), None)


def get_all_bosses() -> list:
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

    boss_initial_hp = 300.0
    known_score = meta.get("known_drug_score", 0.60)
    win_threshold = round(known_score + 0.05, 4)  # discovery: beat known drug by 5%

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
        if session.status in ("won", "lost"):
            return _completed_session_response(session)
        raise ValueError("Session is not active")

    target = target_service.get_curated_target(session.target_id)
    if not target:
        raise ValueError("Target data missing")

    meta = _level_meta(session.target_id)
    user_upgrade_slugs = {u["upgrade_slug"] for u in lab_service.get_user_upgrades(user_id)}

    seed = smiles.strip() if smiles else target.get("starter_smiles", "")
    if not seed:
        raise ValueError("No seed SMILES provided")

    config = DIFFICULTY_CONFIG.get(session.difficulty, DIFFICULTY_CONFIG["junior"])

    gen_result = molecule_generator.generate(
        seed_smile=seed,
        amino_acid_seq=target.get("amino_acid_seq", ""),
        noise=config["noise"],
        n=config["n_molecules"],
    )
    candidates = gen_result.get("smiles", [])
    if not candidates:
        candidates = [seed]

    best_smiles, best_props = _pick_best(candidates, seed)

    if best_smiles is None:
        best_smiles = seed
        props = property_calculator.compute_all(seed, seed)
        composite = _compute_composite(props) if props else 0.30
        best_props = {**(props or {}), "composite_score": composite}

    # Re-read and lock the session before mutating combat state. Molecule
    # generation can be slow; holding the DB lock across the LLM call would
    # serialize users unnecessarily, but the final state update must be atomic.
    session = (
        GameSession.query.filter_by(id=session.id)
        .with_for_update()
        .populate_existing()
        .first()
    )
    if not session:
        raise ValueError("Session not found")
    if str(session.user_id) != str(user_id):
        raise ValueError("Unauthorised")
    if session.status != "active":
        if session.status in ("won", "lost"):
            return _completed_session_response(session, meta)
        raise ValueError("Session is not active")

    # Safety net: swap seed on persistent poor performance
    safety_net_threshold = 0.40
    if "lucky_seed" in user_upgrade_slugs:
        for up in lab_service.get_user_upgrades(user_id):
            if up["upgrade_slug"] == "lucky_seed" and up.get("upgrade"):
                safety_net_threshold = up["upgrade"]["effect_value"]
                break

    composite = best_props.get("composite_score", 0.0)
    if session.bad_streak >= 3 and composite < safety_net_threshold:
        fallback_seed = meta.get("starter_smiles", "") if meta else ""
        if fallback_seed and fallback_seed != seed:
            fallback_props = property_calculator.compute_all(fallback_seed, fallback_seed)
            if fallback_props:
                fallback_composite = _compute_composite(fallback_props)
                fallback_props["composite_score"] = fallback_composite
                best_smiles = fallback_seed
                best_props = fallback_props
                composite = fallback_composite

    composite = best_props.get("composite_score", 0.0)

    # Boss memory penalty
    memory_penalty = False
    memory_smiles = lab_service.get_boss_memory(session.target_id)
    if memory_smiles and best_smiles:
        max_tanimoto = _max_tanimoto(best_smiles, memory_smiles)
        if max_tanimoto > 0.6 and "memory_serum" not in user_upgrade_slugs:
            composite *= 0.75
            best_props["composite_score"] = round(composite, 4)
            memory_penalty = True

    # Update bad_streak
    if composite >= 0.40:
        session.bad_streak = 0
    else:
        session.bad_streak += 1

    active_mutations = session.active_mutations or []
    previous_best = session.best_score
    damage = _calculate_damage(composite, previous_best, active_mutations, best_props)

    new_hp = max(0.0, round(session.boss_current_hp - damage, 2))

    is_new_best = composite > session.best_score
    if is_new_best:
        session.best_score = composite

    session.boss_current_hp = new_hp
    session.attacks_count += 1

    # Boss phase transition check
    hp_pct = new_hp / session.boss_initial_hp if session.boss_initial_hp > 0 else 0
    phase_changed = False
    new_mutation = None
    old_phase = session.phase

    if hp_pct <= 0.30 and old_phase < 2:
        session.phase = 2
        phase_changed = True
    elif hp_pct <= 0.60 and old_phase < 1:
        session.phase = 1
        phase_changed = True

    if phase_changed and meta and meta.get("mutation_pool"):
        existing_ids = {m.get("id") for m in active_mutations} if active_mutations else set()
        pool = [m for m in meta["mutation_pool"] if m.get("id") not in existing_ids]
        if pool:
            new_mutation = random.choice(pool)
            updated_mutations = list(active_mutations) + [new_mutation]
            session.active_mutations = updated_mutations

    # Discovery win: one molecule that beats the known drug by ≥5%
    known_score = meta.get("known_drug_score", 0.60) if meta else 0.60
    discovery_threshold = round(known_score + 0.05, 4)
    won = composite >= discovery_threshold
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

        # RP awards on win
        lab_service.award_rp(user_id, 50)
        first_defeat_key = f"{user_id}:{session.target_id}"
        is_first_defeat = first_defeat_key not in _first_defeats_cache
        if is_first_defeat:
            prior_wins = GameLeaderboard.query.filter_by(
                target_id=session.target_id, user_id=user_id
            ).count()
            if prior_wins == 0:
                lab_service.award_rp(user_id, 100)
                _first_defeats_cache.add(first_defeat_key)

        # Upsert leaderboard — keep only best score per user per target
        existing_entry = GameLeaderboard.query.filter_by(
            target_id=session.target_id, user_id=user_id
        ).order_by(GameLeaderboard.composite_score.desc()).first()
        if existing_entry is None or session.best_score > existing_entry.composite_score:
            if existing_entry:
                db.session.delete(existing_entry)
            lb = GameLeaderboard(
                target_id=session.target_id,
                user_id=user_id,
                mol_name=_mol_codename(best_smiles),
                smiles=best_smiles,
                composite_score=session.best_score,
                attacks_count=session.attacks_count,
                won_at=datetime.now(timezone.utc),
            )
            db.session.add(lb)

    elif lost:
        session.status = "lost"
        session.time_ended = datetime.now(timezone.utc)

    # RP per attack
    lab_service.award_rp(user_id, 5)

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

    # Record in boss memory
    lab_service.save_boss_memory(session.target_id, [best_smiles], damage)

    db.session.commit()

    # Build phase taunt if transition just happened
    phase_taunt = None
    if phase_changed and meta:
        if session.phase == 1:
            phase_taunt = meta.get("phase2_taunt")
        elif session.phase == 2:
            phase_taunt = meta.get("phase3_taunt")

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
        "phase_changed": phase_changed,
        "new_mutation": new_mutation,
        "phase_taunt": phase_taunt,
        "memory_penalty": memory_penalty,
        "known_score": known_score,
        "discovery_threshold": discovery_threshold,
    }


def _completed_session_response(session: GameSession, meta: dict | None = None) -> dict:
    """Return final session state without treating a repeated attack as an API error."""
    if meta is None:
        meta = _level_meta(session.target_id)

    best_attack = (
        GameAttack.query.filter_by(session_id=session.id)
        .order_by(GameAttack.composite_score.desc(), GameAttack.created_at.desc())
        .first()
    )

    best_props = {}
    if best_attack:
        best_props = {
            "qed": best_attack.qed,
            "sas": best_attack.sas,
            "logp": best_attack.logp,
            "mw": best_attack.mw,
            "lipinski_pass": best_attack.lipinski_pass,
            "composite_score": best_attack.composite_score,
        }

    known_score = meta.get("known_drug_score", 0.60) if meta else 0.60
    status = session.status
    return {
        "code": "SESSION_ALREADY_WON" if status == "won" else "SESSION_ALREADY_LOST",
        "message": f"Session already {status}",
        "session": session.to_dict(),
        "attack": best_attack.to_dict() if best_attack else None,
        "best_smiles": best_attack.smiles if best_attack else None,
        "best_props": best_props,
        "all_candidates": [],
        "damage": 0.0,
        "new_hp": session.boss_current_hp,
        "won": status == "won",
        "lost": status == "lost",
        "is_new_best": False,
        "latency_ms": 0,
        "phase_changed": False,
        "new_mutation": None,
        "phase_taunt": None,
        "memory_penalty": False,
        "known_score": known_score,
        "discovery_threshold": session.win_threshold,
    }


def design_molecule(prompt: str = "", blocks: list = None, target_id: str = "") -> dict:
    import json as _json
    import re as _re
    from services.molecule_generator import _call_gemma4
    from utils.mol_utils import canonicalize
    from services.property_calculator import compute_all

    boss_context = ""
    if target_id:
        meta = _level_meta(target_id)
        if meta:
            boss_context = f" Target protein: {meta.get('name', target_id)}."

    if blocks:
        block_str = ", ".join(blocks)
        user_content = (
            f"Assemble a valid drug-like SMILES molecule using these chemical building blocks: {block_str}.{boss_context} "
            f"Follow Lipinski's Rule of Five (MW<500, LogP<5, HBD<=5, HBA<=10). "
            f"Return ONLY a JSON object on one line with exactly these fields: "
            f'{{\"smiles\": \"<valid SMILES>\", \"name\": \"<2-3 word codename>\", \"explanation\": \"<one sentence>\"}}'
        )
    else:
        user_content = (
            f"Design a valid drug-like molecule: {prompt}.{boss_context} "
            f"Follow Lipinski's Rule of Five. "
            f"Return ONLY a JSON object on one line with exactly these fields: "
            f'{{\"smiles\": \"<valid SMILES>\", \"name\": \"<2-3 word codename>\", \"explanation\": \"<one sentence>\"}}'
        )

    raw = _call_gemma4(user_content)

    smiles, name, explanation = None, "CUSTOM-001", "AI-designed molecule"
    json_match = _re.search(r'\{[^}]+\}', raw, _re.DOTALL)
    if json_match:
        try:
            obj = _json.loads(json_match.group())
            smiles = obj.get("smiles", "").strip()
            name = obj.get("name", name).strip()
            explanation = obj.get("explanation", explanation).strip()
        except Exception:
            pass

    if not smiles:
        for line in raw.split("\n"):
            line = line.strip().strip('"\'')
            import re as _r
            if _r.match(r'^[A-Za-z0-9@+\-\[\]()=#$/.\\%]{6,}$', line):
                smiles = line
                break

    canonical = canonicalize(smiles) if smiles else None
    if not canonical:
        raise ValueError("Could not generate a valid SMILES. Try a different description.")

    props = compute_all(canonical, canonical) or {}
    composite = (
        0.45 * props.get("qed", 0)
        + 0.30 * max(0, 1.0 - (props.get("sas", 5) - 1) / 9)
        + 0.15 * props.get("tanimoto", 0)
        + (0.10 if props.get("lipinski_pass") else 0)
    )
    props["composite_score"] = round(min(1.0, max(0.0, composite)), 4)

    return {
        "smiles": canonical,
        "name": name,
        "explanation": explanation,
        "props": props,
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
        return False
    session.status = "abandoned"
    session.time_ended = datetime.now(timezone.utc)
    db.session.commit()
    return True


def get_history(user_id, limit: int = 50) -> list:
    sessions = (
        GameSession.query.filter_by(user_id=user_id)
        .order_by(GameSession.time_started.desc())
        .limit(limit)
        .all()
    )
    results = []
    for s in sessions:
        d = s.to_dict()
        best_attack = (
            GameAttack.query.filter_by(session_id=s.id, is_best=True)
            .order_by(GameAttack.composite_score.desc())
            .first()
        )
        d["best_attack"] = best_attack.to_dict() if best_attack else None
        boss = get_boss(s.target_id)
        d["boss_name"] = boss.get("name", s.target_id) if boss else s.target_id
        d["boss_emoji"] = boss.get("boss_emoji", "🦠") if boss else "🦠"
        if s.time_started and s.time_ended:
            d["duration_s"] = int((s.time_ended - s.time_started).total_seconds())
        else:
            d["duration_s"] = None
        results.append(d)
    return results


def save_session_to_experiment(session_id, user_id) -> dict:
    session = GameSession.query.get(session_id)
    if not session:
        raise ValueError("Session not found")
    if str(session.user_id) != str(user_id):
        raise ValueError("Unauthorised")

    target = target_service.get_curated_target(session.target_id)
    if not target:
        raise ValueError("Target data missing")

    best_attack = (
        GameAttack.query.filter_by(session_id=session.id, is_best=True)
        .order_by(GameAttack.composite_score.desc())
        .first()
    )
    if not best_attack:
        best_attack = (
            GameAttack.query.filter_by(session_id=session.id)
            .order_by(GameAttack.composite_score.desc())
            .first()
        )
    if not best_attack:
        raise ValueError("No attacks in this session to save")

    timestamp = session.time_started.strftime("%Y-%m-%d %H:%M") if session.time_started else "Unknown"
    boss_name = target.get("name", session.target_id)

    exp = Experiment(
        user_id=user_id,
        title=f"PathoHunt Discovery: {boss_name} ({timestamp})",
        hypothesis=(
            f"Game-discovered molecule against {boss_name}. "
            f"Session: {session.attacks_count} attacks, best score {session.best_score:.2%}. "
            f"Status: {session.status.upper()}."
        ),
        amino_acid_seq=target.get("amino_acid_seq", ""),
        seed_smile=best_attack.smiles,
        noise_level=0.3,
        num_requested=session.attacks_count,
        mode="3d",
        target_id=session.target_id,
        target_name=boss_name,
        status="draft",
        num_valid_generated=session.attacks_count,
    )
    db.session.add(exp)
    db.session.flush()

    all_attacks = (
        GameAttack.query.filter_by(session_id=session.id)
        .order_by(GameAttack.composite_score.desc())
        .all()
    )
    for rank, attack in enumerate(all_attacks, 1):
        cand = Candidate(
            experiment_id=exp.id,
            smiles=attack.smiles,
            qed=attack.qed,
            sas=attack.sas,
            logp=attack.logp,
            mw=attack.mw,
            composite_score=attack.composite_score,
            lipinski_pass=attack.lipinski_pass,
            rank=rank,
        )
        db.session.add(cand)

    db.session.commit()
    return {"experiment_id": str(exp.id)}


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
    sas_norm = 1.0 - (sas - 1.0) / 9.0
    tanimoto = props.get("tanimoto", 0.0)
    lipinski_bonus = 0.10 if props.get("lipinski_pass") else 0.0
    composite = (0.45 * qed) + (0.30 * sas_norm) + (0.15 * tanimoto) + lipinski_bonus
    return round(min(1.0, max(0.0, composite)), 4)


def _calculate_damage(composite: float, previous_best: float, mutations: list = None, props: dict = None) -> float:
    if composite < 0.30:
        return 0.0
    quality = (composite - 0.30) / 0.70
    base = quality * 18.0
    discovery_bonus = 0.0
    if composite > previous_best:
        discovery_bonus = min(12.0, (composite - previous_best) * 60.0)

    damage = base + discovery_bonus

    if mutations:
        mw = props.get("mw", 500.0) if props else 500.0
        for mutation in mutations:
            effect = mutation.get("effect_type")
            if effect == "efflux_pump" and mw < 400:
                damage *= 0.5
            elif effect == "binding_mutation":
                tanimoto = props.get("tanimoto", 1.0) if props else 1.0
                capped = min(tanimoto, 0.3)
                if tanimoto > 0.3:
                    damage *= (capped / max(tanimoto, 0.001))
            elif effect == "overexpression":
                damage = max(0.0, damage - 2.0)
            elif effect == "membrane_shield":
                damage *= 0.7

    return round(min(28.0, max(0.0, damage)), 2)


def _max_tanimoto(smiles: str, reference_list: list) -> float:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return 0.0
    fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, 2048)
    max_sim = 0.0
    for ref_smi in reference_list:
        ref_mol = Chem.MolFromSmiles(ref_smi)
        if ref_mol is None:
            continue
        ref_fp = AllChem.GetMorganFingerprintAsBitVect(ref_mol, 2, 2048)
        sim = TanimotoSimilarity(fp, ref_fp)
        if sim > max_sim:
            max_sim = sim
    return max_sim


def get_candidates(session_id, user_id, pinned_seed=None) -> list:
    session = GameSession.query.get(session_id)
    if not session or str(session.user_id) != str(user_id):
        return []
    target = target_service.get_curated_target(session.target_id)
    if not target:
        return []

    if pinned_seed:
        mol = Chem.MolFromSmiles(pinned_seed)
        seed = pinned_seed if mol is not None else target.get("starter_smiles", "")
    else:
        seed = target.get("starter_smiles", "")

    if not seed:
        return []

    candidates = []
    try:
        gen = molecule_generator.generate(
            seed_smile=seed,
            amino_acid_seq=target.get("amino_acid_seq", ""),
            noise=0.25,
            n=3,
        )
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


def get_leaderboard(target_id: str, limit: int = 10) -> list:
    rows = (
        GameLeaderboard.query.filter_by(target_id=target_id)
        .order_by(GameLeaderboard.composite_score.desc())
        .limit(limit)
        .all()
    )
    result = []
    for row in rows:
        d = row.to_dict()
        from models.db_models import User
        user = User.query.get(row.user_id)
        d["username"] = user.display_name or user.username if user else "Unknown"
        result.append(d)
    return result


def get_user_rp(user_id) -> int:
    return lab_service.get_rp(user_id)


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
