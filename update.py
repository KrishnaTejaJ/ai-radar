"""
AI Radar — update.py (v2.1)

Same as v2, PLUS:
- Reads previous data.json before run
- Diffs top-5 per filter (all / paid / open) against prior run
- Marks models with is_new_entrant=true when they enter a top-5 for the first time
"""

import os
import json
import hashlib
import re
import time
import html
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import feedparser
import requests
from groq import Groq

# =========================================================
# CONFIG
# =========================================================
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
AA_API_KEY = os.environ.get("AA_API_KEY")

RADAR_TOP_N = 5
RADAR_EXPAND_N = 10
INVENTORY_PER_SOURCE = 5
ENTRIES_PER_FEED = 10
SUMMARY_CHAR_LIMIT = 600
MIN_SCORE_TOP = 3
MIN_SCORE_EXPAND = 4
SEEN_FILE = "seen.json"
DATA_FILE = "data.json"
SEEN_TTL_DAYS = 30

FRESHNESS_DAYS = {
    "tailored":    60,
    "telecom":     30,
    "top_stories": 14,
    "cautionary":  60,
    "community":    7,
}

TIER1_WINDOW_DAYS = {
    "tailored":    14,
    "telecom":      7,
    "top_stories":  3,
    "cautionary":   7,
    "community":    1,
}

# =========================================================
# SOURCES
# =========================================================
SOURCES = {
    "tailored": [
        {"name": "Anthropic Engineering", "tier": 1, "type": "rss",
         "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_engineering.xml"},
        {"name": "Sebastian Raschka", "tier": 1, "type": "rss",
         "url": "https://magazine.sebastianraschka.com/feed"},
        {"name": "Eugene Yan", "tier": 1, "type": "rss",
         "url": "https://eugeneyan.com/rss/"},
        {"name": "Chip Huyen", "tier": 1, "type": "rss",
         "url": "https://huyenchip.com/feed.xml"},
        {"name": "Interconnects", "tier": 1, "type": "rss",
         "url": "https://www.interconnects.ai/feed"},
        {"name": "Pragmatic Engineer", "tier": 1, "type": "rss",
         "url": "https://blog.pragmaticengineer.com/rss/"},
        {"name": "Google Cloud AI", "tier": 2, "type": "rss",
         "url": "https://cloudblog.withgoogle.com/products/ai-machine-learning/rss/"},
        {"name": "Hugging Face Blog", "tier": 2, "type": "rss",
         "url": "https://huggingface.co/blog/feed.xml"},
        {"name": "GitHub Python Trending", "tier": 2, "type": "rss",
         "url": "https://mshibanami.github.io/GitHubTrendingRSS/daily/python.xml"},
        {"name": "Hacker News (AI/LLM)", "tier": 2, "type": "rss",
         "url": "https://hnrss.org/newest?q=AI+OR+LLM+OR+agent&points=50"},
    ],
    "telecom": [
        {"name": "arXiv: 5G + LLM", "tier": 1, "type": "rss",
         "url": "http://export.arxiv.org/api/query?search_query=abs:%225G%22+AND+%28abs:%22LLM%22+OR+abs:%22large+language+model%22+OR+abs:%22agent%22%29&sortBy=submittedDate&sortOrder=descending&max_results=10"},
        {"name": "arXiv: RAN anomaly", "tier": 1, "type": "rss",
         "url": "http://export.arxiv.org/api/query?search_query=abs:%22RAN%22+AND+%28abs:%22anomaly%22+OR+abs:%22root+cause%22%29&sortBy=submittedDate&sortOrder=descending&max_results=10"},
        {"name": "arXiv: O-RAN", "tier": 1, "type": "rss",
         "url": "http://export.arxiv.org/api/query?search_query=abs:%22O-RAN%22+OR+abs:%22Open+RAN%22&sortBy=submittedDate&sortOrder=descending&max_results=10"},
        {"name": "Light Reading", "tier": 2, "type": "rss",
         "url": "https://www.lightreading.com/rss.xml"},
        {"name": "RCR Wireless", "tier": 2, "type": "rss",
         "url": "https://www.rcrwireless.com/feed"},
        {"name": "Fierce Network", "tier": 2, "type": "rss",
         "url": "https://www.fierce-network.com/rss/xml"},
    ],
    "top_stories": [
        {"name": "Simon Willison", "tier": 1, "type": "rss",
         "url": "https://simonwillison.net/atom/entries/"},
        {"name": "AI Snake Oil", "tier": 1, "type": "rss",
         "url": "https://www.aisnakeoil.com/feed"},
        {"name": "Latent Space", "tier": 2, "type": "rss",
         "url": "https://www.latent.space/feed"},
        {"name": "TechCrunch AI", "tier": 2, "type": "rss",
         "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
    ],
    "cautionary": [
        {"name": "Anthropic Frontier Red Team", "tier": 1, "type": "rss",
         "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_red.xml"},
        {"name": "Anthropic Research", "tier": 1, "type": "rss",
         "url": "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_research.xml"},
        {"name": "AI Incident Database", "tier": 1, "type": "rss",
         "url": "https://incidentdatabase.ai/rss.xml", "title_fallback": True},
        {"name": "OWASP GenAI", "tier": 2, "type": "rss",
         "url": "https://genai.owasp.org/feed/"},
        {"name": "Schneier on Security", "tier": 2, "type": "rss",
         "url": "https://www.schneier.com/feed/atom/"},
        {"name": "DataRobot Blog", "tier": 2, "type": "rss",
         "url": "https://www.datarobot.com/blog/feed/"},
        {"name": "CyberArk Engineering", "tier": 2, "type": "rss",
         "url": "https://medium.com/feed/cyberark-engineering"},
        {"name": "Future of Privacy Forum", "tier": 2, "type": "rss",
         "url": "https://fpf.org/feed/"},
    ],
    "community": [
        {"name": "Lobsters (AI tag)", "tier": 1, "type": "rss",
         "url": "https://lobste.rs/t/ai.rss"},
    ],
}

# =========================================================
# HELPERS
# =========================================================
def url_hash(u: str) -> str:
    return hashlib.sha1(u.encode("utf-8")).hexdigest()[:16]

def load_seen() -> dict:
    if not os.path.exists(SEEN_FILE):
        return {}
    try:
        with open(SEEN_FILE, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=SEEN_TTL_DAYS)).isoformat()
    return {h: ts for h, ts in data.items() if ts >= cutoff}

