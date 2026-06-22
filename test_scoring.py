"""
Offline checks for the opportunity_mcp scoring system.

Run:  python test_scoring.py

No pytest needed. Each check prints PASS/FAIL; exits non-zero if anything fails.
(The semantic checks load a small embedding model on first run.)
"""
from scoring import (
    semantic_split, score, is_blue_collar, _canon, haversine, commute_factor,
)

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

# --- score: commute OR-gate ---
MUM, PUNE = (19.07, 72.88), (18.52, 73.86)
check("white-collar + can relocate -> commute skipped (100)",
      lambda: (lambda r: r["score"] == 100 and r["commute_km"] is None)
      (score(["python"], ["python"], candidate_coords=MUM, job_coords=PUNE, blue_collar=False, can_relocate=True)))
check("cannot relocate + far job -> commute applies (0)",
      lambda: (lambda r: r["score"] == 0 and r["commute_factor"] == 0.0)
      (score(["python"], ["python"], candidate_coords=MUM, job_coords=PUNE, blue_collar=False, can_relocate=False)))

# --- semantic blue-collar classifier ---
check("labourer JD classified blue-collar",
      lambda: is_blue_collar("Labourer cleans the mill, removes copper from the conveyor, applies grease to machinery, heavy lifting, reliable transportation") is True)
check("software JD not blue-collar",
      lambda: is_blue_collar("Senior software engineer, Python, React, AWS, building APIs and microservices") is False)


print("\n" + "-" * 40)
print(f"{_passed} passed, {_failed} failed")
if _failed:
    raise SystemExit(1)