import os
import json
import sqlite3
import hashlib
from typing import Dict
import requests
from datetime import datetime, timezone, timedelta
import html

import math
from dateutil import parser as dateparser


from sentence_transformers import SentenceTransformer, util
from transformers import AutoTokenizer, AutoModelForSequenceClassification

import torch
import re

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header

from dotenv import load_dotenv
load_dotenv() 
# ----------------------------
# Config
# ----------------------------
JOB_EMBED_MODEL = "TechWolf/JobBERT-v2"
RERANK_MODEL = "Qwen/Qwen3-Reranker-8B"  # optional; can disable if too heavy
USE_RERANKER = False

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")          # <-- NEW: AI‑powered search
# Recency boosting
ENABLE_RECENCY_BOOST = True
MAX_RECENCY_BOOST = 1.5            # maximum multiplier for very recent jobs
RECENCY_HALF_LIFE_HOURS = 24       # hours until boost halves to ~1.0

DB_PATH = "job_tracker.db"
THRESHOLD = 0.1
TOP_K = 20

# Mail server configuration (replace with your actual info)
SMTP_SERVER = "smtp.gmail.com"  # Your SMTP server address
SMTP_PORT = 465  # Port number

# Sender information
SENDER_EMAIL = "bot.mboka@gmail.com"
SENDER_PASSWORD = "skfi lchk relb mdsx"

# Recipient information
RECEIVER_EMAIL = "m.kituku@hotmail.com"

PROFILE_TEXT = """
Senior .NET / React engineer specializing in C#, .NET Core, ASP.NET Core, Entity Framework Core,
REST APIs, OData, React, Azure, Docker, Kubernetes, SQL Server, PostgreSQL, CI/CD, and financial systems.
I am only interested in fully remote positions or jobs located in Kenya.
"""

KEYWORDS = [".net", "c#", "react", "asp.net", "aspnet", "dotnet", "azure", "docker", "api", "backend", "software engineer", "developer", "engineer", "software developer"]

FONT = "-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif"
INK = "#16232E"      # headings
BODY = "#526070"     # body copy
MUTED = "#97A2AC"     # dividers, empty-state text
BORDER = "#E3E8ED"    # card border
ACCENT = "#0F766E"    # apply buttons (the one accent color)
 

# ----------------------------
# Storage (unchanged)
# ----------------------------
# def execute_query(sql_query):
#    execute_all(sql_query, True)

# def execute_crud(sql_query):
#     execute_all(sql_query, False)

# def execute_all(sql_query, is_select):
#     sqliteConnection = None
#     try:
#         sqliteConnection = sqlite3.connect(DB_PATH)
#         cur = sqliteConnection.cursor()
#         cur.execute(sql_query)
#         if not is_select:
#             sqliteConnection.commit()
#         else:
#             row = cur.fetchone()
#         sqliteConnection.close()
#         if(is_select):
#             return row is not None
#     except sqlite3.Error as error:
#         print("Exception occured -", error)
#     finally:
#         if sqliteConnection:
#             sqliteConnection.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS seen_jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            url TEXT,
            score REAL,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def job_id_from(job):
    raw = f"{job.get('title','')}_{job.get('company','')}_{job.get('url','')}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def already_seen(job_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM seen_jobs WHERE job_id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None

def save_job(job, score):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO seen_jobs (job_id, title, company, url, score, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        job_id_from(job),
        job.get("title"),
        job.get("company"),
        job.get("url"),
        float(score),
        datetime.now(timezone.utc).isoformat()
    ))
    conn.commit()
    conn.close()

# ----------------------------
# Telegram (unchanged)
# ----------------------------
def send_telegram_message(text):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()

# ----------------------------
# AI‑powered job source (NEW, replaces static list)
# ----------------------------
def build_search_query() -> str:
    """
    Build a Google‑friendly search query from your profile & keywords.
    This tells the AI search engine exactly what you're looking for.
    """
    # Use the most important technologies as required terms
    # must_include = ' AND '.join(f'"{kw}"' for kw in ['.net', 'c#', 'react'])
    optional_include = ' OR '.join(KEYWORDS)  # just in case

    return optional_include
    # return f'({must_include}) ({optional_include}) (engineer OR developer)'

