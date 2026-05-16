The paper shown in the image is an open-access study from IBM Research, officially published on May 4, 2026, in Nature's npj Drug Discovery journal.

Here are the details and how you can access it:

Paper Citation
Title: MAMMAL - Molecular Aligned Multi-Modal Architecture and Language for biomedical discovery

Authors: Yoel Shoshan, Moshiko Raboh, Michal Ozery-Flato, Vadim Ratner, et al.

Journal: npj Drug Discovery 3, Article number: 14 (2026)

Core Overview of the Paper
What is MAMMAL? It is a unified biomedical foundation model developed by IBM to cross-align "messy" and disparate parts of biology that are usually fragmented across separate AI tools.

Data Scale: It was pre-trained on 2 billion biological samples across small molecules, protein sequences, antibody sequences, and transcriptomic (gene expression) profiles.

Performance: Across 11 key drug-discovery benchmarks, the fine-tuned model achieved state-of-the-art (SOTA) results on 9 tasks and highly competitive results on the remaining 2.

The AlphaFold 3 Comparison: In specific antibody-antigen binding tests, fine-tuned MAMMAL prediction scores actually outperformed AlphaFold 3 confidence scores on 5 out of 7 selected antigen targets.

Where to Find and Access It
Official Journal Portal: You can access the full open-access text directly through Nature's publishing platform at npj Drug Discovery by looking up Article 14 (2026).

Preprint Version: The earlier iterations and detailed architectural breakdowns of this methodology are archived on arXiv (2410.22367).

The Open-Source Code & Model: Because IBM built this with an open infrastructure mindset, you can actually access the pre-trained model weights directly on Hugging Face under the repository identifier ibm/biomed.omics.bl.sm.ma-ted-458m.

it absolutely handles small molecule tasks using SMILES strings, but its role is significantly broader than a standard chemistry model.The ibm/biomed.omics.bl.sm.ma-ted-458m model (458 million parameters) is a unified multimodal foundation model built on IBM's MAMMAL (Molecular Aligned Multi-Modal Architecture and Language) framework. Instead of processing just one type of data, it translates multiple biological domains into a single structured language.Its key roles and how it interacts with SMILES strings can be broken down into specific tasks:1. How it uses SMILES stringsThe model tokenizes individual atoms and characters of a SMILES string exactly like words in a sentence. It accepts these strings as inputs—either on their own or paired with other biological sequences—to perform several distinct small molecule tasks:Drug-Target Interaction (DTI) Prediction: You can feed the model the raw amino acid sequence of a target protein alongside the SMILES string of a drug candidate. The model maps the interaction grid between them to predict the binding affinity ($pK_d$).Molecular Property & Toxicity Prediction: Given just a drug’s SMILES string, the model can be fine-tuned to predict crucial pharmacology benchmarks (such as through the Therapeutic Data Commons). Examples include:Carcinogenicity: Predicting whether a molecular structure will cause cancer.ClinTox & BBBP: Estimating clinical toxicity and Blood-Brain Barrier Penetration.Cancer-Drug Response (CDR): It can take a SMILES string and combine it with single-cell RNA sequencing data (transcriptomics) from a specific patient tumor cell line to predict drug efficacy, outputting precise $IC_{50}$ values (the drug concentration needed to inhibit the cancer by half).2. The Multi-Modal Role (Why it is unique)Standard small-molecule models (like ChemBERTa) only understand SMILES. What makes this specific MAMMAL model unique is the "ma" (Multi-Aligned) component of its name.It uses a flexible, multi-domain prompt syntax that acts as a bridge. For instance, a prompt fed into the model can dynamically combine tokenized strings (SMILES, FASTA sequences) and continuous numerical values (gene expression metrics). This allows it to seamlessly shift between:Biologics (bl): Antibody, T-Cell Receptor (TCR), and protein sequence understanding.Small Molecules (sm): Chemical string space (SMILES).Omics: Single-cell RNA sequence data.Summary of its ArchitectureUnder the hood, the model uses an encoder-decoder architecture. Because it handles tasks as sequence-to-sequence operations, it supports classification (e.g., toxic vs. non-toxic), regression (predicting exact binding strength values), and generation (designing or infilling entirely new SMILES strings or protein sequences to fit a specific prompt).

