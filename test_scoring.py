"""
Offline checks for the opportunity_mcp scoring + geolocation + ranking system.

Run:  python test_scoring.py

No pytest needed. Each check prints PASS/FAIL; exits non-zero if anything fails.
(The semantic checks load a small embedding model on first run. No live network:
the rank checks use a fake scorer via dependency injection.)
"""
from scoring import (
    semantic_split, score, is_blue_collar, _canon, haversine, commute_factor,
)
from server import _geocode
from rank import rank_opportunities
from tailor import build_resume
_passed = 0
_failed = 0


def check(name, fn):
    global _passed, _failed
    try:
        ok = bool(fn())
    except Exception as e:
        ok = False
        name = f"{name}  (error: {e})"
    print(("PASS  " if ok else "FAIL  ") + name)
    if ok:
        _passed += 1
    else:
        _failed += 1


# ============================ SCORING ============================

# --- distance math ---
check("haversine Mumbai->Pune is ~120 km",
      lambda: 100 < haversine((19.07, 72.88), (18.52, 73.86)) < 160)
check("commute_factor 0 km -> 1.0", lambda: commute_factor(0) == 1.0)
check("commute_factor 100 km -> 0.0 (beyond max)", lambda: commute_factor(100) == 0.0)
check("commute_factor 25 km -> 0.5", lambda: abs(commute_factor(25) - 0.5) < 0.01)

# --- abbreviation aliasing ---
check("alias k8s -> kubernetes", lambda: "kubernetes" in _canon(["k8s"]))
check("alias aws -> amazon web services", lambda: "amazon web services" in _canon(["aws"]))

# --- semantic skill matching ---
check("synonym matches: aws == amazon web services",
      lambda: semantic_split(["amazon web services"], ["aws"])[0] == ["amazon web services"])
check("unrelated misses: kubernetes vs python",
      lambda: semantic_split(["kubernetes"], ["python"])[1] == ["kubernetes"])

# --- score: skill coverage ---
check("coverage 1 of 2 required -> score 50",
      lambda: score(["python", "amazon web services"], ["python"])["score"] == 50)

# --- score: mandatory license gate ---
check("missing mandatory license -> ineligible, score 0",
      lambda: (lambda r: r["eligible"] is False and r["score"] == 0)
      (score(["python"], ["python"], required_mandatory=["rn"], held_licenses=[])))
check("missing mandatory license is reported",
      lambda: "rn" in score(["python"], ["python"], required_mandatory=["rn"], held_licenses=[])["missing_mandatory"])

# --- score: preferred license boost ---
check("preferred license held boosts score and is listed",
      lambda: (lambda base, boosted: boosted["score"] > base["score"] and "pmp" in boosted["preferred_have"])
      (score(["python", "sql"], ["python"]),
       score(["python", "sql"], ["python"], preferred_in_job=["pmp"], held_licenses=["pmp"])))

# --- semantic blue-collar classifier ---
check("labourer JD classified blue-collar",
      lambda: is_blue_collar("Labourer cleans the mill, removes copper from the conveyor, applies grease to machinery, heavy lifting, reliable transportation") is True)
check("software JD not blue-collar",
      lambda: is_blue_collar("Senior software engineer, Python, React, AWS, building APIs and microservices") is False)


# ========================== GEOLOCATION ==========================

# --- geocoder ---
check("geocode 'Mumbai' -> coordinates", lambda: _geocode("Mumbai") is not None)
check("geocode 'Pune' -> coordinates", lambda: _geocode("Pune") is not None)
check("geocode unknown place -> None", lambda: _geocode("Nowhereville") is None)
check("geocode '' -> None", lambda: _geocode("") is None)

# --- commute OR-gate (white-collar + can relocate => skipped) ---
MUM, PUNE = (19.07, 72.88), (18.52, 73.86)
check("white-collar + can relocate -> commute skipped (100)",
      lambda: (lambda r: r["score"] == 100 and r["commute_km"] is None)
      (score(["python"], ["python"], candidate_coords=MUM, job_coords=PUNE, blue_collar=False, can_relocate=True)))
check("cannot relocate + far job -> commute applies (0)",
      lambda: (lambda r: r["score"] == 0 and r["commute_factor"] == 0.0)
      (score(["python"], ["python"], candidate_coords=MUM, job_coords=PUNE, blue_collar=False, can_relocate=False)))
