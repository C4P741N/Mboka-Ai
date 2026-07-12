
import hashlib
import os


def str2bool(v: str) -> bool:
  return v.lower() in ("yes", "true", "t", "1", "True")

KEYWORDS = [".net", "c#", "react", "asp.net", "aspnet", "dotnet", "azure", "docker", "api", "backend", "software engineer", "developer", "engineer", "software developer"]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DB_PATH = os.getenv("DB_PATH")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
JOB_EMBED_MODEL = os.getenv("JOB_EMBED_MODEL")
RERANK_MODEL = os.getenv("RERANK_MODEL")
USE_RERANKER = str2bool(os.getenv("USE_RERANKER"))
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
ENABLE_RECENCY_BOOST = str2bool(os.getenv("ENABLE_RECENCY_BOOST"))
MAX_RECENCY_BOOST = float(os.getenv("MAX_RECENCY_BOOST"))
RECENCY_HALF_LIFE_HOURS = float(os.getenv("RECENCY_HALF_LIFE_HOURS"))
THRESHOLD = float(os.getenv("THRESHOLD"))
TOP_K = int(os.getenv("TOP_K"))

if not SENDER_EMAIL or not SENDER_PASSWORD:
    raise ValueError("Missing environment variables! Set them in .env or system.")


PROFILE_TEXT = """
Senior .NET / React engineer specializing in C#, .NET Core, ASP.NET Core, Entity Framework Core,
REST APIs, OData, React, Azure, Docker, Kubernetes, SQL Server, PostgreSQL, CI/CD, and financial systems.
I am only interested in fully remote positions or jobs located in Kenya.
"""

def job_id_from(job):
    raw = f"{job.get('title','')}_{job.get('company','')}_{job.get('url','')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def format_alert(job, score):
    return (
        f"*New high-match job detected*\n\n"
        f"*Title:* {job.get('title')}\n"
        f"*Company:* {job.get('company')}\n"
        f"*Location:* {job.get('location')}\n"
        f"*Score:* {score:.3f}\n"
        f"*URL:* {job.get('url')}\n"
    )

def keyword_filter(job):
    text = " ".join([
        job.get("title", ""),
        job.get("company", ""),
        job.get("description", ""),
        job.get("location", "")
    ]).lower()
    return any(k in text for k in KEYWORDS)
