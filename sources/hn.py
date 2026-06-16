"""Hacker News 'Who is Hiring' source via the Algolia API."""

import html
import re
import httpx
from models import Opportunity

HN_SEARCH = "https://hn.algolia.com/api/v1/search"
HN_BY_DATE = "https://hn.algolia.com/api/v1/search_by_date"
HEADERS = {"User-Agent": "opportunity_mcp/0.1 (personal job search)"}

def _normalize(raw: dict) -> Opportunity:
          """Map ONE Hacker News 'Who is hiring' comment into our Opportunity schema."""
          text = re.sub(r"<[^>]+>", " ", raw.get("comment_text") or "")
          text = html.unescape(text)
          text = re.sub(r"\s+", " ", text).strip()
          kind = "internship" if re.search(r"\bintern(ship)?s?\b", text, re.I) else "job"
          return Opportunity(
                    id=str(raw.get("objectID", "")),
                    source="hn",
                    kind=kind,
                    title=text[:80],
                    company="",
                    location="Remote" if "remote" in text.lower() else "",
                    url=f"https://news.ycombinator.com/item?id={raw.get('objectID', '')}",
                    date=(raw.get("created_at") or "")[:10],
                    skills=[],
                    salary="",
                    snippet=text[:200],
          )

async def _latest_hiring_story(client) -> str:
          """Find the id of the most recent 'Ask HN: Who is hiring?' thread."""
          params = {"tags": "story,author_whoishiring", "query": "who is hiring", "hitsPerPage": 1}
          resp = await client.get(HN_BY_DATE, params=params, headers=HEADERS)
          resp.raise_for_status()
          hits = resp.json().get("hits", [])
          return hits[0]["objectID"] if hits else ""

async def fetch(query: str = "", limit: int = 20) -> list[Opportunity]:
          """Fetch matching jobs from the latest HN 'Who is hiring' thread."""
          async with httpx.AsyncClient(timeout=10) as client:
                    story_id = await _latest_hiring_story(client)
                    if not story_id:
                              return []
                    params = {"tags": f"comment,story_{story_id}", "hitsPerPage": limit}
                    if query:
                              params["query"] = query
                    resp = await client.get(HN_SEARCH, params=params, headers=HEADERS)
                    resp.raise_for_status()
                    hits = resp.json().get("hits", [])
                    return [_normalize(h) for h in hits[:limit]]