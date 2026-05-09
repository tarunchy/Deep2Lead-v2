# Deep2Lead Revamp: Requirements and Design Document

## 1. Purpose

Deep2Lead was originally created as an AI-assisted drug discovery application that accepted an amino acid sequence and a small-molecule SMILES string, generated nearby candidate molecules, and evaluated whether those candidates could bind better to a mutated biological target.

The goal of this revamp is to transform Deep2Lead into an educational AI drug discovery platform for high school students, while also modernizing the technical pipeline with newer generative AI, protein structure prediction, molecular docking, and automated experiment loops.

The product should help students understand how AI can accelerate scientific discovery without overselling the idea that computational predictions alone are equivalent to real drug approval or laboratory validation.

---

## 2. Product Vision

Deep2Lead should become a hands-on learning environment where students can explore the modern drug discovery workflow:

1. Choose a biological target.
2. Understand the target as an amino acid sequence.
3. Predict or retrieve the target’s 3D protein structure.
4. Start from an existing small molecule represented as a SMILES string.
5. Generate nearby candidate molecules using AI.
6. Convert molecules into 3D conformations.
7. Dock candidate molecules against the protein target.
8. Score binding affinity and other drug-likeness properties.
9. Check novelty against known chemical databases.
10. Reflect on scientific limitations, ethics, and validation.

The educational message should be:

> AI can help scientists explore ideas faster, but every computational prediction must eventually be validated through real experiments, safety testing, and clinical studies.

---

## 3. Target Users

### 3.1 Primary Users

High school students interested in:

* AI
* biology
* chemistry
* medicine
* biotechnology
* computational science
* future STEM careers

### 3.2 Secondary Users

* Parents evaluating summer STEM programs
* Teachers and mentors
* College applicants seeking project-based research exposure
* Early-stage learners interested in AI for science

---

## 4. Learning Objectives

By the end of the course or app experience, students should be able to explain:

1. What a protein is.
2. What an amino acid sequence represents.
3. Why protein 3D structure matters.
4. What a small molecule is.
5. What a SMILES string represents.
6. Why drugs often work by binding to protein targets.
7. What molecular docking means.
8. What binding affinity means at a high level.
9. How AI can generate candidate molecules.
10. Why novelty checking matters.
11. Why computational drug discovery still needs laboratory validation.
12. Why AI iteration can accelerate scientific exploration but does not automatically guarantee real-world impact.

---

## 5. Core Educational Analogy

Use a LEGO or lock-and-key analogy.

### Protein Target

The protein is like a complex 3D LEGO structure or a lock. Its shape determines what can interact with it.

### Drug Molecule

The drug is like a small LEGO piece or key that needs to fit into the right part of the protein.

### AlphaFold-style Structure Prediction

The amino acid sequence is like a list of instructions for building the protein. Structure prediction turns that list into a 3D shape.

### Molecular Docking

Docking tests whether a candidate molecule fits into the protein’s binding pocket and estimates how strong that fit might be.

---

## 6. Existing Deep2Lead Concept

### 6.1 Current Workflow

The original Deep2Lead workflow can be summarized as:

1. User provides an amino acid sequence for a biological target.
2. User provides an existing drug molecule as a SMILES string.
3. System mutates or accepts a mutated amino acid sequence.
4. System generates nearby candidate molecules based on the original SMILES string.
5. System predicts binding affinity between the new target and generated molecules.
6. System checks whether generated molecules already exist in chemical databases.
7. System identifies promising and potentially novel candidate molecules.

### 6.2 Existing Educational Value

This workflow is already valuable because it teaches students:

* Mutation can change biological targets.
* Existing drugs may become less effective when targets change.
* AI can suggest molecule modifications.
* Molecules can be represented as text.
* Drug discovery is an iterative optimization problem.

---

## 7. Revamped Deep2Lead Product Structure

The updated app should have two major experiment modes.

---

## 8. Experiment Mode 1: Sequence + SMILES Experiment

This mode preserves the current Deep2Lead workflow and keeps the experience approachable for beginners.

### 8.1 Inputs

* Amino acid sequence of target protein
* Optional mutated amino acid sequence
* Existing drug molecule as SMILES string
* Number of candidate molecules to generate
* Optional constraints:

  * similarity range
  * molecular weight range
  * drug-likeness threshold
  * novelty requirement

