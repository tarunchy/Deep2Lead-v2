"""
Build Deep2Lead custom instruction dataset for v2.
v2 changes:
  - All responses use rationale-first format (chain-of-thought before SMILES)
  - New template: cross_modal_design — protein pocket + property constraints together
  - New template: scaffold_hop — given reference drug, design structurally distinct analogue
  - Generates ~1,200 records (300 targets × 4 templates)

Usage:
    python3 data/build_custom_dataset_v2.py
"""

import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import TARGETS_JSON_PATH, CUSTOM_DATASET_PATH
from data.dataset_utils import to_rationale_chatml, to_gemma4_chatml, save_jsonl, SYSTEM_PROMPT


def load_targets() -> list:
    path = os.path.abspath(TARGETS_JSON_PATH)
    if not os.path.exists(path):
        print(f"Targets file not found: {path} — using built-in targets.")
        return _builtin_targets()
    with open(path) as f:
        return json.load(f)


def _builtin_targets() -> list:
    return [
        {
            "name": "SARS-CoV-2 Main Protease",
            "category": "viral protease",
            "known_drug": "Nirmatrelvir",
            "known_drug_smiles": "CC1(C2CC2NC(=O)C(F)(F)F)C(=O)N[C@@H](Cc2ccc(C#N)cc2)C1=O",
            "starter_smiles": "CC1CC1NC(=O)C(F)(F)F",
            "amino_acid_seq": "MESLVPGFNEKTHVQLSLPVLQVRDVLVRGFGDSVEEVLSEARQHLK",
            "description": "Essential cysteine protease for viral polyprotein cleavage.",
        },
        {
            "name": "EGFR Kinase",
            "category": "receptor tyrosine kinase",
            "known_drug": "Erlotinib",
            "known_drug_smiles": "C#Cc1cccc(c1)Nc2ncnc3cc(OCC)c(OCC)cc23",
            "starter_smiles": "c1cnc2cccc(c2n1)N",
            "amino_acid_seq": "MRPSGTAGAALLALLAALCPASRALEEKKVCQGTSNKLTQLGTFEDHFLSLQRMFNNCEVVLGNLEITYVQRNYDLSFLKTIQEVAGYVLIALNTVERIPLENLQIIRGNMYYENSYALAVLSNYDANKTGLKELPMRNLQEILHGAVRFSNNPALCNVESIQWRDIVSSDFLSNMSMDFQNHLGSCQKCDPSCPNGSCWGAGEENCQKLTKIICAQQCSGRCRGKSPSDCCHNQCAAGCTGPRESDCLVCRKFRDEATCKDTCPPLMLYNPTTYQMDVNPEGKYSFGATCVKKCPRNYVVTDHGSCVRACGADSYEMEEDGVRKCKKCEGPCRKVCNGIGIGEFKDSLSINATNIKHFKNCTSISGDLHILPVAFRGDSFTHTPPLDPQELDILKTVKEITGFLLIQAWPENRTDLHAFENLEIIRGRTKQHGQFSLAVVSLNITSLGLRSLKEISDGDVIISGNKNLCYANTINWKKLFGTSGQKTKIISNRGENSCKATGQVCHALCSPEGCWGPEPRDCVSCRNVSRGRECVDKCNLLEGEPREFVENSECIQCHPECLPQAMNITCTGRGPDNCIQCAHYIDGPHCVKTCPAGVMGENNTLVWKYADAGHVCHLCHPNCTYGCTGPGLEGCPTNGPKIPSIATGMVGALLLLLVVALGIGLFMRRRHIVRKRTLRRLLQERELVEPLTPSGEAPNQALLRILKETEFKKIKVLGSGAFGTVYKGLWIPEGEKVKIPVAIKELREATSPKANKEILDEAYVMASVDNPHVCRLLGICLTSTVQLITQLMPFGCLLDYVREHKDNIGSQYLLNWCVQIAKGMNYLEDRRLVHRDLAARNVLVKTPQHVKITDFGLAKLLGAEEKEYHAEGGKVPIKWMALESILHRIYTHQSDVWSYGVTVWELMTFGSKPYDGIPASEISSILEKGERLPQPPICTIDVYMIMVKCWMIDADSRPKFRELIIEFSKMARDPQRYLVIQGDERMHLPSPTDSNFYRALMDEEDMDDVVDADEYLIPQQGFFSSPSTSRTPLLSSLSATSNNSTVACIDRNGLQSCPIKEDSFLQRYSSDPTGALTEDSIDDTFLPVPEYINQSVPKRPAGSVQNPVYHNQPLNPAPSRDPHYQDPHSTAVGNPEYLNTVQPTCVNSTFDSPAHWAQKGSHQISLDNPDYQQDFFPKEAKPNGIFKGSTAENAEYLRVAPQSSEFIGA",
            "description": "Mutated in ~15% of NSCLC; T790M mutation confers erlotinib resistance.",
        },
        {
            "name": "BRAF V600E",
            "category": "serine/threonine kinase",
            "known_drug": "Vemurafenib",
            "known_drug_smiles": "CCCS(=O)(=O)Nc1ccc(cc1F)-c1cc2c(n1)NN=C(c1ccncc1)C2",
            "starter_smiles": "c1ccc(-c2cc3ccccc3[nH]2)cc1",
            "amino_acid_seq": "MAHHHHHHHHHHHIEGRHHHKLVWFPGGAETAERAGQIRGASMKFVALFAVHFAATITLAAIVTARIIYSFVSTNKL",
            "description": "Oncogenic mutation driving ~50% of melanoma cases.",
        },
        {
            "name": "BCR-ABL Kinase",
            "category": "tyrosine kinase",
            "known_drug": "Imatinib",
            "known_drug_smiles": "Cc1ccc(cc1Nc2nccc(n2)c3cccnc3)NC(=O)c4ccc(cc4)CN5CCN(CC5)C",
            "starter_smiles": "c1ccncc1NC(=O)c1ccccc1",
            "amino_acid_seq": "MGSSHHHHHHSSGLVPRGSHMRGPNARRGPPAAPPAPPASTSGGSPAGGSSPAGGSSPAGGSGYGFGANRGRGRGRGRGRG",
            "description": "Fusion kinase driving CML; imatinib resistance via T315I gatekeeper mutation.",
        },
        {
            "name": "HIV-1 Protease",
            "category": "aspartyl protease",
            "known_drug": "Ritonavir",
            "known_drug_smiles": "CC(C)c1nc(CN(C)C(=O)N[C@@H](Cc2ccccc2)[C@@H](O)C[C@@H](Cc2ccccc2)NC(=O)[C@@H](CC(C)C)NC(=O)c2nc3ccccc3s2)cs1",
            "starter_smiles": "CC(C)C[C@@H](NC(=O)c1nc2ccccc2s1)C(=O)O",
            "amino_acid_seq": "PQITLWQRPLVTIKIGGQLKEALLDTGADDTVLEEMSLPGRWKPKMIGGIGGFIKVRQYDQILIEICGHKAIGTVLVGPTPVNIIGRNLLTQIG",
            "description": "Catalyzes viral polyprotein maturation; 99 residue homodimer.",
        },
    ]


