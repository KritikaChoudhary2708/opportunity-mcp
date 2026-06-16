"""opportunity_mcp server: exposes job-search tools to an MCP client over stdio."""

import asyncio
from mcp.server.fastmcp import FastMCP
from sources import remoteok, remotive

mcp = FastMCP("opportunity_mcp")
SOURCES = {"remoteok": remoteok.fetch, "remotive": remotive.fetch}

@mcp.tool()

async def search(query: str = "", limit: int = 10, sources: list[str] | None = None) -> list[dict]:
          """Search remote job and internship listings and return matching opportunities.
          Args:
        query: Keyword matched against job title and skills, e.g. "python" or "llm". Empty returns the most recent listings.
        limit: Maximum number of results to return.
        sources: Which sources to search, e.g. ["remoteok", "remotive"]. Omit to search all.
    """
          chosen = sources or list(SOURCES)
          fetchers = [SOURCES[s](query=query, limit=limit) for s in chosen if s in SOURCES]
          results = await asyncio.gather(*fetchers)
          merged = [o for batch in results for o in batch]

          return [o.model_dump() for o in merged[:limit]]

if __name__ == "__main__":
          mcp.run()