"""XP and badge award service."""
from datetime import datetime, timezone

from models.db_models import db
from models.gamification import UserXP, Badge, UserBadge, MissionProgress
from config.settings import XP_EVENTS

BADGE_DEFINITIONS = [
    {"slug": "sequence_explorer",  "name": "Sequence Explorer",      "icon": "🧬", "xp_reward": 50,  "category": "discovery",      "description": "Validated your first amino acid sequence"},
    {"slug": "molecule_builder",   "name": "Molecule Builder",       "icon": "⚗️", "xp_reward": 50,  "category": "lab",            "description": "Submitted your first valid SMILES string"},
    {"slug": "structure_seeker",   "name": "Structure Seeker",       "icon": "🔬", "xp_reward": 75,  "category": "discovery",      "description": "Viewed your first 3D protein structure"},
    {"slug": "docking_rookie",     "name": "Docking Rookie",         "icon": "🎯", "xp_reward": 100, "category": "lab",            "description": "Completed your first molecular docking run"},
    {"slug": "ai_chemist",         "name": "AI Chemist",             "icon": "🤖", "xp_reward": 100, "category": "lab",            "description": "Generated your first AI candidate molecule"},
    {"slug": "mutation_defender",  "name": "Mutation Defender",      "icon": "🦠", "xp_reward": 150, "category": "science",        "description": "Improved a molecule against a mutated target"},
    {"slug": "novelty_hunter",     "name": "Novelty Hunter",         "icon": "✨", "xp_reward": 150, "category": "science",        "description": "Found a molecule not detected in PubChem"},
    {"slug": "safety_scientist",   "name": "Safety Scientist",       "icon": "🛡️", "xp_reward": 150, "category": "science",        "description": "Chose a safer molecule over a higher-scoring risky one"},
    {"slug": "communicator",       "name": "Research Communicator",  "icon": "📢", "xp_reward": 200, "category": "communication",  "description": "Published an experiment with a strong hypothesis"},
    {"slug": "loop_master",        "name": "Loop Master",            "icon": "🔁", "xp_reward": 300, "category": "science",        "description": "Completed a full Auto Experiment run"},
    # PathoHunt game badges
    {"slug": "game_first_hunt",    "name": "First Hunt",             "icon": "🎮", "xp_reward": 50,  "category": "game",           "description": "Completed your first PathoHunt battle"},
    {"slug": "flu_slayer",         "name": "Flu Slayer",             "icon": "🤧", "xp_reward": 100, "category": "game",           "description": "Defeated the Flu Commander boss"},
    {"slug": "covid_crusher",      "name": "COVID Crusher",          "icon": "🦠", "xp_reward": 100, "category": "game",           "description": "Defeated the Corona Cutter boss"},
    {"slug": "hiv_vanquisher",     "name": "HIV Vanquisher",         "icon": "🔴", "xp_reward": 200, "category": "game",           "description": "Defeated the HIV Hydra boss"},
    {"slug": "cancer_fighter",     "name": "Cancer Fighter",         "icon": "🧬", "xp_reward": 200, "category": "game",           "description": "Defeated the EGFR Enforcer boss"},
    {"slug": "resistance_breaker", "name": "Resistance Breaker",     "icon": "⚡", "xp_reward": 350, "category": "game",           "description": "Defeated the Mutant BRAF boss"},
    {"slug": "longevity_seeker",   "name": "Longevity Seeker",       "icon": "⏳", "xp_reward": 350, "category": "game",           "description": "Defeated the Aging Architect boss"},
    {"slug": "cycle_stopper",      "name": "Cycle Stopper",          "icon": "🔥", "xp_reward": 500, "category": "game",           "description": "Defeated CDK2 Overlord — the final boss"},
]

