#!/usr/bin/env python3
"""Tavily search integration.

Used to enrich hotspot-based articles with concrete facts.

Env:
- TAVILY_API_KEY

API: https://docs.tavily.com/
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass


@dataclass
class TavilyResult:
    ok: bool
    query: str
    results: list
    error: str | None = None
    searched_at: str | None = None


def tavily_search(query: str, max_results: int = 5, timeout: int = 12) -> TavilyResult:
    q = (query or "").strip()
    if not q:
        return TavilyResult(ok=False, query=q, results=[], error="empty query")

    api_key = (os.getenv("TAVILY_API_KEY") or "").strip()
    if not api_key:
        return TavilyResult(ok=False, query=q, results=[], error="missing TAVILY_API_KEY")

    try:
        import requests

        payload = {
            "api_key": api_key,
            "query": q,
            "max_results": int(max_results),
            # request some raw content when available; Tavily may return 'content'
            "include_answer": False,
            "include_raw_content": False,
            "search_depth": "basic",
        }
        r = requests.post("https://api.tavily.com/search", json=payload, timeout=timeout)
        if not r.ok:
            return TavilyResult(ok=False, query=q, results=[], error=f"HTTP {r.status_code}: {r.text[:300]}")
        data = r.json() or {}
        results = data.get("results") or []
        # normalize
        norm = []
        for it in results[:max_results]:
            norm.append({
                "title": it.get("title", ""),
                "url": it.get("url", ""),
                "content": it.get("content", ""),
                "score": it.get("score", None),
            })
        return TavilyResult(ok=True, query=q, results=norm, searched_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
    except Exception as e:
        return TavilyResult(ok=False, query=q, results=[], error=str(e), searched_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
