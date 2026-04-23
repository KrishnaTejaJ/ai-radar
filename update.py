import os
import json
import hashlib
import re
from datetime import datetime, timedelta, timezone
from html import unescape

import feedparser
import requests
from groq import Groq

# ---------------------------------------------------------
# Config
# ---------------------------------------------------------
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
AA_API_KEY = os.environ.get("AA_API_KEY")

ENTRIES_PER_FEED = 5          # was 2 — let the LLM filter, don't pre-truncate
SUMMARY_CHAR_LIMIT = 600      # was 200 — preserve enough signal for scoring
SEEN_FILE = "seen.json"
SEEN_TTL_DAYS = 30
MIN_RELEVANCE_SCORE = 3       # 1-5; drop anything below this

# ---------------------------------------------------------
# Source list — expanded for thinking, telecom depth, and failure modes
# ---------------------------------------------------------
CATEGORIZED_FEEDS = {
    "tailored": [
        # Tooling / releases (kept)
        ("LangChain", "https://blog.langchain.dev/rss/"),
        ("Ollama", "https://ollama.com/blog.xml"),
        ("Google Cloud AI", "https://cloudblog.withgoogle.com/products/ai-machine-learning/rss/"),
        ("GitHub Python Trending", "https://mshibanami.github.io/GitHubTrendingRSS/daily/python.xml"),
        # Practitioner thinking — the pieces you'll either build on or argue with
        ("Anthropic Engineering", "https://www.anthropic.com/engineering/rss.xml"),
        ("Hugging Face Blog", "https://huggingface.co/blog/feed.xml"),
        ("Sebastian Raschka", "https://magazine.sebastianraschka.com/feed"),
        ("Eugene Yan", "https://eugeneyan.com/rss/"),
        ("Chip Huyen", "https://huyenchip.com/feed.xml"),
        ("Pragmatic Engineer", "https://blog.pragmaticengineer.com/rss/"),
        ("InfoQ AI", "https://feed.infoq.com/AI/news.rss"),
    ],
    "telecom": [
        # Industry press (kept + expanded)
        ("Telecoms AI", "https://telecoms.com/category/ai/feed/"),
        ("Fierce Network", "https://www.fierce-network.com/rss/xml"),
        ("Light Reading", "https://www.lightreading.com/rss.xml"),
        ("RCR Wireless", "https://www.rcrwireless.com/feed"),
        # Vendor + standards blogs
        ("Ericsson Blog", "https://www.ericsson.com/en/blog/feed"),
        ("Nokia Blog", "https://www.nokia.com/blog/feed/"),
        # Academic — telecom + AI is a small but high-signal stream
        ("arXiv: 5G + LLM", "http://export.arxiv.org/api/query?search_query=abs:%225G%22+AND+%28abs:%22LLM%22+OR+abs:%22large+language+model%22+OR+abs:%22agent%22%29&sortBy=submittedDate&sortOrder=descending&max_results=10"),
        ("arXiv: RAN anomaly", "http://export.arxiv.org/api/query?search_query=abs:%22RAN%22+AND+%28abs:%22anomaly%22+OR+abs:%22root+cause%22%29&sortBy=submittedDate&sortOrder=descending&max_results=10"),
    ],
    "top_stories": [
        ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
        ("Simon Willison", "https://simonwillison.net/atom/entries/"),
        ("Latent Space", "https://www.latent.space/feed"),
        ("AI Snake Oil", "https://www.aisnakeoil.com/feed"),
    ],
    "cautionary": [
        ("OWASP GenAI", "https://genai.owasp.org/feed/"),
        ("AI Incident Database", "https://incidentdatabase.ai/rss.xml"),
        ("Schneier on Security", "https://www.schneier.com/feed/atom/"),
    ],
}

SUBREDDITS = ["LocalLLaMA", "AI_Agents", "MachineLearning", "AgentsOfAI", "LLMDevs"]

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def url_hash(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]

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

def strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def truncate_smart(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    last_period = cut.rfind(". ")
    if last_period > limit * 0.6:
        return cut[: last_period + 1]
    return cut.rsplit(" ", 1)[0] + "…"

# ---------------------------------------------------------
# 1. Artificial Analysis scoreboard
# ---------------------------------------------------------
def fetch_live_scoreboard():
    if not AA_API_KEY:
        print("Warning: AA_API_KEY is missing.")
        return []
    try:
        headers = {"x-api-key": AA_API_KEY}
        response = requests.get(
            "https://artificialanalysis.ai/api/v2/data/llms/models",
            headers=headers,
            timeout=20,
        )
        if response.status_code != 200:
            print(f"AA API Error: {response.status_code}")
            return []
        data = response.json()
        models_list = data.get("data", [])
        models_list.sort(
            key=lambda x: x.get("evaluations", {}).get("artificial_analysis_intelligence_index", 0) or 0,
            reverse=True,
        )
        out = []
        for model in models_list[:5]:
            evals = model.get("evaluations", {})
            swe = evals.get("artificial_analysis_coding_index", "N/A")
            price = model.get("pricing", {}).get("price_1m_blended_3_to_1", "N/A")
            out.append({
                "title": model.get("name", "Unknown Model"),
                "url": f"https://artificialanalysis.ai/models/{model.get('slug', '')}",
                "summary": f"Coding Index: {swe} | Blended Price: ${price}/1M tokens",
                "source": "Artificial Analysis",
            })
        return out
    except Exception as e:
        print(f"AA API fetch failed: {e}")
        return []

# ---------------------------------------------------------
# 2. Reddit
# ---------------------------------------------------------
def fetch_reddit_community(subreddits):
    posts = []
    headers = {"User-Agent": "linux:ai-radar-bot:v1.0 (by /u/data-science-radar)"}
    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/top.json?t=day&limit=4"
            response = requests.get(url, headers=headers, timeout=20)
            if response.status_code != 200:
                print(f"Reddit blocked r/{sub} - Status: {response.status_code}")
                continue
            data = response.json()
            for post in data.get("data", {}).get("children", []):
                pd = post.get("data", {})
                body = pd.get("selftext") or pd.get("title", "")
                posts.append({
                    "title": pd.get("title", ""),
                    "url": f"https://reddit.com{pd.get('permalink', '')}",
                    "summary": truncate_smart(strip_html(body), SUMMARY_CHAR_LIMIT),
                    "source": f"r/{sub}",
                    "score": pd.get("score", 0),
                    "num_comments": pd.get("num_comments", 0),
                })
        except Exception as e:
            print(f"Failed to fetch r/{sub}: {e}")
    return posts

# ---------------------------------------------------------
# 3. RSS fetch + dedup
# ---------------------------------------------------------
def fetch_rss(seen: dict) -> dict:
    feedparser.USER_AGENT = "Mozilla/5.0 (AI Radar Bot)"
    payload = {section: [] for section in CATEGORIZED_FEEDS}
    now_iso = datetime.now(timezone.utc).isoformat()

    for section, feeds in CATEGORIZED_FEEDS.items():
        for source_name, url in feeds:
            try:
                feed = feedparser.parse(url)
                for e in feed.entries[:ENTRIES_PER_FEED]:
                    link = e.get("link", "")
                    if not link:
                        continue
                    h = url_hash(link)
                    if h in seen:
                        continue
                    seen[h] = now_iso

                    raw_summary = e.get("summary", "") or e.get("description", "") or ""
                    clean = truncate_smart(strip_html(raw_summary), SUMMARY_CHAR_LIMIT)
                    payload[section].append({
                        "title": e.get("title", "").strip(),
                        "url": link,
                        "summary": clean,
                        "source": source_name,
                    })
            except Exception as e:
                print(f"Failed to fetch RSS {url}: {e}")
    return payload

# ---------------------------------------------------------
# 4. Groq curation — score, tag, rewrite
# ---------------------------------------------------------
SYSTEM_PROMPT = """You are an intelligence curator for Krishna, an AI platform architect at Verizon.

CONTEXT ABOUT KRISHNA (use this to judge relevance):
- Builds NetPresso: a multi-agent platform (8 agents) for automated 5G Root Cause Analysis
- Stack: local LLMs (Llama3, Gemma3) on multi-GPU Ollama, RAG with pgvector + ChromaDB,
  custom Elasticsearch MCP server, Prefect orchestration, Langfuse observability, FastAPI + Next.js
- Working on EB-1A evidence: needs to publish practitioner takes (InfoQ, The New Stack, Lawfare-adjacent)
- Interests: AI safety, AI governance, geopolitics of AI, telecom + AI intersection
- NOT interested in: basic DS/ML tutorials, generic "AI is changing everything" pieces,
  vendor marketing dressed as content, beginner LangChain demos, hype-cycle takes

YOUR JOB:
You receive a JSON object with article candidates organized by section.
For each candidate, decide:
1. relevance_score (1-5): 5 = directly actionable for NetPresso or write-worthy for him,
   3 = useful context, 1 = noise. Be ruthless. Most items should score 2-3.
2. tag: one of {"build", "write-about", "watch", "ignore"}
   - "build" = something he can integrate into NetPresso or his stack
   - "write-about" = a take, claim, or framing he should respond to in his own writing
   - "watch" = important context but no immediate action
   - "ignore" = drop it
3. summary: rewrite in 1-2 punchy sentences, prefixed with "Why this matters: " when score >= 4.
   Be specific. Mention NetPresso, telecom, agents, governance, or his stack when relevant.

FILTERING RULES:
- DROP anything with relevance_score < 3 OR tag == "ignore". Do not include them in output.
- DROP duplicates (same story from different sources): keep only the best-sourced version.
- For "telecom": prioritize anything about Verizon, AT&T, T-Mobile, agentic networks, 5G AI, RAN automation, O-RAN, or NetOps.
- For "tailored": prioritize multi-agent patterns, local LLM ops, observability, RAG production lessons, MCP.
- For "cautionary": prioritize concrete production failures, security incidents, agent misbehavior. Avoid abstract think-pieces unless score >= 4.
- For "community": include only posts with real technical substance (problem solved, benchmark, novel pattern). Drop pure questions, memes, drama.

OUTPUT FORMAT — return ONLY this JSON, nothing else:
{
  "tailored":     [{"title": "...", "url": "...", "summary": "...", "source": "...", "relevance_score": 4, "tag": "build"}],
  "telecom":      [...],
  "top_stories":  [...],
  "cautionary":   [...],
  "community":    [...]
}

Each section: max 6 items, ordered by relevance_score descending. If a section has no items scoring >= 3, return an empty array for it."""

def curate_with_groq(payload: dict) -> dict:
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        curated = json.loads(response.choices[0].message.content)
        # Defensive: ensure all expected sections exist
        for section in ["tailored", "telecom", "top_stories", "cautionary", "community"]:
            curated.setdefault(section, [])
            # Hard filter in case the model didn't drop low scores
            curated[section] = [
                item for item in curated[section]
                if item.get("relevance_score", 0) >= MIN_RELEVANCE_SCORE
                and item.get("tag") != "ignore"
            ]
        return curated
    except Exception as e:
        print(f"Groq curation failed: {e}")
        # Fallback: return raw payload with empty community/cautionary preserved
        fallback = {k: v for k, v in payload.items()}
        fallback.setdefault("community", [])
        return fallback

# ---------------------------------------------------------
# 5. Main
# ---------------------------------------------------------
def main():
    seen = load_seen()
    print(f"Loaded {len(seen)} seen URLs (TTL {SEEN_TTL_DAYS}d)")

    payload = fetch_rss(seen)
    payload["community"] = fetch_reddit_community(SUBREDDITS)

    # Mark Reddit URLs as seen too
    now_iso = datetime.now(timezone.utc).isoformat()
    for post in payload["community"]:
        seen[url_hash(post["url"])] = now_iso

    total_pre = sum(len(v) for v in payload.values())
    print(f"Fetched {total_pre} new candidate items")

    curated = curate_with_groq(payload)
    curated["models"] = fetch_live_scoreboard()
    curated["last_updated"] = now_iso

    total_post = sum(
        len(curated.get(s, []))
        for s in ["tailored", "telecom", "top_stories", "cautionary", "community"]
    )
    print(f"After curation: {total_post} items kept")

    with open("data.json", "w") as f:
        json.dump(curated, f, indent=2)

    save_seen(seen)
    print("✅ Radar synced.")

if __name__ == "__main__":
    main()
    
