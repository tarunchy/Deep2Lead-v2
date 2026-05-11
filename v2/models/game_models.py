import uuid
from datetime import datetime, timezone
from sqlalchemy import func
from models.db_models import db


class GameSession(db.Model):
    __tablename__ = "game_session"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False, index=True)
    target_id = db.Column(db.String(64), nullable=False)
    mode = db.Column(db.String(20), nullable=False, default="quick_battle")
    difficulty = db.Column(db.String(10), nullable=False, default="junior")
    status = db.Column(db.String(12), nullable=False, default="active")  # active|won|lost|abandoned
    boss_initial_hp = db.Column(db.Float, nullable=False, default=100.0)
    boss_current_hp = db.Column(db.Float, nullable=False, default=100.0)
    attacks_count = db.Column(db.Integer, default=0)
    best_score = db.Column(db.Float, default=0.0)
    win_threshold = db.Column(db.Float, nullable=False, default=0.70)
    time_started = db.Column(db.DateTime(timezone=True), server_default=func.now())
    time_ended = db.Column(db.DateTime(timezone=True), nullable=True)
    phase = db.Column(db.Integer, default=0, nullable=False)
    active_mutations = db.Column(db.JSON, default=list)
    outbreak_mode = db.Column(db.Boolean, default=False, nullable=False)
    outbreak_started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    bad_streak = db.Column(db.Integer, default=0, nullable=False)
    pinned_smiles = db.Column(db.Text, nullable=True)

    attacks = db.relationship("GameAttack", back_populates="session", lazy="dynamic",
                              order_by="GameAttack.attack_number")

    def to_dict(self):
        return {
            "id": str(self.id),
            "target_id": self.target_id,
            "mode": self.mode,
            "difficulty": self.difficulty,
            "status": self.status,
            "boss_initial_hp": self.boss_initial_hp,
            "boss_current_hp": self.boss_current_hp,
            "attacks_count": self.attacks_count,
            "best_score": self.best_score,
            "win_threshold": self.win_threshold,
            "time_started": self.time_started.isoformat() if self.time_started else None,
            "time_ended": self.time_ended.isoformat() if self.time_ended else None,
            "phase": self.phase,
            "active_mutations": self.active_mutations or [],
            "outbreak_mode": self.outbreak_mode,
            "outbreak_started_at": self.outbreak_started_at.isoformat() if self.outbreak_started_at else None,
            "bad_streak": self.bad_streak,
            "pinned_smiles": self.pinned_smiles,
        }


class GameAttack(db.Model):
    __tablename__ = "game_attack"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("game_session.id"), nullable=False, index=True)
    smiles = db.Column(db.Text, nullable=False)
    composite_score = db.Column(db.Float, nullable=False, default=0.0)
    qed = db.Column(db.Float, nullable=True)
    sas = db.Column(db.Float, nullable=True)
    logp = db.Column(db.Float, nullable=True)
    mw = db.Column(db.Float, nullable=True)
    damage_dealt = db.Column(db.Float, default=0.0)
    boss_hp_after = db.Column(db.Float, nullable=False)
    lipinski_pass = db.Column(db.Boolean, default=False)
    is_best = db.Column(db.Boolean, default=False)
    attack_number = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    session = db.relationship("GameSession", back_populates="attacks")

    def to_dict(self):
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "smiles": self.smiles,
            "composite_score": self.composite_score,
            "qed": self.qed,
            "sas": self.sas,
            "logp": self.logp,
            "mw": self.mw,
            "damage_dealt": self.damage_dealt,
            "boss_hp_after": self.boss_hp_after,
            "lipinski_pass": self.lipinski_pass,
            "is_best": self.is_best,
            "attack_number": self.attack_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
