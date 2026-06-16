"""RemoteOK source: fetch remote jobs and normalize them into Opportunity."""
import re
import httpx
from models import Opportunity

REMOTEOK_API = "https://remoteok.com/api"
HEADERS = {"User-Agent": "opportunity_mcp/0.1 (personal job search)"}

def _normalize(raw:dict)-> Opportunity:
          """Map ONE RemoteOK job record into our common Opportunity schema."""
          smin, smax = raw.get("salary_min") or 0, raw.get("salary_max") or 0
          salary = f"${smin:,}-${smax:,}" if smin and smax else ""
          desc = re.sub(r"<[^>]+>", " ", raw.get("description") or "")
          snippet = re.sub(r"\s+", " ", desc).strip()[:200]
          return Opportunity(
                    id=str(raw.get("id", "")),
                    source="remoteok",
                    kind="internship" if re.search(r"\bintern(ship)?s?\b", raw.get("position", ""), re.I) else "job",
                    title=raw.get("position", ""),
                    company=raw.get("company", ""),
                    location=raw.get("location") or "",
                    url=raw.get("url") or raw.get("apply_url") or "",
                    date=(raw.get("date") or "")[:10],
                    skills=raw.get("tags") or [],
                    salary=salary,
                    snippet=snippet
          )


async def fetch(query: str = "", limit: int = 20) -> list[Opportunity]:
          """Fetch jobs from RemoteOK, optionally filter by query, return Opportunity list."""
          async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(REMOTEOK_API, headers=HEADERS)
                    resp.raise_for_status()
                    data = resp.json()
          rows = [r for r in data if r.get("position")]
          if query:
                    q = query.lower()
                    rows = [r for r in rows if q in (r.get("position", "") + " " + " ".join(r.get("tags", []))).lower()]
          return [_normalize(r) for r in rows[:limit]]