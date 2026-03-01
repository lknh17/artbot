#!/usr/bin/env python3
"""GZH Topics (选题库): generate many candidate topics based on account profile + benchmark prompts.

Web-first: used by web/app.py.
"""

from __future__ import annotations

import json
from typing import Any

from scripts.llm import chat

CATEGORY_LIST = [
    "亲密关系",
    "育儿",
    "父母养老",
    "情绪与自我修复",
    "健康与生活方式",
    "职场与成长",
    "金钱与消费",
    "社会热点解读",
]


TOPIC_GEN_PROMPT = """你是一个公众号主编，负责为账号批量产出“可写成爆款”的选题。

## 账号信息
- 账号名：{name}
- 受众：{audience}
- 领域：{domain}
- 人设/简介：{persona}
- 语气：{tone}
- 标题风格：{title_style}

## 分类写作约束（来自爆款库沉淀，可能为空）
{category_prompts}

## 任务
请一次性生成 {count} 条【候选选题】，要求：
1) 覆盖尽量多的分类（优先覆盖：{categories}），避免同质化
2) 每条必须是“单主题可深挖”，能写出：场景→情绪命名→机制解释→3分钟动作→评论提问
3) 标题长度 10~18 字左右，克制但想点（好奇/刺痛/反差/画面感）
4) 避免管理套话（向上管理/复盘/绩效/背锅等）

## 输出格式
只输出严格 JSON（不要 markdown）：
{{
  "items": [
    {{"title": "", "category": "", "angle": "一句话角度/切入点", "pain": "一句话痛点"}},
    ...
  ]
}}
"""


def generate_topics(profile: dict[str, Any], category_prompts: dict[str, str], count: int = 80) -> list[dict[str, Any]]:
    name = profile.get("name") or ""
    audience = profile.get("audience") or ""
    domain = profile.get("domain") or ""
    persona = profile.get("persona") or ""
    tone = profile.get("tone") or ""
    title_style = (profile.get("title_config") or {}).get("style_desc") or ""

    cp_lines = []
    for cat in CATEGORY_LIST:
        p = (category_prompts.get(cat) or "").strip()
        if p:
            cp_lines.append(f"### {cat}\n{p}\n")
    category_prompts_text = "\n".join(cp_lines) if cp_lines else "（暂无沉淀，按账号风格与爆款结构常识生成）"

    prompt = TOPIC_GEN_PROMPT.format(
        name=name,
        audience=audience,
        domain=domain,
        persona=persona,
        tone=tone,
        title_style=title_style,
        category_prompts=category_prompts_text,
        count=int(count),
        categories="/".join(CATEGORY_LIST),
    )

    out = chat(prompt, temperature=0.6, max_tokens=1800)
    try:
        data = json.loads(out)
        items = data.get("items") or []
        if isinstance(items, list):
            cleaned = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                title = (it.get("title") or "").strip()
                cat = (it.get("category") or "").strip() or "其他"
                if not title:
                    continue
                cleaned.append({
                    "title": title,
                    "category": cat if cat in CATEGORY_LIST else "其他",
                    "angle": (it.get("angle") or "").strip(),
                    "pain": (it.get("pain") or "").strip(),
                })
            return cleaned
    except Exception:
        pass
    # fallback: treat as plain text list
    lines = [l.strip("-• ") for l in (out or "").splitlines() if l.strip()]
    return [{"title": l[:40], "category": "其他", "angle": "", "pain": ""} for l in lines[:count]]
