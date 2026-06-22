"""Remotive source: fetch remote jobs and normalize them into Opportunity."""

import re
import httpx
from models import Opportunity

REMOTIVE_API = "https://remotive.com/api/remote-jobs"
HEADERS = {"User-Agent": "opportunity_mcp/0.1 (personal job search)"}

def _normalize(raw: dict) -> Opportunity:
          """Map ONE Remotive job record into our common Opportunity schema."""
          job_type = (raw.get("job_type") or "").lower()
          if "intern" in job_type:
                    kind = "internship"
          elif "freelance" in job_type:
                    kind = "freelance"
          else:
                    kind = "job"
          desc = re.sub(r"<[^>]+>", " ", raw.get("description") or "")
          snippet = re.sub(r"\s+", " ", desc).strip()[:200]
          return Opportunity(
                    id=str(raw.get("id", "")),
                    source="remotive",
                    kind=kind,
                    title=raw.get("title", ""),
                    company=raw.get("company_name", ""),
                    location=raw.get("candidate_required_location") or "",
                    url=raw.get("url", ""),
                    date=(raw.get("publication_date") or "")[:10],
                    skills=raw.get("tags") or [],
                    salary=raw.get("salary") or "",
                    snippet=snippet,
                    description=desc
          )

async def fetch(query: str = "", limit: int = 20) -> list[Opportunity]:
          """Fetch jobs from Remotive, optionally filtered by query, as Opportunity objects."""
          params = {"limit": limit}
          if query:
                    params["search"] = query
          async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(REMOTIVE_API, params=params, headers=HEADERS)
                    resp.raise_for_status()
                    data = resp.json()
          jobs = data.get("jobs", [])
          return [_normalize(j) for j in jobs[:limit]]