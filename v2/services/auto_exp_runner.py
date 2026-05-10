"""
Autonomous experiment loop — inspired by Karpathy's autoresearch.
Pattern: Generate → Validate → Score → Keep/Discard → Repeat.
Runs in a background thread; streams progress via a shared state dict.

Modes:
  evolve  — start from top candidate, optimize with chosen strategy
  rescue  — 0 candidates in source experiment, cycles through all strategies
"""
import threading
import time
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Strategy parameter presets
STRATEGY_PARAMS = {
    "conservative": {"noise_level": 0.2, "tanimoto_min": 0.7, "novelty_weight": 0.10, "safety_weight": 0.20},
    "explorer":     {"noise_level": 0.6, "tanimoto_min": 0.30, "novelty_weight": 0.25, "safety_weight": 0.10},
    "safety_first": {"noise_level": 0.3, "tanimoto_min": 0.50, "novelty_weight": 0.10, "safety_weight": 0.35},
    "novelty":      {"noise_level": 0.5, "tanimoto_min": 0.30, "novelty_weight": 0.40, "safety_weight": 0.10},
    "balanced":     {"noise_level": 0.4, "tanimoto_min": 0.40, "novelty_weight": 0.20, "safety_weight": 0.20},
}

RESCUE_CYCLE = ["conservative", "explorer", "novelty", "safety_first", "balanced"]

# Global run state: run_id → RunState dict
_runs: dict[str, dict] = {}
_lock = threading.Lock()


def get_run_state(run_id: str) -> dict | None:
    with _lock:
        return _runs.get(run_id)


def _set_state(run_id: str, updates: dict):
    with _lock:
        if run_id in _runs:
            _runs[run_id].update(updates)


def _append_log(run_id: str, msg: str):
    ts = time.strftime("%H:%M:%S")
    with _lock:
        if run_id in _runs:
            _runs[run_id]["logs"].append(f"[{ts}] {msg}")
            _runs[run_id]["logs"] = _runs[run_id]["logs"][-100:]


def start_auto_experiment(run_id: str, config: dict, app):
    """
    Kick off the loop in a daemon thread.
    config keys: seed_smiles, amino_acid_seq, rounds, molecules_per_round,
                 mode, strategy, target_info, structure_path, binding_site_center
    """
    with _lock:
        _runs[run_id] = {
            "run_id": run_id,
            "status": "starting",
            "phase": "init",
            "mode": config.get("mode", "evolve"),
            "target_info": config.get("target_info", {}),
            "logs": [],
            "rounds": [],
            "best_score": None,
            "best_smiles": config.get("seed_smiles"),
            "rounds_completed": 0,
            "error": None,
        }

    t = threading.Thread(
        target=_loop,
        args=(run_id, config, app),
        daemon=True,
    )
    t.start()
    return run_id


def stop_auto_experiment(run_id: str):
    _set_state(run_id, {"status": "stopped"})


def _compute_composite(candidate: dict, docking_score_norm: float | None, strategy: str) -> float:
    """Weighted composite score for auto-experiment loop."""
    params = STRATEGY_PARAMS.get(strategy, STRATEGY_PARAMS["balanced"])
    nw = params["novelty_weight"]
    sw = params["safety_weight"]
    dw = 0.35
    qw = max(0.0, 1.0 - nw - sw - dw)

    qed = candidate.get("qed") or 0.0
    sas_norm = max(0.0, 1.0 - (candidate.get("sas") or 5.0) / 10.0)
    lipinski = 1.0 if candidate.get("lipinski_pass") else 0.0
    novelty = 1.0 if candidate.get("novelty_status") == "novel" else 0.5
    docking = docking_score_norm or 0.0

    return round(
        dw * docking + qw * qed + sw * (sas_norm * 0.5 + lipinski * 0.5) + nw * novelty,
        4
    )