def save_seen(seen: dict) -> None:
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, indent=2)

def load_previous_data() -> dict:
    """Load previous data.json to diff against. Returns {} if missing."""
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}

def strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()

def truncate_smart(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    last_period = cut.rfind(". ")
    if last_period > limit * 0.6:
        return cut[: last_period + 1]
    return cut.rsplit(" ", 1)[0] + "…"

def parse_entry_date(entry):
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime.fromtimestamp(time.mktime(st), tz=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                continue
    return None

def is_fresh_enough(dt, section: str) -> bool:
    if dt is None:
        return True
    max_age = FRESHNESS_DAYS.get(section, 30)
    return (datetime.now(timezone.utc) - dt).days <= max_age

def is_today(dt) -> bool:
    if dt is None:
        return False
    now = datetime.now(timezone.utc)
    return (now - dt).days == 0

def is_within_tier1_window(dt, section: str) -> bool:
    if dt is None:
        return True
    window = TIER1_WINDOW_DAYS.get(section, 7)
    return (datetime.now(timezone.utc) - dt).days <= window

def is_valid_title(title: str) -> bool:
    if not title or len(title.strip()) < 5:
        return False
    if title.strip().lower() in {"no title", "untitled", "(no title)"}:
        return False
    return True

def make_id(section: str, url: str) -> str:
    prefix = section[:2]
    return f"{prefix}_{url_hash(url)}"

# =========================================================
# FETCHERS
# =========================================================
def fetch_rss_source(source_cfg: dict, section: str) -> list:
    items = []
    try:
        feed = feedparser.parse(source_cfg["url"], agent="Mozilla/5.0 (AI Radar Bot)")
        for e in feed.entries[:ENTRIES_PER_FEED]:
            link = e.get("link", "")
            if not link:
                continue

            title = strip_html(e.get("title", ""))
            raw_summary = e.get("summary", "") or e.get("description", "") or ""
            summary = truncate_smart(strip_html(raw_summary), SUMMARY_CHAR_LIMIT)

            if not is_valid_title(title) and source_cfg.get("title_fallback"):
                if summary:
                    first_sentence = re.split(r"(?<=[.!?])\s", summary, maxsplit=1)[0]
                    title = first_sentence[:120] or source_cfg["name"]
                else:
                    continue

            if not is_valid_title(title):
                continue

            dt = parse_entry_date(e)
            items.append({
                "id": make_id(section, link),
                "title": title,
                "url": link,
                "summary": summary,
                "source": source_cfg["name"],
                "tier": source_cfg["tier"],
                "published": dt.isoformat() if dt else None,
                "_dt": dt,
            })
    except Exception as ex:
        print(f"  [warn] failed to fetch {source_cfg['name']}: {ex}")
    return items

def fetch_hn_algolia(min_points: int, hours_back: int = 24) -> list:
    items = []
    since_ts = int(time.time()) - (hours_back * 3600)
    query = "LLM OR agent OR RAG OR \"local model\" OR multi-agent"
    url = (
        f"https://hn.algolia.com/api/v1/search"
        f"?query={quote(query)}"
        f"&tags=story"
        f"&numericFilters=points>{min_points},created_at_i>{since_ts}"
        f"&hitsPerPage=15"
    )
    try:
        r = requests.get(url, timeout=20)
        if r.status_code != 200:
            print(f"  [warn] HN Algolia status {r.status_code}")
            return []
        data = r.json()
        for hit in data.get("hits", []):
            story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            discussion_url = f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            title = strip_html(hit.get("title", ""))
            if not is_valid_title(title):
                continue
            body = hit.get("story_text") or ""
            dt = None
            if hit.get("created_at_i"):
                dt = datetime.fromtimestamp(hit["created_at_i"], tz=timezone.utc)
            source_label = f"Hacker News (≥{min_points})"
            items.append({
                "id": make_id("community", story_url),
                "title": title,
                "url": story_url,
                "discussion_url": discussion_url,
                "summary": truncate_smart(strip_html(body), SUMMARY_CHAR_LIMIT),
                "source": source_label,
                "tier": 1 if min_points >= 100 else 2,
                "points": hit.get("points", 0),
                "num_comments": hit.get("num_comments", 0),
                "published": dt.isoformat() if dt else None,
                "_dt": dt,
            })
    except Exception as ex:
        print(f"  [warn] HN Algolia failed: {ex}")
    return items

def fetch_models() -> list:
    """Artificial Analysis API → top 20 models."""
    if not AA_API_KEY:
        print("  [warn] AA_API_KEY missing")
        return []
    try:
        r = requests.get(
            "https://artificialanalysis.ai/api/v2/data/llms/models",
            headers={"x-api-key": AA_API_KEY},
            timeout=20,
        )
        if r.status_code != 200:
            print(f"  [warn] AA API status {r.status_code}")
            return []
        data = r.json()
        models = data.get("data", [])
        models.sort(
            key=lambda m: m.get("evaluations", {}).get("artificial_analysis_intelligence_index", 0) or 0,
            reverse=True,
        )
        out = []
        for m in models[:20]:
            evals = m.get("evaluations", {})
            pricing = m.get("pricing", {})
            is_open = (
                m.get("is_open_weights")
                or m.get("open_weights")
                or (m.get("license", "") or "").lower() in {"open", "open-weights", "open_weights", "apache-2.0", "mit", "llama", "gemma"}
            )
            out.append({
                "name": m.get("name", "Unknown"),
                "slug": m.get("slug", ""),
                "url": f"https://artificialanalysis.ai/models/{m.get('slug', '')}",
                "creator": (m.get("model_creator") or {}).get("name", "Unknown"),
                "intelligence_index": evals.get("artificial_analysis_intelligence_index"),
                "coding_index": evals.get("artificial_analysis_coding_index"),
                "price_blended": pricing.get("price_1m_blended_3_to_1"),
                "is_open_weights": bool(is_open),
                "license_type": "open" if is_open else "proprietary",
            })
        return out
    except Exception as ex:
        print(f"  [warn] AA API failed: {ex}")
        return []

# =========================================================
# MODEL DIFF — NEW-ENTRANT TRACKING
# =========================================================
def compute_model_new_entrants(current_models: list, previous_data: dict) -> dict:
    """
    Returns {filter_name: set of slugs that are NEW to that filter's top-5 this run}.
    Filters: all, paid, open.
    """
    # Previous top-5 slugs per filter (if prior data exists)
    prev_sets = previous_data.get("models", {}).get("previous_top_slugs", {})
    prev_all = set(prev_sets.get("all", []))
    prev_paid = set(prev_sets.get("paid", []))
    prev_open = set(prev_sets.get("open", []))

    # Compute current top-5 per filter
    def top_5_slugs(filter_name):
        if filter_name == "all":
            filtered = current_models[:5]
        elif filter_name == "paid":
            filtered = [m for m in current_models if m["license_type"] == "proprietary"][:5]
        elif filter_name == "open":
            filtered = [m for m in current_models if m["license_type"] == "open"][:5]
        return [m["slug"] for m in filtered]

    cur_all = top_5_slugs("all")
    cur_paid = top_5_slugs("paid")
    cur_open = top_5_slugs("open")

    new_entrants = {
        "all":  [s for s in cur_all  if s not in prev_all],
        "paid": [s for s in cur_paid if s not in prev_paid],
        "open": [s for s in cur_open if s not in prev_open],
    }

    # First-run case: nothing is "new" if we have no prior data
    if not prev_sets:
        new_entrants = {"all": [], "paid": [], "open": []}

    return {
        "new_entrants": new_entrants,
        "current_top_slugs": {
            "all": cur_all,
            "paid": cur_paid,
            "open": cur_open,
        },
    }

# =========================================================
# SECTION ORCHESTRATION
# =========================================================
def fetch_section(section: str) -> dict:
    sources_out = {}
    all_items = []

    for src_cfg in SOURCES.get(section, []):
        fetched = fetch_rss_source(src_cfg, section)
        fetched.sort(key=lambda i: i.get("_dt") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        fetched = fetched[:INVENTORY_PER_SOURCE]
        sources_out[src_cfg["name"]] = {
            "tier": src_cfg["tier"],
            "items": fetched,
        }
        all_items.extend(fetched)

    if section == "community":
        hn_high = fetch_hn_algolia(min_points=100, hours_back=24)
        hn_mid = fetch_hn_algolia(min_points=50, hours_back=24)
        high_ids = {i["id"] for i in hn_high}
        hn_mid = [i for i in hn_mid if i["id"] not in high_ids]

        hn_high.sort(key=lambda i: i.get("points", 0), reverse=True)
        hn_mid.sort(key=lambda i: i.get("points", 0), reverse=True)

        sources_out["Hacker News (≥100)"] = {
            "tier": 1,
            "items": hn_high[:INVENTORY_PER_SOURCE],
        }
        sources_out["Hacker News (≥50)"] = {
            "tier": 2,
            "items": hn_mid[:INVENTORY_PER_SOURCE],
        }
        all_items.extend(hn_high[:INVENTORY_PER_SOURCE])
        all_items.extend(hn_mid[:INVENTORY_PER_SOURCE])

    return {"sources": sources_out, "all_candidates": all_items}

# =========================================================
# LLM SCORING
# =========================================================
SYSTEM_PROMPT_BASE = """You are an intelligence curator for Krishna, an AI platform architect at Verizon.

CONTEXT:
- Builds NetPresso: a multi-agent platform (8 agents) for automated 5G Root Cause Analysis
- Stack: local LLMs (Llama3, Gemma3) on multi-GPU Ollama, RAG with pgvector + ChromaDB,
  custom Elasticsearch MCP server, Prefect orchestration, Langfuse observability, FastAPI + Next.js
- Working on EB-1A evidence: publishing practitioner takes (InfoQ, The New Stack)
- Interests: AI safety, governance, geopolitics, telecom + AI
- NOT interested in: basic DS/ML tutorials, generic AI-is-changing-everything pieces,
  vendor marketing dressed as content, beginner LangChain demos, hype-cycle takes

YOUR TASK:
You receive a JSON array of candidate items, each with a unique `id`. For each item, return:
- id: echo the input id EXACTLY
- score: integer 1-5. Be ruthless. Most items should score 2-3.
- tag: one of "build" | "write-about" | "watch" | "ignore"
- summary: 1-2 punchy sentences. If score >= 4, prefix "Why this matters: ".

CRITICAL RULES:
- Echo IDs EXACTLY — do not invent, modify, or rename IDs
- Return ONLY items with score >= 2
- Do not invent new items. Do not output titles or URLs.
- If uncertain, score 2 and tag "watch".

SECTION GUIDANCE:
{section_guidance}

OUTPUT (JSON object with key "items"):
{{"items": [{{"id": "ta_abc123", "score": 4, "tag": "build", "summary": "Why this matters: ..."}}]}}"""

SECTION_GUIDANCE = {
    "tailored": """Tailored prioritizes VOICE and JUDGMENT. Original analysis, contrarian framings,
and practitioner essays score higher than announcements. Sebastian Raschka / Chip Huyen / Eugene Yan
posts with novel framings = 4-5. Hugging Face model releases = 3 unless directly relevant to local-LLM ops.
HN items: score the LINKED content quality, not HN discussion volume.""",
    "telecom": """Telecom mixes news and academic preprints. Academic arXiv items should score 4+ if
directly relevant to RAN/5G/O-RAN/agents. News items need to be Verizon-specific OR documenting a real
deployment to score 4+.""",
    "top_stories": """Deprioritize Latent Space [AINews] aggregation posts (score 2-3 max) in favor of
original analysis. Simon Willison + AI Snake Oil get tier-1 weight because they are opinionated takes.""",
    "cautionary": """Cautionary = concrete failures, security incidents, agent misbehavior. Anthropic
Red Team / Research = 5. AIID incidents = 4-5. Schneier posts: score 3+ ONLY if AI-relevant. DataRobot
and CyberArk are vendor blogs — only score 4+ if documenting a specific failure pattern.""",
    "community": """Community = practitioners discussing tech. Prioritize problem-solution pairs,
benchmarks with numbers, production lessons. Deprioritize pure questions, memes, drama, hype.
Lobsters items default to score 3 minimum unless clearly off-target.""",
}

def score_with_llm(section: str, candidates: list) -> dict:
    if not candidates:
        return {}

    llm_input = [
        {
            "id": c["id"],
            "title": c["title"][:200],
            "source": c["source"],
            "summary": c["summary"][:500],
        }
        for c in candidates
    ]

    prompt = SYSTEM_PROMPT_BASE.format(section_guidance=SECTION_GUIDANCE.get(section, ""))

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": json.dumps(llm_input)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = json.loads(response.choices[0].message.content)
        llm_items = raw.get("items", [])

        valid_ids = {c["id"] for c in candidates}
        scored = {}
        for item in llm_items:
            item_id = item.get("id")
            if item_id not in valid_ids:
                continue
            score = item.get("score")
            tag = item.get("tag")
            if not isinstance(score, int) or score < 1 or score > 5:
                continue
            if tag not in {"build", "write-about", "watch", "ignore"}:
                tag = "watch"
            scored[item_id] = {
                "score": score,
                "tag": tag,
                "summary": item.get("summary", "")[:SUMMARY_CHAR_LIMIT],
            }
        return scored
    except Exception as ex:
        print(f"  [warn] LLM scoring failed for {section}: {ex}")
        return {}

# =========================================================
# PROMOTION
# =========================================================
def promote_to_radar(section: str, inventory: dict, scores: dict) -> dict:
    all_items = []
    for source_name, src in inventory.items():
        for item in src["items"]:
            if item["id"] not in scores:
                continue
            s = scores[item["id"]]
            if s["tag"] == "ignore":
                continue
            enriched = {**item, **s, "tag_raw": s["tag"]}
            all_items.append(enriched)

    for item in all_items:
        item["_is_today"] = is_today(item.get("_dt"))
        item["_in_tier1_window"] = is_within_tier1_window(item.get("_dt"), section)

    top = []
    tier1_sources_used = set()

    tier1_candidates = [
        i for i in all_items
        if i["tier"] == 1 and i["_in_tier1_window"] and i["score"] >= MIN_SCORE_TOP
    ]
    tier1_candidates.sort(key=lambda x: (x["score"], x.get("_dt") or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    for item in tier1_candidates:
        if len(top) >= RADAR_TOP_N:
            break
        if item["source"] in tier1_sources_used:
            continue
        top.append(item)
        tier1_sources_used.add(item["source"])

    if len(top) < RADAR_TOP_N:
        top_ids = {i["id"] for i in top}
        today_candidates = [
            i for i in all_items
            if i["id"] not in top_ids and i["_is_today"] and i["score"] >= MIN_SCORE_TOP
        ]
        today_candidates.sort(key=lambda x: x["score"], reverse=True)
        for item in today_candidates:
            if len(top) >= RADAR_TOP_N:
                break
            top.append(item)

    if len(top) < RADAR_TOP_N:
        top_ids = {i["id"] for i in top}
        window_candidates = [
            i for i in all_items
            if i["id"] not in top_ids
            and is_fresh_enough(i.get("_dt"), section)
            and i["score"] >= MIN_SCORE_TOP
        ]
        window_candidates.sort(key=lambda x: (x["score"], x.get("_dt") or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
        for item in window_candidates:
            if len(top) >= RADAR_TOP_N:
                break
            top.append(item)

    top_ids = {i["id"] for i in top}
    expand_candidates = [
        i for i in all_items
        if i["id"] not in top_ids
        and is_fresh_enough(i.get("_dt"), section)
        and i["score"] >= MIN_SCORE_EXPAND
    ]
    expand_candidates.sort(key=lambda x: (x["score"], x.get("_dt") or datetime.min.replace(tzinfo=timezone.utc)), reverse=True)
    expand = expand_candidates[:RADAR_EXPAND_N - len(top)]

    def finalize(item):
        out = {k: v for k, v in item.items() if not k.startswith("_")}
        out["flags"] = {
            "new": is_today(item.get("_dt")),
            "featured": True,
            "tier": item["tier"],
        }
        return out

    return {
        "top": [finalize(i) for i in top],
        "expand": [finalize(i) for i in expand],
    }

def clean_inventory_for_json(inventory: dict, radar_ids: set) -> dict:
    out = {}
    for source_name, src in inventory.items():
        clean_items = []
        for item in src["items"]:
            clean = {k: v for k, v in item.items() if not k.startswith("_")}
            clean["flags"] = {
                "new": is_today(item.get("_dt")),
                "featured": item["id"] in radar_ids,
                "tier": src["tier"],
            }
            clean_items.append(clean)
        out[source_name] = {
            "tier": src["tier"],
            "items": clean_items,
        }
    return out

# =========================================================
# MAIN
# =========================================================
def main():
    print(f"\n{'=' * 70}\n  AI RADAR SYNC — {datetime.now(timezone.utc).isoformat()}\n{'=' * 70}")

    seen = load_seen()
    previous_data = load_previous_data()
    now_iso = datetime.now(timezone.utc).isoformat()
    print(f"\nLoaded {len(seen)} seen URLs, prior data: {'yes' if previous_data else 'no (first run)'}")

    data = {
        "meta": {
            "last_updated": now_iso,
            "version": "2.1",
            "stats": {},
        },
        "radar": {},
        "sources": {},
        "models": {"all": [], "default_sort": "intelligence_index"},
    }

    total_stats = {"fetched": 0, "scored": 0, "radar_top": 0, "radar_expand": 0}

    for section in ["tailored", "telecom", "top_stories", "cautionary", "community"]:
        print(f"\n──── {section.upper()} ────")
        fetched = fetch_section(section)
        inventory = fetched["sources"]
        candidates = fetched["all_candidates"]

        for item in candidates:
            seen[url_hash(item["url"])] = now_iso

        source_count = len(inventory)
        item_count = len(candidates)
        print(f"  Fetched {item_count} items from {source_count} sources")

        if not candidates:
            print(f"  [skip] no candidates; skipping LLM call")
            scores = {}
        else:
            scores = score_with_llm(section, candidates)
            print(f"  Scored {len(scores)} items (dropped {item_count - len(scores)})")

        radar = promote_to_radar(section, inventory, scores)
        radar_ids = {i["id"] for i in radar["top"] + radar["expand"]}
        print(f"  Radar: {len(radar['top'])} top + {len(radar['expand'])} expand")

        data["radar"][section] = radar
        data["sources"][section] = clean_inventory_for_json(inventory, radar_ids)

        total_stats["fetched"] += item_count
        total_stats["scored"] += len(scores)
        total_stats["radar_top"] += len(radar["top"])
        total_stats["radar_expand"] += len(radar["expand"])

    # Models + diff for new entrants
    print(f"\n──── MODELS ────")
    models = fetch_models()
    diff = compute_model_new_entrants(models, previous_data)
    data["models"]["all"] = models
    data["models"]["new_entrants"] = diff["new_entrants"]
    data["models"]["previous_top_slugs"] = diff["current_top_slugs"]  # stored for NEXT run's diff
    print(f"  Fetched {len(models)} models")
    print(f"  New entrants: all={len(diff['new_entrants']['all'])}, "
          f"paid={len(diff['new_entrants']['paid'])}, "
          f"open={len(diff['new_entrants']['open'])}")

    data["meta"]["stats"] = total_stats

    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, default=str)
    save_seen(seen)

    print(f"\n{'=' * 70}")
    print(f"  SUMMARY: {total_stats}")
    print(f"  ✅ data.json + seen.json written")
    print(f"{'=' * 70}\n")

if __name__ == "__main__":
    main()