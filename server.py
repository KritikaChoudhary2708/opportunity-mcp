"""opportunity_mcp server: exposes job-search tools to an MCP client over stdio."""

import itertools
import asyncio
from mcp.server.fastmcp import FastMCP
from sources import remoteok, remotive, hn

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



if __name__ == "__main__":
          mcp.run()