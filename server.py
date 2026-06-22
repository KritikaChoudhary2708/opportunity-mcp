"""opportunity_mcp server: exposes job-search tools to an MCP client over stdio."""

import re
from pathlib import Path
import itertools
import asyncio
from mcp.server.fastmcp import FastMCP
from sources import remoteok, remotive, hn
from models import Fact
import scoring
import geonamescache
from rank import rank_opportunities
import time
import readiness

_SEARCH_CACHE: dict = {}
_SEARCH_TTL = 600  # seconds (10 minutes)
_CITIES = geonamescache.GeonamesCache().get_cities()
SKILLS_FILE = Path(__file__).parent / "data" / "skills.txt"
SKILLS = {line.strip() for line in SKILLS_FILE.read_text(encoding="utf-8").splitlines() if line.strip()}
STOPSKILLS = {"computer", "engineering", "design", "database", "software", "it", "data", "re", "source", "signing", "control", "communication", "energy", "english", "hindi"}
SOURCES = {"remoteok": remoteok.fetch, "remotive": remotive.fetch, "hn": hn.fetch}
MANDATORY_LICENSES_FILE = Path(__file__).parent / "data" / "licenses_mandatory.txt"
PREFERRED_LICENSES_FILE = Path(__file__).parent / "data" / "licenses_preferred.txt"
MANDATORY_LICENSES = {l.strip() for l in MANDATORY_LICENSES_FILE.read_text(encoding="utf-8").splitlines() if l.strip()}
PREFERRED_LICENSES = {l.strip() for l in PREFERRED_LICENSES_FILE.read_text(encoding="utf-8").splitlines() if l.strip()}

def _geocode(name: str):
  name = (name or "").strip().lower()
  matches = [c for c in _CITIES.values() if c["name"].lower() == name]
  if not matches:
    return None
  c = max(matches, key=lambda x: x.get("population", 0))
  return (c["latitude"], c["longitude"])

mcp = FastMCP("opportunity_mcp")
@mcp.tool()
async def search(query: str = "", limit: int = 10, sources: list[str] | None = None) -> list[dict]:
          """Search remote job and internship listings and return matching opportunities.
          Args:
          query: Keyword matched against job title and skills, e.g. "python" or "llm". Empty returns the most recent listings.
          limit: Maximum number of results to return.
          sources: Which sources to search, e.g. ["remoteok", "remotive"]. Omit to search all."""
          
          key = (query, limit, tuple(sources or []))
          cached = _SEARCH_CACHE.get(key)
          if cached and time.time() - cached[0] < _SEARCH_TTL:
            return cached[1]
          chosen = sources or list(SOURCES)
          fetchers = [SOURCES[s](query=query, limit=limit) for s in chosen if s in SOURCES]
          results = await asyncio.gather(*fetchers)
          merged = [o for group in itertools.zip_longest(*results) for o in group if o is not None]

          out = [o.model_dump() for o in merged[:limit]]
          _SEARCH_CACHE[key] = (time.time(), out)
          return out


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

def _guess_type(line: str) -> str:
  l = line.lower()
  if any(w in l for w in ("university", "college", "b.tech", "m.tech", "bachelor", "master", "degree", "gpa", "cgpa")):
    return "education"
  if any(w in l for w in ("work", "experience", "employment", "hired", "hiring", "role", "position")):
    return "experience"
  if any(w in l for w in ("project", "repo", "github", "gitlab", "bitbucket")):
    return "project"
  if any(w in l for w in ("cert", "certification", "certificate", "course", "diploma", "license")):
    return "certification"
  if any(w in l for w in ("language", "speak", "fluent", "proficient", "native", "bilingual", "multilingual")):
    return "language"
  if any(w in l for w in ("award", "prize", "honor", "recognition", "scholarship", "fellowship", "grant", "hackathon")):
    return "award"
  if any(w in l for w in ("publication", "paper", "conference", "journal", "patent", "article", "book", "poster")):
    return "publication"
  if any(w in l for w in ("volunteer", "volunteering", "ngo", "nonprofit", "charity", "community", "service")):
    return "volunteer"
  return "other"