def fetch_jobs_from_serpapi():
    """
    Use SerpAPI's google_jobs engine to get structured job listings.
    (SerpAPI uses machine learning to extract the fields.)
    """
    if not SERPAPI_API_KEY:
        print("WARNING: SERPAPI_API_KEY not set. Returning empty job list.")
        return []

    query = build_search_query()
    print(f"Searching for jobs with query: {query}")

    params = {
        "engine": "google_jobs",
        "q": query,
        "api_key": SERPAPI_API_KEY,
        "hl": "en",
        "google_domain": "google.co.ke",
        "location": "Kenya"
    }

    try:
        resp = requests.get("https://serpapi.com/search", params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"SerpAPI request failed: {e}")
        return []

    jobs = []
    for result in data.get("jobs_results", []):
        title = result.get("title", "")
        company = result.get("company_name", "")
        location = result.get("location", "")
        
        source_title = result.get("via")
        source_link = result.get("source_link") or result.get("share_link", "")

        apply_options = []
        for url_option in result.get("apply_options") or {}.values():
            apply_options.append({
                "title": url_option.get("title"),
                "url": url_option.get("link")
            })

          # Attempt to grab a raw posting date
        posted_raw = None
        detected = result.get("detected_extensions", {})
        for key in ("posted", "date", "schedule", "posted_at", "posted_date", "posted_at"):
            if key in detected:
                posted_raw = detected[key]
                break
        if not posted_raw:
            posted_raw = result.get("posted") or result.get("date")
        
        description_parts = []

        for det in result.get("detected_extensions", {}).values():
            if isinstance(det, str):
                description_parts.append(det)
        description = " ".join(description_parts) if description_parts else ""

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "description": description,
            "apply_options": apply_options,
            "posted_raw": posted_raw,
            "source_link": [{
                "title": source_title,
                "url": source_link
            }]

        })

    print(f"Found {len(jobs)} jobs via SerpAPI.")
    return jobs

def fetch_jobs():
    """Main entry point – returns a list of job dicts."""
    return fetch_jobs_from_serpapi()

# ----------------------------
# Filtering (unchanged)
# ----------------------------
def keyword_filter(job):
    text = " ".join([
        job.get("title", ""),
        job.get("company", ""),
        job.get("description", ""),
        job.get("location", "")
    ]).lower()
    return any(k in text for k in KEYWORDS)

# ----------------------------
# Scoring (unchanged)
# ----------------------------
embedder = SentenceTransformer(JOB_EMBED_MODEL)

if USE_RERANKER:
    rerank_tokenizer = AutoTokenizer.from_pretrained(RERANK_MODEL)
    rerank_model = AutoModelForSequenceClassification.from_pretrained(RERANK_MODEL)
    rerank_model.eval()
else:
    rerank_tokenizer = None
    rerank_model = None

profile_embedding = embedder.encode(PROFILE_TEXT, convert_to_tensor=True, normalize_embeddings=True)

def location_sentence(job):
    """Create a natural‑language description of the job's location and onsite requirements."""
    loc = job.get("location", "Unknown location")
    desc = job.get("description", "")
    # Simple hybrid detection – adjust keywords as needed
    is_hybrid = any(w in f"{job.get('title','')} {desc}".lower() 
                    for w in ["hybrid", "on-site", "onsite", "in-office", "partially remote"])
    arrangement = "hybrid/onsite" if is_hybrid else "remote"
    return f"This job is {arrangement} and located in {loc}."

def embed_score(job):
    text = (
        f"{job.get('title','')}\n"
        f"{job.get('description','')}\n"
        f"{job.get('company','')}\n"
        f"{location_sentence(job)}"
        )
    
    emb = embedder.encode(text, convert_to_tensor=True, normalize_embeddings=True)

    #Performs the comparison between the skills i have(currently stored in the vector profile_embedding) and the job that has been found stored in (encoded into a vector then stored in emb)
    return float(util.cos_sim(profile_embedding, emb).item())

