from rdkit import Chem
from rdkit import RDLogger

RDLogger.DisableLog("rdApp.*")


def canonicalize(smiles: str) -> str | None:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return Chem.MolToSmiles(mol, canonical=True)


def is_valid(smiles: str) -> bool:
    return Chem.MolFromSmiles(smiles) is not None


def mol_to_svg(smiles: str, size: tuple = (300, 200)) -> str | None:
    from rdkit.Chem import Draw
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    from rdkit.Chem.Draw import rdMolDraw2D
    drawer = rdMolDraw2D.MolDraw2DSVG(size[0], size[1])
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()
