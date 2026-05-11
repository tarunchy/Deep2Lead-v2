from datetime import datetime, timezone

from models.db_models import db
from models.game_progression import UserResearchPoints, LabUpgrade, UserLabUpgrade, BossMemory

_DEFAULT_UPGRADES = [
    {
        "slug": "wider_net",
        "name": "+1 Molecule Card",
        "description": "Generate one extra candidate molecule per attack.",
        "cost_rp": 150,
        "effect_type": "n_molecules",
        "effect_value": 1.0,
        "icon": "🃏",
    },
    {
        "slug": "quantum_boost",
        "name": "QED Amplifier (×1.2 weight)",
        "description": "Increases QED weighting in the composite score calculation.",
        "cost_rp": 200,
        "effect_type": "qed_weight",
        "effect_value": 0.55,
        "icon": "⚡",
    },
    {
        "slug": "lucky_seed",
        "name": "Safety Net Threshold −0.05",
        "description": "Lowers the safety-net trigger threshold from 0.40 to 0.35.",
        "cost_rp": 100,
        "effect_type": "safety_net",
        "effect_value": 0.35,
        "icon": "🛡️",
    },
    {
        "slug": "memory_serum",
        "name": "Boss Memory Bypass (−20% penalty)",
        "description": "Reduces the memory penalty applied when re-using known molecules.",
        "cost_rp": 250,
        "effect_type": "memory_bypass",
        "effect_value": 0.8,
        "icon": "🧠",
    },
    {
        "slug": "combat_stim",
        "name": "Combo Damage ×1.5",
        "description": "Multiplies the discovery bonus when you beat your previous best score.",
        "cost_rp": 300,
        "effect_type": "combo_mult",
        "effect_value": 1.5,
        "icon": "💊",
    },
]


def seed_lab_upgrades():
    if LabUpgrade.query.count() > 0:
        return
    for data in _DEFAULT_UPGRADES:
        db.session.add(LabUpgrade(**data))
    db.session.commit()


def award_rp(user_id, amount: int):
    row = UserResearchPoints.query.filter_by(user_id=user_id).first()
    if row is None:
        row = UserResearchPoints(user_id=user_id, points=0, total_earned=0)
        db.session.add(row)
    row.points += amount
    row.total_earned += amount
    db.session.commit()


def get_rp(user_id) -> int:
    row = UserResearchPoints.query.filter_by(user_id=user_id).first()
    return row.points if row else 0


def get_user_upgrades(user_id) -> list:
    rows = UserLabUpgrade.query.filter_by(user_id=user_id).all()
    return [r.to_dict() for r in rows]


def purchase_upgrade(user_id, slug: str) -> dict:
    upgrade = LabUpgrade.query.filter_by(slug=slug).first()
    if not upgrade:
        raise ValueError(f"Unknown upgrade: {slug}")

    already_owned = UserLabUpgrade.query.filter_by(
        user_id=user_id, upgrade_slug=slug
    ).first()
    if already_owned:
        raise ValueError("You already own this upgrade")

    rp_row = UserResearchPoints.query.filter_by(user_id=user_id).first()
    current_points = rp_row.points if rp_row else 0
    if current_points < upgrade.cost_rp:
        raise ValueError(f"Insufficient RP: need {upgrade.cost_rp}, have {current_points}")

    rp_row.points -= upgrade.cost_rp
    user_upgrade = UserLabUpgrade(user_id=user_id, upgrade_slug=slug)
    db.session.add(user_upgrade)
    db.session.commit()
    return user_upgrade.to_dict()


def save_boss_memory(target_id: str, smiles_list: list, avg_damage: float):
    now = datetime.now(timezone.utc)
    for smiles in smiles_list:
        existing = BossMemory.query.filter_by(target_id=target_id, smiles=smiles).first()
        if existing:
            existing.frequency += 1
            existing.avg_damage = (existing.avg_damage + avg_damage) / 2.0
            existing.last_seen_at = now
        else:
            db.session.add(BossMemory(
                target_id=target_id,
                smiles=smiles,
                frequency=1,
                avg_damage=avg_damage,
                last_seen_at=now,
            ))
    db.session.commit()


def get_boss_memory(target_id: str) -> list:
    rows = BossMemory.query.filter_by(target_id=target_id).all()
    return [r.smiles for r in rows]