You have a highly solid foundation here. Cracking 87.5% SMILES validity on a 2B model with just a 4-hour QLoRA run on a Grace Blackwell rig is a fantastic baseline.But your diagnostic is spot on: the data imbalance is killing your v2 potential. Having generic MOSES string drilling at 49.7% while your actual business logic (target-conditioned generation) languishes at 0.6% means Gemma learned how to speak chemical syntax perfectly, but it has no idea how to actually listen to your target commands.You absolutely can use the IBM MAMMAL framework and its open-source data ecosystem to fix these exact gaps for your v2 fine-tune. Here is the strategic blueprint for how to bridge the two.1. You Can't Merge the Weights, But You Can Use MAMMAL as a "Teacher"Because IBM’s MAMMAL is a specialized encoder-decoder multimodal architecture and Gemma is a decoder-only LLM, you cannot directly merge their weights or adapters.Instead, you can use the ibm/biomed.omics.bl.sm.ma-ted-458m model as an In-Silico Data Filter (Knowledge Distillation).The Problem: When you scale up your target data, you don't want to feed Gemma low-affinity or toxic junk.The Solution: Generate a massive pool of synthetic target-to-SMILES data, and run it through the IBM model first. Use IBM's binding probability and cancer-drug response metrics as a strict gatekeeper. If the IBM model scores a synthetic molecule below 0.7, drop it.The Goal: You only train Gemma v2 on "gold-standard" target-molecule pairs validated by the SOTA multimodal model.2. Ingest MAMMAL’s Dataset Ecosystem to Fix the 0.6% BottleneckMAMMAL was trained on 2 billion samples, largely pulled from open multi-omic and chemical interaction databases. You can leverage the exact same open-source datasets it used to aggressively scale your target-conditioned data.To turn your 240 custom samples into a massive, steering dataset, pull from:BindingDB & ChEMBL: Extract pairs of Target Protein Sequences (FASTA) and their known binding small molecules (SMILES).Format for Gemma (ChatML): Convert these into instructions that mirror your app's true intent.Plaintext<|im_start|>user
Design a small molecule drug candidate that binds to the following protein target.
Target FASTA: MERALAPVQR...
Provide the rationale and output the SMILES string.<|im_end|>
<|im_start|>assistant
Rationale: The target requires a molecule capable of hydrophobic interactions at the primary binding pocket...
SMILES: CC1=C(C=C(C=C1)NC2=NC=CC(=N2)C3=CN=CC=C3)NY...<|im_end|>
3. The Proposed Dataset Rebalance for Gemma v2To stop the model from repeating similar MOSES-like structures and force it to pay attention to your prompts, you need to completely flip the data ratios. Drop the flat "Generate a drug molecule" drilling entirely and replace it with contextualized grammar.Dataset Componentv1 RatioProposed v2 RatioStrategic Purpose in v2Target-Conditioned Pairs (ChEMBL/BindingDB/Deep2Lead)0.6%65.0%Massive expansion. Teaches Gemma to map protein structures directly to chemical outputs.Mol-Instructions49.7%25.0%Keeps general chemistry reasoning, translation, and captioning alive without overwhelming the model.MOSES (Downsampled & Contextualized)49.7%10.0%Kept only as a minimal baseline to preserve the basic valence and ring-closure grammar.Why this fixes the Repetition Gap:By downsampling MOSES to 10% and wrapping your chemical data inside diverse, multi-modal prompt formats (e.g., matching text rationales, target proteins, and property constraints), the model can no longer minimize its loss function by simply memorizing a few generic, high-QED drug strings. It is forced to adapt its chemical output to the specific token patterns in the prompt.What does the timeline look like for your production target list—are you looking to stick to the 20 core targets from your custom data, or do you want to dynamically expand Gemma's vocabulary to a broader set of therapeutic areas for this next run?

   [Raw ChEMBL / BindingDB]
              │
              ▼
┌─────────────────────────────┐│ IBM MAMMAL Filter Engine    │  ◄── Reject if Binding Probability < 0.70└──────────────┬──────────────┘│ (High-Affinity Pass)▼┌─────────────────────────────┐│ ChatML Prompt Serialization  │  ◄── Dynamic Rationale Generation└──────────────┬──────────────┘▼[Gemma v2 Train Set]
### 1.1 Dataset Sourcing Layout
1. **Target-Conditioned Pairs (65% / ~65,000 samples):** Extract Protein FASTA sequences paired with highly active small-molecule ligands ($IC_{50} < 100\text{ nM}$ or $K_i < 100\text{ nM}$) from **ChEMBL v33** and **BindingDB**.
2. **Mol-Instructions (25% / ~25,000 samples):** Retain functional subcomponents from `zjunlp/Mol-Instructions` focusing on forward reaction prediction and molecular captioning to sustain biochemical reasoning.
3. **MOSES Syntactic Grammar (10% / ~10,000 samples):** Downsample the original `katielink/moses` set to a strict regulatory fraction. This acts purely as structural scaffolding to maintain valid valence and aromatic ring closure rules.

### 1.2 Knowledge Distillation Filter Script via IBM MAMMAL
Run all raw synthetic target pairings through `ibm/biomed.omics.bl.sm.ma-ted-458m` to curate absolute affinity. Use this script to gatekeep the validation pool:

