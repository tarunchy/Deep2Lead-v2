# Deep2Lead V2 — Project State for Claude

> Hand this file to Claude at the start of any new session so it has full context without re-reading all the source files.
> Update the "Future Enhancements" section as features are completed.

---

## What This App Is

**Deep2Lead V2** is a Flask web app for Georgia Tech graduate students (CS8803).  
Students log in, provide a protein amino-acid sequence and a seed SMILES string, and the app uses **Gemma4 on an NVIDIA DGX Spark** to generate novel drug-like candidate molecules. Candidates are scored and ranked. Students can publish experiments to a class feed, like/comment on each other's work, and get an AI-generated title + hypothesis suggestion.

---

## Stack

| Layer | Choice |
|---|---|
| Web framework | Flask 3.x, app-factory pattern, Blueprints |
| Auth | Flask-Login (session cookies) + bcrypt |
| ORM | Flask-SQLAlchemy 3.x + Flask-Migrate / Alembic |
| Database | PostgreSQL 16 (Homebrew, localhost:5432, db=`deep2lead_v2`, role=`deep2lead`) |
| Molecule science | RDKit (rdkit-pypi 2022.9.5, pinned numpy<2) |
| Validation | marshmallow >=3.21,<4 (marshmallow 4.x broke the API) |
| AI model | Gemma4-E4B via Unsloth 4-bit on DGX Spark (dgx1, GB10 GPU) |
| DGX API | FastAPI at `http://dgx1:9001`, screen session `gemma4_api` |
| WSGI | gunicorn (2 workers, 120s timeout, port 5018) |
| Frontend | Vanilla JS (no frameworks), Jinja2 templates |
| Service manager | `v2/run.sh` (setup/start/stop/restart/status/log/tail/create-admin) |

---

## Directory Layout

```
v2/
├── app.py                   # Flask app factory, CLI commands
├── run.sh                   # Service manager
├── requirements.txt
├── test_data.json           # Seed data for testing
├── config/
│   └── settings.py          # All env-backed config (DGX_BASE_URL, SCORE_WEIGHTS, etc.)
├── models/
│   └── db_models.py         # User, Experiment, Candidate, Comment, Like
├── api/
│   ├── auth.py              # /login, /logout
│   ├── experiments.py       # /api/v2/generate, CRUD, publish, retract, suggest-metadata
│   ├── feed.py              # /api/v2/feed, likes, comments, /api/health
│   ├── admin.py             # /admin pages, /api/admin/users
│   └── schemas.py           # Marshmallow schemas
├── services/
│   ├── molecule_generator.py   # Calls Gemma4, parses SMILES, retries 3x
│   ├── molecule_validator.py   # filter_candidates() — deduplicates, validates
│   ├── property_calculator.py  # compute_all(): QED, SAS, LogP, MW, Tanimoto, Lipinski
│   └── dti_predictor.py        # Phase 1 heuristic DTI + composite_score()
├── utils/
│   ├── mol_utils.py         # canonicalize(), is_valid(), mol_to_svg()
│   └── protein_utils.py     # is_valid_sequence(), clean_sequence()
├── templates/
│   ├── base.html            # Navbar, flash alerts, loads app.js
│   ├── login.html
│   ├── feed.html            # Class feed page
│   ├── run.html             # Run experiment + Save & Publish panel (with AI Suggest)
│   ├── experiment.html      # Experiment detail, Edit section (with AI Suggest), comments
│   ├── dashboard.html
│   └── admin/
│       ├── overview.html
│       └── users.html
└── static/
    ├── css/style.css
    └── js/
        ├── app.js           # apiFetch(), showAlert(), setLoading(), formatDate(), molSvgUrl()
        ├── run.js           # Generation form, results table, publish, AI Suggest
        ├── experiment.js    # Like, comments, candidate table, loadComments guard
        └── feed.js          # Feed rendering, sort/filter controls
```

---

## Data Models

### User
`id (UUID PK) | username | display_name | email | password_hash (bcrypt) | role (student/admin) | cohort | is_active | created_at | last_login`

