"""
opportunity_mcp - end-to-end demo.

Run:  python demo.py

Shows extract_skills, score_fit, and a live ranked search against a sample
resume. The first run downloads a small embedding model (~80 MB).
"""
import asyncio
import json

from server import extract_skills, score_fit, rank

RESUME = (
    "Backend engineer with 4 years of experience. "
    "Built REST APIs in Python with FastAPI and PostgreSQL. "
    "Deployed services on AWS using Docker and CI/CD. "
    "Comfortable with SQL, Redis, and Git."
)

JOB = (
    "We are hiring a Backend Engineer. Requirements: strong Python, "
    "PostgreSQL, AWS, and Docker. Kubernetes is a plus. "
    "AWS Certified preferred."
)

QUERY = "python backend"


def show(title, obj):
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)
    print(json.dumps(obj, indent=2, default=str))


async def main():
    show("1) extract_skills(JOB)", extract_skills(JOB))
    show("2) score_fit(RESUME, JOB)", score_fit(RESUME, JOB))
    show(f"3) rank('{QUERY}') - top 5 live listings by fit",
         await rank(QUERY, RESUME, limit=5))


if __name__ == "__main__":
    asyncio.run(main())