# ── Rationale pool by target category ──────────────────────────────────────────

_RATIONALE_BY_CATEGORY = {
    "viral protease": [
        "Viral cysteine proteases require a warhead group that engages the nucleophilic cysteine. "
        "A nitrile or aldehyde electrophile provides reversible covalent binding while a bicyclic "
        "P2 cap fills the S2 hydrophobic pocket for selectivity over human proteases.",
        "The substrate recognition groove of this protease is rigid and well-defined. "
        "A lactam or cyclopropane P2 motif provides pre-organized backbone geometry, "
        "reducing entropic cost of binding. The P1' group exploits the glutamine preference of the S1 subsite.",
    ],
    "receptor tyrosine kinase": [
        "Kinase hinge region binding is achieved via 1-2 hydrogen bonds to backbone NH/C=O. "
        "A 4-anilinoquinazoline or 4-aminopyrimidine scaffold provides this interaction while "
        "hydrophobic substituents fill the back pocket beyond the gatekeeper residue.",
        "The active conformation DFG-in state exposes a deep hydrophobic cavity. "
        "An acrylamide warhead enables irreversible covalent engagement of Cys797 in the αC-helix, "
        "giving durable target suppression beyond the ATP competition window.",
    ],
    "serine/threonine kinase": [
        "The V600E mutation creates a constitutively active DFG-out conformation, exposing an "
        "allosteric back-pocket. A sulfonamide-propylamine tail exploits polar contacts in this "
        "induced pocket, delivering selectivity over wild-type BRAF and CRAF.",
        "Type II kinase inhibitors lock the DFG loop in the out conformation. A meta-chlorophenyl "
        "group fills the hydrophobic pocket formed when Asp moves away from the ATP site, "
        "and an amide NH provides the key hydrogen bond to Glu501.",
    ],
    "tyrosine kinase": [
        "The BCR-ABL active site in the inactive conformation reveals a unique hydrophobic groove "
        "adjacent to the Asp-Phe-Gly loop. A 2-phenylaminopyrimidine core bridges the hinge, "
        "a benzamide arm contacts the hydrophobic cleft, and a piperazine tail improves aqueous solubility.",
        "Gatekeeper mutation T315I expands the binding pocket at the cost of losing the key threonine "
        "OH interaction. A bulkier, more flexible back-pocket group accommodating the isoleucine "
        "side-chain maintains potency against this resistance mutant.",
    ],
    "aspartyl protease": [
        "Both catalytic aspartates require a transition-state isostere — a hydroxyethylamine or "
        "hydroxyethylene — positioned to mimic the gem-diol tetrahedral intermediate. "
        "Flanking hydrophobic residues fill S2/S2' pockets for >nM affinity.",
        "The P1/P1' subsites of retroviral proteases accommodate bulky aromatic groups. "
        "An inhibitor with a C2-symmetric core maximises van der Waals contacts with the homodimer "
        "while a polar solubilising tail prevents excessive lipophilicity.",
    ],
    "default": [
        "The binding pocket analysis suggests a rigid bicyclic core for entropy minimisation, "
        "with polar contacts exploited by a hydrogen-bond donor at the 3-position. "
        "A flexible alkyl chain provides aqueous solubility balance.",
        "Structural complementarity to the active site requires matching both shape and electrostatics. "
        "An aromatic scaffold pi-stacks with Phe/Tyr residues while a carboxamide linker "
        "forms a salt bridge with the conserved Lys.",
    ],
}

