import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://deep2lead:password@localhost:5432/deep2lead_v2")

DGX_HOST = os.getenv("DGX_HOST", "dgx1")
DGX_PORT = int(os.getenv("DGX_PORT", "9001"))
DGX_BASE_URL = f"http://{DGX_HOST}:{DGX_PORT}"
DGX_TIMEOUT = int(os.getenv("DGX_GEMMA4_TIMEOUT", "90"))

# Molecule generation
MAX_CANDIDATES = 50
MAX_RETRY_ATTEMPTS = 3

# Scoring weights: DTI, QED, SAS (inverted), Tanimoto
SCORE_WEIGHTS = {"dti": 0.35, "qed": 0.30, "sas": 0.20, "tanimoto": 0.15}