def rerank_score(job):
    if not USE_RERANKER:
        return None
    query = PROFILE_TEXT.strip()
    passage = f"{job.get('title','')}. {job.get('description','')}"
    inputs = rerank_tokenizer(query, passage, return_tensors="pt", truncation=True, max_length=512)
    with torch.no_grad():
        logits = rerank_model(**inputs).logits
    if logits.shape[-1] == 1:
        score = torch.sigmoid(logits).item()
    else:
        score = torch.softmax(logits, dim=-1)[0, -1].item()
    return float(score)

def get_recency_boost(job):
    if not ENABLE_RECENCY_BOOST:
        return 1.0

    date_str = job.get("posted_raw")
    if not date_str:
        return 1.0                # unknown age → no boost

    try:
        post_date = None
        #matches if has number and if contains day ago or days ago
        pattern = r'\d+\s+days?\s+ago'

        if re.search(pattern, date_str):
            today = datetime.now(timezone.utc)
            prev_days = date_str.split(' ')[0]
            previous_date = today - timedelta(days=int(prev_days))
            post_date = previous_date
        else:
            post_date = dateparser.parse(date_str)
        
        now = datetime.now(timezone.utc)
        # Make post_date timezone-aware if it isn't
        if post_date.tzinfo is None:
            post_date = post_date.replace(tzinfo=timezone.utc)
        delta = now - post_date
        hours = max(0, delta.total_seconds() / 3600)

        # Exponential decay: boost starts at MAX_RECENCY_BOOST and fades to 1.0
        boost = 1.0 + (MAX_RECENCY_BOOST - 1.0) * math.exp(-hours / RECENCY_HALF_LIFE_HOURS)
        return boost
    except Exception:
        return 1.0   # if parsing fails, no boost

def final_score(job):
    base = embed_score(job)
    if USE_RERANKER:
        rr = rerank_score(job)
        if rr is None:
            return base
        return 0.6 * base + 0.4 * rr
    
    # Multiply by recency boost – recent jobs get a higher final score
    recency = get_recency_boost(job)

    return base * recency

# ----------------------------
# Alert formatting (unchanged)
# ----------------------------
def format_alert(job, score):
    return (
        f"*New high-match job detected*\n\n"
        f"*Title:* {job.get('title')}\n"
        f"*Company:* {job.get('company')}\n"
        f"*Location:* {job.get('location')}\n"
        f"*Score:* {score:.3f}\n"
        f"*URL:* {job.get('url')}\n"
    )

# ----------------------------
# Build html job posting
# ----------------------------

def _render_apply_buttons(apply_options: Dict[str, str]) -> str:
    """Render one styled button per apply option. Each option needs 'title' and 'url'."""
    if not apply_options:
        return (
            f'<p style="margin:0; color:{MUTED}; font-size:13px; '
            'font-style:italic;">No application links available</p>'
        )
 
    buttons = []
    for option in apply_options:
        title = html.escape(str(option.get("title") or "Apply now"))
        url = html.escape(str(option.get("url") or "#"), quote=True)
        buttons.append(
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
            'style="display:inline-block; padding:10px 16px; '
            f'margin:0 8px 8px 0; background:{ACCENT}; color:#ffffff; '
            'text-decoration:none; border-radius:6px; font-size:14px; '
            f'font-weight:600; font-family:{FONT};">'
            f'{title}</a>'
        )
    return "".join(buttons)
 
 
