import uuid
from datetime import datetime
from sqlalchemy import func
from models.db_models import db


class UserXP(db.Model):
    __tablename__ = "user_xp"

    user_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("users.id"), primary_key=True)
    total_xp = db.Column(db.Integer, default=0, nullable=False)
    level = db.Column(db.Integer, default=1, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    XP_THRESHOLDS = [0, 100, 300, 600, 1000, 1500, 2100, 2800]

    @property
    def computed_level(self):
        for lvl, threshold in reversed(list(enumerate(self.XP_THRESHOLDS, start=1))):
            if self.total_xp >= threshold:
                return lvl
        return 1

    @property
    def xp_to_next_level(self):
        if self.level >= len(self.XP_THRESHOLDS):
            return 0
        return self.XP_THRESHOLDS[self.level] - self.total_xp

    @property
    def level_progress_pct(self):
        if self.level >= len(self.XP_THRESHOLDS):
            return 100
        prev = self.XP_THRESHOLDS[self.level - 1]
        nxt = self.XP_THRESHOLDS[self.level]
        span = nxt - prev
        earned = self.total_xp - prev
        return max(0, min(100, int(earned / span * 100)))

    def to_dict(self):
        return {
            "total_xp": self.total_xp,
            "level": self.level,
            "xp_to_next": self.xp_to_next_level,
            "level_progress_pct": self.level_progress_pct,
        }


class Badge(db.Model):
    __tablename__ = "badges"

    slug = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(8), default="🏅")
    xp_reward = db.Column(db.Integer, default=50)
    category = db.Column(db.String(32))  # discovery | lab | science | communication

    def to_dict(self):
        return {
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "xp_reward": self.xp_reward,
            "category": self.category,
        }


class UserBadge(db.Model):
    __tablename__ = "user_badges"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False, index=True)
    badge_slug = db.Column(db.String(64), db.ForeignKey("badges.slug"), nullable=False)
    earned_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    badge = db.relationship("Badge")

    def to_dict(self):
        return {
            "badge_slug": self.badge_slug,
            "badge": self.badge.to_dict() if self.badge else None,
            "earned_at": self.earned_at.isoformat() if self.earned_at else None,
        }


class MissionProgress(db.Model):
    __tablename__ = "mission_progress"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False, index=True)
    level = db.Column(db.Integer, nullable=False)   # 1–7
    status = db.Column(db.String(16), default="locked")  # locked|available|complete
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (db.UniqueConstraint("user_id", "level"),)

    def to_dict(self):
        return {
            "level": self.level,
            "status": self.status,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
