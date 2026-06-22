"""Ranking: order opportunities by fit to a resume."""
from __future__ import annotations


def rank_opportunities(jobs: list[dict], resume_text: str, score_fn, candidate_location: str = "", can_relocate: bool = False) -> list[dict]:
  """Score each job with score_fn and return them sorted best-first. score_fn is injected so this module never imports the server (no circular import)."""
  ranked = []
  for job in jobs:
    job_text = " ".join([job.get("title", ""), job.get("snippet", ""), " ".join(job.get("skills") or [])])
    try:
      fit = score_fn(resume_text, job_text, candidate_location, job.get("location", ""), can_relocate)
    except Exception:
      continue
    ranked.append({"title": job.get("title"), "company": job.get("company"), "source": job.get("source"), "url": job.get("url"), "score": fit["score"], "eligible": fit["eligible"], "matched": fit["matched"], "missing": fit["missing"]})
  ranked.sort(key=lambda r: r["score"], reverse=True)
  return ranked