### Experiment
`id | user_id FK | title | hypothesis | amino_acid_seq | seed_smile | noise_level | num_requested | status (draft/published/retracted/archived) | version | published_at | gemma4_latency_ms | num_valid_generated | created_at | updated_at`  
Properties: `like_count`, `comment_count` (computed, not stored)

### Candidate
`id | experiment_id FK CASCADE | smiles | qed | sas | logp | mw | tanimoto | dti_score | lipinski_pass | composite_score | rank`

### Comment
`id | experiment_id FK | user_id FK | parent_id FK (self-ref, one level deep) | body | tag (question/suggestion/correction/praise) | is_edited | is_deleted | created_at | edited_at`

### Like
`user_id PK + experiment_id PK | created_at` (composite PK — one like per user per experiment)

---

## Core Pipeline (what happens when a student clicks Generate)

```
POST /api/v2/generate
  → validate AA seq (protein_utils)
  → canonicalize seed SMILES (mol_utils / RDKit)
  → molecule_generator.generate()
       → build Gemma4 prompt (seed SMILES, first 80 AA, diversity level, n)
       → POST http://dgx1:9001/v1/text   ← Gemma4 FastAPI
       → parse SMILES lines with regex
       → filter_candidates() → deduplicate, validate with RDKit
       → retry up to 3x if < n valid candidates
  → for each valid SMILES:
       property_calculator.compute_all()  → QED, SAS, LogP, MW, Tanimoto, Lipinski
       dti_predictor.predict()            → heuristic DTI score [0,1]
       dti_predictor.composite_score()    → final rank score
  → re-rank by composite score
  → save Experiment + Candidates to PostgreSQL
  → return JSON to frontend
```

### Scoring formulas

**DTI heuristic (Phase 1):**
```
score = 0.35 × QED
      + 0.25 × (1 if Lipinski else 0)
      + 0.20 × (1 if 0≤LogP≤3 else 0.5 if -1≤LogP≤5 else 0)
      + 0.20 × max(0, (10 - SAS) / 9)
```

**Composite score:**
```
score = 0.35 × DTI + 0.30 × QED + 0.20 × (1 - SAS/9) + 0.15 × Tanimoto
```
Weights are in `config/settings.py → SCORE_WEIGHTS`.

---

## Key API Endpoints

| Method | URL | Who | What |
|---|---|---|---|
| POST | `/api/v2/generate` | Student | Run generation pipeline |
| GET | `/api/v2/experiments` | Student | List own experiments |
| GET/PATCH | `/api/v2/experiments/<id>` | Student/Admin | Get or update experiment |
| POST | `/api/v2/experiments/<id>/publish` | Owner | Publish to feed |
| POST | `/api/v2/experiments/<id>/retract` | Owner/Admin | Retract from feed |
| POST | `/api/v2/suggest-metadata` | Owner | Ask Gemma4 for title + hypothesis |
| GET | `/api/v2/feed` | Student | Paginated published experiments |
| POST | `/api/v2/experiments/<id>/like` | Student | Toggle like |
| GET/POST | `/api/v2/experiments/<id>/comments` | Student | Read / post comments |
| DELETE/PATCH | `/api/v2/comments/<id>` | Owner/Admin | Delete or edit comment |
| GET | `/api/v2/validate` | Student | Validate SMILES |
| POST | `/api/v2/properties` | Student | Compute molecule properties |
| GET | `/api/v2/mol/svg` | Student | Get SVG rendering of SMILES |
| GET | `/api/health` | Anyone | App + DGX health check |
| POST | `/api/admin/users` | Admin | Create student accounts |

---

## Access Control

- **Admin** creates student accounts. Students cannot self-register.
- **Draft** experiments: only owner + admin can view.
- **Published** experiments: all logged-in users can view, like, comment.
- **Admin** can see/retract any experiment.
- Comments: owner can edit/delete own; admin can delete any (soft-delete → `[removed by instructor]`).

---

## AI Suggest Feature (✨ button)

Available on two pages:
1. **`/run`** — Save & Publish panel, after generation completes
2. **`/experiments/<id>`** — Edit section (only visible to experiment owner)

