"""AutoDock Vina molecular docking service.

Requires: pip install vina meeko openbabel-wheel scipy
"""
import os
import subprocess
import tempfile
import logging

log = logging.getLogger(__name__)

_VINA_AVAILABLE = False
_MEEKO_AVAILABLE = False

try:
    from vina import Vina as _Vina
    _VINA_AVAILABLE = True
except ImportError:
    pass

try:
    from meeko import MoleculePreparation as _MolPrep
    _MEEKO_AVAILABLE = True
except ImportError:
    pass

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    _RDKIT_AVAILABLE = True
except ImportError:
    _RDKIT_AVAILABLE = False


def is_docking_available() -> bool:
    return _VINA_AVAILABLE and _MEEKO_AVAILABLE and _RDKIT_AVAILABLE


def prepare_ligand_pdbqt(smiles: str) -> tuple[str | None, str]:
    """
    Convert SMILES to PDBQT string for Vina.
    Returns (pdbqt_string, error_message).
    """
    if not (_RDKIT_AVAILABLE and _MEEKO_AVAILABLE):
        return None, "RDKit or Meeko not available."
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None, "Invalid SMILES."
        mol = Chem.AddHs(mol)
        result = AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        if result != 0:
            # Fallback to ETKDG v1
            result = AllChem.EmbedMolecule(mol, AllChem.ETKDG())
        if result != 0:
            return None, "Could not generate 3D conformation for this molecule."
        AllChem.MMFFOptimizeMolecule(mol)
        prep = _MolPrep()
        prep.prepare(mol)
        pdbqt_str = prep.write_pdbqt_string()
        return pdbqt_str, ""
    except Exception as e:
        return None, str(e)


def prepare_receptor_pdbqt(pdb_path: str) -> tuple[str | None, str]:
    """
    Convert a PDB file to PDBQT using OpenBabel.
    Returns (pdbqt_path, error_message).
    """
    pdbqt_path = pdb_path.replace(".pdb", "_receptor.pdbqt")
    if os.path.exists(pdbqt_path):
        return pdbqt_path, ""
    try:
        result = subprocess.run(
            ["obabel", pdb_path, "-O", pdbqt_path, "-xr", "-p", "7.4", "--partialcharge", "eem"],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode != 0 or not os.path.exists(pdbqt_path):
            return None, result.stderr or "OpenBabel conversion failed."
        return pdbqt_path, ""
    except FileNotFoundError:
        return None, "OpenBabel (obabel) not found. Install openbabel-wheel."
    except subprocess.TimeoutExpired:
        return None, "Receptor preparation timed out."
    except Exception as e:
        return None, str(e)


def normalize_docking_score(kcal: float) -> float:
    """
    Map docking score (kcal/mol) to [0, 1].
    -12 kcal/mol → 1.0 (excellent)
    0 kcal/mol → 0.0 (no binding)
    Uses sigmoid-like mapping.
    """
    import math
    # Clamp between -15 and 0
    clamped = max(-15.0, min(0.0, kcal))
    return round(abs(clamped) / 15.0, 4)


def dock_molecule(
    receptor_pdbqt_path: str,
    ligand_pdbqt_str: str,
    center: list,
    box_size: list = None,
    exhaustiveness: int = 8,
    n_poses: int = 5,
) -> dict:
    """
    Run AutoDock Vina docking.
    Returns dict with docking_score_kcal, docking_score_norm, poses_pdbqt, error.
    """
    if box_size is None:
        box_size = [22, 22, 22]

    if not _VINA_AVAILABLE:
        return {"error": "AutoDock Vina not installed. Run: pip install vina"}

    try:
        v = _Vina(sf_name="vina", verbosity=0)
        v.set_receptor(receptor_pdbqt_path)
        v.set_ligand_from_string(ligand_pdbqt_str)
        v.compute_vina_maps(center=center, box_size=box_size)
        v.dock(exhaustiveness=exhaustiveness, n_poses=n_poses)

        energies = v.energies(n_poses=1)
        best_score = float(energies[0][0]) if energies else 0.0
        poses = v.poses(n_poses=1)

        return {
            "docking_score_kcal": round(best_score, 3),
            "docking_score_norm": normalize_docking_score(best_score),
            "poses_pdbqt": poses,
            "error": None,
        }
    except Exception as e:
        return {"error": str(e), "docking_score_kcal": None, "docking_score_norm": None}


def run_docking_pipeline(
    smiles: str,
    pdb_file_path: str,
    binding_site_center: list,
    binding_site_size: list = None,
    exhaustiveness: int = 8,
) -> dict:
    """
    Full pipeline: SMILES + PDB file → docking score.
    Returns result dict ready for DB storage.
    """
    if not is_docking_available():
        return {
            "error": "Docking dependencies not installed (vina, meeko, openbabel).",
            "docking_score_kcal": None,
            "docking_score_norm": None,
            "available": False,
        }

    # Step 1: prepare receptor
    receptor_pdbqt, err = prepare_receptor_pdbqt(pdb_file_path)
    if err:
        return {"error": f"Receptor preparation: {err}", "docking_score_kcal": None, "docking_score_norm": None}

    # Step 2: prepare ligand
    ligand_pdbqt, err = prepare_ligand_pdbqt(smiles)
    if err:
        return {"error": f"Ligand preparation: {err}", "docking_score_kcal": None, "docking_score_norm": None}

    # Step 3: dock
    result = dock_molecule(
        receptor_pdbqt_path=receptor_pdbqt,
        ligand_pdbqt_str=ligand_pdbqt,
        center=binding_site_center,
        box_size=binding_site_size or [22, 22, 22],
        exhaustiveness=exhaustiveness,
    )
    result["available"] = True
    return result