### 8.2 Outputs

* Generated candidate SMILES strings
* Similarity score compared with original molecule
* Predicted binding affinity score
* Drug-likeness indicators
* Toxicity or risk flags if available
* Novelty result
* Ranked candidate list

### 8.3 Student Interpretation

Students should answer:

* Did mutation change the predicted binding behavior?
* Which generated molecule scored best?
* Is the molecule similar or very different from the original?
* Is it novel?
* What are the limitations of this prediction?

---

## 9. Experiment Mode 2: 3D Structure Experiment

This is the new modernized workflow that integrates AlphaFold-style protein structure prediction and molecular docking.

### 9.1 Goal

Help students understand that molecules do not bind to a flat text sequence. They bind to a folded 3D protein structure.

### 9.2 Inputs

* Amino acid sequence of the target protein
* Existing drug SMILES string
* Optional mutation information
* Optional target name or database ID
* Optional binding pocket coordinates, if known
* Candidate generation settings
* Docking settings

### 9.3 Pipeline

1. Accept amino acid sequence.
2. Predict or retrieve protein 3D structure.
3. Clean and prepare protein structure.
4. Accept existing drug SMILES.
5. Convert SMILES into a 3D molecule conformation.
6. Generate nearby candidate molecules.
7. Convert generated molecules into 3D conformations.
8. Dock each molecule against the protein target.
9. Score docking pose and estimated binding affinity.
10. Rank candidate molecules.
11. Check novelty.
12. Present student-friendly explanation.

### 9.4 Outputs

* Protein 3D visualization
* Original molecule 2D and 3D visualization
* Generated candidate molecules
* Docking score for each molecule
* Binding pose visualization
* Ranking table
* Novelty result
* Explainable summary

### 9.5 Student Interpretation

Students should answer:

* What does the protein look like in 3D?
* Where does the molecule bind?
* Which molecule appears to fit best?
* Did the AI-generated molecule improve the score?
* Is the best-scoring molecule chemically reasonable?
* What further validation would be needed?

---

## 10. Technical Architecture

## 10.1 High-Level Architecture

The system should be modular so each step can be swapped as better models or APIs become available.

### Frontend

* Student dashboard
* Experiment setup screen
* Protein sequence input
* SMILES input
* Experiment mode selector
* Progress tracker
* Molecule viewer
* Protein 3D viewer
* Results dashboard
* Reflection questions

### Backend

* Experiment orchestration service
* Sequence validation service
* Protein structure service
* Molecule generation service
* Molecule preparation service
* Docking service
* Scoring service
* Novelty checking service
* Report generation service
* Auto Experiment service

### Data Layer

* User experiments
* Input sequences
* Input molecules
* Generated candidate molecules
* Docking scores
* Novelty results
* Student reports
* Experiment logs

---

## 11. Proposed Developer Pipeline

## 11.1 Sequence-to-Structure Step

### Purpose

Convert an amino acid sequence into a 3D protein structure.

### Possible Implementation Options

* Use an AlphaFold-style model or API.
* Retrieve existing predicted structures from public protein structure databases when available.
* Use a lighter educational model for fast classroom demos.

### Input

```text
MKTIIALSYIFCLVFADYKDDDDK...
```

### Output

Protein 3D structure file, usually in a format such as:

```text
.pdb
.cif
```

### Developer Notes

* Cache structure predictions because they can be expensive.
* For educational use, prefer known proteins with precomputed structures.
* Allow advanced mode for custom sequences.
* Show students that structure prediction is not always equally confident across all protein regions.

---

## 11.2 Protein Preparation Step

### Purpose

Prepare the protein structure for docking.

### Tasks

* Remove unnecessary molecules if present.
* Add hydrogens.
* Assign charges.
* Identify or define binding pocket.
* Convert file format if needed.

### Output

Prepared protein structure suitable for docking.

---

## 11.3 SMILES-to-3D Step

### Purpose

Convert a text-based molecule representation into a 3D molecular shape.

### Input

```text
CC(C)C1=CC=C(C=C1)C(C)C(=O)O
```

### Output

3D molecule conformation file, such as:

```text
.sdf
.mol2
.pdbqt
```

### Developer Notes

