"""opportunity_mcp server: exposes job-search tools to an MCP client over stdio."""

from mcp.server.fastmcp import FastMCP
from sources import remoteok

mcp = FastMCP("opportunity_mcp")


@mcp.tool()

async def search(query: str = "", limit: int = 10) -> list[dict]:
          """Search remote job and internship listings and return matching opportunities.
          Args:
        query: Keyword matched against job title and skills, e.g. "python" or "llm". Empty returns the most recent listings.
        limit: Maximum number of results to return.
    """
          opportunities = await remoteok.fetch(query=query, limit=limit)
          return [o.model_dump() for o in opportunities]

if __name__ == "__main__":
          mcp.run()