import sqlite3

from datetime import datetime, timezone

from services.string_handlers.string_handler import DB_PATH, job_id_from

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


def already_seen(job_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM seen_jobs WHERE job_id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    return row is not None