Flow:
1. Frontend clicks "✨ AI Suggest" → `POST /api/v2/suggest-metadata` with `{experiment_id}`
2. Backend fetches experiment + top 3 candidates from DB
3. Builds Gemma4 prompt asking for JSON `{title, hypothesis}`
4. Parses response with regex (handles extra text around JSON)
5. Frontend shows preview card → Accept fills the fields / Retry calls again / Dismiss hides
6. User still clicks "Save Changes" or "Publish" to persist

**Important:** Gemma4 response key is `"response"` (not `"text"`) — must match `molecule_generator.py`.

---

## DGX / Gemma4 Operations

```bash
ssh dlyog@dgx1                        # passwordless SSH
screen -r gemma4_api                  # reattach to running API session
# If dead:
screen -S gemma4_api
cd /home/dlyog1/gemma4_api            # (verify actual path)
python server.py                      # or whatever starts FastAPI
# Health check:
curl http://dgx1:9001/health
```

DGX IP: 192.168.86.107 (same LAN as Mac). If SSH times out, Mac is on a different network.

---

## Known Bugs Fixed

| Bug | Fix |
|---|---|
| `Limiter(app, key_func=...)` TypeError | Changed to `Limiter(get_remote_address, app=app, ...)` |
| RDKit NumPy 2.x incompatibility | Pinned `numpy<2` in requirements.txt |
| marshmallow 4.x API break | Pinned `marshmallow>=3.21,<4` |
| Empty SMILES reported valid | Added `not smiles.strip()` and `mol.GetNumAtoms() == 0` guards in `mol_utils.py` |
| `loadComments` null crash on drafts | Added `if (!container) return;` guard in `experiment.js:17` |
| `suggest-metadata` wrong response key | Changed `"text"` → `"response"` in `experiments.py` to match Gemma4 API |
| Feed test failed when top candidate was None | Changed test to `any(item.get("top_candidate") for item in feed["items"])` |

---

## Test Accounts (from test_data.json)

| Username | Password | Role | Cohort |
|---|---|---|---|
| prof_tarun | admin123 | admin | Faculty |
| alice_gt | student123 | student | CS8803-Spring2026 |
| bob_gt | student123 | student | CS8803-Spring2026 |
| carol_gt | student123 | student | CS8803-Spring2026 |

Run full test suite: `cd v2 && python scripts/seed_and_test.py`

---

## Future Enhancements (ask Claude to implement these)

### High priority
- [ ] **Phase 2 DTI model** — Replace heuristic with ESM-2 (protein embeddings) + ECFP4 MLP trained on BindingDB. Training script stub at `scripts/train_dti.py`. Deploy on DGX, expose as `/v1/dti` endpoint, update `dti_predictor.py` to call it when available.
- [ ] **Gemma4 fine-tuning** — Fine-tune on known drug-target pairs (ChEMBL export) so it generates better SMILES. Use Unsloth LoRA on DGX. Update `molecule_generator.py` to point to fine-tuned checkpoint.
- [ ] **Experiment comparison view** — Side-by-side table of two experiments' top candidates, with property delta highlights.

### Medium priority
- [ ] **Molecule structure search** — Let students search the feed by substructure SMILES (RDKit `HasSubstructMatch`).
- [ ] **Export to CSV/SDF** — Download button on experiment page to export candidates as CSV or SDF file for use in external tools (Schrodinger, AutoDock).
- [ ] **Admin dashboard stats** — Charts on `/admin`: experiments per student, avg composite score by cohort, Gemma4 latency over time.
- [ ] **Email notifications** — Notify student when someone comments on their published experiment. Use Flask-Mail + SMTP.
- [ ] **Feed sort by score** — Feed currently sorts by newest/likes/comments. Add sort by "top composite score of leading candidate."
- [ ] **Comment editing on UI** — Backend supports PATCH `/api/v2/comments/<id>` but the frontend has no edit button yet.

