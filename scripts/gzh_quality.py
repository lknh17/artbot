#!/usr/bin/env python3
"""Quality checks & optional auto-rewrite for GZH articles."""

from __future__ import annotations

import re
from typing import Any


def heuristic_score(article: dict[str, Any]) -> tuple[float, dict]:
    """Return (score 0..1, details). Cheap heuristics only."""
    title = (article.get("title") or "").strip()
    digest = (article.get("digest") or "").strip()
    subtitle = (article.get("subtitle") or "").strip()
    sections = article.get("sections") or []

    details: dict[str, Any] = {}
    score = 0.0

    # Title
    if 10 <= len(title) <= 32:
        score += 0.12
    elif title:
        score += 0.06
    details["title_len"] = len(title)

    # Digest
    if 10 <= len(digest) <= 40:
        score += 0.06
    elif digest:
        score += 0.03

    # Subtitle hook
    if 12 <= len(subtitle) <= 80:
        score += 0.08
    elif subtitle:
        score += 0.04

    # Sections count
    sc = len(sections) if isinstance(sections, list) else 0
    details["sections"] = sc
    if 4 <= sc <= 6:
        score += 0.18
    elif 3 <= sc <= 8:
        score += 0.10

    # Paragraph density
    para_ok = 0
    total_paras = 0
    for sec in sections if isinstance(sections, list) else []:
        paras = (sec or {}).get("paragraphs") if isinstance(sec, dict) else []
        if not isinstance(paras, list):
            continue
        total_paras += len(paras)
        if len(paras) >= 3:
            para_ok += 1
    details["total_paragraphs"] = total_paras
    if sc and para_ok / max(1, sc) >= 0.75:
        score += 0.20
    elif para_ok >= 2:
        score += 0.12

    # Ending: action + question
    last_text = ""
    try:
        if sections and isinstance(sections, list):
            last = sections[-1]
            paras = (last or {}).get("paragraphs") if isinstance(last, dict) else []
            if isinstance(paras, list) and paras:
                last_text = "\n".join([p for p in paras if isinstance(p, str)])
    except Exception:
        last_text = ""

    has_q = "？" in last_text or "?" in last_text
    has_action = any(k in last_text for k in ["今晚", "现在", "立刻", "今天", "做一次", "试着", "写下", "给自己", "3分钟", "30秒"])
    details["ending_has_question"] = has_q
    details["ending_has_action"] = has_action
    if has_q and has_action:
        score += 0.16
    elif has_q or has_action:
        score += 0.10

    # Anti-generic penalty
    generic_phrases = ["快节奏时代", "不难发现", "越来越", "在当下", "我们都知道"]
    penalty = 0.0
    blob = (subtitle + "\n" + "\n".join([str(s.get('title','')) for s in sections if isinstance(s, dict)]))
    for p in generic_phrases:
        if p in blob:
            penalty += 0.04
    score = max(0.0, min(1.0, score - penalty))
    details["generic_penalty"] = penalty

    return score, details


def llm_self_check_prompt(article: dict[str, Any]) -> str:
    """Optional: ask LLM to score and point out concrete issues (JSON output)."""
    title = (article.get("title") or "").strip()
    digest = (article.get("digest") or "").strip()
    subtitle = (article.get("subtitle") or "").strip()
    sections = article.get("sections") or []

    # Keep prompt size controlled: only include first 2 paragraphs per section
    sec_lines = []
    for i, sec in enumerate(sections[:7], 1):
        if not isinstance(sec, dict):
            continue
        st = (sec.get("title") or "").strip()
        paras = sec.get("paragraphs") or []
        paras2 = [p.strip() for p in paras[:2] if isinstance(p, str) and p.strip()]
        sec_lines.append(f"{i}. {st}\n" + "\n".join([f"- {p}" for p in paras2]))

    body = "\n\n".join(sec_lines)

    return f"""你是公众号内容质检官。请对这篇文章做质量自检，并给出可执行修改建议。

必须输出严格 JSON（不要 Markdown/不要解释/不要多余文字）：

{{
  "score": 0.0,
  "issues": ["..."],
  "rewrite_strategy": "..."
}}

评分标准（0~1）：
- 单主题深挖、观点清晰、读者能带走一个洞见/练习
- 结构清晰，段落不糊
- 不套用泛化职场管理模板（除非主题就是管理）
- 结尾有行动+提问

文章如下：
标题：{title}
摘要：{digest}
引言：{subtitle}
正文：
{body}
"""


def rewrite_prompt(topic: str, issues: list[str], strategy: str) -> str:
    """Ask LLM to rewrite the whole article, single-topic deep dive."""
    issues_text = "\n".join([f"- {x}" for x in (issues or [])[:12]])
    return f"""请根据以下问题清单，重写一篇公众号文章。要求：单主题深挖，不要套用通用职场管理模板；语言口语、有画面；结构清晰；结尾必须包含一个3分钟内可完成的小练习+一个问题引导评论。

主题：{topic}

需要修复的问题：
{issues_text if issues_text else '（无）'}

重写策略：{strategy or '围绕一个核心洞见递进展开'}

必须严格输出可解析 JSON（不要 Markdown/不要解释/不要多余文字），格式：
{{
  "title": "...",
  "digest": "...",
  "subtitle": "...",
  "sections": [{{"title": "...", "paragraphs": ["...", "..."]}}]
}}
"""