```python
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

model_id = "ibm-research/biomed.omics.bl.sm.ma-ted-458m"
tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
model = AutoModelForSeq2SeqLM.from_pretrained(model_id, trust_remote_code=True).cuda()

def verify_binding_affinity(fasta_seq, smiles_str):
    # Formulate multi-modal alignment token format
    prompt = f"<protein>{fasta_seq}</protein><smiles>{smiles_str}</smiles> Task: Predict Binding Probability."
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
    
    with torch.no_grad():
        outputs = model.generate(**inputs, max_length=16)
        pred_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Parse out affinity probability float metric
    try:
        prob = float(pred_text)
        return prob >= 0.70  # Strict gatekeeping threshold
    except ValueError:
        return False
Step 2: Multi-Modal ChatML Prompt SerializationTo force Gemma to contextualize the small molecule rather than blindly repeating learned strings, wrap all parameters into structured, variable-length ChatML dictionaries.2.1 Training JSON Schema FormatJSON{
  "messages": [
    {
      "role": "user",
      "content": "Task: Design a small molecule drug candidate matching these specific criteria.\\nTarget Protein Sequence: [FASTA]\\nDesired Profile: High selectivity, low cardiotoxicity, QED > 0.55."
    },
    {
      "role": "assistant",
      "content": "Rationale: The targeted primary pocket contains a highly hydrophobic cleft flanked by polar residues. The structural solution incorporates an aromatic core to maximize pi-pi stacking, balanced with a flexible alkyl chain to maintain optimal aqueous solubility.\\nSMILES: [SMILES_STRING]"
    }
  ]
}
Step 3: Unsloth & QLoRA Config Tuning ($v2$ Adapters)Because mapping deep token configurations from amino acids to discrete SMILES tokens demands higher capability, elevate Rank and Alpha parameters while keeping hardware consumption minimal.Pythonfrom unsloth import FastLanguageModel
import torch

max_seq_length = 4096 
dtype = None # Auto-detected (Float16 or Bfloat16)
load_in_4bit = True # Quantize base to save VRAM

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "google/gemma-4-e2b-it", # Base Target
    max_seq_length = max_seq_length,
    dtype = dtype,
    load_in_4bit = load_in_4bit,
)

# Expand LoRA mapping capacity across all critical projections
model = FastLanguageModel.get_peft_model(
    model,
    r = 32,            # Upgraded from 16 to maximize interaction capacity
    target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                      "gate_proj", "up_proj", "down_proj"],
    lora_alpha = 64,   # Upgraded from 32
    lora_dropout = 0,  # Optimized for Unsloth
    bias = "none",     
    use_gradient_checkpointing = "unsloth",
    random_state = 3407,
    use_rslora = False,
    loftq_config = None,
)
Step 4: Hyperparameters & Compute Engine OptimizationExecute training using the following optimized execution configuration on your Grace Blackwell (DGX Spark GB10) cluster:Pythonfrom transformers import TrainingArguments
from trl import SFTTrainer
from unsloth import is_bfloat16_supported

trainer = SFTTrainer(
    model = model,
    tokenizer = tokenizer,
    train_dataset = dataset,
    dataset_text_field = "text",
    max_seq_length = max_seq_length,
    dataset_num_proc = 4,
    packing = False, # Maintain strict separation for molecular prompts
    args = TrainingArguments(
        per_device_train_batch_size = 8,  # Increased density
        gradient_accumulation_steps = 4,  # Effective Batch Size = 32
        warmup_ratio = 0.05,
        num_train_epochs = 3,
        learning_rate = 1.5e-4,           # Stable learning curve for higher rank
        fp16 = not is_bfloat16_supported(),
        bf16 = is_bfloat16_supported(),
        logging_steps = 1,
        optim = "adamw_8bit",              # Lower storage footprint
        weight_decay = 0.01,
        lr_scheduler_type = "cosine",     # Progressive decay curve
        seed = 3407,
        output_dir = "gemma_drug_discovery_v2",
    ),
)
trainer_stats = trainer.train()
Step 5: Post-Training Validation LoopTo ensure the model has cleared the repetition barrier, the inference script must calculate internal structural divergence across multiple generations.5.1 Inference Generation SettingsWhen invoking the adapter for live target screening, always enforce penalties to maximize uniqueness:Pythonfrom unsloth import FastLanguageModel
FastLanguageModel.for_inference(model) # Ultra-fast execution mode

inputs = tokenizer(
    [
        "<|im_start|>user\\nDesign a drug candidate against Target: MERALAPVQR...<|im_end|>\n<|im_start|>assistant\\n"
    ], return_tensors = "pt").to("cuda")

outputs = model.generate(
    **inputs, 
    max_new_tokens = 512,
    temperature = 0.75,         # Introduces natural diversity
    top_p = 0.92,               # Nucleus filtering
    repetition_penalty = 1.25,  # Prevents loop-state artifacts
    use_cache = True
)
5.2 Metrics Tracking FrameworkCalculate these five internal metrics over batches of 1,000 generations to measure pipeline success:SMILES Validity ($\%$): Percentage parsing successfully via RDKit (Chem.MolFromSmiles).Internal Uniqueness ($\%$): Count of unique canonical SMILES strings divided by total generated structures. Target $>90\%$.Internal Novelty ($\%$): Percentage of compounds absent from both the training set and ChEMBL baseline.Quantitative Estimate of Drug-Likeness (QED): Calculated using RDKit descriptors. Maintain a running average $>0.55$.Synthetic Accessibility (SA Score): Fragment-based evaluation verifying the molecule can be realistically synthesized in a laboratory setting (Target Score $\le 4.0$)."""Save the markdown content to a filefile_path = "gemma_v2_finetune_instructions.md"with open(file_path, "w", encoding="utf-8") as file:file.write(markdown_content)print(f"File successfully created: {file_path}")