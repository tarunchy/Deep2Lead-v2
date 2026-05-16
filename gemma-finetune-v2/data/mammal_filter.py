"""
IBM MAMMAL binding affinity filter — remote API client.
Calls the MAMMAL FastAPI service running on dlyog03:8090.

dlyog03 hosts: ibm/biomed.omics.bl.sm.ma-ted-458m (458M, Apache 2.0)
dgx1 calls it over LAN (192.168.86.0/24) during training data curation.

Usage:
    from data.mammal_filter import MAMMALFilter
    f = MAMMALFilter()
    kept = f.filter_pairs(pairs)   # pairs = list of (fasta, smiles) tuples
"""

import logging
import os
import time
from typing import Optional

import requests

log = logging.getLogger(__name__)

MAMMAL_API_HOST    = os.getenv("MAMMAL_API_HOST", "192.168.86.20")
MAMMAL_API_PORT    = int(os.getenv("MAMMAL_API_PORT", "8090"))
MAMMAL_API_BASE    = f"http://{MAMMAL_API_HOST}:{MAMMAL_API_PORT}"
MAMMAL_BATCH_SIZE  = int(os.getenv("MAMMAL_BATCH_SIZE", "20"))   # pairs per API call
MAMMAL_TIMEOUT     = int(os.getenv("MAMMAL_TIMEOUT", "300"))     # seconds per batch


class MAMMALFilter:
    """Remote client for IBM MAMMAL DTI scoring on dlyog03."""

    def __init__(self, threshold: float = 0.70):
        self.threshold = threshold
        self._verified = False

    def _verify_api(self) -> bool:
        """Check MAMMAL API is reachable and ready."""
        if self._verified:
            return True
        try:
            r = requests.get(f"{MAMMAL_API_BASE}/health", timeout=10)
            data = r.json()
            if data.get("status") != "ready":
                log.warning(f"MAMMAL API not ready: status={data.get('status')}")
                return False
            log.info(f"MAMMAL API ready at {MAMMAL_API_BASE} — GPU: {data.get('gpu')}")
            self._verified = True
            return True
        except Exception as e:
            log.error(f"MAMMAL API unreachable at {MAMMAL_API_BASE}: {e}")
            return False

    def score_pair(self, fasta: str, smiles: str) -> float:
        """Score a single (fasta, smiles) pair. Returns probability [0, 1]."""
        if not self._verify_api():
            raise RuntimeError(f"MAMMAL API not available at {MAMMAL_API_BASE}")
        try:
            r = requests.post(
                f"{MAMMAL_API_BASE}/predict-binding",
                json={"fasta": fasta, "smiles": smiles},
                timeout=MAMMAL_TIMEOUT,
            )
            r.raise_for_status()
            return r.json()["score"]
        except Exception as e:
            log.warning(f"MAMMAL score_pair error: {e}")
            return 0.0

    def filter_pairs(self, pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """
        pairs: list of (fasta_seq, smiles_str)
        Returns the subset where MAMMAL affinity score >= threshold.
        Sends pairs to dlyog03 in batches for efficiency.
        """
        if not self._verify_api():
            log.error("MAMMAL API unreachable — cannot filter pairs. Returning empty list.")
            return []

        kept    = []
        dropped = 0
        total   = len(pairs)

        log.info(f"MAMMAL filter: {total} pairs, threshold={self.threshold}, batch_size={MAMMAL_BATCH_SIZE}")

        for batch_start in range(0, total, MAMMAL_BATCH_SIZE):
            batch = pairs[batch_start:batch_start + MAMMAL_BATCH_SIZE]
            batch_payload = {
                "pairs": [{"fasta": f, "smiles": s} for f, s in batch]
            }
            try:
                t0 = time.time()
                r = requests.post(
                    f"{MAMMAL_API_BASE}/predict-batch",
                    json=batch_payload,
                    timeout=MAMMAL_TIMEOUT,
                )
                r.raise_for_status()
                results = r.json()["results"]
                elapsed = time.time() - t0

                for (fasta, smiles), result in zip(batch, results):
                    if result["score"] >= self.threshold:
                        kept.append((fasta, smiles))
                    else:
                        dropped += 1

                processed = min(batch_start + MAMMAL_BATCH_SIZE, total)
                log.info(
                    f"  MAMMAL filter: {processed}/{total} processed | "
                    f"kept={len(kept)} dropped={dropped} | "
                    f"batch time={elapsed:.1f}s"
                )

            except Exception as e:
                log.warning(f"  MAMMAL batch error (skipping batch {batch_start}): {e}")
                dropped += len(batch)

        log.info(f"MAMMAL filter complete: kept {len(kept)}/{total} pairs (dropped {dropped})")
        return kept


def load_mammal_filter_or_passthrough(threshold: float = 0.70) -> Optional[MAMMALFilter]:
    """
    Returns MAMMALFilter if dlyog03 API is reachable and ready, else None.
    None means: skip MAMMAL gating (training still runs but without affinity filter).
    """
    f = MAMMALFilter(threshold=threshold)
    if f._verify_api():
        return f
    log.warning(
        f"MAMMAL API not reachable at {MAMMAL_API_BASE}. "
        "Training will proceed without affinity gating. "
        "Start the API on dlyog03: bash /home/dlyog/apps/ibm_biomed/start.sh"
    )
    return None
