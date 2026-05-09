import re

VALID_AA = set("ACDEFGHIKLMNPQRSTVWY")


def is_valid_sequence(seq: str) -> bool:
    if not seq or len(seq) < 5:
        return False
    return all(c.upper() in VALID_AA for c in seq.strip())


def clean_sequence(seq: str) -> str:
    return re.sub(r"\s+", "", seq).upper()
