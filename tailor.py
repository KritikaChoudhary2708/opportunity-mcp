"""Faithful-by-construction resume tailoring: SELECT true facts that cover a job's
required skills. Output is assembled only from existing fact text, so it can never
invent a claim. match_fn is injected (like rank.py) -> no scoring import, stays
unit-testable offline."""
from __future__ import annotations


def build_resume(facts: list[dict], required_skills: list[str], match_fn, top_k: int = 8) -> dict:
  """Pick up to top_k true facts that best cover required_skills (greedy max-coverage),
  render to Markdown with fact-id provenance, and report covered/uncovered skills."""
  # 1. How many required skills does each fact cover? (computed once, against the full need)
  coverage = []
  for f in facts:
    covered, _ = match_fn(required_skills, f.get("tags", []))
    coverage.append((f, set(covered)))

  # 2. Greedy max-coverage: repeatedly take the fact that adds the most NEW skills.
  selected, used, covered_all = [], set(), set()
  while len(selected) < top_k:
    best, best_gain = None, 0
    for f, cov in coverage:
      if f["id"] in used:
        continue
      gain = len(cov - covered_all)
      if gain > best_gain:
        best, best_gain = (f, cov), gain
    if best is None:              # no remaining fact adds coverage -> stop early
      break
    f, cov = best
    selected.append(f)
    used.add(f["id"])
    covered_all |= cov

  # 3. Render Markdown grouped by fact type, each line citing its source fact id.
  by_type: dict[str, list[dict]] = {}
  for f in selected:
    by_type.setdefault(f["type"], []).append(f)
  lines = []
  for t, group in by_type.items():
    lines.append(f"## {t.title()}")
    for f in group:
      lines.append(f"- {f['text']}  _(fact {f['id']})_")
  markdown = "\n".join(lines)

  # 4. Honest coverage report from the SELECTED facts (one match_fn call -> consistent).
  selected_tags = [tag for f in selected for tag in f.get("tags", [])]
  covered_skills, uncovered_skills = match_fn(required_skills, selected_tags)
  return {
    "markdown": markdown,
    "used_fact_ids": [f["id"] for f in selected],
    "covered_skills": covered_skills,
    "uncovered_skills": uncovered_skills,
  }