### Lower priority / polish
- [ ] **Pagination controls on feed** — Feed API supports pagination (`page`, `per_page`) but the frontend currently loads page 1 only. Add infinite scroll or Next/Prev buttons.
- [ ] **Molecule similarity heatmap** — For an experiment with N candidates, render an N×N Tanimoto similarity grid.
- [ ] **Rate limiter storage** — Currently uses in-memory storage (gunicorn warning). Switch to Redis: `pip install flask-limiter[redis]`, set `RATELIMIT_STORAGE_URI=redis://localhost:6379` in `.env`.
- [ ] **SMILES diversity check** — Pre-filter generated SMILES so no two candidates have Tanimoto > 0.9 to each other (avoids near-duplicate clusters).
- [ ] **Retracted experiment recovery** — Admin UI button to restore a retracted experiment to draft.
- [ ] **Student profile page** — `/profile/<username>` showing all published experiments, like count, cohort.

---

## MCP (Model Context Protocol) Integration Plan

### What MCP is
MCP servers expose tools that AI agents (Claude) can call. For Deep2Lead, the strategy is **two-pronged**:
1. **Backend enrichment** — Flask calls the underlying public REST APIs directly (simpler than running MCP servers as subprocesses). The Flask endpoints wrap these APIs and return structured JSON to the frontend.
2. **Claude Code MCP config** — configure MCP servers in `~/.claude/mcp.json` so Claude can look up drug data while developing or helping students.

The underlying REST APIs that the MCP servers wrap are all **public and free** — no API key required for Tier 1 servers.

---

### Tier 1 — Integrate into Flask backend (no API key, free, high value)

#### 1. ChEMBL REST API → `POST /api/v2/enrich/chembl`
- **What**: Bioactivity data (IC50, Ki, EC50) for any SMILES against any target
- **REST base**: `https://www.ebi.ac.uk/chembl/api/data`
- **MCP server**: `github.com/Augmented-Nature/ChEMBL-MCP-Server` (27 tools, Node.js stdio)
- **Flask call**: `GET /chembl/api/data/similarity/{smiles}/85?format=json` for similar compounds
- **Use in app**: After generation, show known ChEMBL bioactivity for each candidate; cross-validate DTI heuristic score against real IC50 data

#### 2. PubChem REST API → `POST /api/v2/enrich/pubchem`
- **What**: 110M compound database — lookup by SMILES, get CID, synonyms, XLogP3, GHS hazard, patent cross-refs
- **REST base**: `https://pubchem.ncbi.nlm.nih.gov/rest/pug`
- **MCP server**: `github.com/Augmented-Nature/PubChem-MCP-Server` (24 tools, Node.js stdio)
- **Flask call**: `GET /pug/compound/smiles/{encoded_smiles}/property/XLogP,MolecularWeight,IUPACName/JSON`
- **Use in app**: Check if generated SMILES already exists in PubChem (novelty check); pull XLogP3 for LogP validation; fetch GHS hazard flags

#### 3. Open Targets GraphQL API → `POST /api/v2/enrich/target`
- **What**: Evidence scores linking genes to diseases from 20+ databases (ChEMBL, ClinVar, GWAS, Reactome)
- **REST base**: `https://api.platform.opentargets.org/api/v4/graphql`
- **MCP server**: `github.com/Augmented-Nature/OpenTargets-MCP-Server` (6 tools, Node.js stdio)
- **Flask call**: GraphQL POST with gene symbol query
- **Use in app**: Validate target choice — show disease association score before running generation; surface related targets student may not have considered

#### 4. UniProt REST API → `POST /api/v2/enrich/protein`
- **What**: Protein name, function, active sites, disease associations, sequence
- **REST base**: `https://rest.uniprot.org/uniprotkb`
- **MCP server**: `github.com/Augmented-Nature/Augmented-Nature-UniProt-MCP-Server` (26 tools, Node.js stdio)
- **Flask call**: `GET /uniprotkb/search?query={gene_name}&format=json`
- **Use in app**: Auto-enrich the protein target card on the experiment page with UniProt annotation; suggest canonical sequence if student's sequence has errors