check("blue-collar + can relocate -> commute still applies (OR)",
      lambda: score(["python"], ["python"], candidate_coords=MUM, job_coords=PUNE, blue_collar=True, can_relocate=True)["score"] == 0)

# --- geocoder + commute integration (real city names end to end) ---
check("real geocode Mumbai->Pune, cannot relocate -> score 0",
      lambda: score(["python"], ["python"], candidate_coords=_geocode("Mumbai"),
                    job_coords=_geocode("Pune"), blue_collar=False, can_relocate=False)["score"] == 0)
check("real geocode same city -> commute factor 1.0",
      lambda: score(["python"], ["python"], candidate_coords=_geocode("Mumbai"),
                    job_coords=_geocode("Mumbai"), blue_collar=False, can_relocate=False)["commute_factor"] == 1.0)


# ============================ RANKING ============================
# rank_opportunities is pure (scorer injected) -> testable with a fake scorer,
# no network. We record what it forwards to assert location wiring + sorting.

_received = []


def _fake_score(resume, job_text, cand_loc, job_loc, can_relocate):
    _received.append((cand_loc, job_loc, can_relocate))
    return {"score": 90 if "python" in job_text.lower() else 10,
            "eligible": True, "matched": [], "missing": []}


_jobs = [
    {"title": "Backend Engineer", "snippet": "python and aws", "skills": [], "location": "Pune", "source": "x", "url": "u1", "id": "1"},
    {"title": "Sales Rep", "snippet": "selling and calls", "skills": [], "location": "Delhi", "source": "x", "url": "u2", "id": "2"},
]
_ranked = rank_opportunities(_jobs, "resume text", _fake_score, candidate_location="Mumbai", can_relocate=False)

check("rank passes candidate_location to scorer", lambda: all(r[0] == "Mumbai" for r in _received))
check("rank passes each job's location to scorer", lambda: {r[1] for r in _received} == {"Pune", "Delhi"})
check("rank passes can_relocate to scorer", lambda: all(r[2] is False for r in _received))
check("rank sorts best-fit first", lambda: _ranked[0]["score"] >= _ranked[1]["score"] and _ranked[0]["title"] == "Backend Engineer")

# ============================ TAILORING ============================
# Fake matcher (no model): a required skill is "covered" if it's in the fact's tags.
def _fake_match(req, tags):
    t = set(tags)
    return [s for s in req if s in t], [s for s in req if s not in t]


_facts = [
    {"id": "0", "type": "project",    "text": "Built a churn model in PyTorch", "tags": ["pytorch", "machine learning"]},
    {"id": "1", "type": "experience", "text": "Shipped APIs in Python on AWS",   "tags": ["python", "aws"]},
    {"id": "2", "type": "skill",      "text": "Comfortable with SQL",            "tags": ["sql"]},
    {"id": "3", "type": "education",  "text": "M.Tech in AI",                    "tags": []},
]
_req = ["python", "aws", "pytorch", "go"]
_fact_texts = {f["text"] for f in _facts}

_out = build_resume(_facts, _req, _fake_match, top_k=2)

check("build_resume greedy picks the highest-coverage fact first",
      lambda: _out["used_fact_ids"][0] == "1")
check("build_resume respects top_k",
      lambda: len(_out["used_fact_ids"]) == 2)
check("build_resume reports covered skills",
      lambda: set(_out["covered_skills"]) == {"python", "aws", "pytorch"})
check("build_resume reports the honest gap (go uncovered)",
      lambda: _out["uncovered_skills"] == ["go"])
check("build_resume NEVER invents: every bullet is a real fact's text",
      lambda: all(line[2:].rsplit("  _(fact", 1)[0] in _fact_texts
                  for line in _out["markdown"].splitlines() if line.startswith("- ")))

# With room to spare, zero-coverage facts (2, 3) are still skipped -> no filler.
_full = build_resume(_facts, _req, _fake_match, top_k=8)
check("build_resume adds no filler (skips zero-coverage facts)",
      lambda: set(_full["used_fact_ids"]) == {"0", "1"})

print("\n" + "-" * 40)
print(f"{_passed} passed, {_failed} failed")
if _failed:
    raise SystemExit(1)