def _get_rationale(category: str) -> str:
    pool = _RATIONALE_BY_CATEGORY.get(category.lower(), _RATIONALE_BY_CATEGORY["default"])
    return random.choice(pool)


# ── Template builders ──────────────────────────────────────────────────────────

def target_rationale_v2(target: dict) -> dict:
    name     = target.get("name", "Unknown Target")
    category = target.get("category", "enzyme")
    known    = target.get("known_drug", "")
    ksmiles  = target.get("known_drug_smiles", "")
    desc     = target.get("description", "")
    seq      = target.get("amino_acid_seq", "")[:120]

    user = (
        f"Target: {name} ({category})\n"
        f"Protein sequence (first 120 AA): {seq}\n"
        f"Context: {desc}\n"
        f"Reference drug: {known} (SMILES: {ksmiles})\n"
        "Design 3 novel SMILES candidates that could improve on the reference drug. "
        "First explain your structural reasoning, then provide the SMILES strings."
    )
    rationale = _get_rationale(category)
    variants  = _generate_synthetic_variants(ksmiles, 3)
    return to_rationale_chatml(user, rationale, variants, system=SYSTEM_PROMPT)


def scaffold_hop(target: dict) -> dict:
    """v2 new template: generate structurally distinct scaffold from reference drug."""
    name   = target.get("name", "Unknown Target")
    ksmiles = target.get("known_drug_smiles", "CC(=O)O")
    known  = target.get("known_drug", "reference drug")
    category = target.get("category", "enzyme")

    user = (
        f"Target: {name}\n"
        f"Reference drug to escape: {known} (SMILES: {ksmiles})\n"
        "Perform a scaffold hop: design 2 structurally distinct molecules that maintain "
        "the key pharmacophore features but use a completely different core ring system. "
        "Avoid IP conflict with the reference. First explain the bioisostere strategy, then provide SMILES."
    )
    rationale = (
        f"A scaffold hop from {known} replaces the core ring system while preserving the "
        "essential hydrogen-bond donor/acceptor pattern and hydrophobic vector. "
        "A fused bicyclic heterocycle substitutes the original scaffold, maintaining "
        "spatial arrangement of key pharmacophore elements with improved IP freedom."
    )
    variants = _generate_synthetic_variants(ksmiles, 2)
    return to_rationale_chatml(user, rationale, variants, system=SYSTEM_PROMPT)


