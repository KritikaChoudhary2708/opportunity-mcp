"""Semantic skill matching for opportunity_mcp: embeddings + cosine similarity."""
from __future__ import annotations
from sentence_transformers import SentenceTransformer
from sentence_transformers import util

_EMB_MODEL = None


def _get_model():
  global _EMB_MODEL
  if _EMB_MODEL is None:
    
    _EMB_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
  return _EMB_MODEL


def semantic_split(job_skills: list[str], my_skills: list[str], threshold: float = 0.55) -> tuple[list[str], list[str]]:
  """Split required skills into (matched, missing) by best cosine similarity to owned skills."""
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


def score(job_skills: list[str], my_skills: list[str], threshold: float = 0.55) -> dict:
  """Return {score, matched, missing} for required vs owned skills."""
  matched, missing = semantic_split(job_skills, my_skills, threshold)
  pct = round(len(matched) / len(job_skills) * 100) if job_skills else 0
  return {"score": pct, "matched": matched, "missing": missing}