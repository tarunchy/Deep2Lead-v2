#!/usr/bin/env python3
"""
Seed test data and verify all app objectives.
Run from v2/ with: python scripts/seed_and_test.py
"""
import json
import sys
import time
import requests

BASE = "http://localhost:5018"
DATA = json.load(open("test_data.json"))

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
HEAD = "\033[1m"
END  = "\033[0m"

errors = []

def check(label, condition, detail=""):
    if condition:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}" + (f"  → {detail}" if detail else ""))
        errors.append(label)

def section(title):
    print(f"\n{HEAD}── {title} {'─'*(50-len(title))}{END}")

def login(username, password):
    s = requests.Session()
    r = s.post(f"{BASE}/login", data={"username": username, "password": password},
                allow_redirects=True)
    return s, r.status_code < 400

# ── 1. Health check ────────────────────────────────────────────────
section("1. System Health")
r = requests.get(f"{BASE}/api/health")
check("API is reachable", r.status_code == 200)
h = r.json()
check("Health endpoint returns status", h.get("status") == "ok")
check("Gemma4 on DGX is reachable", h.get("dgx_gemma4") == "ready",
      "DGX may be busy or port 9001 unreachable")

# ── 2. Admin account ───────────────────────────────────────────────
section("2. Admin Account Creation")
admin = DATA["admin"]

# Create via Flask CLI (already done in setup, try via API if exists)
admin_session, ok = login(admin["username"], admin["password"])
if not ok:
    # Bootstrap admin via direct DB insert through seed
    print(f"  Admin not found — creating via CLI (run: ./run.sh create-admin {admin['username']} {admin['password']})")
    import subprocess
    subprocess.run(
        ["python", "-c",
         f"import sys; sys.path.insert(0,'.');"
         f"from app import create_app; from models.db_models import db, User;"
         f"app=create_app();\n"
         f"with app.app_context():\n"
         f"  u=User(username='{admin['username']}',display_name='{admin['display_name']}',role='admin',cohort='{admin['cohort']}');\n"
         f"  u.set_password('{admin['password']}'); db.session.add(u); db.session.commit();\n"
         f"  print('Admin created')"],
        capture_output=True
    )
    admin_session, ok = login(admin["username"], admin["password"])

check("Admin login succeeds", ok)
check("Admin can access /admin", admin_session.get(f"{BASE}/admin").status_code == 200)

# ── 3. Student account creation (admin creates) ────────────────────
section("3. Student Account Management")
student_sessions = {}
for student in DATA["students"]:
    r = admin_session.post(f"{BASE}/api/admin/users", json={
        "username": student["username"],
        "password": student["password"],
        "display_name": student["display_name"],
        "cohort": student["cohort"],
        "role": "student"
    })
    created = r.status_code in (201, 409)  # 409 = already exists
    check(f"Admin creates student '{student['username']}'", created, r.text[:100])
    s, ok = login(student["username"], student["password"])
    check(f"Student '{student['username']}' can login", ok)
    student_sessions[student["username"]] = s

# ── 4. Non-admin cannot access admin panel ─────────────────────────
section("4. Role-Based Access Control")
alice_session = student_sessions["alice_gt"]
r = alice_session.get(f"{BASE}/admin")
check("Student cannot access /admin (403)", r.status_code == 403)
r = alice_session.post(f"{BASE}/api/admin/users", json={"username":"hacker","password":"x","role":"admin"})
check("Student cannot create users (403)", r.status_code == 403)

# ── 5. Molecule validation ─────────────────────────────────────────
section("5. SMILES Validation")
valid_smiles = [("C1CNP(=O)(OC1)N(CCCl)CCCl", True), ("CC(=O)Oc1ccccc1C(=O)O", True), ("NOTASMILES!!", False), ("", False)]
for smiles, expected in valid_smiles:
    r = alice_session.post(f"{BASE}/api/v2/validate", json={"smiles": smiles})
    result = r.json().get("valid", False)
    check(f"Validate '{smiles[:30]}…' → {expected}", result == expected)