def _loop(run_id: str, config: dict, app):
    """Main experiment loop. Runs in background thread."""
    from services.molecule_generator import generate as _gen_fn
    from services.molecule_validator import filter_candidates
    from services.property_calculator import compute_all
    from services.docking_service import run_docking_pipeline, is_docking_available
    from models import db, AutoExperimentRun, AutoExperimentRound, Candidate, Experiment
    import uuid

    with app.app_context():
        mode = config.get("mode", "evolve")
        strategy = config.get("strategy", "balanced")
        rounds = config.get("rounds", 3)
        mol_per_round = config.get("molecules_per_round", 5)
        seed_smiles = config["seed_smiles"]
        aa_seq = config["amino_acid_seq"]
        structure_path = config.get("structure_path")
        binding_center = config.get("binding_site_center", [0, 0, 0])
        exp_id = config.get("experiment_id")
        use_docking = is_docking_available() and bool(structure_path)

        mode_label = "Evolve" if mode == "evolve" else "Rescue"
        if mode == "rescue":
            _append_log(run_id, f"RESCUE mode: cycling through {len(RESCUE_CYCLE)} strategies to find valid molecules")
        else:
            _append_log(run_id, f"EVOLVE mode: improving top candidate with {strategy} strategy")
        _append_log(run_id, f"Rounds: {rounds}, Molecules/round: {mol_per_round}, Docking: {'enabled' if use_docking else 'disabled'}")
        _set_state(run_id, {"status": "running", "phase": "baseline"})

        # Establish baseline
        best_smiles = seed_smiles
        best_score = 0.0
        all_scored = []   # accumulate every candidate across all rounds
        _append_log(run_id, f"Baseline seed: {seed_smiles[:60]}...")

        for round_num in range(1, rounds + 1):
            state = get_run_state(run_id)
            if state and state.get("status") in ("stopped", "failed"):
                _append_log(run_id, "Loop stopped by user.")
                break

            # In rescue mode, cycle through strategies per round
            if mode == "rescue":
                round_strategy = RESCUE_CYCLE[(round_num - 1) % len(RESCUE_CYCLE)]
                params = STRATEGY_PARAMS[round_strategy]
            else:
                round_strategy = strategy
                params = STRATEGY_PARAMS.get(strategy, STRATEGY_PARAMS["balanced"])

            _set_state(run_id, {"phase": f"round-{round_num}"})
            _append_log(run_id, f"Round {round_num}/{rounds} [{round_strategy}]: generating {mol_per_round} candidates...")

            round_record = {
                "round_num": round_num,
                "strategy": round_strategy,
                "seed_smiles": best_smiles,
                "status": "running",
                "best_score": None,
                "improved": False,
                "candidates": [],
                "rationale": "",
            }

            try:
                # Generate candidates using Gemma4
                gen = _gen_fn(
                    seed_smile=best_smiles,
                    amino_acid_seq=aa_seq or "",
                    noise=params["noise_level"],
                    n=mol_per_round,
                )
                raw = gen["smiles"]
                valid = filter_candidates(raw, best_smiles)
                _append_log(run_id, f"  Generated {len(raw)} raw, {len(valid)} valid molecules.")

                if not valid:
                    _append_log(run_id, f"  Round {round_num}: no valid candidates. Discarding.")
                    round_record.update({"status": "discard", "rationale": "No valid SMILES generated."})
                    _set_state(run_id, {"rounds": get_run_state(run_id)["rounds"] + [round_record]})
                    continue

                # Score all valid candidates
                round_best_score = 0.0
                round_best_smiles = best_smiles
                scored = []

                for smiles in valid[:mol_per_round]:
                    props = compute_all(smiles, seed_smiles)
                    dock_result = {}
                    if use_docking:
                        dock_result = run_docking_pipeline(
                            smiles=smiles,
                            pdb_file_path=structure_path,
                            binding_site_center=binding_center,
                            exhaustiveness=4,  # fast in loop
                        )
                    dock_norm = dock_result.get("docking_score_norm") if dock_result else None
                    score = _compute_composite(props, dock_norm, strategy)
                    scored.append({
                        "smiles": smiles,
                        "score": score,
                        "props": props,
                        "docking_kcal": dock_result.get("docking_score_kcal") if dock_result else None,
                    })
                    if score > round_best_score:
                        round_best_score = score
                        round_best_smiles = smiles

                # Keep or discard
                improved = round_best_score > best_score
                if improved:
                    _append_log(run_id, f"  Round {round_num}: IMPROVED {best_score:.4f} → {round_best_score:.4f}. Keeping.")
                    rationale = f"Score improved from {best_score:.4f} to {round_best_score:.4f} with molecule {round_best_smiles[:40]}..."
                    best_score = round_best_score
                    best_smiles = round_best_smiles
                    _set_state(run_id, {"best_score": best_score, "best_smiles": best_smiles})
                else:
                    _append_log(run_id, f"  Round {round_num}: no improvement ({round_best_score:.4f} vs best {best_score:.4f}). Discarding.")
                    rationale = f"Best candidate scored {round_best_score:.4f}, did not exceed current best {best_score:.4f}."

                round_record.update({
                    "status": "keep" if improved else "discard",
                    "best_score": round_best_score,
                    "improved": improved,
                    "candidates": [{"smiles": c["smiles"], "score": c["score"]} for c in scored[:5]],
                    "rationale": rationale,
                })
                all_scored.extend(scored)

                # Persist round to DB
                with _lock:
                    rounds_so_far = _runs[run_id]["rounds"]
                _set_state(run_id, {
                    "rounds": rounds_so_far + [round_record],
                    "rounds_completed": round_num,
                })

                # Save to DB
                try:
                    run_row = AutoExperimentRun.query.get(uuid.UUID(run_id))
                    if run_row:
                        rnd = AutoExperimentRound(
                            auto_run_id=uuid.UUID(run_id),
                            round_num=round_num,
                            seed_smiles=best_smiles if improved else round_record["seed_smiles"],
                            candidates_tried=len(valid),
                            best_score=round_best_score,
                            prev_best_score=best_score if not improved else best_score - (round_best_score - best_score),
                            improved=improved,
                            status=round_record["status"],
                            rationale=rationale,
                        )
                        db.session.add(rnd)
                        run_row.rounds_completed = round_num
                        run_row.best_score = best_score
                        db.session.commit()
                except Exception as db_err:
                    log.warning(f"DB write error in loop: {db_err}")

            except Exception as e:
                _append_log(run_id, f"  Round {round_num} error: {e}")
                round_record.update({"status": "failed", "rationale": str(e)})
                with _lock:
                    _runs[run_id]["rounds"].append(round_record)
                continue

        # Finalize — save results as a new Experiment
        _append_log(run_id, f"Auto Experiment complete. Best score: {best_score:.4f}")
        _set_state(run_id, {"status": "complete", "phase": "done"})

        result_exp_id = None
        try:
            run_row = AutoExperimentRun.query.get(uuid.UUID(run_id))
            src_exp = Experiment.query.get(uuid.UUID(exp_id)) if exp_id else None

            if run_row and src_exp and all_scored:
                # Deduplicate by SMILES, keep best score per molecule
                seen: dict[str, dict] = {}
                for c in all_scored:
                    s = c["smiles"]
                    if s not in seen or c["score"] > seen[s]["score"]:
                        seen[s] = c
                top_candidates = sorted(seen.values(), key=lambda x: x["score"], reverse=True)[:10]

                # Derive title
                target_label = (
                    src_exp.target_name or
                    (src_exp.target_id.replace("_", " ").title() if src_exp.target_id else None) or
                    src_exp.title or
                    "Unknown Target"
                )
                result_title = f"Auto {mode_label}: {target_label}"

                result_exp = Experiment(
                    user_id=src_exp.user_id,
                    title=result_title,
                    amino_acid_seq=src_exp.amino_acid_seq,
                    seed_smile=src_exp.seed_smile,
                    noise_level=src_exp.noise_level,
                    num_requested=rounds * mol_per_round,
                    num_valid_generated=len(top_candidates),
                    target_id=src_exp.target_id,
                    target_name=src_exp.target_name,
                    pdb_id=src_exp.pdb_id,
                    uniprot_id=src_exp.uniprot_id,
                    mode="3d",
                    status="draft",
                )
                db.session.add(result_exp)
                db.session.flush()

                for rank, c in enumerate(top_candidates, start=1):
                    p = c.get("props") or {}
                    cand = Candidate(
                        experiment_id=result_exp.id,
                        smiles=c["smiles"],
                        rank=rank,
                        composite_score=c["score"],
                        dti_score=None,
                        qed=p.get("qed"),
                        sas=p.get("sas"),
                        logp=p.get("logp"),
                        mw=p.get("mw"),
                        tanimoto=p.get("tanimoto"),
                        lipinski_pass=p.get("lipinski_pass"),
                        novelty_status=p.get("novelty_status"),
                        docking_score_kcal=c.get("docking_kcal"),
                    )
                    db.session.add(cand)

                run_row.result_experiment_id = result_exp.id
                result_exp_id = str(result_exp.id)
                _append_log(run_id, f"Saved {len(top_candidates)} candidates → new experiment {result_exp_id[:8]}…")

            if run_row:
                run_row.status = "complete"
                run_row.completed_at = datetime.now(timezone.utc)
                run_row.best_score = best_score
            db.session.commit()
        except Exception as e:
            log.warning(f"Finalize DB error: {e}")

        _set_state(run_id, {"result_experiment_id": result_exp_id})