* SMILES is mostly used for small molecules.
* Large molecules such as proteins, antibodies, or peptides should be represented differently, usually with amino acid sequences and 3D structure files.
* Generate multiple conformers when possible because the same molecule may adopt different 3D shapes.

---

## 11.4 Molecule Generation Step

### Purpose

Generate new candidate molecules near the existing molecule.

### Approaches

* Variational autoencoder
* Transformer-based molecular language model
* Graph neural network generation
* Reinforcement learning optimization
* LLM-assisted molecule proposal with chemical validation

### Input

* Existing SMILES string
* Target information
* Optional docking feedback from previous round
* Constraints such as molecular weight, similarity, toxicity, and novelty

### Output

List of generated candidate SMILES strings.

### Important Guardrails

Every generated SMILES should be validated before scoring:

* Is the SMILES syntactically valid?
* Can the molecule be parsed by cheminformatics tools?
* Does it satisfy basic chemical valency rules?
* Is it too large or too reactive?
* Does it violate obvious drug-likeness constraints?

---

## 11.5 Molecular Docking Step

### Purpose

Estimate how well a molecule may bind to the protein target.

### Inputs

* Prepared protein 3D structure
* Candidate molecule 3D conformation
* Binding pocket information

### Outputs

* Docking pose
* Docking score
* Estimated binding energy
* Rank among candidates

### Student-Friendly Explanation

Docking is like testing whether a key fits into a lock. The software tries many possible positions and gives a score for how well the molecule fits.

### Developer Notes

* Docking scores are approximations.
* Docking should not be presented as proof that a molecule is a real drug.
* Use consistent docking settings so students can compare results fairly.

---

## 11.6 Novelty Checking Step

### Purpose

Check whether generated molecules already exist in known chemical databases.

### Inputs

* Generated SMILES
* Canonicalized SMILES
* InChIKey if available

### Outputs

* Known or unknown molecule status
* Similar known compounds
* Database match result
* Novelty score

### Developer Notes

* Exact novelty should use canonical representations such as canonical SMILES or InChIKey.
* Similarity-based novelty should use molecular fingerprints.
* A molecule being absent from a database does not automatically mean it is synthesizable, safe, or useful.

---

## 12. Auto Experiment Concept

## 12.1 Inspiration

Auto Experiment borrows the general idea of automated research loops: instead of a human manually changing parameters, rerunning experiments, and comparing scores, the system automates the cycle.

In neural network training, weights are repeatedly updated to reduce loss. In drug discovery, candidate molecules and experiment settings can be repeatedly adjusted to improve binding scores and other properties.

## 12.2 Goal

Create an automated loop that generates, tests, scores, and improves candidate molecules over multiple rounds.

## 12.3 Auto Experiment Loop

1. Start with a protein target and baseline molecule.
2. Generate candidate molecules.
3. Validate generated molecules.
4. Convert candidates into 3D conformations.
5. Dock candidates to the target structure.
6. Score candidates.
7. Filter candidates using rules.
8. Select best candidates.
9. Use feedback to generate the next round.
10. Repeat for a fixed number of iterations or until improvement plateaus.

## 12.4 Objective Function

The system should optimize a multi-objective score, not only binding affinity.

Example scoring formula:

```text
Total Score =
  docking_score_weight * docking_score
+ novelty_weight * novelty_score
+ drug_likeness_weight * drug_likeness_score
- toxicity_weight * predicted_toxicity_risk
- synthetic_difficulty_weight * synthesis_risk
```

## 12.5 Auto Experiment Parameters

* Number of rounds
* Number of molecules per round
* Similarity constraint
* Docking score threshold
* Novelty threshold
* Drug-likeness threshold
* Maximum compute budget
* Maximum runtime
* Exploration vs. exploitation setting

## 12.6 Auto Experiment Outputs

* Best molecule from each round
* Score trend over time
* Docking improvement chart
* Molecule lineage graph
* Final ranked candidate list
* Explanation of what changed between rounds
* Student-readable experiment report

## 12.7 Educational Value

Students learn that AI science is not one-shot magic. It is an iterative loop:

```text
Generate → Test → Score → Learn → Improve
```

This is similar to:

* training a neural network
* improving an essay draft
* running science experiments
* optimizing engineering designs

---

## 13. Suggested Course Structure

## Module 1: Why AI for Drug Discovery?

Topics:

* What is a disease target?
* What is a protein?
* What is a drug molecule?
* Why is drug discovery hard?
* Why can AI help?