# ── 6. Property calculation ────────────────────────────────────────
section("6. Molecular Property Calculation")
r = alice_session.post(f"{BASE}/api/v2/properties", json={
    "smiles": "CC(=O)Oc1ccccc1C(=O)O",  # Aspirin
    "seed_smile": "CC(=O)Oc1ccccc1C(=O)O"
})
check("Properties endpoint returns 200", r.status_code == 200)
props = r.json()
check("QED is in [0,1]", 0 <= props.get("qed", -1) <= 1, str(props.get("qed")))
check("SAS is in [1,10]", 1 <= props.get("sas", 0) <= 10, str(props.get("sas")))
check("LogP returned", props.get("logp") is not None)
check("MW returned", props.get("mw") is not None)
check("Tanimoto = 1.0 for same molecule", abs(props.get("tanimoto", 0) - 1.0) < 0.001)
check("Lipinski pass returned", props.get("lipinski_pass") is not None)

# ── 7. Experiment generation (Gemma4 pipeline) ────────────────────
section("7. Molecule Generation via Gemma4")
experiment_ids = {}
for exp_data in DATA["experiments"]:
    username = exp_data["by"]
    session = student_sessions[username]
    print(f"  Generating for {username}: '{exp_data['title']}' …")
    r = session.post(f"{BASE}/api/v2/generate", json={
        "amino_acid_seq": exp_data["amino_acid_seq"],
        "smile": exp_data["smile"],
        "noise": exp_data["noise"],
        "num_candidates": exp_data["num_candidates"]
    })
    check(f"  Generation returns 201", r.status_code == 201, r.text[:150])
    if r.status_code == 201:
        body = r.json()
        exp_id = body["experiment_id"]
        experiment_ids[username] = exp_id
        candidates = body.get("candidates", [])
        check(f"  Returns candidates (got {len(candidates)})", len(candidates) > 0)
        if candidates:
            top = candidates[0]
            check(f"  Top candidate has composite_score", top.get("composite_score") is not None)
            check(f"  Top candidate has DTI score", top.get("dti_score") is not None)
            check(f"  Top candidate has QED", top.get("qed") is not None)
            check(f"  Top candidate SMILES is non-empty", bool(top.get("smiles")))

        # Update title + hypothesis
        session.patch(f"{BASE}/api/v2/experiments/{exp_id}", json={
            "title": exp_data["title"],
            "hypothesis": exp_data["hypothesis"]
        })

        # Publish if flagged
        if exp_data.get("publish"):
            r2 = session.post(f"{BASE}/api/v2/experiments/{exp_id}/publish")
            check(f"  Experiment published to feed", r2.status_code == 200, r2.text[:100])

# ── 8. Feed & author attribution ──────────────────────────────────
section("8. Feed & Author Attribution")
r = alice_session.get(f"{BASE}/api/v2/feed")
check("Feed returns 200", r.status_code == 200)
feed = r.json()
published_count = feed.get("total", 0)
check(f"Feed has published experiments (got {published_count})", published_count > 0)
if feed.get("items"):
    item = feed["items"][0]
    check("Feed item has author field", bool(item.get("author")))
    check("Feed item has cohort field", item.get("cohort") is not None)
    check("Feed item has seed_smile", bool(item.get("seed_smile")))
    # top_candidate may be None if Gemma4 returned 0 valid SMILES for that seed
    has_any_top = any(i.get("top_candidate") for i in feed["items"])
    check("At least one feed item has top_candidate", has_any_top)

