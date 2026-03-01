#!/usr/bin/env python3
"""GZH data stores (JSONL) for 4-stage pipeline.

All "libraries" live under data/ (gitignored by default):
- inspirations.jsonl
- topics.jsonl
- drafts.jsonl
- published.jsonl

This module intentionally keeps dependencies minimal.
"""

from __future__ import annotations

import json
import os
import time
import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _project_root() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def _data_dir() -> str:
    try:
        from scripts.config import get
        d = get("data_dir", None)
        if d:
            return d
    except Exception:
        pass
    return os.path.join(_project_root(), "data")


def ensure_dirs() -> dict[str, str]:
    base = _data_dir()
    gzh = os.path.join(base, "gzh")
    metrics = os.path.join(base, "metrics")
    os.makedirs(gzh, exist_ok=True)
    os.makedirs(metrics, exist_ok=True)
    return {"data": base, "gzh": gzh, "metrics": metrics}


def _path(kind: str) -> str:
    d = ensure_dirs()["gzh"]
    name = {
        "inspirations": "inspirations.jsonl",
        "topics": "topics.jsonl",
        "drafts": "drafts.jsonl",
        "published": "published.jsonl",
    }.get(kind)
    if not name:
        raise ValueError(f"unknown kind: {kind}")
    return os.path.join(d, name)


def make_id(prefix: str, content: str = "") -> str:
    seed = f"{prefix}|{time.time()}|{os.getpid()}|{content}".encode("utf-8")
    h = hashlib.sha1(seed).hexdigest()[:12]
    return f"{prefix}_{h}"


def append_jsonl(path: str, obj: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    line = json.dumps(obj, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def iter_jsonl(path: str, limit: int | None = None) -> Iterable[dict[str, Any]]:
    if not os.path.exists(path):
        return
    n = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue
            n += 1
            if limit and n >= limit:
                return


# -----------------
# Store operations
# -----------------

def add_inspiration(text: str, source: dict | None = None, tags: list[str] | None = None) -> dict:
    rec = {
        "id": make_id("insp", text[:40]),
        "created_at": _now_iso(),
        "text": (text or "").strip(),
        "source": source or {"type": "manual"},
        "tags": tags or [],
        "status": "new",
    }
    append_jsonl(_path("inspirations"), rec)
    return rec


def add_topic_candidate(account_id: str, title: str, category: str, source: str = "", original_title: str = "", url: str = "", date: str | None = None, extra: dict | None = None) -> dict:
    rec = {
        "id": make_id("topic", f"{account_id}|{title}"),
        "created_at": _now_iso(),
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "account_id": account_id,
        "platform": "wechat_mp",
        "title": (title or "").strip(),
        "category": category,
        "source": source,
        "original_title": (original_title or "").strip(),
        "url": (url or "").strip(),
        "rank": None,
    }
    if isinstance(extra, dict) and extra:
        rec.update(extra)
    append_jsonl(_path("topics"), rec)
    return rec


def add_draft(account_id: str, topic_title: str, article: dict, topic_id: str = "", outputs: dict | None = None, metrics: dict | None = None, dedup: dict | None = None, status: str = "draft") -> dict:
    rec = {
        "id": make_id("draft", f"{account_id}|{topic_title}|{article.get('title','')}"),
        "created_at": _now_iso(),
        "account_id": account_id,
        "topic_id": topic_id,
        "topic_title": (topic_title or "").strip(),
        "status": status,
        "article": article,
        "outputs": outputs or {},
        "metrics": metrics or {},
        "dedup": dedup or {},
    }
    append_jsonl(_path("drafts"), rec)
    return rec


def add_published(account_id: str, title: str, wechat: dict | None = None, source: dict | None = None, metrics: dict | None = None) -> dict:
    rec = {
        "id": make_id("pub", f"{account_id}|{title}"),
        "created_at": _now_iso(),
        "account_id": account_id,
        "title": (title or "").strip(),
        "wechat": wechat or {},
        "source": source or {},
        "metrics": metrics or {},
    }
    append_jsonl(_path("published"), rec)
    return rec


def load_recent(kind: str, limit: int = 200) -> list[dict[str, Any]]:
    path = _path(kind)
    # read all then keep tail (JSONL tail read without indexing is OK for small sizes)
    rows = list(iter_jsonl(path, limit=None))
    return rows[-limit:]