Activity:

Students explore a known protein and a known drug example.

---

## Module 2: Proteins as Sequences

Topics:

* Amino acids
* Protein sequences
* Mutations
* Pathogens vs. human disease targets
* Aging-related pathways as an example

Activity:

Students compare an original and mutated protein sequence.

---

## Module 3: Molecules as Text

Topics:

* Small molecules
* SMILES strings
* Why text representation helps AI models
* Difference between small molecules and large molecules

Activity:

Students enter a SMILES string and see the molecule structure.

---

## Module 4: From Sequence to 3D Structure

Topics:

* Why 3D shape matters
* AlphaFold-style structure prediction
* Lock-and-key analogy
* Protein confidence and uncertainty

Activity:

Students generate or retrieve a protein 3D structure.

---

## Module 5: Molecular Docking

Topics:

* Binding pockets
* Docking poses
* Docking scores
* Why docking is only an estimate

Activity:

Students dock a known molecule to a known protein.

---

## Module 6: Generating New Molecules

Topics:

* Generative AI
* VAEs
* molecular transformers
* candidate generation
* validity and constraints

Activity:

Students generate new SMILES strings from an existing molecule.

---

## Module 7: Auto Experiment

Topics:

* Iterative optimization
* Feedback loops
* Hyperparameter tuning analogy
* Scientific automation

Activity:

Students run a small Auto Experiment for several rounds and compare improvements.

---

## Module 8: Ethics, Reality, and Validation

Topics:

* Computational prediction vs. real drugs
* Lab testing
* clinical trials
* safety
* responsible AI
* hype vs. validation
* adoption and real-world ROI

Activity:

Students write a short reflection: “What can AI accelerate, and what can it not replace?”

---

## 14. Example Student Project

### Project Title

Designing a Better Candidate Molecule for a Mutated Protein Target

### Student Tasks

1. Choose a target from a curated list.
2. Read a plain-English explanation of the target.
3. Load the amino acid sequence.
4. View the predicted 3D protein structure.
5. Start with an existing molecule.
6. Generate 10 candidate molecules.
7. Dock candidates against the protein.
8. Rank candidates by score.
9. Check novelty.
10. Choose the best candidate.
11. Write a final report.

### Final Report Questions

* What target did you choose?
* Why is this target biologically interesting?
* What molecule did you start with?
* Which candidate scored best?
* Was the candidate novel?
* What evidence supports your result?
* What are the limitations?
* What would a real scientist need to do next?

---

## 15. Recommended Initial Target Themes

For high school students, avoid starting with extremely complex unsolved diseases. Use curated, understandable examples.

### Option A: Viral Protein Example

Good for explaining mutation and target adaptation.

Examples:

* SARS-CoV-2 spike protein
* SARS-CoV-2 main protease
* influenza neuraminidase

### Option B: Aging and Longevity Example

Good for student engagement because it connects to a big human question.

Possible pathway themes:

* inflammation
* cellular senescence
* mTOR signaling
* sirtuins
* DNA repair
* mitochondrial function

### Option C: Cancer Target Example

Good for showing real biomedical complexity.

Possible target themes:

* kinases
* growth factor receptors
* mutated signaling proteins

### Recommendation

For the first version of the course, use curated targets instead of asking beginners to find fully unsolved targets by themselves. Students can later graduate to open-ended target discovery.

---

## 16. System Requirements

## 16.1 Functional Requirements

### User and Course Flow

* Students can create an experiment.
* Students can select beginner or advanced mode.
* Students can choose from curated targets.
* Students can enter their own amino acid sequence in advanced mode.
* Students can enter a SMILES string.
* Students can run sequence-based prediction.
* Students can run 3D structure experiment.
* Students can view results in a ranked table.
* Students can generate a report.

### Protein Functionality

* Validate amino acid sequence input.
* Retrieve known protein metadata when possible.
* Predict or retrieve 3D structure.
* Display protein structure.
* Prepare protein for docking.

### Molecule Functionality

* Validate SMILES input.
* Canonicalize SMILES.
* Display 2D molecule.
* Generate 3D conformer.
* Generate nearby candidate molecules.
* Filter invalid molecules.
* Score drug-likeness.
* Check novelty.

### Docking Functionality