MISSION_DEFINITIONS = [
    {"level": 1, "name": "Molecule Basics",         "description": "Enter a SMILES string and view the molecule structure"},
    {"level": 2, "name": "Target Basics",            "description": "Choose a target, view its amino acid sequence and 3D structure"},
    {"level": 3, "name": "First Docking Battle",     "description": "Dock a known molecule against the target and interpret the score"},
    {"level": 4, "name": "AI Molecule Upgrade",      "description": "Generate 5 candidate molecules and compare their scores"},
    {"level": 5, "name": "Mutation Challenge",       "description": "Generate a molecule that works better against a mutated target"},
    {"level": 6, "name": "Auto Experiment Arena",    "description": "Run a 3-round Auto Experiment and track score improvement"},
    {"level": 7, "name": "Research Defense",         "description": "Submit your best molecule with docking score, novelty, and limitations"},
]


def seed_badges():
    """Idempotently seed the badge table from BADGE_DEFINITIONS."""
    for bd in BADGE_DEFINITIONS:
        existing = Badge.query.filter_by(slug=bd["slug"]).first()
        if not existing:
            db.session.add(Badge(**bd))
    db.session.commit()


def get_or_create_xp(user_id) -> UserXP:
    xp = UserXP.query.filter_by(user_id=user_id).first()
    if not xp:
        xp = UserXP(user_id=user_id, total_xp=0, level=1)
        db.session.add(xp)
        db.session.commit()
    return xp


def award_xp(user_id, event_key: str) -> int:
    """Award XP for a named event. Returns new total_xp."""
    amount = XP_EVENTS.get(event_key, 0)
    if amount == 0:
        return 0
    xp = get_or_create_xp(user_id)
    xp.total_xp += amount
    xp.level = xp.computed_level
    db.session.commit()
    return xp.total_xp


def award_badge(user_id, badge_slug: str) -> bool:
    """Award a badge if not already earned. Returns True if newly earned."""
    existing = UserBadge.query.filter_by(user_id=user_id, badge_slug=badge_slug).first()
    if existing:
        return False
    badge = Badge.query.filter_by(slug=badge_slug).first()
    if not badge:
        return False
    ub = UserBadge(user_id=user_id, badge_slug=badge_slug)
    db.session.add(ub)
    # Also award XP
    xp = get_or_create_xp(user_id)
    xp.total_xp += badge.xp_reward
    xp.level = xp.computed_level
    db.session.commit()
    return True


def get_user_badges(user_id) -> list:
    rows = UserBadge.query.filter_by(user_id=user_id).all()
    return [r.to_dict() for r in rows]


def get_user_xp(user_id) -> dict:
    xp = get_or_create_xp(user_id)
    return xp.to_dict()


def init_missions_for_user(user_id):
    """Create mission progress rows if they don't exist."""
    existing = {m.level for m in MissionProgress.query.filter_by(user_id=user_id).all()}
    for md in MISSION_DEFINITIONS:
        if md["level"] not in existing:
            status = "available" if md["level"] == 1 else "locked"
            db.session.add(MissionProgress(user_id=user_id, level=md["level"], status=status))
    db.session.commit()


def complete_mission(user_id, level: int):
    """Mark a mission complete and unlock the next one."""
    mp = MissionProgress.query.filter_by(user_id=user_id, level=level).first()
    if mp and mp.status != "complete":
        mp.status = "complete"
        mp.completed_at = datetime.now(timezone.utc)
        # Unlock next level
        nxt = MissionProgress.query.filter_by(user_id=user_id, level=level + 1).first()
        if nxt:
            nxt.status = "available"
        db.session.commit()


def get_missions(user_id) -> list:
    init_missions_for_user(user_id)
    rows = MissionProgress.query.filter_by(user_id=user_id).order_by(MissionProgress.level).all()
    definitions = {md["level"]: md for md in MISSION_DEFINITIONS}
    result = []
    for r in rows:
        d = definitions.get(r.level, {})
        result.append({
            **r.to_dict(),
            "name": d.get("name", ""),
            "description": d.get("description", ""),
        })
    return result
