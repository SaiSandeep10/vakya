"""
V.A.K.Y.A — Voice Activated Knowledge Yantric Agent
Week 5 | mcp_servers/search_server.py

Web Search MCP Tool Server.
Uses DuckDuckGo — completely free, no API key needed.
Gives VAKYA access to current information beyond its training cutoff.

Requirements:
  pip install ddgs
"""

import json
import time
from datetime import datetime

from ddgs import DDGS

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────

MAX_RESULTS      = 5      # number of search results to fetch
MAX_BODY_CHARS   = 400    # max chars per result body to send to brain
SEARCH_TIMEOUT   = 10     # seconds before giving up


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────

def _summarise_results(results: list[dict], query: str) -> str:
    """
    Convert raw DuckDuckGo results into a clean summary string
    that the brain can read and turn into a spoken answer.
    """
    if not results:
        return f"No results found for '{query}'."

    lines = [f"Web search results for '{query}':\n"]
    for i, r in enumerate(results[:MAX_RESULTS], 1):
        title = r.get("title", "").strip()
        body  = r.get("body",  "").strip()[:MAX_BODY_CHARS]
        href  = r.get("href",  "").strip()

        if title:
            lines.append(f"{i}. {title}")
        if body:
            lines.append(f"   {body}")
        lines.append("")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# TOOL FUNCTIONS
# ──────────────────────────────────────────────

def web_search(query: str) -> dict:
    """
    Search the web using DuckDuckGo and return a summary.
    Use this for current events, news, scores, prices, or
    any information that may have changed recently.
    """
    query = query.strip()
    if not query:
        return {"success": False, "message": "Please provide a search query."}

    print(f"[Search] Searching: {query}")

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(
                query,
                max_results=MAX_RESULTS,
                timelimit=None,
            ))

        if not results:
            return {
                "success": False,
                "message": f"No results found for '{query}'. Try rephrasing the search."
            }

        summary = _summarise_results(results, query)
        print(f"[Search] Found {len(results)} results.")

        return {
            "success": True,
            "message": summary,
            "count":   len(results),
            "query":   query
        }

    except Exception as e:
        print(f"[Search] Error: {e}")
        return {
            "success": False,
            "message": f"Search failed. Please check your internet connection."
        }


def search_news(topic: str) -> dict:
    """
    Search for latest news on a topic.
    Use for breaking news, current events, sports scores, etc.
    """
    topic = topic.strip()
    if not topic:
        return {"success": False, "message": "Please provide a news topic."}

    print(f"[Search] News search: {topic}")

    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(
                topic,
                max_results=MAX_RESULTS,
            ))

        if not results:
            # Fall back to regular search
            return web_search(f"{topic} latest news")

        lines = [f"Latest news on '{topic}':\n"]
        for i, r in enumerate(results[:MAX_RESULTS], 1):
            title = r.get("title", "").strip()
            body  = r.get("body",  "").strip()[:MAX_BODY_CHARS]
            date  = r.get("date",  "").strip()[:10]

            if title:
                lines.append(f"{i}. [{date}] {title}")
            if body:
                lines.append(f"   {body}")
            lines.append("")

        summary = "\n".join(lines)
        print(f"[Search] Found {len(results)} news results.")

        return {
            "success": True,
            "message": summary,
            "count":   len(results),
            "topic":   topic
        }

    except Exception as e:
        print(f"[Search] News error: {e}")
        return web_search(f"{topic} latest news today")


def search_weather(location: str) -> dict:
    """
    Get current weather for a location by searching the web.
    location: city name e.g. 'Bangalore' or 'Mumbai'
    """
    location = location.strip()
    if not location:
        return {"success": False, "message": "Please provide a location for weather."}

    query = f"weather in {location} today temperature"
    print(f"[Search] Weather search: {query}")

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))

        if not results:
            return {"success": False, "message": f"Could not find weather for {location}."}

        summary = _summarise_results(results, query)
        return {
            "success":  True,
            "message":  summary,
            "location": location
        }

    except Exception as e:
        return {"success": False, "message": f"Weather search failed: {e}"}


def search_answer(question: str) -> dict:
    """
    Try to get a direct answer to a factual question.
    Best for: 'who is', 'what is', 'when did', 'how many' type questions.
    """
    question = question.strip()
    if not question:
        return {"success": False, "message": "Please provide a question."}

    print(f"[Search] Answer search: {question}")

    try:
        with DDGS() as ddgs:
            # Try instant answer first
            results = list(ddgs.answers(question))

        if results:
            answer = results[0].get("text", "").strip()
            if answer:
                return {
                    "success":  True,
                    "message":  answer,
                    "question": question
                }

        # Fall back to web search
        return web_search(question)

    except Exception as e:
        return web_search(question)


# ──────────────────────────────────────────────
# TOOL DEFINITIONS
# ──────────────────────────────────────────────

SEARCH_TOOLS = [
    {
        "name":        "web_search",
        "description": "Search the web for current information. Use when asked about recent events, news, sports scores, stock prices, or anything that may have changed recently.",
        "function":    web_search,
        "parameters":  {"query": str}
    },
    {
        "name":        "search_news",
        "description": "Search for the latest news on a topic. Use for breaking news, current events, IPL scores, election results, etc.",
        "function":    search_news,
        "parameters":  {"topic": str}
    },
    {
        "name":        "search_weather",
        "description": "Get current weather information for a city or location.",
        "function":    search_weather,
        "parameters":  {"location": str}
    },
    {
        "name":        "search_answer",
        "description": "Get a direct factual answer to a question. Best for who/what/when/how many questions.",
        "function":    search_answer,
        "parameters":  {"question": str}
    },
]


# ──────────────────────────────────────────────
# STANDALONE TEST
# Run: python mcp_servers/search_server.py
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("[TEST] Web Search Server\n")

    print("[TEST] General search:")
    result = web_search("latest AI news 2026")
    print(result["message"][:500])

    print("\n[TEST] News search:")
    result = search_news("IPL 2026")
    print(result["message"][:500])

    print("\n[TEST] Weather:")
    result = search_weather("Bangalore")
    print(result["message"][:500])

    print("\n[TEST] Direct answer:")
    result = search_answer("who is the prime minister of India")
    print(result["message"][:300])

    print("\n[TEST] Done.")