#### 5. AlphaFold EBI API → `GET /api/v2/enrich/alphafold`
- **What**: Predicted 3D structure + per-residue confidence (pLDDT) for any UniProt protein
- **REST base**: `https://alphafold.ebi.ac.uk/api`
- **MCP server**: `github.com/Augmented-Nature/AlphaFold-MCP-Server` (20+ tools, HTTP)
- **Flask call**: `GET /api/prediction/{uniprot_id}`
- **Use in app**: Link to AlphaFold structure viewer for the target protein; show pLDDT confidence for key residues in the binding pocket

---

### Tier 2 — Literature enrichment (free, some optional API keys)

#### 6. PubMed / NCBI API → `GET /api/v2/enrich/literature`
- **What**: Search PubMed for papers on target protein or seed molecule
- **REST base**: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils`
- **MCP server**: `github.com/cyanheads/pubmed-mcp-server` (9 tools, bunx/stdio)
- **Flask call**: `GET /esearch.fcgi?db=pubmed&term={query}&retmax=5&format=json`
- **Use in app**: "Related papers" panel on experiment page; auto-suggest citations for hypothesis; optionally show in feed card

#### 7. Semantic Scholar API → `GET /api/v2/enrich/papers`
- **What**: Semantic search across 200M+ papers; citation graphs
- **REST base**: `https://api.semanticscholar.org/graph/v1`
- **MCP server**: `github.com/akapet00/semantic-scholar-mcp` (Python, uvx)
- **API key**: Optional free key from semanticscholar.org (higher rate limits)
- **Use in app**: Better relevance than PubMed keyword search for finding mechanistic papers

---

### Tier 3 — Regulatory & Drug DB (free academic registration required)

#### 8. OpenFDA API → `GET /api/v2/enrich/fda`
- **What**: Adverse events (FAERS), product labels, drug recalls
- **REST base**: `https://api.fda.gov/drug`
- **MCP server**: `github.com/Augmented-Nature/OpenFDA-MCP-Server` (10 tools)
- **API key**: Optional free key from open.fda.gov (upgrades rate limit 1K → 120K/hr)
- **Use in app**: Show FDA safety context for drugs in the same class as the candidate

#### 9. DrugBank SQLite MCP → enriches the experiment detail page
- **What**: 17,430 drugs — pharmakokinetics, drug-drug interactions, metabolic pathways
- **MCP server**: `github.com/openpharma-org/drugbank-mcp-server` (Node.js stdio, SQLite)
- **Requires**: Free academic registration at go.drugbank.com to download XML → convert to SQLite
- **Use in app**: Check if target already has approved drugs; show their half-life for comparison

---

### Implementation approach (tell Claude to build this)

```
For any enrichment endpoint, the pattern is:
1. Add route to v2/api/enrich.py (new Blueprint)
2. Call underlying public REST API with httpx/requests
3. Cache response in Redis or in-memory LRU (avoid hammering free APIs)
4. Return structured JSON to frontend
5. Frontend fetches lazily (on-demand, not blocking page load)
6. Show enrichment data in collapsible panel on experiment page
```

The Flask proxy approach means students don't need API keys and the app controls rate limiting.

---

### For Claude Code development (MCP config)
Add to `~/.claude/mcp.json` to let Claude look up drug data while coding:
```json
{
  "mcpServers": {
    "fetch": { "command": "uvx", "args": ["mcp-server-fetch"] },
    "pubmed": { "command": "bunx", "args": ["@cyanheads/pubmed-mcp-server@latest"] },
    "brave-search": {
      "command": "npx", "args": ["-y", "@brave/brave-search-mcp-server"],
      "env": { "BRAVE_API_KEY": "your-key" }
    }
  }
}
```

---

### Key GitHub orgs producing drug discovery MCP servers
- **Augmented Nature**: `github.com/Augmented-Nature` — ChEMBL, PubChem, UniProt, PDB, AlphaFold, STRING, KEGG, Open Targets, OpenFDA, PubMed, SureChEMBL, Ensembl, Reactome (all free, no API key)
- **OpenPharma**: `github.com/openpharma-org` — DrugBank, EMA, PubMed (free academic)
- **Official MCP**: `github.com/modelcontextprotocol/servers` — Fetch, Brave Search, filesystem
