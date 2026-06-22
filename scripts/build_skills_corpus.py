#!/usr/bin/env python3
"""
build_skills_corpus.py — builds data/skills.txt for opportunity_mcp's extract_skills tool.

Cross-domain + tech-heavy skills vocabulary, merged from open sources:

  - ESCO (European Skills, Competences, Qualifications and Occupations):
    preferredLabel + altLabels. (c) European Union. Free to download, use and
    reuse for any purpose under Commission Decision 2011/833/EU.
    CSV mirror: https://github.com/tabiya-tech/tabiya-open-dataset (ESCO v1.1.1)

  - O*NET 30.3 "Software Skills" (Element Name categories).
    Licensed under CC BY 4.0 by the U.S. Department of Labor, Employment and
    Training Administration. https://www.onetcenter.org/database.html

  - A curated booster of common tools/frameworks that job descriptions name
    (factual product/library names: Python, Excel, Tableau, AWS, ...).

Output: data/skills.txt (one normalized skill per line; tech terms first).
Usage:  python build_skills_corpus.py
NOTE: keep the attributions above in your repo's README (O*NET CC BY 4.0 requires it).
"""
from __future__ import annotations

import csv
import io
import re
import urllib.request
import zipfile
from pathlib import Path

ONET_URL = "https://www.onetcenter.org/dl_files/database/db_30_3_text.zip"
ESCO_URL = (
    "https://raw.githubusercontent.com/tabiya-tech/tabiya-open-dataset/"
    "main/tabiya-esco-v1.1.1/csv/skills.csv"
)
OUT = Path(__file__).resolve().parent.parent / "data" / "skills.txt"

# Common tools/libraries/skills that JDs name but ESCO/O*NET miss or bury.
BOOSTER = [
    # languages
    "python", "java", "javascript", "typescript", "c", "c++", "c#", "go", "golang",
    "rust", "ruby", "php", "swift", "kotlin", "scala", "r", "matlab", "perl",
    "bash", "powershell", "sql", "html", "css",
    # web frameworks
    "react", "react native", "angular", "vue.js", "svelte", "next.js", "node.js",
    "express", "django", "flask", "fastapi", "spring", "spring boot", ".net",
    "asp.net", "laravel", "rails", "jquery", "bootstrap", "tailwind",
    # data / ml
    "pandas", "numpy", "scipy", "scikit-learn", "pytorch", "tensorflow", "keras",
    "xgboost", "hugging face", "transformers", "opencv", "nltk", "spacy",
    "matplotlib", "seaborn", "plotly", "machine learning", "deep learning",
    "natural language processing", "computer vision", "data science",
    "data analysis", "data engineering", "data visualization", "statistics",
    # ai / llm tooling (post-dates ESCO/O*NET; must be hand-maintained)
    "openai", "anthropic", "gemini", "claude", "llama", "mistral", "cohere",
    "llm", "llms", "large language models", "generative ai", "genai", "rag",
    "langchain", "llamaindex", "langfuse", "langsmith", "braintrust", "ragas",
    "deepeval", "prompt engineering", "fine-tuning", "embeddings",
    "vector database", "pinecone", "weaviate", "chroma", "qdrant", "milvus",
    "ollama", "vllm", "tool calling", "function calling", "structured outputs",
    "streaming", "evals", "observability", "supabase", "cursor", "copilot",
    "github copilot", "claude code", "codex", "agentic", "ai agents",
    "full stack", "full-stack", "api", "apis",
    # common abbreviations (canonicalized by ALIASES in scoring.py)
    "k8s", "k8", "js", "ts", "postgres", "psql", "ci/cd",
    # ML/NLP terms (these live in ESCO altLabels; re-added here as an allowlist
    # because we drop altLabels for precision)
    "ml", "nlp", "retrieval", "transformer", "data processing",
    "vector search", "semantic search",
    # databases
    "mysql", "postgresql", "sqlite", "oracle", "sql server", "mongodb",
    "cassandra", "redis", "elasticsearch", "dynamodb", "neo4j", "snowflake",
    "bigquery", "redshift", "databricks",
    # cloud / devops
    "aws", "amazon web services", "azure", "google cloud", "gcp", "docker",
    "kubernetes", "terraform", "ansible", "jenkins", "github actions", "circleci",
    "prometheus", "grafana", "git", "github", "gitlab", "bitbucket", "linux",
    "nginx", "kafka", "spark", "hadoop", "airflow", "dbt", "rest api", "graphql",
    "microservices", "ci/cd", "devops", "mlops", "agile", "scrum", "kanban",
    # bi / office / erp / crm
    "power bi", "tableau", "looker", "qlik", "excel", "microsoft excel",
    "microsoft word", "powerpoint", "microsoft office", "google sheets", "sap",
    "salesforce", "hubspot", "workday", "quickbooks",
    # design
    "figma", "sketch", "adobe xd", "photoshop", "illustrator", "indesign",
    "canva", "after effects", "premiere pro",
    # business / finance / marketing
    "financial modeling", "financial analysis", "accounting", "bookkeeping",
    "auditing", "budgeting", "forecasting", "business analysis",
    "business intelligence", "digital marketing", "seo", "sem",
    "content marketing", "social media marketing", "google analytics",
    "google ads", "email marketing", "copywriting", "project management",
    "product management", "stakeholder management", "risk management",
    "change management",
]


def norm(s: str) -> str:
    """Lowercase; keep + # . ; turn every other separator into a single space."""
    s = s.lower()
    s = re.sub(r"[^a-z0-9+#.]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ok(s: str) -> bool:
    """Keep sane, matchable skills only (<= 4 words; the matcher checks 1-3 grams)."""
    return bool(s) and 2 <= len(s) <= 50 and not s.isdigit() and len(s.split()) <= 4


def fetch(url: str) -> bytes:
    print("downloading", url)
    with urllib.request.urlopen(url, timeout=300) as r:
        return r.read()


def main() -> None:
    tech: set[str] = set()
    cross: set[str] = set()

    for w in BOOSTER:
        v = norm(w)
        if ok(v):
            tech.add(v)

    onet = zipfile.ZipFile(io.BytesIO(fetch(ONET_URL)))
    fn = next(n for n in onet.namelist() if n.lower().endswith("software skills.txt"))
    rows = onet.read(fn).decode("utf-8", "replace").splitlines()
    ci = [h.strip() for h in rows[0].split("\t")].index("Element Name")
    for ln in rows[1:]:
        p = ln.split("\t")
        if ci < len(p):
            v = norm(p[ci])
            if ok(v):
                tech.add(v)

    csv.field_size_limit(10 ** 7)
    esco = fetch(ESCO_URL).decode("utf-8", "replace")
    for row in csv.DictReader(io.StringIO(esco)):
        # preferredLabel only. ESCO altLabels (~84k synonyms) are 6x the main
        # labels and where most of the generic noise lives, so we drop them.
        cells = [row.get("PREFERREDLABEL", "")]
        for cell in cells:
            v = norm(cell)
            if ok(v):
                cross.add(v)
 
    tech_sorted = sorted(tech)
    cross_sorted = sorted(cross - tech)
    all_skills = tech_sorted + cross_sorted
 
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(all_skills) + "\n", encoding="utf-8")
    print(f"wrote {OUT}: {len(all_skills)} skills "
          f"({len(tech_sorted)} tech + {len(cross_sorted)} cross-domain)")
 
 
if __name__ == "__main__":
    main()