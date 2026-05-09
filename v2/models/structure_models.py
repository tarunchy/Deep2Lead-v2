import uuid
from datetime import datetime, timezone
from sqlalchemy import func
from models.db_models import db


class ProteinStructure(db.Model):
    __tablename__ = "protein_structures"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uniprot_id = db.Column(db.String(32), nullable=True, index=True)
    pdb_id = db.Column(db.String(16), nullable=True, index=True)
    source = db.Column(db.String(32), nullable=False)  # rcsb | alphafold | esmfold
    sequence_hash = db.Column(db.String(64), nullable=True, index=True)  # sha256 of AA seq
    pdb_file_path = db.Column(db.String(512), nullable=True)
    resolution = db.Column(db.Float, nullable=True)
    plddt_mean = db.Column(db.Float, nullable=True)    # for AlphaFold/ESMFold
    organism = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    docking_results = db.relationship(
        "DockingResult", backref="structure", lazy="dynamic",
        cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "uniprot_id": self.uniprot_id,
            "pdb_id": self.pdb_id,
            "source": self.source,
            "resolution": self.resolution,
            "plddt_mean": self.plddt_mean,
            "organism": self.organism,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DockingResult(db.Model):
    __tablename__ = "docking_results"

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id = db.Column(
        db.UUID(as_uuid=True), db.ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    structure_id = db.Column(
        db.UUID(as_uuid=True), db.ForeignKey("protein_structures.id", ondelete="CASCADE"),
        nullable=False
    )
    docking_score_kcal = db.Column(db.Float, nullable=True)   # kcal/mol, negative = better
    docking_score_norm = db.Column(db.Float, nullable=True)   # [0,1] normalized
    pose_pdbqt_path = db.Column(db.String(512), nullable=True)
    exhaustiveness = db.Column(db.Integer, default=8)
    status = db.Column(db.String(16), default="pending")      # pending|running|done|failed
    error_msg = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    def to_dict(self):
        return {
            "id": str(self.id),
            "candidate_id": str(self.candidate_id),
            "structure_id": str(self.structure_id),
            "docking_score_kcal": round(self.docking_score_kcal, 3) if self.docking_score_kcal is not None else None,
            "docking_score_norm": round(self.docking_score_norm, 3) if self.docking_score_norm is not None else None,
            "status": self.status,
            "error_msg": self.error_msg,
        }
