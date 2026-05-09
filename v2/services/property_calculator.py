import math
from rdkit import Chem
from rdkit.Chem import Descriptors, QED, AllChem, rdMolDescriptors


def _sas(mol) -> float:
    """Simplified synthetic accessibility score (1=easy, 10=hard)."""
    fp = rdMolDescriptors.GetMorganFingerprint(mol, 2)
    fps = fp.GetNonzeroElements()
    nf = sum(fps.values())
    score1 = sum(fps.values()) / nf if nf else 0.0

    nAtoms = mol.GetNumAtoms()
    nChiral = len(Chem.FindMolChiralCenters(mol, includeUnassigned=True))
    ri = mol.GetRingInfo()
    nSpiro = rdMolDescriptors.CalcNumSpiroAtoms(mol)
    nBridge = rdMolDescriptors.CalcNumBridgeheadAtoms(mol)
    nMacro = sum(1 for r in ri.AtomRings() if len(r) > 8)

    score2 = (
        -(nAtoms ** 1.005 - nAtoms)
        - math.log10(nChiral + 1)
        - math.log10(nSpiro + 1)
        - math.log10(nBridge + 1)
        - (math.log10(2) if nMacro > 0 else 0)
    )
    score3 = math.log(float(nAtoms) / len(fps)) * 0.5 if nAtoms > len(fps) else 0.0

    raw = score1 + score2 + score3
    sas = 11.0 - (raw - (-4.0) + 1) / (2.5 - (-4.0)) * 9.0
    if sas > 8.0:
        sas = 8.0 + math.log(sas + 1.0 - 9.0)
    return float(max(1.0, min(10.0, sas)))


def _tanimoto(mol, seed_mol) -> float:
    fp1 = AllChem.GetMorganFingerprintAsBitVect(mol, 2, 2048)
    fp2 = AllChem.GetMorganFingerprintAsBitVect(seed_mol, 2, 2048)
    from rdkit.DataStructs import TanimotoSimilarity
    return float(TanimotoSimilarity(fp1, fp2))


def _lipinski(mol) -> bool:
    mw = Descriptors.MolWt(mol)
    logp = Descriptors.MolLogP(mol)
    hbd = rdMolDescriptors.CalcNumHBD(mol)
    hba = rdMolDescriptors.CalcNumHBA(mol)
    return mw <= 500 and logp <= 5 and hbd <= 5 and hba <= 10


def compute_all(smiles: str, seed_smile: str) -> dict | None:
    mol = Chem.MolFromSmiles(smiles)
    seed_mol = Chem.MolFromSmiles(seed_smile)
    if mol is None or seed_mol is None:
        return None
    return {
        "qed": float(QED.qed(mol)),
        "sas": _sas(mol),
        "logp": float(Descriptors.MolLogP(mol)),
        "mw": float(Descriptors.MolWt(mol)),
        "tanimoto": _tanimoto(mol, seed_mol),
        "lipinski_pass": _lipinski(mol),
    }
