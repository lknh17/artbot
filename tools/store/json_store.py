#!/usr/bin/env python3
"""Tiny JSON file store with atomic writes.

Purpose
- Keep artbot lightweight (no DB required for Phase 1)
- Provide a single place for load/save patterns (easy to swap to SQLite later)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict


def load_json(path: str, default: Any) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
