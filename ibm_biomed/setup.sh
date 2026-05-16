#!/usr/bin/env bash
# Full setup for IBM MAMMAL on dlyog03 (RTX 3060 Ti, CUDA 12.4, Python 3.11)
# Run once from: /home/dlyog/apps/ibm_biomed/
# This script does everything — no shortcuts.
#
# Steps:
#   1. Create Python venv
#   2. Upgrade pip
#   3. Install PyTorch with CUDA 12.1 (binary compatible with driver 12.4)
#   4. Install biomed-multi-alignment from GitHub (IBM MAMMAL)
#   5. Install FastAPI / uvicorn for serving
#   6. Pre-download model weights from HuggingFace (ibm/biomed.omics.bl.sm.ma-ted-458m)
#   7. Smoke test: load model + run one binding prediction
#
# Time estimate: 20-40 min (mostly model download ~1.8GB)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/venv"

echo "============================================================"
echo " IBM MAMMAL Setup — dlyog03"
echo " Deploy dir: $SCRIPT_DIR"
echo " Venv:       $VENV"
echo "============================================================"
echo ""

# ── Step 1: Create venv ────────────────────────────────────────────────────────
echo "[1/7] Creating Python 3.11 virtual environment ..."
python3.11 -m venv "$VENV"
source "$VENV/bin/activate"
echo "  Active Python: $(python --version)"
echo "  Active pip:    $(pip --version)"
echo ""

# ── Step 2: Upgrade pip + wheel ────────────────────────────────────────────────
echo "[2/7] Upgrading pip, wheel, setuptools ..."
pip install --upgrade pip wheel setuptools
echo ""

# ── Step 3: Install PyTorch (CUDA 12.1 wheel — compatible with 12.4 driver) ──
echo "[3/7] Installing PyTorch 2.3 with CUDA 12.1 wheels ..."
pip install torch==2.3.1 torchvision==0.18.1 \
    --index-url https://download.pytorch.org/whl/cu121
echo ""
echo "  PyTorch CUDA check:"
python -c "import torch; print(f'  torch={torch.__version__}  cuda_available={torch.cuda.is_available()}  device={torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"none\"}')"
echo ""

# ── Step 4: Install IBM biomed-multi-alignment (MAMMAL) ───────────────────────
echo "[4/7] Installing biomed-multi-alignment from GitHub ..."
pip install git+https://github.com/BiomedSciAI/biomed-multi-alignment.git
echo ""

# ── Step 5: Install FastAPI serving stack ─────────────────────────────────────
echo "[5/7] Installing FastAPI / uvicorn ..."
pip install fastapi>=0.111.0 uvicorn[standard]>=0.29.0 pydantic>=2.7.0 requests>=2.31.0 tqdm>=4.66.0
echo ""

# ── Step 6: Pre-download model weights ────────────────────────────────────────
echo "[6/7] Pre-downloading IBM MAMMAL model weights from HuggingFace ..."
echo "      Model: ibm/biomed.omics.bl.sm.ma-ted-458m (~1.8 GB)"
echo "      This may take 10-20 minutes depending on bandwidth ..."
python - <<'PYEOF'
import os
os.environ["TRANSFORMERS_VERBOSITY"] = "info"

print("  Loading MAMMAL model (downloads weights on first run) ...")
from mammal.model import Mammal
from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp

MODEL_ID = "ibm/biomed.omics.bl.sm.ma-ted-458m"

model = Mammal.from_pretrained(MODEL_ID)
model.eval()
print("  Model loaded.")

tok = ModularTokenizerOp.from_pretrained(MODEL_ID)
print("  Tokenizer loaded.")
print("  Model weights cached to HuggingFace cache dir.")
PYEOF
echo ""

# ── Step 7: Smoke test — one binding prediction ────────────────────────────────
echo "[7/7] Smoke test — one DTI binding prediction ..."
python - <<'PYEOF'
import torch
from mammal.model import Mammal
from mammal.keys import (
    ENCODER_INPUTS_STR, ENCODER_INPUTS_TOKENS,
    ENCODER_INPUTS_ATTENTION_MASK, CLS_PRED,
)
from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp

MODEL_ID = "ibm/biomed.omics.bl.sm.ma-ted-458m"
DEVICE   = "cuda" if torch.cuda.is_available() else "cpu"

print(f"  Using device: {DEVICE}")

model = Mammal.from_pretrained(MODEL_ID)
model.eval()
if DEVICE == "cuda":
    model = model.cuda()

tok = ModularTokenizerOp.from_pretrained(MODEL_ID)

# Test pair: SARS-CoV-2 Main Protease + Nirmatrelvir
FASTA  = "MESLVPGFNEKTHVQLSLPVLQVRDVLVRGFGDSVEEVLSEARQHLK"
SMILES = "CC1(C2CC2NC(=O)C(F)(F)F)C(=O)N[C@@H](Cc2ccc(C#N)cc2)C1=O"

sample = {
    ENCODER_INPUTS_STR: (
        f"<@TOKENIZER-TYPE=AA><BINDING_AFFINITY_CLASS><SENTINEL_ID_0>"
        f"<MOLECULAR_ENTITY><MOLECULAR_ENTITY_GENERAL_PROTEIN>"
        f"<SEQUENCE_NATURAL_START>{FASTA}<SEQUENCE_NATURAL_END>"
        f"<MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
        f"<SEQUENCE_NATURAL_START>{SMILES}<SEQUENCE_NATURAL_END><EOS>"
    )
}

tok(
    sample_dict=sample,
    key_in=ENCODER_INPUTS_STR,
    key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
    key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK,
)
sample[ENCODER_INPUTS_TOKENS]        = torch.tensor(sample[ENCODER_INPUTS_TOKENS])
sample[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sample[ENCODER_INPUTS_ATTENTION_MASK])
if DEVICE == "cuda":
    sample[ENCODER_INPUTS_TOKENS]         = sample[ENCODER_INPUTS_TOKENS].cuda()
    sample[ENCODER_INPUTS_ATTENTION_MASK] = sample[ENCODER_INPUTS_ATTENTION_MASK].cuda()

with torch.no_grad():
    batch = model.generate(
        [sample],
        output_scores=True,
        return_dict_in_generate=True,
        max_new_tokens=5,
    )

raw = tok._tokenizer.decode(batch[CLS_PRED][0])
print(f"  Test pair: SARS-CoV-2 MPro + Nirmatrelvir")
print(f"  Raw model output: '{raw}'")
print(f"  Smoke test PASSED.")
PYEOF

echo ""
echo "============================================================"
echo " Setup complete!"
echo ""
echo " Next steps:"
echo "   bash start.sh          — start MAMMAL API on port 8090"
echo "   tail -f mammal_api.log — monitor"
echo "   python test_api.py     — verify API is responding"
echo "============================================================"