# ── 9. Likes ──────────────────────────────────────────────────────
section("9. Likes")
if feed.get("items"):
    target_id = feed["items"][0]["id"]
    # Bob likes Alice's experiment
    r = student_sessions["bob_gt"].post(f"{BASE}/api/v2/experiments/{target_id}/like")
    check("Student can like an experiment", r.status_code == 200, r.text[:80])
    data = r.json()
    check("Like toggled = True", data.get("liked") == True)
    check("Like count increased", data.get("like_count", 0) >= 1)
    # Unlike
    r2 = student_sessions["bob_gt"].post(f"{BASE}/api/v2/experiments/{target_id}/like")
    check("Student can unlike (toggle off)", r2.json().get("liked") == False)
    # Like again to leave it liked for demo
    student_sessions["bob_gt"].post(f"{BASE}/api/v2/experiments/{target_id}/like")

# ── 10. Comments & threading ──────────────────────────────────────
section("10. Comments & Threaded Replies")
if feed.get("items"):
    target_id = feed["items"][0]["id"]
    # Post comments from test data
    posted_comment_id = None
    for cmt in DATA["comments"]:
        by_session = student_sessions.get(cmt["by"])
        if not by_session:
            continue
        r = by_session.post(f"{BASE}/api/v2/experiments/{target_id}/comments", json={
            "body": cmt["body"],
            "tag": cmt["tag"]
        })
        ok = r.status_code == 201
        check(f"  {cmt['by']} posts comment (tag={cmt['tag']})", ok, r.text[:80])
        if ok and posted_comment_id is None:
            posted_comment_id = r.json().get("id")

    # Post a threaded reply
    if posted_comment_id:
        r = student_sessions["carol_gt"].post(f"{BASE}/api/v2/experiments/{target_id}/comments", json={
            "body": "Agreed — the Tanimoto filter really helps with candidate diversity.",
            "parent_id": posted_comment_id
        })
        check("Carol posts threaded reply", r.status_code == 201)

    # Read comments back
    r = alice_session.get(f"{BASE}/api/v2/experiments/{target_id}/comments")
    check("Comments endpoint returns 200", r.status_code == 200)
    cmts = r.json()
    check(f"Comments returned (got {len(cmts)})", len(cmts) > 0)
    if cmts and cmts[0].get("replies"):
        check("Threaded reply present", len(cmts[0]["replies"]) > 0)

# ── 11. Draft stays private ───────────────────────────────────────
section("11. Draft Privacy")
carol_draft_id = experiment_ids.get("carol_gt")
if carol_draft_id:
    # Bob should NOT see Carol's draft
    r = student_sessions["bob_gt"].get(f"{BASE}/api/v2/experiments/{carol_draft_id}")
    check("Bob cannot see Carol's draft (404)", r.status_code == 404)
    # Carol can see her own draft
    r = student_sessions["carol_gt"].get(f"{BASE}/api/v2/experiments/{carol_draft_id}")
    check("Carol can see her own draft", r.status_code == 200)
    # Admin can see any draft
    r = admin_session.get(f"{BASE}/api/v2/experiments/{carol_draft_id}")
    check("Admin can see any draft", r.status_code == 200)

# ── 12. Molecule SVG rendering ────────────────────────────────────
section("12. Molecule SVG Rendering")
test_smiles = "CC(=O)Oc1ccccc1C(=O)O"
r = alice_session.get(f"{BASE}/api/v2/mol/svg?smiles={requests.utils.quote(test_smiles)}")
check("SVG endpoint returns 200", r.status_code == 200)
check("Response is SVG content", "svg" in r.headers.get("Content-Type","").lower())
check("SVG contains molecule drawing", "<svg" in r.text)

# ── Summary ───────────────────────────────────────────────────────
section("Summary")
total = 0
passed = 0
# Count from errors list
total_checks = sum(1 for _ in [])  # will just use errors list
if errors:
    print(f"\n  {FAIL} {len(errors)} checks failed:")
    for e in errors:
        print(f"      • {e}")
else:
    print(f"\n  {PASS} All checks passed!")

print(f"""
  App URL:    http://localhost:5018
  Login:      username=prof_tarun  password=admin123 (admin)
              username=alice_gt    password=student123
              username=bob_gt      password=student123
              username=carol_gt    password=student123
""")