* Accept prepared protein and molecule structures.
* Run docking job.
* Return docking score.
* Return docking pose.
* Display molecule-protein interaction visually.

### Auto Experiment Functionality

* Run multiple candidate generation and docking rounds.
* Track best score per round.
* Stop when budget or iteration limit is reached.
* Store all experiment results.
* Explain improvement trajectory.

---

## 16.2 Non-Functional Requirements

### Performance

* Beginner demos should complete quickly enough for classroom use.
* Expensive jobs should run asynchronously with visible progress.
* Cache repeated structure predictions and docking results.

### Safety and Responsible Use

* Do not claim that generated molecules are real drugs.
* Add disclaimers explaining educational and computational nature.
* Prevent harmful or inappropriate molecule design use cases.
* Avoid giving medical advice.
* Avoid presenting student results as clinically validated.

### Reliability

* Validate every input before running expensive jobs.
* Fail gracefully when docking or structure prediction fails.
* Provide student-readable error messages.

### Explainability

* Every score should have a plain-English explanation.
* Students should see why a molecule ranked higher or lower.
* The app should explain uncertainty and limitations.

### Cost Control

* Limit number of candidates in beginner mode.
* Cache common targets.
* Use curated examples with precomputed outputs for demos.
* Put strict limits on Auto Experiment loops.

---

## 17. UX Design

## 17.1 Main Navigation

* Home
* Learn
* Experiments
* 2D Sequence Experiment
* 3D Structure Experiment
* Auto Experiment
* Reports
* Glossary

## 17.2 Experiment Setup Screen

Fields:

* Experiment name
* Target selection
* Amino acid sequence
* Existing drug SMILES
* Experiment mode
* Candidate count
* Difficulty level

Buttons:

* Validate Inputs
* Preview Molecule
* Preview Protein
* Run Experiment

## 17.3 Results Dashboard

Sections:

* Target summary
* Protein structure viewer
* Original molecule viewer
* Candidate molecule table
* Docking results
* Novelty results
* Best candidate explanation
* Limitations
* Export report

## 17.4 Auto Experiment Dashboard

Sections:

* Round-by-round progress
* Best score per round
* Candidate lineage
* Current best molecule
* Failed molecules
* Cost and compute usage
* Final recommendation

---

## 18. Data Model Draft

## Experiment

```text
experiment_id
user_id
mode
target_name
amino_acid_sequence
mutation_description
input_smiles
status
created_at
completed_at
```

## ProteinStructure

```text
structure_id
experiment_id
source
sequence_hash
pdb_file_path
confidence_summary
prepared_structure_path
```

## MoleculeCandidate

```text
candidate_id
experiment_id
parent_smiles
generated_smiles
canonical_smiles
inchi_key
validity_status
similarity_score
drug_likeness_score
novelty_status
```

## DockingResult

```text
docking_id
candidate_id
protein_structure_id
docking_score
binding_energy
pose_file_path
rank
notes
```

## AutoExperimentRun

```text
auto_run_id
experiment_id
round_count
molecules_per_round
objective_config
best_candidate_id
status
cost_estimate
```

---

## 19. MVP Scope

## 19.1 MVP Should Include

* Curated target list
* Amino acid sequence input
* SMILES input
* SMILES validation
* Molecule visualization
* Candidate molecule generation
* Basic binding affinity prediction
* 3D structure retrieval for curated targets
* Basic docking for curated examples
* Ranked results
* Student report export

## 19.2 MVP Can Exclude Initially

* Fully custom AlphaFold prediction for any sequence
* Large-scale Auto Experiment
* Advanced toxicity prediction
* Real synthesis planning
* Wet-lab validation
* Complex teacher classroom management

---

## 20. Phase 2 Scope

* Custom sequence-to-structure prediction
* Full 3D docking for custom targets
* Auto Experiment loop
* Molecule lineage visualization
* Better novelty checking
* Teacher dashboard
* Assignment grading rubric
* More target libraries
* Aging-focused module
* Cancer-focused module
* Viral mutation module

---

## 21. Phase 3 Scope

* Fine-tuned molecular generation model
* Reinforcement learning molecule optimization
* Multi-objective optimization
* Natural language research assistant
* Literature search integration
* Student project portfolio
* Team-based experiments
* Cloud GPU acceleration
* Advanced explainability

---

## 22. Important Scientific Limitations to Teach

