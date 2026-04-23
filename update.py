import os
import json
import feedparser
import requests
from groq import Groq

# Keys from GitHub Secrets
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
AA_API_KEY = os.environ.get("AA_API_KEY")

# ---------------------------------------------------------
# 1. FETCH ARTIFICIAL ANALYSIS SCOREBOARD (Bypasses Groq)
# ---------------------------------------------------------
def fetch_live_scoreboard():
    if not AA_API_KEY:
        print("Warning: AA_API_KEY is missing.")
        return []
    try:
        headers = {"x-api-key": AA_API_KEY}
        response = requests.get("https://artificialanalysis.ai/api/v2/data/llms/models", headers=headers)
        if response.status_code != 200:
            print(f"AA API Error: {response.status_code}")
            return []
            
        data = response.json()
        models_ui_data = []
        
        # Sort by intelligence index to simulate the leaderboard ranking
        models_list = data.get("data", [])
        models_list.sort(key=lambda x: x.get("evaluations", {}).get("artificial_analysis_intelligence_index", 0) or 0, reverse=True)
        
        for model in models_list[:5]:
            swe = model.get("evaluations", {}).get("artificial_analysis_coding_index", "N/A")
            price = model.get("pricing", {}).get("price_1m_blended_3_to_1", "N/A")
            models_ui_data.append({
                "title": model.get("name", "Unknown Model"),
                "url": f"https://artificialanalysis.ai/models/{model.get('slug', '')}",
                "summary": f"Coding Index: {swe} | Blended Price: ${price}/1M tokens",
                "source": "Artificial Analysis"
            })
        return models_ui_data
    except Exception as e:
        print(f"AA API Fetch failed: {e}")
        return []

# ---------------------------------------------------------
# 2. FETCH REDDIT VIA NATIVE JSON API (Bypasses Firewall)
# ---------------------------------------------------------
def fetch_reddit_community(subreddits):
    reddit_posts = []
    # This specific User-Agent format is REQUIRED by Reddit's API guidelines
    headers = {
        "User-Agent": "linux:ai-radar-bot:v1.0 (by /u/data-science-radar)"
    }
    
    for sub in subreddits:
        try:
            url = f"https://www.reddit.com/r/{sub}/top.json?t=day&limit=2"
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                for post in data.get('data', {}).get('children', []):
                    post_data = post.get('data', {})
                    reddit_posts.append({
                        "title": post_data.get('title', ''),
                        "url": f"https://reddit.com{post_data.get('permalink', '')}",
                        "summary": post_data.get('selftext', '')[:200], # Extract the actual post body
                        "source": f"r/{sub}"
                    })
            else:
                print(f"Reddit blocked r/{sub} - Status: {response.status_code}")
        except Exception as e:
            print(f"Failed to fetch r/{sub}: {e}")
            
    return reddit_posts

# ---------------------------------------------------------
# 3. SETUP FEEDS AND BUILD PAYLOAD
# ---------------------------------------------------------
CATEGORIZED_FEEDS = {
    "tailored": [
        ("InfoQ", "https://feed.infoq.com/AI/news.rss"),
        ("Pragmatic Engineer", "https://blog.pragmaticengineer.com/rss/"),
        ("GitHub Python", "https://mshibanami.github.io/GitHubTrendingRSS/daily/python.xml"),
        ("Google Cloud AI", "https://cloudblog.withgoogle.com/products/ai-machine-learning/rss/"),
        ("LangChain", "https://blog.langchain.dev/rss/"),
        ("Ollama", "https://ollama.com/blog.xml")
    ],
    "telecom": [
        ("Telecoms AI", "https://telecoms.com/category/ai/feed/"),
        ("Fierce Network", "https://www.fierce-network.com/rss/xml")
    ],
    "top_stories": [
        ("TechCrunch", "https://techcrunch.com/category/artificial-intelligence/feed/"),
        ("Simon Willison", "https://simonwillison.net/atom/entries/"),
        ("Latent Space", "https://www.latent.space/feed")
    ],
    "cautionary": [
        ("OWASP GenAI", "https://genai.owasp.org/feed/")
    ]
}

SUBREDDITS = ["LocalLLaMA", "AI_Agents", "MachineLearning", "AgentsOfAI", "LLMDevs"]

radar_payload = {
    "tailored": [], "telecom": [], "top_stories": [], 
    "cautionary": [], "community": []
}

# Fetch RSS
feedparser.USER_AGENT = "Mozilla/5.0 (AI Radar Bot)"
for section, feeds in CATEGORIZED_FEEDS.items():
    for source_name, url in feeds:
        try:
            feed = feedparser.parse(url)
            for e in feed.entries[:2]:
                radar_payload[section].append({
                    "title": e.get("title", ""),
                    "url": e.get("link", ""),
                    "summary": e.get("description", "")[:200],
                    "source": source_name
                })
        except Exception as e:
            print(f"Failed to fetch RSS {url}: {e}")

# Fetch Reddit
radar_payload["community"] = fetch_reddit_community(SUBREDDITS)

# ---------------------------------------------------------
# 4. FILTER WITH GROQ LLM
# ---------------------------------------------------------
prompt = """
You are an intelligence curator for a Data Scientist at Verizon specializing in MLOps, Agentic AI, and Local LLMs.
I am providing you with a JSON object containing articles pre-sorted by category. 

Filter out the noise and rewrite the summaries to be punchy and relevant to my Verizon/MLOps context.
- If a "telecom" article mentions Verizon, AT&T, or Agentic Networks, highlight that.
- If a "tailored" article mentions a tool useful for multi-agent systems, local GPUs, or GCP, explain why.
- For "community", summarize the Reddit post context briefly.

Return a JSON object with ONLY these 5 arrays: "tailored", "telecom", "top_stories", "cautionary", "community".
Format: {"tailored": [{"title": "...", "url": "...", "summary": "...", "source": "..."}], ...}
"""

try:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(radar_payload)}
        ],
        response_format={"type": "json_object"},
        temperature=0.1
    )
    groq_data = json.loads(response.choices[0].message.content)
except Exception as e:
    print(f"Groq API failed: {e}")
    groq_data = radar_payload # Fallback to uncurated data on failure

# ---------------------------------------------------------
# 5. MERGE SCOREBOARD & SAVE
# ---------------------------------------------------------
groq_data["models"] = fetch_live_scoreboard()

with open("data.json", "w") as f:
    json.dump(groq_data, f, indent=2)
    
print("✅ Radar synced successfully with Groq, Reddit Native API, and Artificial Analysis!")