#!/usr/bin/env python3
"""Topic banks loader.

Each account may have a topic bank file at:
- config/topic_banks/<account_id>.json

The bank is used to generate *specific* non-hot topics (pain points + scenes + conflicts + actions),
so the writing won't become generic.
"""

from __future__ import annotations

import json
import os

ARTBOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOPIC_BANKS_DIR = os.path.join(ARTBOT_DIR, "config", "topic_banks")


def load_topic_bank(account_id: str) -> dict:
    account_id = (account_id or "").strip()
    if not account_id:
        return {"account_id": "", "banks": []}
    path = os.path.join(TOPIC_BANKS_DIR, f"{account_id}.json")
    if not os.path.exists(path):
        return {"account_id": account_id, "banks": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {"account_id": account_id, "banks": []}
    except Exception:
        return {"account_id": account_id, "banks": []}


def flatten_atoms(bank: dict) -> dict:
    """Flatten bank atoms into lists for prompt feeding."""
    banks = bank.get("banks") or []
    problems, scenes, conflicts, actions = [], [], [], []
    for b in banks:
        problems += (b.get("problems") or [])
        scenes += (b.get("scenes") or [])
        conflicts += (b.get("conflicts") or [])
        actions += (b.get("actions") or [])
    # de-dup keep order
    def _uniq(xs):
        seen = set(); out=[]
        for x in xs:
            x=(x or "").strip()
            if not x or x in seen: continue
            seen.add(x); out.append(x)
        return out
    return {
        "problems": _uniq(problems)[:80],
        "scenes": _uniq(scenes)[:80],
        "conflicts": _uniq(conflicts)[:80],
        "actions": _uniq(actions)[:80],
    }