The app must clearly explain:

1. Docking scores are approximations.
2. Binding is not the same as being a safe drug.
3. A molecule can bind well but be toxic.
4. A molecule can look promising but be impossible to synthesize.
5. A molecule can be novel but useless.
6. AI-generated molecules require expert review.
7. Real drug development requires lab experiments, animal studies, clinical trials, and regulatory approval.
8. AI accelerates exploration but does not replace science.

---

## 23. Responsible AI and Safety Requirements

* Position the platform as educational, not therapeutic.
* Do not recommend treatment decisions.
* Do not claim disease cures.
* Add warnings when students interpret scores too strongly.
* Avoid enabling harmful biological design workflows.
* Keep target libraries curated and safe for education.
* Provide teacher controls for advanced features.

---

## 24. Business and ROI Considerations

A key product principle should be validation before over-expansion.

Avoid building only for demo excitement. The product should be tested with real students, parents, and educators.

### Metrics to Track

* Student completion rate
* Student understanding before and after course
* Parent willingness to pay
* Teacher adoption interest
* Number of completed experiments
* Report quality
* Student confidence in AI + biology concepts
* Repeat usage
* Conversion to paid course

### Validation Strategy

1. Run a small pilot with curated examples.
2. Collect student feedback.
3. Measure learning outcomes.
4. Improve unclear modules.
5. Test willingness to pay.
6. Expand only after evidence of real educational value.

---

## 25. Success Criteria

The revamped Deep2Lead succeeds if students can confidently explain:

* A protein target can be represented by an amino acid sequence.
* The same protein folds into a 3D shape.
* Drugs often work by binding to a specific part of that shape.
* SMILES strings represent small molecules.
* AI can generate new candidate molecules.
* Docking can estimate fit but cannot prove a real drug.
* Scientific discovery is an iterative process.
* Real-world validation is essential.

The product succeeds commercially if students and parents see it as a meaningful STEM learning experience, not just a flashy AI demo.

---

## 26. Open Questions

1. Should the first course focus on viral mutation, aging, or cancer?
2. Should students use only curated targets in version 1?
3. Which structure prediction service should be used?
4. Which docking engine should be used?
5. Should Auto Experiment be part of the first release or a premium advanced module?
6. How much compute budget is acceptable per student?
7. What safety limits should be placed on custom molecule generation?
8. Should the app support teacher review before experiments run?
9. Should students export reports as PDF, slides, or portfolio pages?
10. What is the right balance between scientific realism and simplicity?

---

## 27. Recommended Next Step

Build a pilot version around one curated example.

Recommended first pilot:

```text
Theme: Viral mutation and drug adaptation
Mode: 2D Sequence + SMILES and 3D Structure Experiment
Student Outcome: Generate, dock, rank, and explain candidate molecules
```

After the first pilot works, add an aging-focused module because it has strong student interest and connects to broader questions about longevity, inflammation, cellular repair, and AI-assisted biomedical discovery.

---

## 28. One-Sentence Product Summary

Deep2Lead teaches students how modern AI drug discovery works by letting them move from protein sequences and SMILES strings to 3D structures, docking scores, generated molecules, novelty checks, and responsible scientific interpretation.

---

## 29. Gamified Drug Discovery Mode

High school students often learn faster when complex ideas are turned into a game. Deep2Lead can include a gamified mode that turns AI drug discovery into a mission-based strategy game while still teaching real scientific concepts.

The goal is not to make drug discovery look like magic or combat only. The goal is to make the learning experience interactive, competitive, and memorable.

---

## 29.1 Game Concept: Molecule Quest

### Core Idea

Students enter a virtual biomedical world where a disease target, pathogen protein, or aging-related protein is represented as a challenge boss. The student’s job is to use AI to design or improve small molecules that can bind to the target and reduce its harmful activity.

The game teaches the same scientific pipeline:

```text
Target → Structure → Molecule → Docking → Score → Improve → Explain
```

But it presents the experience as a mission.

### Example Story

A harmful protein has become active in the body. The student joins a research team as an AI drug discovery scientist. Their mission is to design a molecule that can fit into the target’s binding pocket and reduce the target’s effect.

---

## 29.2 Game Characters and Objects

### Target Boss

The protein target becomes the “boss” or challenge.

Examples:

