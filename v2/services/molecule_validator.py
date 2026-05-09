from rdkit import Chem
from utils.mol_utils import canonicalize, is_valid


def validate_and_canonicalize(smiles: str) -> str | None:
    return canonicalize(smiles)


def filter_candidates(smiles_list: list[str], seed_smile: str) -> list[str]:
    seed_canon = canonicalize(seed_smile)
    seen = set()
    result = []
    for s in smiles_list:
        canon = canonicalize(s.strip())
        if canon and canon not in seen and canon != seed_canon:
            seen.add(canon)
            result.append(canon)
    return result
