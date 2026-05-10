import uuid
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import func
import bcrypt

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String(64), unique=True, nullable=False)
    display_name = db.Column(db.String(128))
    email = db.Column(db.String(128))
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), nullable=False, default="student")
    cohort = db.Column(db.String(64))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    last_login = db.Column(db.DateTime(timezone=True))

    experiments = db.relationship("Experiment", backref="author", lazy="dynamic")
    comments = db.relationship("Comment", backref="author", lazy="dynamic")
    likes = db.relationship("Like", backref="user", lazy="dynamic")

    def set_password(self, password: str):
        self.password_hash = bcrypt.hashpw(
            password.encode(), bcrypt.gensalt()
        ).decode()

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())

    def to_dict(self):
        return {
            "id": str(self.id),
            "username": self.username,
            "display_name": self.display_name or self.username,
            "email": self.email,
            "role": self.role,
            "cohort": self.cohort,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Experiment(db.Model):
    __tablename__ = "experiments"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(256))
    hypothesis = db.Column(db.Text)
    amino_acid_seq = db.Column(db.Text, nullable=False)
    seed_smile = db.Column(db.String(512), nullable=False)
    noise_level = db.Column(db.Float, default=0.5)
    num_requested = db.Column(db.Integer, default=10)
    # v3 fields — mode + target identity
    mode = db.Column(db.String(8), default="2d", nullable=False)   # 2d | 3d
    target_id = db.Column(db.String(64), nullable=True)            # curated target id
    target_name = db.Column(db.String(256), nullable=True)
    uniprot_id = db.Column(db.String(32), nullable=True)
    pdb_id = db.Column(db.String(16), nullable=True)
    protein_structure_id = db.Column(UUID(as_uuid=True), nullable=True)
    status = db.Column(db.String(16), default="draft", nullable=False)
    version = db.Column(db.Integer, default=1)
    published_at = db.Column(db.DateTime(timezone=True))
    gemma4_latency_ms = db.Column(db.Integer)
    num_valid_generated = db.Column(db.Integer)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    candidates = db.relationship(
        "Candidate", backref="experiment", lazy="dynamic",
        cascade="all, delete-orphan", order_by="Candidate.rank"
    )
    comments = db.relationship("Comment", backref="experiment", lazy="dynamic")
    likes = db.relationship("Like", backref="experiment", lazy="dynamic")

    @property
    def like_count(self):
        return self.likes.count()

    @property
    def comment_count(self):
        return self.comments.filter_by(is_deleted=False).count()

    def to_dict(self, include_candidates=False):
        top = self.candidates.first()
        d = {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "author": self.author.display_name or self.author.username,
            "cohort": self.author.cohort,
            "title": self.title,
            "hypothesis": self.hypothesis,
            "amino_acid_seq": self.amino_acid_seq,
            "seed_smile": self.seed_smile,
            "noise_level": self.noise_level,
            "num_requested": self.num_requested,
            "status": self.status,
            "version": self.version,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "gemma4_latency_ms": self.gemma4_latency_ms,
            "mode": self.mode,
            "num_valid_generated": self.num_valid_generated,
            "target_id": self.target_id,
            "pdb_id": self.pdb_id,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "top_candidate": top.to_dict() if top else None,
        }
        if include_candidates:
            d["candidates"] = [c.to_dict() for c in self.candidates]
        return d


class Candidate(db.Model):
    __tablename__ = "candidates"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
    )
    smiles = db.Column(db.String(512), nullable=False)
    qed = db.Column(db.Float)
    sas = db.Column(db.Float)
    logp = db.Column(db.Float)
    mw = db.Column(db.Float)
    tanimoto = db.Column(db.Float)
    dti_score = db.Column(db.Float)
    lipinski_pass = db.Column(db.Boolean)
    composite_score = db.Column(db.Float)
    rank = db.Column(db.Integer)
    # v3 docking fields
    docking_score_kcal = db.Column(db.Float, nullable=True)
    novelty_status = db.Column(db.String(16), nullable=True)  # novel | known | unknown

    def to_dict(self):
        return {
            "id": str(self.id),
            "smiles": self.smiles,
            "qed": round(self.qed, 3) if self.qed is not None else None,
            "sas": round(self.sas, 2) if self.sas is not None else None,
            "logp": round(self.logp, 2) if self.logp is not None else None,
            "mw": round(self.mw, 1) if self.mw is not None else None,
            "tanimoto": round(self.tanimoto, 3) if self.tanimoto is not None else None,
            "dti_score": round(self.dti_score, 3) if self.dti_score is not None else None,
            "lipinski_pass": self.lipinski_pass,
            "composite_score": round(self.composite_score, 3) if self.composite_score is not None else None,
            "rank": self.rank,
            "docking_score_kcal": round(self.docking_score_kcal, 3) if self.docking_score_kcal is not None else None,
            "novelty_status": self.novelty_status,
        }


class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("experiments.id"), nullable=False
    )
    user_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False
    )
    parent_id = db.Column(UUID(as_uuid=True), db.ForeignKey("comments.id"))
    body = db.Column(db.Text, nullable=False)
    tag = db.Column(db.String(16))  # question|suggestion|correction|praise
    is_edited = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    edited_at = db.Column(db.DateTime(timezone=True))

    replies = db.relationship(
        "Comment", backref=db.backref("parent", remote_side=[id]), lazy="dynamic"
    )

    def to_dict(self, include_replies=False):
        d = {
            "id": str(self.id),
            "experiment_id": str(self.experiment_id),
            "user_id": str(self.user_id),
            "author": self.author.display_name or self.author.username,
            "parent_id": str(self.parent_id) if self.parent_id else None,
            "body": "[removed by instructor]" if self.is_deleted else self.body,
            "tag": self.tag,
            "is_edited": self.is_edited,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "edited_at": self.edited_at.isoformat() if self.edited_at else None,
        }
        if include_replies:
            d["replies"] = [
                r.to_dict() for r in self.replies.filter_by(is_deleted=False)
            ]
        return d


class Like(db.Model):
    __tablename__ = "likes"

    user_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("users.id"), primary_key=True
    )
    experiment_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("experiments.id"), primary_key=True
    )
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
