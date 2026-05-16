"""
IBM MAMMAL binding affinity filter for v2 training data curation.
Model: ibm/biomed.omics.bl.sm.ma-ted-458m (458M, Apache 2.0)
Paper: https://arxiv.org/abs/2410.22367

Uses the MAMMAL DTI (Drug-Target Interaction) task to score each
protein FASTA + SMILES pair. Pairs scoring below the threshold are
dropped before they reach Gemma's training set.

Install dependency:
    pip install git+https://github.com/BiomedSciAI/biomed-multi-alignment.git

Usage:
    from data.mammal_filter import MAMMALFilter
    f = MAMMALFilter()
    keep = f.filter_pairs(pairs)  # pairs = list of (fasta, smiles) tuples
"""

import sys
import logging

log = logging.getLogger(__name__)

MAMMAL_MODEL_ID = "ibm/biomed.omics.bl.sm.ma-ted-458m"


class MAMMALFilter:
    """Wraps IBM MAMMAL for batch binding affinity scoring."""

    def __init__(self, threshold: float = 0.70, device: str = "cuda"):
        self.threshold = threshold
        self.device    = device
        self._model    = None
        self._tok      = None

    def _load(self):
        if self._model is not None:
            return
        try:
            import torch
            from mammal.model import Mammal
            from fuse.data.tokenizers.modular_tokenizer.op import ModularTokenizerOp

            log.info(f"Loading IBM MAMMAL from {MAMMAL_MODEL_ID} ...")
            self._model = Mammal.from_pretrained(MAMMAL_MODEL_ID)
            self._model.eval()
            if self.device == "cuda":
                import torch
                self._model = self._model.cuda()
            self._tok = ModularTokenizerOp.from_pretrained(MAMMAL_MODEL_ID)
            log.info("MAMMAL loaded.")
        except ImportError:
            log.error(
                "biomed-multi-alignment not installed. "
                "Run: pip install git+https://github.com/BiomedSciAI/biomed-multi-alignment.git"
            )
            raise

    def score_pair(self, fasta: str, smiles: str) -> float:
        """
        Returns a binding affinity probability in [0, 1].
        Uses MAMMAL's BINDING_AFFINITY_CLASS task in generation mode.
        """
        self._load()
        import torch
        from mammal.keys import (
            ENCODER_INPUTS_STR, ENCODER_INPUTS_TOKENS, ENCODER_INPUTS_ATTENTION_MASK,
            CLS_PRED,
        )

        fasta_trimmed = fasta[:512]   # cap length for memory safety

        sample = {
            ENCODER_INPUTS_STR: (
                f"<@TOKENIZER-TYPE=AA><BINDING_AFFINITY_CLASS><SENTINEL_ID_0>"
                f"<MOLECULAR_ENTITY><MOLECULAR_ENTITY_GENERAL_PROTEIN>"
                f"<SEQUENCE_NATURAL_START>{fasta_trimmed}<SEQUENCE_NATURAL_END>"
                f"<MOLECULAR_ENTITY><MOLECULAR_ENTITY_SMALL_MOLECULE>"
                f"<SEQUENCE_NATURAL_START>{smiles}<SEQUENCE_NATURAL_END><EOS>"
            )
        }

        self._tok(
            sample_dict=sample,
            key_in=ENCODER_INPUTS_STR,
            key_out_tokens_ids=ENCODER_INPUTS_TOKENS,
            key_out_attention_mask=ENCODER_INPUTS_ATTENTION_MASK,
        )
        sample[ENCODER_INPUTS_TOKENS] = torch.tensor(sample[ENCODER_INPUTS_TOKENS])
        sample[ENCODER_INPUTS_ATTENTION_MASK] = torch.tensor(sample[ENCODER_INPUTS_ATTENTION_MASK])

        if self.device == "cuda":
            sample[ENCODER_INPUTS_TOKENS] = sample[ENCODER_INPUTS_TOKENS].cuda()
            sample[ENCODER_INPUTS_ATTENTION_MASK] = sample[ENCODER_INPUTS_ATTENTION_MASK].cuda()

        with torch.no_grad():
            batch = self._model.generate(
                [sample],
                output_scores=True,
                return_dict_in_generate=True,
                max_new_tokens=5,
            )

        decoded = self._tok._tokenizer.decode(batch[CLS_PRED][0])
        try:
            return float(decoded.strip())
        except ValueError:
            # If output is a class label like "high"/"low", map it
            text = decoded.strip().lower()
            if "high" in text or "active" in text or "binder" in text:
                return 0.85
            return 0.30   # conservative — mark as low affinity

    def filter_pairs(self, pairs: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """
        pairs: list of (fasta_seq, smiles_str)
        Returns subset where MAMMAL affinity score >= threshold.
        """
        self._load()
        kept = []
        dropped = 0
        for i, (fasta, smiles) in enumerate(pairs):
            if i % 100 == 0:
                log.info(f"  MAMMAL filter: {i}/{len(pairs)} processed, {dropped} dropped ...")
            try:
                score = self.score_pair(fasta, smiles)
                if score >= self.threshold:
                    kept.append((fasta, smiles))
                else:
                    dropped += 1
            except Exception as e:
                log.warning(f"  MAMMAL score error (skipping pair): {e}")
                dropped += 1
        log.info(f"MAMMAL filter: kept {len(kept)}/{len(pairs)} pairs (dropped {dropped})")
        return kept


def load_mammal_filter_or_passthrough(threshold: float = 0.70) -> "MAMMALFilter | None":
    """
    Returns MAMMALFilter if biomed-multi-alignment is installed, else None.
    Callers should check: if filter is None → skip MAMMAL gating.
    """
    try:
        import mammal  # noqa: F401
        return MAMMALFilter(threshold=threshold)
    except ImportError:
        log.warning(
            "biomed-multi-alignment not installed — MAMMAL filter disabled. "
            "Training will proceed without affinity gating (lower data quality expected). "
            "Install: pip install git+https://github.com/BiomedSciAI/biomed-multi-alignment.git"
        )
        return None
