# opportunity_mcp

A local [MCP](https://modelcontextprotocol.io) server that turns any MCP-compatible assistant (e.g. Claude Desktop) into a personal opportunity agent. It searches live job listings across multiple sources, extracts the skills each role requires, and scores how well a résumé fits — by **meaning**, not keywords — with honest handling of hard requirements like licenses and commute. Everything runs locally; your résumé never leaves your machine.

> Status: a build-in-public project. Search, skill/fact extraction, fit scoring, and ranking are working. Fact-faithful résumé tailoring (with an anti-fabrication gate) is on the roadmap.

---

## Why

Job hunting is repetitive: many boards, re-reading every JD, guessing fit, rewriting the résumé per role. Tailoring also tempts exaggeration, which then fails at interview. `opportunity_mcp` automates **search → fit → (soon) tailor** while guaranteeing that any generated résumé only ever uses facts you can defend.

## Features

- **Unified search** across RemoteOK, Remotive, and Hacker News "Who is Hiring", normalized into one common shape. Adding a source is a small adapter.
- **Skill extraction** from a job description against a large, cross-domain vocabulary (tech + non-tech).
- **Semantic fit scoring** — matches skills by meaning (so "AWS" and "Amazon Web Services" count as the same), returns a score plus matched and missing skills.
- **License gating** — a missing *mandatory* license (e.g. RN, CDL, bar admission) makes a candidate ineligible; *preferred* certifications nudge the score.
- **Commute awareness** — for onsite blue-collar roles, or when the candidate can't relocate, distance discounts the score. Detected automatically; skipped for remote or relocation-friendly cases.
- **One-call ranking** — `rank` chains search + scoring + sort into a shortlist, best fit first.
- **Local & private** — no résumé data leaves the machine; search results are cached to respect source rate limits.

## How it works

Source-agnostic core: every source normalizes its response into one `Opportunity` schema, so everything downstream (filter, score, rank) is blind to where a listing came from.

| Module | Responsibility |
|---|---|
| `server.py` | MCP server (FastMCP): tool/resource definitions, wiring, and a TTL cache on search. |
| `models.py` | Pydantic models — `Opportunity` (a listing) and `Fact` (an atomic résumé fact). |
| `sources/` | Per-source adapters (`remoteok`, `remotive`, `hn`) that map each API into `Opportunity`. |
| `scoring.py` | The ML/scoring layer: semantic skill matching, abbreviation aliasing, license gating, blue-collar classification, and commute distance. Pure — takes lists, returns a result. |
| `rank.py` | Ordering logic. The scorer is **injected**, so this module imports nothing from the server (no circular dependency) and is unit-testable. |
| `data/` | Editable vocabularies: `skills.txt`, `licenses_mandatory.txt`, `licenses_preferred.txt`. |
| `scripts/build_skills_corpus.py` | Rebuilds `data/skills.txt` from open sources. |

## MCP surface

**Tools**

| Tool | Does |
|---|---|
| `search(query, limit, sources)` | Find opportunities across sources. |
| `get_job(id, source)` | Full detail for one listing. |
| `extract_skills(text)` | Skills named in a job description. |
| `extract_facts(resume_text)` | Parse a résumé into atomic, typed facts. |
| `score_fit(resume_text, job_text, candidate_location, job_location, can_relocate)` | Fit score, eligibility, matched/missing skills, missing licenses, commute. |
| `rank(query, resume_text, ...)` | Search and return listings ranked by fit. |

**Resource**

- `resume://schema` — the contract every résumé fact must follow (auto-generated from the `Fact` model, so it never drifts).

## Install

Requires Python 3.11+.

```bash
git clone <your-repo-url> opportunity-mcp
cd opportunity-mcp
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

The skills corpus (`data/skills.txt`) is included. To rebuild or refresh it:

```bash
python scripts/build_skills_corpus.py
```

## Connect to Claude Desktop

Add an entry to your `claude_desktop_config.json` (use absolute paths):

```json
{
  "mcpServers": {
    "opportunity_mcp": {
      "command": "/absolute/path/to/opportunity-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/opportunity-mcp/server.py"]
    }
  }
}
```

Fully quit and reopen Claude Desktop. The tools and the `resume://schema` resource will appear.

## Demo

```bash
python demo.py
```

Runs `extract_skills`, `score_fit`, and `rank` against a sample résumé and a live search, printing the results. (First run downloads a small embedding model.)

## Usage example

In Claude Desktop, once connected:

> "Search for remote Python roles and rank them against my résumé."

Claude calls `rank`, and you get a shortlist scored by genuine fit, with the skills you match and the gaps you'd need to close.

## Data & attribution

- **Job listings:** RemoteOK, Remotive, and Hacker News (via the Algolia API) — public endpoints, used within their terms; results are cached. Gated platforms (LinkedIn, Upwork, etc.) are intentionally **not** scraped.
- **Skills vocabulary:** built from
  - **ESCO** (European Skills, Competences, Qualifications and Occupations) — © European Union, free to reuse for any purpose under Commission Decision 2011/833/EU.
  - **O*NET® 30.3** — used under the **Creative Commons Attribution 4.0** license, courtesy of the U.S. Department of Labor, Employment and Training Administration. O*NET® is a trademark of USDOL/ETA.
  - plus a curated booster of common tools and frameworks.

## Privacy & honesty

- **Local only.** Your résumé and fact base stay on your machine.
- **Anti-fabrication (roadmap).** The planned `build_resume` will tailor by selecting and rephrasing *true* facts only; `verify_resume` will block any claim that can't be traced to your fact base, and `gap_report` will surface real gaps as a study list rather than inventing experience.

## Roadmap

- `build_resume` — fact-faithful tailored résumé with provenance per bullet.
- `verify_resume` — deterministic + LLM faithfulness gate.
- `gap_report` — honest missing-requirement report with closest true experience.
- Freelance source (Freelancer.com); intra-city commute precision; cover letters.

## Tech stack

Python 3.11+, FastMCP, httpx (async), Pydantic v2, sentence-transformers (semantic matching), geonamescache (offline geocoding). Transport: stdio (local).

## License

Code: add your chosen license (e.g. MIT). Note the data attributions above — O*NET requires attribution under CC BY 4.0.