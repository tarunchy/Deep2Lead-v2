import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-prod")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://deep2lead:password@localhost:5432/deep2lead_v2")

# DGX1 (offline — fine-tuning in progress)
# DGX_HOST = os.getenv("DGX_HOST", "dgx1")
# DGX_PORT = int(os.getenv("DGX_PORT", "9001"))

# dlyog04 — Gemma 4 E2B running on port 9000
DGX_HOST = os.getenv("DGX_HOST", "dlyog04")
DGX_PORT = int(os.getenv("DGX_PORT", "9000"))
DGX_BASE_URL = f"http://{DGX_HOST}:{DGX_PORT}"
DGX_TIMEOUT = int(os.getenv("DGX_GEMMA4_TIMEOUT", "90"))

# Molecule generation
MAX_CANDIDATES = 50
MAX_RETRY_ATTEMPTS = 3

# Scoring weights: DTI, QED, SAS (inverted), Tanimoto  (2D mode)
SCORE_WEIGHTS = {"dti": 0.35, "qed": 0.30, "sas": 0.20, "tanimoto": 0.15}

# 3D scoring weights (docking mode)
SCORE_WEIGHTS_3D = {"docking": 0.35, "qed": 0.20, "novelty": 0.20, "lipinski": 0.15, "sas": 0.10}

# Structure cache
import os as _os
STRUCTURE_CACHE_DIR = _os.getenv(
    "STRUCTURE_CACHE_DIR",
    _os.path.join(_os.path.dirname(__file__), "..", "data", "structures")
)

# ESMFold API
ESMFOLD_URL = _os.getenv("ESMFOLD_URL", "https://api.esmatlas.com/foldSequence/v1/pdb/")
ESMFOLD_TIMEOUT = int(_os.getenv("ESMFOLD_TIMEOUT", "120"))
ESMFOLD_MAX_SEQ_LEN = 400

# AlphaFold EBI API
ALPHAFOLD_API_URL = _os.getenv("ALPHAFOLD_API_URL", "https://alphafold.ebi.ac.uk/api/prediction")
ALPHAFOLD_FILES_URL = _os.getenv("ALPHAFOLD_FILES_URL", "https://alphafold.ebi.ac.uk/files")

# RCSB PDB
RCSB_DOWNLOAD_URL = _os.getenv("RCSB_DOWNLOAD_URL", "https://files.rcsb.org/download")
RCSB_SEARCH_URL = _os.getenv("RCSB_SEARCH_URL", "https://search.rcsb.org/rcsbsearch/v2/query")
RCSB_DATA_URL = _os.getenv("RCSB_DATA_URL", "https://data.rcsb.org/rest/v1/core/entry")

# UniProt
UNIPROT_SEARCH_URL = _os.getenv("UNIPROT_SEARCH_URL", "https://rest.uniprot.org/uniprotkb/search")

# External chemistry databases
PUBCHEM_URL = _os.getenv("PUBCHEM_URL", "https://pubchem.ncbi.nlm.nih.gov/rest/pug")
CHEMBL_URL  = _os.getenv("CHEMBL_URL",  "https://www.ebi.ac.uk/chembl/api/data")

# Kokoro TTS service
KOKORO_URL = _os.getenv("KOKORO_URL", "http://dlyog05:5151")

# Docking limits per user
DOCKING_MAX_PER_HOUR = int(_os.getenv("DOCKING_MAX_PER_HOUR", "10"))
DOCKING_EXHAUSTIVENESS = int(_os.getenv("DOCKING_EXHAUSTIVENESS", "8"))
DOCKING_N_POSES = 5

# Auto Experiment limits
AUTO_EXP_MAX_ROUNDS = int(_os.getenv("AUTO_EXP_MAX_ROUNDS", "5"))
AUTO_EXP_MAX_MOLECULES = int(_os.getenv("AUTO_EXP_MAX_MOLECULES", "10"))

# Whisper STT service (dlyog05)
WHISPER_URL     = _os.getenv("WHISPER_URL",     "http://dlyog05:5002/api/transcribe")
WHISPER_TIMEOUT = int(_os.getenv("WHISPER_TIMEOUT", "60"))

# Gamification XP values
XP_EVENTS = {
    "sequence_validated": 10,
    "smiles_validated": 10,
    "structure_viewed": 25,
    "first_dock": 50,
    "experiment_generated": 30,
    "experiment_published": 50,
    "auto_exp_round": 40,
    "auto_exp_complete": 100,
    "report_generated": 75,
}