def _match_vocab(text: str, vocab: set) -> list[str]:
  tokens = [t.rstrip(".") for t in re.findall(r"[a-z0-9+#.]+", text.lower())]
  found = set()
  for n in (1, 2, 3):
    for i in range(len(tokens) - n + 1):
      gram = " ".join(tokens[i:i + n])
      if gram in vocab:
        found.add(gram)
  return sorted(found)


@mcp.tool()
def extract_facts(resume_text: str) -> list[dict]:
  """Parse a resume into atomic facts (id, type, text, tags, source_ref). Pass the raw resume text; returns the per-session fact base."""
  facts = []
  for line in resume_text.splitlines():
    line = line.strip()
    if not line:
      continue
    fact_type = _guess_type(line)
    tags = extract_skills(line)
    fact = Fact(
      id=str(len(facts)),
      type=fact_type,
      text=line,
      tags=tags,
      source_ref="resume",
    )
    facts.append(fact)
  return [f.model_dump() for f in facts]


@mcp.tool()
def score_fit(resume_text: str, job_text: str, candidate_location: str = "", job_location: str = "", can_relocate: bool = False) -> dict:
  """Score how well a resume fits a job: semantic skill match, hard gate on mandatory licenses, boost for preferred ones, and a commute factor for onsite blue-collar roles or candidates who cannot relocate. Pass raw resume and job text. Ask the user for their city (candidate_location), the job's city (job_location), and whether they can relocate (can_relocate). Returns score, eligibility, matched/missing skills, missing licenses, and commute info."""
  job_skills = sorted(set(extract_skills(job_text)))
  my_skills = set()
  for fact in extract_facts(resume_text):
    my_skills.update(fact["tags"])
  required_mandatory = _match_vocab(job_text, MANDATORY_LICENSES)
  preferred_in_job = _match_vocab(job_text, PREFERRED_LICENSES)
  held = _match_vocab(resume_text, MANDATORY_LICENSES) + _match_vocab(resume_text, PREFERRED_LICENSES)
  remote = "remote" in job_text.lower()
  blue_collar = scoring.is_blue_collar(job_text)
  return scoring.score(job_skills, sorted(my_skills), required_mandatory, preferred_in_job, held,
                       candidate_coords=_geocode(candidate_location), job_coords=_geocode(job_location),
                       remote=remote, blue_collar=blue_collar, can_relocate=can_relocate)

@mcp.tool()
async def rank(query: str, resume_text: str, sources: list[str] | None = None, limit: int = 10, candidate_location: str = "", can_relocate: bool = False) -> list[dict]:
  """Search jobs and rank them by fit to the resume, best first. Each result has its fit score and matched/missing skills. Ask the user for their location and whether they can relocate."""
  jobs = await search(query, limit, sources)
  return rank_opportunities(jobs, resume_text, score_fit, candidate_location, can_relocate)


@mcp.tool()
async def market_readiness(resume_text: str, sources: list[str] | None = None, limit_per_skill: int = 5, candidate_location: str = "", can_relocate: bool = True) -> dict:
  """Scan the job market with a resume: search jobs matching your top skills, score each, and report how prepared you are - average fit, how many roles you're eligible for, and the most in-demand skills you're missing (your study list). Pass your real resume text."""
  my_skills = extract_skills(resume_text)
  jobs, seen = [], set()
  for q in readiness.top_skills(resume_text, my_skills, 3):
    for job in await search(q, limit_per_skill, sources):
      key = job.get("url") or (job.get("source"), job.get("id"))
      if key not in seen:
        seen.add(key)
        jobs.append(job)
  ranked = rank_opportunities(jobs, resume_text, score_fit, candidate_location, can_relocate)
  return readiness.summarize(ranked, my_skills)

if __name__ == "__main__":
          mcp.run()