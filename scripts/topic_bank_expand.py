#!/usr/bin/env python3
"""Periodic topic bank expansion.

Goal:
- Run on a schedule (e.g. weekly) to expand an account's topic bank with concrete *titles*.
- This keeps daily autotopic selection cheap: daily run should NOT call LLM for brainstorming.

This script generates N titles in one LLM call and appends them to:
  config/topic_banks/<account_id>.json
under top-level key: "titles" (a de-duplicated list).

Usage:
  python -m scripts.topic_bank_expand mp_chaguan --count 50
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime


def _load_bank(path: str) -> dict:
    if not os.path.exists(path):
        return {"account_id": os.path.basename(path).replace('.json', ''), "banks": [], "titles": []}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f) or {}
    except Exception:
        return {"account_id": os.path.basename(path).replace('.json', ''), "banks": [], "titles": []}


def _uniq(xs: list[str]) -> list[str]:
    seen = set(); out = []
    for x in xs:
        x = (x or '').strip()
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('account_id')
    ap.add_argument('--count', type=int, default=50)
    args = ap.parse_args()

    from scripts.topic_banks import load_topic_bank, flatten_atoms, TOPIC_BANKS_DIR
    from scripts.article_service import load_account
    from scripts.llm import chat

    acc = load_account(args.account_id)
    ws = (acc.get('profile') or {}).get('writing_style') or {}

    bank_path = os.path.join(TOPIC_BANKS_DIR, f"{args.account_id}.json")
    bank = _load_bank(bank_path)
    atoms = flatten_atoms(load_topic_bank(args.account_id))

    platform = '公众号' if acc.get('platform') == 'wechat_mp' else '小红书'
    prompt = f"""你是一位{platform}内容创作者，请一次性生成 {args.count} 个高质量中文标题，用于本账号的长期选题库。\n\n账号定位：\n- 领域：{ws.get('domain','')}\n- 人设：{ws.get('persona','')}\n- 读者：{ws.get('audience','')}\n- 语气：{ws.get('tone','')}\n\n素材（只能当灵感，标题必须具体、有画面）：\n- 痛点：{(atoms.get('problems') or [])[:18]}\n- 场景：{(atoms.get('scenes') or [])[:18]}\n- 冲突：{(atoms.get('conflicts') or [])[:18]}\n- 动作：{(atoms.get('actions') or [])[:18]}\n\n格式要求：\n1) 每行一个标题，不要编号，不要解释\n2) 10-22字为主，口语化，有冲突\n3) 禁止空泛句（快节奏时代/不难发现/越来越…）\n\n请输出 {args.count} 个标题："""

    out = chat(prompt, temperature=0.9, max_tokens=1200)
    lines = []
    for l in out.splitlines():
        l = (l or '').strip().strip('-•')
        if not l:
            continue
        # remove numbering if any
        import re
        l = re.sub(r"^\(?\s*\d+\s*[\.、)]\s*", "", l).strip()
        if l:
            lines.append(l)

    existing = bank.get('titles') or []
    bank['titles'] = _uniq(existing + lines)
    bank['updated_at'] = datetime.now().isoformat()
    bank['titles_generated_at'] = datetime.now().isoformat()

    os.makedirs(os.path.dirname(bank_path), exist_ok=True)
    with open(bank_path, 'w', encoding='utf-8') as f:
        json.dump(bank, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        'ok': True,
        'account_id': args.account_id,
        'added': max(0, len(bank['titles']) - len(_uniq(existing))),
        'total_titles': len(bank['titles']),
        'path': bank_path,
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
