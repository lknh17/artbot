#!/usr/bin/env python3
"""Similarity & de-dup utilities (cheap, no embeddings).

We use a character 2-gram Jaccard similarity which works reasonably for Chinese titles.
"""

from __future__ import annotations

import re
from typing import Iterable


def _normalize(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", "", s)
    # remove common punctuation/brackets
    s = re.sub(r"[\[\]（）()【】《》<>“”\"'‘’：:，,。.!！？?；;—\-_·]", "", s)
    return s


def _ngrams(s: str, n: int = 2) -> set[str]:
    s = _normalize(s)
    if not s:
        return set()
    if len(s) <= n:
        return {s}
    return {s[i:i+n] for i in range(0, len(s) - n + 1)}


def jaccard(a: str, b: str, n: int = 2) -> float:
    A = _ngrams(a, n=n)
    B = _ngrams(b, n=n)
    if not A or not B:
        return 0.0
    inter = len(A & B)
    union = len(A | B)
    return inter / union if union else 0.0


def nearest(text: str, candidates: Iterable[dict], text_key: str = "title") -> tuple[float, dict | None]:
    best = 0.0
    best_item = None
    for it in candidates:
        t2 = (it.get(text_key) or "") if isinstance(it, dict) else ""
        s = jaccard(text, t2)
        if s > best:
            best = s
            best_item = it
    return best, best_item
