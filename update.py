import os
import json
import feedparser
from groq import Groq

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Sources
FEEDS = [
    ("Simon Willison", "https://simonwillison.net/atom/entries/"),
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("OWASP GenAI", "https://genai.owasp.org/feed/")
]

articles = []
for source_name, url in FEEDS:
    feed = feedparser.parse(url)
    for e in feed.entries[:3]:
        articles.append({
            "title": e.title, 
            "url": e.link, 
            "summary": e.get("description", "")[:200], 
            "source": source_name
        })

prompt = """
Review these AI articles. Categorize them into a strict JSON object with these exact arrays:
1. "tailored": MLOps, local LLMs, agentic orchestration, telecommunications.
2. "top_stories": Major AI model releases or industry news.
3. "cautionary": AI security failures or prompt injection.
Discard fluff. 
Format: {"tailored": [{"title": "...", "url": "...", "summary": "...", "source": "..."}], "top_stories": [...], "cautionary": [...]}
"""

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(articles)}
    ],
    response_format={"type": "json_object"},
    temperature=0.1
)

with open("data.json", "w") as f:
    f.write(response.choices[0].message.content)