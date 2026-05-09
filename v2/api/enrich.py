"""External database enrichment: parallel calls to ChEMBL and PubChem."""
import concurrent.futures
from urllib.parse import quote

from flask import Blueprint, jsonify
from flask_login import login_required
import requests as http

from models.db_models import Experiment

bp = Blueprint("enrich", __name__)

PUBCHEM = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"
TIMEOUT = 15


def _pubchem_similar(smiles: str) -> dict:
    try:
        url = f"{PUBCHEM}/compound/fastsimilarity_2d/smiles/property/IUPACName,MolecularWeight,IsomericSMILES/JSON"
        r = http.post(url, data={"smiles": smiles, "Threshold": 80, "MaxRecords": 5}, timeout=TIMEOUT)
        if r.status_code == 404:
            return {"hits": []}
        r.raise_for_status()
        props = r.json().get("PropertyTable", {}).get("Properties", [])
        hits = [
            {
                "cid": p.get("CID"),
                "name": p.get("IUPACName", "—"),
                "mw": p.get("MolecularWeight"),
                "smiles": p.get("IsomericSMILES", ""),
                "url": f"https://pubchem.ncbi.nlm.nih.gov/compound/{p.get('CID')}",
            }
            for p in props[:5]
        ]
        return {"hits": hits}
    except Exception as e:
        return {"error": str(e)}


def _chembl_similar(smiles: str) -> dict:
    try:
        encoded = quote(smiles, safe="")
        r = http.get(f"{CHEMBL}/similarity/{encoded}/70?format=json&limit=5", timeout=TIMEOUT)
        r.raise_for_status()
        mols = r.json().get("molecules", [])
        hits = [
            {
                "chembl_id": m.get("molecule_chembl_id"),
                "name": m.get("pref_name") or m.get("molecule_chembl_id"),
                "similarity": round(float(m.get("similarity", 0)), 1),
                "max_phase": m.get("max_phase"),
                "url": f"https://www.ebi.ac.uk/chembl/compound_report_card/{m.get('molecule_chembl_id')}/",
            }
            for m in mols[:5]
        ]
        return {"hits": hits}
    except Exception as e:
        return {"error": str(e)}


@bp.route("/api/v2/enrich/<experiment_id>")
@login_required
def enrich(experiment_id):
    exp = Experiment.query.get_or_404(experiment_id)
    smiles = exp.seed_smile
    seq = (exp.amino_acid_seq or "")[:100]

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        f_pc = pool.submit(_pubchem_similar, smiles)
        f_ch = pool.submit(_chembl_similar, smiles)

    return jsonify({
        "pubchem": f_pc.result(),
        "chembl": f_ch.result(),
        "external_links": {
            "uniprot_blast": f"https://www.uniprot.org/blast?sequence={seq}",
            "pubchem_browse": f"https://pubchem.ncbi.nlm.nih.gov/#query={quote(smiles)}",
            "chembl_browse": f"https://www.ebi.ac.uk/chembl/#search_results/compounds/{quote(smiles)}",
        },
    })
