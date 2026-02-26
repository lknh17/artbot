#!/usr/bin/env python3
"""
自我生成类选题 — 辅助模块

提供 prompt 构建和历史去重，实际 AI 调用由 agent 层完成。
"""
import json
import os
from datetime import datetime

ARTBOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(ARTBOT_DIR, "output", "title_history.json")


def load_title_history(account_id: str) -> list:
    """加载某账号的历史标题列表"""
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE) as f:
            data = json.load(f)
        return data.get(account_id, [])
    except Exception:
        return []


def save_title_to_history(account_id: str, title: str, category: str = "self"):
    """记录一个标题到历史"""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    data = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f:
                data = json.load(f)
        except Exception:
            data = {}

    if account_id not in data:
        data[account_id] = []

    data[account_id].append({
        "title": title,
        "category": category,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "created_at": datetime.now().isoformat(),
    })

    # Keep last 200 per account
    data[account_id] = data[account_id][-200:]

    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def build_self_title_prompt(account: dict, count: int = 3) -> str:
    """构建自我生成类标题的 prompt（不依赖热点）"""
    profile = account.get("profile", {})
    ws = profile.get("writing_style", {})
    tc = profile.get("title_config", {})

    domain = ws.get("domain", "通用")
    persona = ws.get("persona", "")
    audience = ws.get("audience", "")
    tone = ws.get("tone", "")
    title_style = tc.get("style_desc", "")

    # Load writing style reference articles for vibe
    ref_id = ws.get("reference", "")
    ref_snippets = ""
    if ref_id:
        from scripts.article_service import _load_writing_style_articles
        articles = _load_writing_style_articles(ref_id)
        if articles:
            # Extract just first lines as title-vibe reference
            for art in articles[:3]:
                first_line = art.strip().split("\n")[0][:80]
                ref_snippets += f"- {first_line}\n"

    # Load history to avoid repeats
    history = load_title_history(account.get("id", ""))
    recent_titles = [h["title"] for h in history[-30:]]
    history_text = "\n".join(f"- {t}" for t in recent_titles[-15:]) if recent_titles else "（暂无历史）"

    platform = "公众号" if account.get("platform") == "wechat_mp" else "小红书"

    prompt = f"""你是一位{platform}内容创作者，请根据账号定位自主生成 {count} 个文章标题。

## 账号定位
- 领域：{domain}
- 人设：{persona}
- 目标读者：{audience}
- 语气风格：{tone}
{f'- 标题风格要求：{title_style}' if title_style else ''}

{f'## 风格参考（标题氛围参考）' + chr(10) + ref_snippets if ref_snippets else ''}

## 近期已用标题（不要重复或过于相似）
{history_text}

## 要求
1. 标题必须和账号的领域定位相关，但不依赖任何热点新闻
2. 每个标题要有独立的主题和切入角度
3. 标题风格要统一，符合账号调性
4. 不要和近期已用标题重复或过于相似
5. 直接输出标题，每行一个，不要编号，不要解释

请输出 {count} 个标题："""

    return prompt
