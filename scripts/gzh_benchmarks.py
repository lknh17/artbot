#!/usr/bin/env python3
"""GZH Benchmarks (爆款库): ingest user-provided URL/text/PDF and analyze into structured assets.

Principles:
- No active crawling.
- Web-first: called by web/app.py endpoints.
- Keep it simple and robust; analysis is best-effort.

Stores:
- data/gzh/benchmarks.jsonl
- data/gzh/benchmark_prompts.jsonl  (per category summarized prompt)
"""

from __future__ import annotations

import os
import re
import json
import urllib.request
from typing import Any

from scripts.llm import chat
from scripts.gzh_store import append_jsonl, ensure_dirs, make_id


def _paths() -> dict[str, str]:
    base = ensure_dirs()["gzh"]
    return {
        "benchmarks": os.path.join(base, "benchmarks.jsonl"),
        "prompts": os.path.join(base, "benchmark_prompts.jsonl"),
    }


def _strip_html(html: str) -> str:
    # very small/robust html strip (avoid extra deps)
    html = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    html = re.sub(r"<style[\s\S]*?</style>", " ", html, flags=re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def fetch_url_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        # best-effort encoding
        ct = (resp.headers.get("Content-Type") or "").lower()
        enc = "utf-8"
        m = re.search(r"charset=([\w\-]+)", ct)
        if m:
            enc = m.group(1)
        try:
            html = raw.decode(enc, errors="ignore")
        except Exception:
            html = raw.decode("utf-8", errors="ignore")
    return _strip_html(html)


def extract_pdf_text(file_path: str, max_pages: int = 30) -> str:
    from pypdf import PdfReader

    reader = PdfReader(file_path)
    parts: list[str] = []
    n = min(len(reader.pages), max_pages)
    for i in range(n):
        try:
            parts.append(reader.pages[i].extract_text() or "")
        except Exception:
            continue
    text = "\n".join(parts)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


ANALYZE_PROMPT = """你是一个‘公众号爆款文章拆解器’，我会给你一篇文章的正文（可能是从URL/PDF抽取的）。

请输出严格的 JSON（不要 markdown，不要解释），字段如下：
{
  \"title_guess\": \"\",
  \"category\": \"\",                  // 从以下主类中选1个：亲密关系/育儿/父母养老/情绪与自我修复/健康与生活方式/职场与成长/金钱与消费/社会热点解读/其他
  \"subtags\": [\"\"],                  // 0-5个
  \"tone\": [\"\"],                     // 0-5个：克制/煽情/冷幽默/强观点/故事体/反鸡汤/治愈/尖锐/理性/温柔 等
  \"structure\": [\"\"],                // 文章结构步骤列表（5-12条）
  \"viral_elements\": [\"\"],           // 爆款要素（5-12条，尽量具体）
  \"hook\": \"\",                      // 开头钩子（1-2句概括）
  \"payoff\": \"\",                    // 读者读完获得什么（1-2句）
  \"quotable_lines\": [\"\"],           // 可转发/金句（0-8条）
  \"writing_constraints_prompt\": \"\"  // 用于复刻该类爆款的‘写作约束prompt’，要求：1)列出开头/递进/动作建议/结尾的硬要求 2)语言风格约束 3)禁区（不要职场管理套话）
}

注意：
- 如果正文很杂/不完整，仍要给出‘最佳猜测’并保持 JSON 合法。
- writing_constraints_prompt 请用中文，口吻像写作SOP。

正文如下：
{{TEXT}}
"""


def analyze_benchmark(text: str) -> dict[str, Any]:
    prompt = ANALYZE_PROMPT.replace("{{TEXT}}", (text or "").strip()[:12000])
    out = chat(prompt, temperature=0.2, max_tokens=1400)
    # best-effort parse JSON
    try:
        data = json.loads(out)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    # fallback
    return {
        "title_guess": "",
        "category": "其他",
        "subtags": [],
        "tone": [],
        "structure": [],
        "viral_elements": [],
        "hook": "",
        "payoff": "",
        "quotable_lines": [],
        "writing_constraints_prompt": out.strip(),
    }


def add_benchmark(source: dict[str, Any], raw_text: str, analysis: dict[str, Any]) -> dict[str, Any]:
    paths = _paths()
    rec = {
        "id": make_id("bm", (analysis.get("title_guess") or "")[:40]),
        "created_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "source": source,
        "raw": {
            "text": (raw_text or "").strip()[:200000],
            "chars": len((raw_text or "")),
        },
        "analysis": analysis,
        "category": (analysis.get("category") or "其他").strip() or "其他",
    }
    append_jsonl(paths["benchmarks"], rec)
    return rec


def _load_latest_prompts() -> dict[str, dict[str, Any]]:
    paths = _paths()
    latest: dict[str, dict[str, Any]] = {}
    if not os.path.exists(paths["prompts"]):
        return latest
    with open(paths["prompts"], "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            cat = (obj.get("category") or "").strip()
            if not cat:
                continue
            latest[cat] = obj
    return latest


PROMPT_SUMMARY_PROMPT = """你是‘公众号爆款分类prompt沉淀器’。

我会给你：
- 分类名
- 该分类当前已沉淀的写作约束prompt（可能为空）
- 新入库的一篇爆款文章拆解信息（含结构/要素/约束prompt）

请输出：一个更新后的‘该分类写作约束prompt’（中文），要求：
1) 更像SOP，条目化，直接可用于写作
2) 综合老prompt与新样本，去重、补缺
3) 增加“禁区/不要写什么”段落（尤其禁止职场管理套话）
4) 不要提到“来自某篇文章”

只输出最终prompt文本，不要JSON。

分类：{category}

旧prompt：
{old}

新样本拆解：
{new}
"""


def update_category_prompt(category: str, analysis: dict[str, Any]) -> dict[str, Any]:
    category = (category or "其他").strip() or "其他"
    latest = _load_latest_prompts().get(category, {})
    old = (latest.get("prompt") or "").strip()
    new_stub = {
        "tone": analysis.get("tone") or [],
        "structure": analysis.get("structure") or [],
        "viral_elements": analysis.get("viral_elements") or [],
        "hook": analysis.get("hook") or "",
        "payoff": analysis.get("payoff") or "",
        "writing_constraints_prompt": analysis.get("writing_constraints_prompt") or "",
    }
    prompt = PROMPT_SUMMARY_PROMPT.format(category=category, old=old, new=json.dumps(new_stub, ensure_ascii=False, indent=2))
    merged = chat(prompt, temperature=0.2, max_tokens=900).strip()
    rec = {
        "id": make_id("bmp", category),
        "created_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "category": category,
        "prompt": merged,
        "sample_count_delta": 1,
    }
    append_jsonl(_paths()["prompts"], rec)
    return rec


def ingest_text(text: str, source: dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    analysis = analyze_benchmark(text)
    bm = add_benchmark(source=source, raw_text=text, analysis=analysis)
    p = update_category_prompt(bm.get("category"), analysis)
    return {"benchmark": bm, "category_prompt": p}


def ingest_url(url: str) -> dict[str, Any]:
    text = fetch_url_text(url)
    return ingest_text(text, source={"type": "url", "url": url})


def ingest_pdf(file_path: str, filename: str = "") -> dict[str, Any]:
    text = extract_pdf_text(file_path)
    return ingest_text(text, source={"type": "pdf", "filename": filename})
