"""Semantic skill matching for opportunity_mcp: embeddings + cosine similarity."""
from __future__ import annotations

import math
from sources import remoteok
from sentence_transformers import SentenceTransformer
from sentence_transformers import util


_EMB_MODEL = None

ALIASES = {
  "k8s": "kubernetes",
  "k8": "kubernetes",
  "js": "javascript",
  "ts": "typescript",
  "postgres": "postgresql",
  "psql": "postgresql",
  "aws": "amazon web services",
  "gcp": "google cloud",
  "nlp": "natural language processing",
  "ml": "machine learning",
  "dl": "deep learning",
  "golang": "go",
}

_BLUE_ANCHORS = ["manual labor and physical work", "factory and production line worker", "construction and skilled trades", "warehouse machinery and equipment operation", "driving trucking and material handling", "maintenance cleaning and groundskeeping"]
_WHITE_ANCHORS = ["office and professional desk work", "software engineering and data science", "devops cloud infrastructure kubernetes and ci cd pipelines", "information technology systems and networking", "management and business strategy", "sales marketing and communications", "finance and accounting analysis", "design research and writing"]
_ANCHOR_EMB = None


def _anchors():
  global _ANCHOR_EMB
  if _ANCHOR_EMB is None:
    m = _get_model()
    _ANCHOR_EMB = (m.encode(_BLUE_ANCHORS), m.encode(_WHITE_ANCHORS))
  return _ANCHOR_EMB


def is_blue_collar(job_text: str, margin: float = 0.05) -> bool:
  """True if the job reads blue-collar: closer to manual/trade anchors than office/professional ones."""
  blue_emb, white_emb = _anchors()
  jt = _get_model().encode(job_text[:2000])
  blue = float(util.cos_sim(jt, blue_emb).max())
  white = float(util.cos_sim(jt, white_emb).max())
  return blue > white + margin

def _canon(skills: list[str]) -> list[str]:
  return sorted({ALIASES.get(s, s) for s in skills})

def _get_model():
  global _EMB_MODEL
  if _EMB_MODEL is None:
    
    _EMB_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
  return _EMB_MODEL


def semantic_split(job_skills: list[str], my_skills: list[str], threshold: float = 0.55) -> tuple[list[str], list[str]]:
  """Split required skills into (matched, missing) by best cosine similarity to owned skills."""
  job_skills = _canon(job_skills)
  my_skills = _canon(my_skills)
  if not job_skills:
    return [], []
  if not my_skills:
    return [], sorted(job_skills)
  
  model = _get_model()
  sims = util.cos_sim(model.encode(job_skills), model.encode(my_skills))
  matched, missing = [], []
  for i, skill in enumerate(job_skills):
    if float(sims[i].max()) >= threshold:
      matched.append(skill)
    else:
      missing.append(skill)
  return sorted(matched), sorted(missing)

def haversine(a: tuple, b: tuple) -> float:
  """Great-circle distance in km between (lat, lon) points a and b."""
  (lat1, lon1), (lat2, lon2) = a, b
  r = 6371.0
  p1, p2 = math.radians(lat1), math.radians(lat2)
  # dphi = difference in latitude, dlmb = difference in longitude
  dphi = math.radians(lat2 - lat1)
  dlmb = math.radians(lon2 - lon1)
  h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
  return 2 * r * math.asin(math.sqrt(h))


def commute_factor(distance_km: float, max_km: float = 50.0) -> float:
  """1.0 when co-located, decaying linearly to 0.0 at/after max_km."""
  if distance_km <= 0:
    return 1.0
  if distance_km >= max_km:
    return 0.0
  return 1 - distance_km / max_km

def score(job_skills: list[str], my_skills: list[str], required_mandatory: list[str] | None = None, preferred_in_job: list[str] | None = None, held_licenses: list[str] | None = None, candidate_coords: tuple | None = None, job_coords: tuple | None = None, remote: bool = False, blue_collar: bool = False, can_relocate: bool = False, threshold: float = 0.55, max_km: float = 50.0) -> dict:
  """Semantic skills + mandatory-license gate + preferred adjustment + commute factor (onsite only)."""
  matched, missing = semantic_split(job_skills, my_skills, threshold)
  base = round(len(matched) / len(job_skills) * 100) if job_skills else 0
  held = set(held_licenses or [])
  missing_mandatory = sorted(set(required_mandatory or []) - held)
  eligible = not missing_mandatory
  preferred = set(preferred_in_job or [])
  preferred_have = sorted(preferred & held)
  preferred_missing = sorted(preferred - held)
  adjust = 5 * len(preferred_have) - 3 * len(preferred_missing)
  pct = 0 if not eligible else max(0, min(100, base + adjust))
  commute_km = None
  factor = 1.0
  if not remote and (blue_collar or not can_relocate) and candidate_coords and job_coords:
    commute_km = round(haversine(candidate_coords, job_coords), 1)
    factor = commute_factor(commute_km, max_km)
    pct = round(pct * factor)
  return {
    "score": pct,
    "eligible": eligible,
    "matched": matched,
    "missing": missing,
    "missing_mandatory": missing_mandatory,
    "preferred_have": preferred_have,
    "preferred_missing": preferred_missing,
    "commute_km": commute_km,
    "commute_factor": round(factor, 2),
  }