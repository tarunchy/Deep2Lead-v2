import uuid
from datetime import datetime, timezone
from sqlalchemy import func
from models.db_models import db


class GameLeaderboard(db.Model):
    __tablename__ = "game_leaderboard"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id = db.Column(db.String(64), nullable=False, index=True)
    user_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    mol_name = db.Column(db.String(64), nullable=False)
    smiles = db.Column(db.Text, nullable=False)
    composite_score = db.Column(db.Float, nullable=False)
    attacks_count = db.Column(db.Integer, nullable=False)
    won_at = db.Column(db.DateTime(timezone=True), nullable=False)

    def to_dict(self):
        return {
            "id": str(self.id),
            "target_id": self.target_id,
            "user_id": str(self.user_id),
            "mol_name": self.mol_name,
            "smiles": self.smiles,
            "composite_score": self.composite_score,
            "attacks_count": self.attacks_count,
            "won_at": self.won_at.isoformat() if self.won_at else None,
        }


class UserResearchPoints(db.Model):
    __tablename__ = "user_research_points"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        db.UUID(as_uuid=True), db.ForeignKey("users.id"),
        nullable=False, unique=True
    )
    points = db.Column(db.Integer, default=0, nullable=False)
    total_earned = db.Column(db.Integer, default=0, nullable=False)

    def to_dict(self):
        return {
            "user_id": str(self.user_id),
            "points": self.points,
            "total_earned": self.total_earned,
        }


class LabUpgrade(db.Model):
    __tablename__ = "lab_upgrades"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(64), nullable=False)
    description = db.Column(db.String(256), nullable=False)
    cost_rp = db.Column(db.Integer, nullable=False)
    effect_type = db.Column(db.String(32), nullable=False)
    effect_value = db.Column(db.Float, nullable=False)
    icon = db.Column(db.String(8), nullable=False)

    def to_dict(self):
        return {
            "id": str(self.id),
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "cost_rp": self.cost_rp,
            "effect_type": self.effect_type,
            "effect_value": self.effect_value,
            "icon": self.icon,
        }


class UserLabUpgrade(db.Model):
    __tablename__ = "user_lab_upgrades"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    upgrade_slug = db.Column(db.String(32), db.ForeignKey("lab_upgrades.slug"), nullable=False)
    activated_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    upgrade = db.relationship("LabUpgrade")

    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "upgrade_slug": self.upgrade_slug,
            "upgrade": self.upgrade.to_dict() if self.upgrade else None,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
        }


class BossMemory(db.Model):
    __tablename__ = "boss_memory"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    target_id = db.Column(db.String(64), nullable=False, index=True)
    smiles = db.Column(db.Text, nullable=False)
    frequency = db.Column(db.Integer, default=1, nullable=False)
    avg_damage = db.Column(db.Float, default=0.0, nullable=False)
    last_seen_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())

    def to_dict(self):
        return {
            "id": str(self.id),
            "target_id": self.target_id,
            "smiles": self.smiles,
            "frequency": self.frequency,
            "avg_damage": self.avg_damage,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
        }


class CoopSession(db.Model):
    __tablename__ = "coop_sessions"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = db.Column(
        db.UUID(as_uuid=True), db.ForeignKey("game_session.id"),
        unique=True, nullable=False
    )
    analyst_user_id = db.Column(
        db.UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=True
    )
    analyst_annotations = db.Column(db.JSON, default=dict)
    joined_at = db.Column(db.DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": str(self.id),
            "session_id": str(self.session_id),
            "analyst_user_id": str(self.analyst_user_id) if self.analyst_user_id else None,
            "analyst_annotations": self.analyst_annotations or {},
            "joined_at": self.joined_at.isoformat() if self.joined_at else None,
        }
