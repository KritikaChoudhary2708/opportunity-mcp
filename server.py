"""opportunity_mcp server: exposes job-search tools to an MCP client over stdio."""

import re
from pathlib import Path
import itertools
import asyncio
from mcp.server.fastmcp import FastMCP
from sources import remoteok, remotive, hn
from models import Fact

SKILLS_FILE = Path(__file__).parent / "data" / "skills.txt"
SKILLS = {line.strip() for line in SKILLS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()}
STOPSKILLS = {"computer", "engineering", "design", "database", "software", "it", "data"}
mcp = FastMCP("opportunity_mcp")
SOURCES = {"remoteok": remoteok.fetch, "remotive": remotive.fetch, "hn": hn.fetch}

@mcp.tool()
async def search(query: str = "", limit: int = 10, sources: list[str] | None = None) -> list[dict]:
          """Search remote job and internship listings and return matching opportunities.
          Args:
          query: Keyword matched against job title and skills, e.g. "python" or "llm". Empty returns the most recent listings.
          limit: Maximum number of results to return.
          sources: Which sources to search, e.g. ["remoteok", "remotive"]. Omit to search all."""

          chosen = sources or list(SOURCES)
          fetchers = [SOURCES[s](query=query, limit=limit) for s in chosen if s in SOURCES]
          results = await asyncio.gather(*fetchers)
          merged = [o for group in itertools.zip_longest(*results) for o in group if o is not None]

          return [o.model_dump() for o in merged[:limit]]


@mcp.tool()
async def get_job(id: str, source:str)-> dict:
  """Return full detail for one listing, given its id and source.

    Args:
        id: The listing's id within its source.
        source: Which board it came from, e.g. "remoteok", "remotive", "hn".
    """
  if source not in SOURCES:
    return {"error": f"unknown source '{source}'"}
  opportunities = await SOURCES[source](query="", limit=100)
  for o in opportunities:
        if o.id == id:
            return o.model_dump()
  return {"error": f"no job with id '{id}' in source '{source}'"}

@mcp.resource("resume://schema")
def resume_schema() -> dict:
  """The exact shape every resume fact must follow, so any client can produce valid facts."""
  return Fact.model_json_schema()

@mcp.tool()
def extract_skills(text: str) -> list[str]:
  """Extract the skills named in a job description. Pass the raw JD text; returns the matched skills, deduplicated and sorted."""
  tokens = [t.rstrip(".") for t in re.findall(r"[a-z0-9+#.]+", text.lower())]
  found = set()
  for n in (1, 2, 3):
    for i in range(len(tokens) - n + 1):
      gram = " ".join(tokens[i:i + n])
      if gram in SKILLS:
        found.add(gram)
        if n > 1 and i + n < len(tokens):
            # Avoid overlapping multi-word matches if possible
            tokens[i + n] = ""
  return sorted(found - STOPSKILLS)

if __name__ == "__main__":
          mcp.run()