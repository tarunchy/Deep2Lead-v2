import uuid
from sqlalchemy import func
from models.db_models import db


class AutoExperimentRun(db.Model):
    __tablename__ = "auto_experiment_runs"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    experiment_id = db.Column(
        db.UUID(as_uuid=True), db.ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    strategy = db.Column(db.String(32), default="balanced")
    # conservative | explorer | safety_first | novelty | balanced
    rounds_planned = db.Column(db.Integer, default=3)
    rounds_completed = db.Column(db.Integer, default=0)
    molecules_per_round = db.Column(db.Integer, default=5)
    best_candidate_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("candidates.id"), nullable=True)
    best_score = db.Column(db.Float, nullable=True)
    result_experiment_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey("experiments.id"), nullable=True)
    status = db.Column(db.String(16), default="pending")
    # pending | running | complete | failed | stopped
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    rounds = db.relationship(
        "AutoExperimentRound", backref="run", lazy="dynamic",
        cascade="all, delete-orphan", order_by="AutoExperimentRound.round_num"
    )

    def to_dict(self, include_rounds=False):
        d = {
            "id": str(self.id),
            "experiment_id": str(self.experiment_id),
            "result_experiment_id": str(self.result_experiment_id) if self.result_experiment_id else None,
            "strategy": self.strategy,
            "rounds_planned": self.rounds_planned,
            "rounds_completed": self.rounds_completed,
            "molecules_per_round": self.molecules_per_round,
            "best_score": round(self.best_score, 4) if self.best_score else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }
        if include_rounds:
            d["rounds"] = [r.to_dict() for r in self.rounds]
        return d


class AutoExperimentRound(db.Model):
    __tablename__ = "auto_experiment_rounds"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    auto_run_id = db.Column(
        db.UUID(as_uuid=True), db.ForeignKey("auto_experiment_runs.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    round_num = db.Column(db.Integer, nullable=False)
    seed_smiles = db.Column(db.Text, nullable=False)
    candidates_tried = db.Column(db.Integer, default=0)
    best_score = db.Column(db.Float, nullable=True)
    prev_best_score = db.Column(db.Float, nullable=True)
    improved = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(16), default="keep")   # keep | discard | failed
    rationale = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "id": str(self.id),
            "round_num": self.round_num,
            "seed_smiles": self.seed_smiles,
            "candidates_tried": self.candidates_tried,
            "best_score": round(self.best_score, 4) if self.best_score else None,
            "prev_best_score": round(self.prev_best_score, 4) if self.prev_best_score else None,
            "improved": self.improved,
            "status": self.status,
            "rationale": self.rationale,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