def cross_modal_design(target: dict) -> dict:
    """v2 new template: protein sequence + multi-property constraints simultaneously."""
    name     = target.get("name", "Unknown Target")
    category = target.get("category", "enzyme")
    seq      = target.get("amino_acid_seq", "")[:150]
    seed     = target.get("starter_smiles", "CC(=O)O")

    mw_target   = random.choice([350, 400, 450])
    qed_target  = round(random.uniform(0.55, 0.75), 2)
    logp_target = round(random.uniform(2.0, 4.0), 1)

    user = (
        f"Design a drug candidate for {name} ({category}) with these simultaneous constraints:\n"
        f"• Protein target (first 150 AA): {seq}\n"
        f"• MW ≈ {mw_target} Da (±25 Da tolerance)\n"
        f"• LogP ≈ {logp_target} (±0.5)\n"
        f"• QED ≥ {qed_target}\n"
        f"• Inspired by but distinct from: {seed}\n"
        "Reason about how you balance the structural requirements, then output the SMILES."
    )
    rationale = _get_rationale(category)
    variants  = _generate_synthetic_variants(seed, 3)
    return to_rationale_chatml(user, rationale, variants, system=SYSTEM_PROMPT)


def game_explanation_v2(target: dict) -> dict:
    """Game-style feedback explanation — high school friendly, still uses rationale format."""
    name   = target.get("name", "target protein")
    seed   = target.get("starter_smiles", "")
    mols   = _generate_synthetic_variants(seed, 1)
    new_mol = mols[0] if mols else seed

    user = (
        f"Previous molecule: {seed} | Score: 0.42\n"
        f"New molecule: {new_mol} | Score: 0.68\n"
        f"Target: {name}\n"
        "Explain why the new molecule scored better. Keep it understandable for a high school student."
    )
    rationale = (
        "The structural change improved the fit between the molecule and the target protein. "
        "The new functional group acts like an extra 'grip' that locks onto a key part of the protein. "
        "In chemistry terms, it forms an additional hydrogen bond with a critical residue in the binding site, "
        "lowering the binding energy and increasing the predicted inhibition constant."
    )
    return to_rationale_chatml(user, rationale, [new_mol], system=SYSTEM_PROMPT)


# ── Synthetic SMILES variants ──────────────────────────────────────────────────

_FRAGMENTS = [
    "C", "CC", "CCO", "c1ccccc1", "C(=O)N", "NC(=O)",
    "OC", "FC", "ClC", "C1CCCC1", "C(F)(F)F", "c1ccncc1",
    "C1CCOCC1",  # morpholine
]

def _generate_synthetic_variants(seed_smiles: str, n: int) -> list[str]:
    results = []
    base = seed_smiles or "CC(=O)O"
    modifications = [
        lambda s: s.replace("C", "CC", 1),
        lambda s: s + "O",
        lambda s: s + "N",
        lambda s: "F" + s,
        lambda s: s.replace("O", "S", 1) if "O" in s else s + "S",
        lambda s: s + "C(=O)N",
        lambda s: s + "c1ccccc1",
        lambda s: "C(F)(F)F" + s,
        lambda s: s + "C1CCOCC1",
    ]
    random.seed(hash(seed_smiles) % (2**31))
    chosen = random.sample(modifications, min(n, len(modifications)))
    for mod in chosen:
        try:
            variant = mod(base)
            if variant != base:
                results.append(variant)
        except Exception:
            pass
    while len(results) < n:
        frag = random.choice(_FRAGMENTS)
        results.append(base + frag)
    return results[:n]


# ── Main ───────────────────────────────────────────────────────────────────────

def build(targets_per_type: int = 1) -> list:
    targets = load_targets()
    print(f"Building v2 custom dataset from {len(targets)} targets ...")

    records = []
    for t in targets:
        for _ in range(targets_per_type):
            records.append(target_rationale_v2(t))
            records.append(scaffold_hop(t))
            records.append(cross_modal_design(t))
            records.append(game_explanation_v2(t))

    random.seed(42)
    random.shuffle(records)
    print(f"Generated {len(records):,} v2 custom instruction pairs")
    return records


if __name__ == "__main__":
    records = build(targets_per_type=3)
    os.makedirs(os.path.dirname(CUSTOM_DATASET_PATH) or ".", exist_ok=True)
    save_jsonl(records, CUSTOM_DATASET_PATH)
    print(f"\nSaved → {CUSTOM_DATASET_PATH}")
    print("Tip: run download_datasets_v2.py next to merge into full training set.")