def render_job_card(job: Dict[str, str]) -> str:
    """
    Render a single job posting as a styled HTML card.
 
    `job["apply_options"]` should be a list of dicts shaped like:
        [{"title": "Apply on LinkedIn", "url": "https://..."},
         {"title": "Apply on company site", "url": "https://..."}]
 
    Missing fields and an empty/absent apply_options list degrade
    gracefully so a malformed job entry never breaks the layout.
    """
    title = html.escape(str(job.get("title") or "Untitled position"))
    company = html.escape(str(job.get("company") or ""))
    location = html.escape(str(job.get("location") or ""))
    description = html.escape(str(job.get("description") or "")).replace("\n", "<br>")
 
    meta_parts = []
    if company:
        meta_parts.append(f'<strong style="color:{INK};">{company}</strong>')
    if location:
        meta_parts.append(f'<span>\U0001F4CD {location}</span>')
 
    meta_html = ""
    if meta_parts:
        divider = f'<span style="color:{MUTED}; margin:0 8px;">&middot;</span>'
        meta_html = (
            f'<p style="margin:0 0 14px 0; color:{BODY}; font-size:14px;">'
            f'{divider.join(meta_parts)}</p>'
        )
 
    options = job.get("apply_options") or job.get("source_link")

    apply_buttons = _render_apply_buttons(options)
 
    return f"""
    <div style="
        width:100%;
        max-width:640px;
        box-sizing:border-box;
        border:1px solid {BORDER};
        border-radius:10px;
        padding:24px;
        margin-bottom:20px;
        background:#ffffff;
        font-family:{FONT};
        box-shadow:0 1px 2px rgba(22,35,46,0.04), 0 1px 6px rgba(22,35,46,0.05);
    ">
        <h2 style="margin:0 0 8px 0; color:{INK}; font-size:19px; font-weight:700; line-height:1.3;">
            {title}
        </h2>
 
        {meta_html}
 
        <p style="
            margin:0 0 18px 0;
            color:{BODY};
            font-size:14px;
            line-height:1.6;
            display:-webkit-box;
            -webkit-line-clamp:3;
            -webkit-box-orient:vertical;
            overflow:hidden;
            text-overflow:ellipsis;
            word-break:break-word;
        ">
            {description}
        </p>
 
        <div>
            {apply_buttons}
        </div>
    </div>
    """

def render_email(job_cards):
    return f"""
    <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    padding: 20px;
                }}

                .container {{
                    max-width: 700px;
                    margin: auto;
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                }}

                h1 {{
                    color: #333;
                }}

                p {{
                    color: #555;
                    line-height: 1.6;
                }}
            </style>
        </head>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #f5f5f5;
                    padding: 20px;
                }}

                .container {{
                    max-width: 700px;
                    margin: auto;
                    background: white;
                    padding: 30px;
                    border-radius: 10px;
                }}

                h1 {{
                    color: #333;
                }}

                p {{
                    color: #555;
                    line-height: 1.6;
                }}
            </style>
        </head>

        <body>

            <div class="container">

            <p>We found the following jobs that may interest you.</p>

            {job_cards}

            <hr>

            <p style="font-size:12px;color:#888;">
            You're receiving this email because you subscribed to job alerts.
            </p>

            </div>

        </body>
    </html>
"""

def send_email_notification(job_cards):

    # server = None
    try:
        html_content = render_email(job_cards)

        # Create email object
        msg = MIMEMultipart()
        msg['From'] = Header("Mboka Bot", 'utf-8')  # Sender display name
        msg['To'] = Header("Krunch Sensei", 'utf-8') # Recipient display name
        msg['Subject'] = Header("Job Alerts", 'utf-8') # Email subject

        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        # # Create SMTP object and connect to the server
        # server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        # server.starttls() # Enable TLS encryption (usually required for port 587)

        # # Log in to the mailbox
        # server.login(SENDER_EMAIL, PASSWORD)

        # # Send the email
        # server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                # server.connect()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())

        print("Email sent successfully!")

    except Exception as e:
        print(f"Failed to send email: {e}")
    # finally:
        # server.quit() # Close the connection




# ----------------------------
# Main run (unchanged)
# ----------------------------
def run():
    init_db()
    jobs = fetch_jobs()

    scored = []
    for job in jobs:
        if not keyword_filter(job):
            continue
        score = final_score(job)
        scored.append((job, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    top_jobs = scored[:TOP_K]

    job_cards = ""

    for job, score in top_jobs:
        jid = job_id_from(job)
        # if already_seen(jid):
        #     continue
        if score >= THRESHOLD:
            # message = format_alert(job, score)
            # send_telegram_message(message)
            job_cards += render_job_card(job)
            save_job(job, score)

    if len(job_cards) != 0:
        send_email_notification(job_cards)


if __name__ == "__main__":
    run()