* Viral protease boss
* Spike protein boss
* Inflammation boss
* Aging pathway boss
* Cancer signaling boss

The boss should visually represent the biological target, but the app should explain that this is a simplified educational metaphor.

### Molecule Hero

The candidate drug molecule becomes the student’s “hero” or “tool.”

Students can improve the molecule by changing properties such as:

* binding strength
* stability
* novelty
* drug-likeness
* safety score
* synthetic feasibility

### AI Lab Assistant

An AI assistant guides students through the experiment.

The assistant can say things like:

* “Your molecule binds well, but it may be too large.”
* “This candidate is novel, but its drug-likeness score is weak.”
* “Try balancing binding strength with safety.”
* “A stronger docking score is useful, but it is not enough by itself.”

---

## 29.3 Gameplay Loop

Each mission should follow a simple loop:

1. Choose a target boss.
2. Learn what the target does.
3. Load or predict the target’s 3D structure.
4. Start with a known molecule.
5. Ask AI to generate improved candidate molecules.
6. Dock the molecules against the target.
7. Receive a score.
8. Upgrade or modify the molecule.
9. Try again.
10. Submit the best molecule with an explanation.

This loop mirrors real scientific iteration.

```text
Generate → Test → Score → Improve
```

---

## 29.4 Scoring System

The game should not reward only binding strength. A molecule that binds strongly may still be unsafe, unrealistic, or impossible to synthesize.

Use a balanced scorecard.

### Example Score Categories

| Category              | Meaning                                                        | Student-Friendly Name |
| --------------------- | -------------------------------------------------------------- | --------------------- |
| Docking Score         | How well the molecule fits the protein                         | Attack Power          |
| Drug-Likeness         | Whether the molecule has reasonable drug-like properties       | Health Balance        |
| Novelty               | Whether the molecule appears new compared with known databases | Discovery Bonus       |
| Safety Prediction     | Whether the molecule has obvious risk signals                  | Safety Shield         |
| Synthetic Feasibility | Whether the molecule may be practical to make                  | Buildability          |
| Similarity Control    | Whether the molecule stays near the original drug              | Evolution Control     |

### Example Total Score

```text
Mission Score =
  Attack Power
+ Discovery Bonus
+ Health Balance
+ Safety Shield
+ Buildability
- Risk Penalty
```

### Important Teaching Point

A molecule should not win just because it has the strongest docking score. Students should learn that real drug discovery is multi-objective optimization.

---

## 29.5 Levels and Missions

### Level 1: Molecule Basics

Students learn what SMILES strings are and how molecules can be visualized.

Mission:

* Enter a SMILES string.
* View the molecule.
* Identify basic properties.

### Level 2: Target Basics

Students learn what proteins are and why shape matters.

Mission:

* Choose a simple protein target.
* View its amino acid sequence.
* View its 3D structure.

### Level 3: First Docking Battle

Students dock an existing molecule against a target.

Mission:

* Run docking.
* Interpret the score.
* View the binding pose.

### Level 4: AI Molecule Upgrade

Students use AI to generate nearby molecules.

Mission:

* Generate 5 candidate molecules.
* Compare scores.
* Pick the best candidate.

### Level 5: Mutation Challenge

The target mutates and the old molecule may not bind as well.

Mission:

* Compare original and mutated protein.
* Generate a molecule that works better against the mutated target.

### Level 6: Auto Experiment Arena

Students run an automated multi-round experiment.

Mission:

* Set constraints.
* Run multiple improvement rounds.
* Track best score over time.
* Explain why the final molecule improved.

### Level 7: Final Research Defense

Students present their best molecule and defend their reasoning.

Mission:

* Submit molecule.
* Show docking score.
* Show novelty result.
* Explain limitations.
* Propose next real-world validation steps.

---

## 29.6 Game Modes

### Solo Mission Mode

A student works alone through guided missions.

Best for:

* self-paced summer course
* beginner students
* homework assignments

### Team Lab Mode

Students work in teams and compare results.

Best for:

* live workshops
* classroom sessions
* hackathons

### Tournament Mode

Students compete on the same target with the same starting molecule.

Winning should be based on a balanced scientific score, not only docking.

Possible awards:

* Best Binding Score
* Best Balanced Molecule
* Most Novel Candidate
* Best Scientific Explanation
* Best Safety-Aware Design
* Best Team Collaboration

