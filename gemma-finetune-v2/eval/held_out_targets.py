"""
Held-out evaluation targets — NOT used in training data.
Each entry has: name, uniprot_id, fasta (full or 400 AA), known_drugs (positive controls).
Used by Tier 2 (target-conditioned generation + MAMMAL scoring).
"""

HELD_OUT_TARGETS = [
    {
        "name": "SARS-CoV-2 Main Protease (Nsp5)",
        "uniprot_id": "P0DTD1",
        "disease": "COVID-19",
        "fasta": (
            "SGFRKMAFPSGKVEGCMVQVTCGTTTLNGLWLDDVVYCPRHVICTSEDMLNPNYEDLLIRKSNHNFLVQAGNVQLRVIGHSMQNCVLKLKVDTANPKTPKYKFVRIQPGQTFSVLACYNGSPSGVYQCAMRPNFTIKGSFLNGSCGSVGFNIDYDCVSFCYMHHMELPTGVHAGTDLEGNFYGPFVDRQTAQAAGTDTTITVNVLAWLYAAVINGDRWFLNRFTTTLNDFNLVAMKYNYEPLTQDHVDILGPLSAQTGIAVLDMCASLKELLQNGMNGRTILGSALLEDEFTPFDVVRQCSGVTFQ"
        ),
        "known_drugs": [
            # Nirmatrelvir (Paxlovid component) - covalent inhibitor, IC50 ~22 nM
            "CC1(C2CC2NC(=O)C(F)(F)F)C(=O)N[C@@H](Cc2ccc(C#N)cc2)C1=O",
            # GC-376 - another MPro inhibitor
            "CC(C)[C@@H](CC(=O)c1ccc(S(N)(=O)=O)cc1)NC(=O)[C@@H]1CC(=O)N1",
        ],
        "prompt_template": (
            "Target: SARS-CoV-2 Main Protease (Nsp5) — COVID-19 drug target\n"
            "Protein sequence (first 300 AA): {fasta}\n"
            "The active site contains a catalytic Cys145-His41 dyad. "
            "Design 4 small-molecule inhibitors with MW 300-500 Da, QED > 0.55, SAS ≤ 5.0. "
            "First explain your structural reasoning, then provide SMILES."
        ),
    },
    {
        "name": "EGFR T790M (Gatekeeper mutant)",
        "uniprot_id": "P00533",
        "disease": "Non-small cell lung cancer",
        "fasta": (
            "MRPSGTAGAALLALLAALCPASRALEEKKVCQGTSNKLTQLGTFEDHFLSLQRMFNNCEVVLGNLEITYVQRNYDLSFLKT"
            "IQEVAGYVLIALNTVERIPLENLQIIRGNMYYENSYALAVLSNYDANKTGLKELPMRNLQEILHGAVRFSNNPALCNVESI"
            "QWRDIVSSDFLSNMSMDFQNHLGSCQKCDPSCPNGSCWGAGEENCQKLTKIICAQQCSGRCRGKSPSDCCHNQCAAGCTG"
            "PRESDCLVCRKFRDEATCKDTCPPLMLYNPTTYQMDVNPEGKYSFGATCVKKCPRNYVVTDHGSCVRACGADSYEMEEDG"
        ),
        "known_drugs": [
            # Osimertinib (3rd gen EGFR, targets T790M), IC50 ~1 nM
            "C=CC(=O)Nc1cc2c(Nc3ccc(F)c(Cl)c3)ncnc2cc1OCC[NH+]1CC[NH+](C)CC1",
            # Erlotinib (1st gen), IC50 ~2 nM wild-type
            "C#Cc1cccc(Nc2ncnc3cc(OCC)c(OCC)cc23)c1",
        ],
        "prompt_template": (
            "Target: EGFR Kinase (T790M resistance mutant) — lung cancer\n"
            "Protein sequence (first 320 AA): {fasta}\n"
            "T790M substitution sterically blocks 1st/2nd gen inhibitors. "
            "Design 4 covalent or allosteric inhibitors overcoming T790M. "
            "Explain your resistance mechanism reasoning, then provide SMILES."
        ),
    },
    {
        "name": "CDK2 / Cyclin E complex",
        "uniprot_id": "P24941",
        "disease": "Cancer (cell cycle dysregulation)",
        "fasta": (
            "MENFQKVEKIGEGTYGVVYKARNKLTGEVVALKKIRLDTETEGVPSTAIREISLLKELNHPNIVKLLDVIHTENKLYLVFE"
            "FLHQDLKKFMDASALTGIPLPLIKSYLFQLLQGLAFCHSHRVLHRDLKPQNLLIDKEGYQLKLADFGLARAREFDSAGSFY"
            "MAEIVTLWYRAPEVLLGSTKYTSTDIWALGCLLYKLCYFTLPFGESQAIYNILMKDGNLRVDQKSLYLKDYNRVDPEFRNL"
            "SGQVSDPDMDFSGSTESSDLAAENQAAHSISKELDRSDWQNEQFQVGRRGGSMHFHLFPNHNEDEAQASMLQLSRGPASATA"
        ),
        "known_drugs": [
            # Palbociclib (CDK4/6 - close family), for reference
            "Cc1cn(-c2cc3c(cc2=O)N(C)c2ccc(F)cc2C3=O)cn1",
            # Roscovitine (CDK2 inhibitor), IC50 ~0.1 µM
            "CCn1cnc2c(Nc3cccc(c3)C(C)C)nc(NCC=C)nc21",
        ],
        "prompt_template": (
            "Target: CDK2 (Cyclin-Dependent Kinase 2) — cancer cell cycle target\n"
            "Protein sequence (first 320 AA): {fasta}\n"
            "CDK2 has a conserved ATP-binding pocket with Leu83 hinge residue. "
            "Design 4 ATP-competitive inhibitors selective over CDK1. "
            "Reason about selectivity strategy first, then provide SMILES."
        ),
    },
    {
        "name": "DPP-4 (Dipeptidyl Peptidase 4)",
        "uniprot_id": "P27487",
        "disease": "Type 2 Diabetes",
        "fasta": (
            "MKTPWKVLLGLLGAAALVTIITVPVVLLNKGTDDATADSRKTYTLTNKNVFEGQTLDATLYHYQMNRRVFPVTGESMLKV"
            "THKLEDGKSVVFNSTLMRSQRMAVSEGQTLALVQHKNITVYIDASAVNDFSSLQYDQSIMNLTYRTNESFIQGKFPKIYP"
            "SFEKVELRQNLNSGPFPQILRDINVNFTYLGSEPMTLQALVQHLKKSDKTEAMLQFIKDRQGKEMPTYSPIKAFLESVKY"
            "SGETTLREAANEVGFYAIVNTVQRYLSQDPANLKHLTEAQNRLHQELKEREKEKLKDARKDFLQSLKDLKDSVHNNVKEL"
        ),
        "known_drugs": [
            # Sitagliptin (Januvia), IC50 ~18 nM
            "Fc1cc(CC(N)CC(=O)N2CC(F)(F)c3ccccc3C2=O)ccc1F.[H]C(=O)O",
            # Saxagliptin, IC50 ~50 nM
            "N#C[C@@H]1C[C@H]1NC(=O)[C@@H](N)C1(O)CC1",
        ],
        "prompt_template": (
            "Target: DPP-4 (Dipeptidyl Peptidase 4) — type 2 diabetes\n"
            "Protein sequence (first 320 AA): {fasta}\n"
            "DPP-4 has a Ser630-Asp708-His740 catalytic triad. "
            "Design 4 competitive inhibitors with selectivity over DPP-8/9. "
            "Explain your pharmacophore design strategy first, then provide SMILES."
        ),
    },
    {
        "name": "BACE1 (Beta-secretase 1)",
        "uniprot_id": "P56817",
        "disease": "Alzheimer's Disease",
        "fasta": (
            "MAQALPWLLLWMGAGVLPAHGTQHGIRLPLRSGLGGAPLGLRLPRETDEEPEEPGRRGSFVEMVDNLRGKSGQGYYVEMTV"
            "GSPPQTLNILTDPQITATSLTLFHPFCLQAQDDQKIAVIGGHVVKDSYMEAVEQGLKPGQSVVVLKDQFEVQKLAHDKYR"
            "EQISRKLKDLASQRFGIFQKHTNQIIFNQDKHLIDLHHDLIGGQNTYYSYSNEDAGFRWAQEAEGVKADLMVAFPFYQEH"
            "RTLAEAFLAAQFHLHTQEQIKDSTDLSEHCNLDEKKERRQALRESLLNKTIAHIPEKRVISESQGQRWIFIDQVKANLPEP"
        ),
        "known_drugs": [
            # Lanabecestat (AZ/Eli Lilly BACE1 inhibitor, clinical-stage)
            "Cc1cc(F)ccc1-c1cc(C(F)(F)F)nn1-c1ccc(OCC2CC2)cc1",
            # Verubecestat (Merck, discontinued)
            "FC(F)(F)c1cc(-c2cc(C#N)c(N)n2-c2cccc(F)c2F)ccn1",
        ],
        "prompt_template": (
            "Target: BACE1 (Beta-secretase 1) — Alzheimer's disease\n"
            "Protein sequence (first 320 AA): {fasta}\n"
            "BACE1 is an aspartyl protease with Asp32-Asp228 catalytic dyad. "
            "Design 4 CNS-penetrant inhibitors: MW < 450, PSA < 90, LogP 1-4. "
            "Explain your BBB permeability and selectivity strategy, then provide SMILES."
        ),
    },
]
