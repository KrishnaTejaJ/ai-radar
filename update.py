import os
import json
import feedparser
import requests
from groq import Groq

# API Keys from GitHub Secrets
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
AA_API_KEY = os.environ.get("AA_API_KEY")

feedparser.USER_AGENT = "Mozilla/5.0 (AI Radar Bot)"

# 1. Fetch Artificial Analysis Scoreboard
def fetch_live_scoreboard():
    try:
        headers = {"Authorization": f"Bearer {AA_API_KEY}"}
        # Artificial Analysis models endpoint
        response = requests.get("https://api.artificialanalysis.ai/v1/models?limit=5", headers=headers)
        if response.status_code != 200:
            return []
            
        data = response.json()
        models_ui_data = []
        for model in data.get("models", [])[:5]:
            # Extract scores safely
            swe = model.get("benchmarks", {}).get("swe_bench", "N/A")
            price = model.get("pricing", {}).get("blended", "N/A")
            models_ui_data.append({
                "title": model.get("name", "Unknown Model"),
                "url": f"https://artificialanalysis.ai/models/{model.get('slug', '')}",
                "summary": f"SWE-Bench: {swe}% | Blended Price: ${price}/1M tokens",
                "source": "Artificial Analysis"
            })
        return models_ui_data
    except Exception as e:
        print(f"AA API Fetch failed: {e}")
        return []

# 2. Fetch News Feeds for Groq
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
    ],
    "community": [
        ("Reddit LocalLLaMA", "https://www.reddit.com/r/LocalLLaMA/top/.rss?t=day")
    ]
}

radar_payload = {
    "tailored": [], "telecom": [], "top_stories": [], 
    "cautionary": [], "community": []
}

for section, feeds in CATEGORIZED_FEEDS.items():
    for source_name, url in feeds:
        feed = feedparser.parse(url)
        # Top 2 from each source keeps the LLM prompt lean
        for e in feed.entries[:2]:
            radar_payload[section].append({
                "title": e.get("title", ""),
                "url": e.get("link", ""),
                "summary": e.get("description", "")[:200],
                "source": source_name
            })

# 3. Process News with Groq
prompt = """
You are an intelligence curator for a Data Scientist at Verizon specializing in MLOps, Agentic AI, and Local LLMs.
I am providing you with a JSON object containing articles pre-sorted by category. 

Filter out the noise and rewrite the summaries to be punchy and relevant to my Verizon/MLOps context.
- If a "telecom" article mentions Verizon, AT&T, or Agentic Networks, highlight that.
- If a "tailored" article mentions a tool useful for multi-agent systems, local GPUs, or GCP, explain why.

Return a JSON object with ONLY these 5 arrays: "tailored", "telecom", "top_stories", "cautionary", "community".
Format: {"tailored": [{"title": "...", "url": "...", "summary": "...", "source": "..."}], ...}
"""

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

# 4. Merge Data & Save
groq_data["models"] = fetch_live_scoreboard()

with open("data.json", "w") as f:
    json.dump(groq_data, f, indent=2)
    
print("✅ Radar synced successfully with Groq and Artificial Analysis!")