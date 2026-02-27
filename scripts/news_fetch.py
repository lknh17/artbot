#!/usr/bin/env python3
"""Lightweight news/hotspot fetcher.

We only need small, concrete facts to avoid "泛泛而谈":
- title / source url
- a short plaintext snippet (first ~1200 chars)

No heavy dependencies.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass


@dataclass
class FetchResult:
    url: str
    ok: bool
    status: int | None = None
    content_type: str | None = None
    text: str = ""
    error: str | None = None
    fetched_at: str | None = None


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    s = html
    # remove scripts/styles
    s = re.sub(r"<script[\s\S]*?</script>", " ", s, flags=re.I)
    s = re.sub(r"<style[\s\S]*?</style>", " ", s, flags=re.I)
    s = _TAG_RE.sub(" ", s)
    s = s.replace("&nbsp;", " ")
    s = s.replace("&amp;", "&")
    s = s.replace("&lt;", "<").replace("&gt;", ">")
    s = s.replace("&quot;", '"').replace("&#39;", "'")
    s = _WS_RE.sub(" ", s).strip()
    return s


def fetch_url_text(url: str, max_chars: int = 1200, timeout: int = 8) -> FetchResult:
    url = (url or "").strip()
    if not url:
        return FetchResult(url=url, ok=False, error="empty url")

    try:
        import requests

        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        r = requests.get(url, headers=headers, timeout=timeout)
        ct = r.headers.get("Content-Type", "")
        text = r.text or ""
        if "text/html" in ct or text.lstrip().startswith("<"):
            text = _strip_html(text)
        text = text[:max_chars]

        return FetchResult(
            url=url,
            ok=bool(r.ok),
            status=r.status_code,
            content_type=ct,
            text=text,
            fetched_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        )
    except Exception as e:
        return FetchResult(url=url, ok=False, error=str(e), fetched_at=time.strftime("%Y-%m-%dT%H:%M:%S%z"))
