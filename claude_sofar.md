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
