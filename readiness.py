"""Market readiness: scan the job market with a resume and summarize fit.

Pure logic. The async search and the scorer are injected by the server, so this
module imports nothing from server.py.

Design note: no hardcoded "broad skill" list (that would bake in domain bias).
Search seeds come only from what the resume emphasizes (mention frequency), which
self-adapts per user; relevance is decided by the scorer + the min_score filter,
not by an author-curated word list.
"""
from __future__ import annotations

from collections import Counter


def top_skills(resume_text: str, skills: list[str], n: int = 3) -> list[str]:
  """The n skills the resume emphasizes most (by mention frequency), used to
  seed market searches. Neutral and self-adapting: an AI resume seeds AI, a
  frontend resume seeds frontend."""
  low = resume_text.lower()
  return sorted(skills, key=lambda s: low.count(s), reverse=True)[:n]


def summarize(ranked: list[dict], my_skills: list[str], min_score: int = 30) -> dict:
  """Aggregate scored jobs into a market-readiness report.
  Shortlist and gaps use only RELEVANT jobs (score >= min_score) so off-target
  listings don't pollute the study list. The scorer decides relevance."""
  relevant = [r for r in ranked if r["score"] >= min_score]
  scores = [r["score"] for r in ranked]
  avg = round(sum(scores) / len(scores)) if scores else 0
  gaps: Counter = Counter()
  for r in relevant:
    gaps.update(r.get("missing", []))
  band = "strong" if avg >= 70 else "moderate" if avg >= 40 else "needs work"
  return {
    "jobs_scanned": len(ranked),
    "relevant_matches": len(relevant),
    "avg_fit": avg,
    "readiness": band,
    "eligible_for": sum(1 for r in ranked if r.get("eligible")),
    "your_skills": my_skills,
    "top_market_gaps": [s for s, _ in gaps.most_common(10)],
    "shortlist": relevant[:10],
  }