#!/usr/bin/env python3
"""Structured metrics/event logging (JSONL).

Goal: make it easy to distinguish:
- text LLM calls (scripts/llm.py)
- hunyuan image calls (scripts/image_gen.py)

Writes to data/metrics/YYYY-MM-DD.jsonl (gitignored).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _metrics_path() -> str:
    try:
        from scripts.gzh_store import ensure_dirs
        dirs = ensure_dirs()
        base = dirs["metrics"]
    except Exception:
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "metrics")
    os.makedirs(base, exist_ok=True)
    day = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(base, f"{day}.jsonl")


def log_event(event: str, payload: dict[str, Any] | None = None) -> None:
    rec = {
        "ts": _now_iso(),
        "event": event,
        "payload": payload or {},
    }
    try:
        with open(_metrics_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        # best-effort only
        return