### Story Campaign Mode

Students progress through a fictional biomedical research storyline.

Example campaign:

```text
Mission 1: Learn the molecule language
Mission 2: Decode the protein target
Mission 3: Predict the 3D structure
Mission 4: Dock the first molecule
Mission 5: Respond to a mutation
Mission 6: Run Auto Experiment
Mission 7: Present the discovery report
```

---

## 29.7 Badges and Rewards

Badges can motivate students while reinforcing learning outcomes.

### Example Badges

* Sequence Explorer: Validated the first amino acid sequence
* Molecule Builder: Submitted the first valid SMILES string
* Structure Seeker: Viewed the first 3D protein structure
* Docking Rookie: Completed the first docking run
* AI Chemist: Generated the first candidate molecule
* Mutation Defender: Improved a molecule against a mutated target
* Novelty Hunter: Found a molecule not detected in the database
* Safety Scientist: Chose a safer molecule over a stronger but riskier one
* Research Communicator: Wrote a strong final explanation
* Auto Experiment Master: Completed a multi-round optimization loop

---

## 29.8 Student Dashboard for Gamification

The student dashboard can show:

* current mission
* target boss health bar
* molecule score
* docking score
* safety shield
* novelty bonus
* experiment rounds completed
* badges earned
* leaderboard ranking if enabled
* final research report progress

### Boss Health Bar Concept

The boss health bar should represent the molecule’s ability to bind or inhibit the target in the simulation.

Important wording:

* Use “simulation score” or “model score.”
* Avoid saying the student has cured or destroyed a real disease.

Example:

```text
Your molecule reduced the target’s simulation health by 62%.
This means your candidate scored better in the computational model.
It does not mean the molecule is a real medicine.
```

---

## 29.9 AI-Powered Hints

The AI assistant can give hints after each experiment.

### Example Hints

* “Your molecule is strong, but its size may make it less drug-like.”
* “Try generating candidates closer to the original molecule.”
* “This molecule is novel, but novelty alone is not enough.”
* “Your docking score improved, but your safety score decreased.”
* “A real scientist would now test this in a lab.”

Hints should teach tradeoffs, not simply tell students the answer.

---

## 29.10 Gamified Auto Experiment

Auto Experiment can become a special game mode where students configure an AI research agent.

### Student Choices

Students can choose a strategy:

| Strategy           | Meaning                         |
| ------------------ | ------------------------------- |
| Conservative       | Stay close to original molecule |
| Explorer           | Try more diverse molecules      |
| Safety First       | Prioritize safer candidates     |
| Novelty Hunter     | Prioritize new molecules        |
| Balanced Scientist | Optimize across all scores      |

### Auto Experiment Output

The game should show:

* round-by-round improvement
* best molecule per round
* molecule family tree
* score trend
* AI strategy explanation
* final recommended candidate

This teaches students that automated science is not random. It is guided by objectives, constraints, and feedback.

---

## 29.11 Safety and Responsible Framing

Because the game uses disease and drug discovery concepts, the language must be careful.

Use phrases like:

* “simulation”
* “candidate molecule”
* “model prediction”
* “educational experiment”
* “computational score”

Avoid phrases like:

* “cure cancer”
* “destroy virus”
* “real medicine”
* “approved drug”
* “guaranteed treatment”

The game should repeatedly remind students:

> A high score in Deep2Lead means the molecule performed well in a computer simulation. Real medicines require laboratory testing, safety studies, clinical trials, and regulatory review.

---

## 29.12 Recommended MVP Gamification Features

For the first gamified release, keep the scope simple.

### Include in MVP

* Mission-based flow
* Target boss visual metaphor
* Molecule scorecard
* Badges
* Basic leaderboard for classroom mode
* AI hints
* Final research report

### Save for Later

* Full animated battle system
* Real-time multiplayer
* Complex 3D game environment
* Custom avatars
* Advanced storyline campaigns
* Large-scale tournament infrastructure

---

## 29.13 Why Gamification Matters

Gamification can make the app more engaging, but it should also deepen understanding.

The best version of this game should make students feel:

* curiosity about biology
* excitement about AI
* respect for scientific validation
* awareness of safety and ethics
* confidence that they can participate in future scientific innovation

The game should not replace the science. The game should make the science easier to understand and more exciting to explore.
