from datetime import datetime, timedelta, timezone
import math
import re
from xml.sax import make_parser

from sentence_transformers import SentenceTransformer, util
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from services.string_handlers.string_handler import ENABLE_RECENCY_BOOST, JOB_EMBED_MODEL, MAX_RECENCY_BOOST, PROFILE_TEXT, RECENCY_HALF_LIFE_HOURS, RERANK_MODEL, USE_RERANKER


embedder = SentenceTransformer(JOB_EMBED_MODEL)

if USE_RERANKER:
    rerank_tokenizer = AutoTokenizer.from_pretrained(RERANK_MODEL)
    rerank_model = AutoModelForSequenceClassification.from_pretrained(RERANK_MODEL)
    rerank_model.eval()
else:
    rerank_tokenizer = None
    rerank_model = None

profile_embedding = embedder.encode(PROFILE_TEXT, convert_to_tensor=True, normalize_embeddings=True)

def _location_sentence(job):
    """Create a natural‑language description of the job's location and onsite requirements."""
    loc = job.get("location", "Unknown location")
    desc = job.get("description", "")
    # Simple hybrid detection – adjust keywords as needed
    is_hybrid = any(w in f"{job.get('title','')} {desc}".lower() 
                    for w in ["hybrid", "on-site", "onsite", "in-office", "partially remote"])
    arrangement = "hybrid/onsite" if is_hybrid else "remote"
    return f"This job is {arrangement} and located in {loc}."

def _embed_score(job):
    text = (
        f"{job.get('title','')}\n"
        f"{job.get('description','')}\n"
        f"{job.get('company','')}\n"
        f"{_location_sentence(job)}"
        )
    
    emb = embedder.encode(text, convert_to_tensor=True, normalize_embeddings=True)

    #Performs the comparison between the skills i have(currently stored in the vector profile_embedding) and the job that has been found stored in (encoded into a vector then stored in emb)
    return float(util.cos_sim(profile_embedding, emb).item())

def _rerank_score(job):
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

def _get_recency_boost(job):
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
            post_date = make_parser.parse(date_str)
        
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
    base = _embed_score(job)
    if USE_RERANKER:
        rr = _rerank_score(job)
        if rr is None:
            return base
        return 0.6 * base + 0.4 * rr
    
    # Multiply by recency boost – recent jobs get a higher final score
    recency = _get_recency_boost(job)

    return base * recency