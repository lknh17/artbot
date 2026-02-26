#!/usr/bin/env python3
"""
统一文章生成服务

三条路径统一入口：
1. Jobs 页面手动触发
2. 自动选题 - 自动模式（直接生成）
3. 自动选题 - 人工确认模式（选定标题后生成）

本模块负责：
- 构建 prompt（基于账号 profile）
- 调用 AI 生成文章内容
- 调用排版渲染
- 保存到 output 目录
- 返回结果（标题、预览链接等）

注意：实际的 AI 调用由外部完成（OpenClaw agent），
本模块生成结构化的任务描述和 prompt，供 agent 执行。
"""
import json
import os
import re
import time
from datetime import datetime

ARTBOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ARTBOT_DIR, "output")
ACCOUNTS_FILE = os.path.join(ARTBOT_DIR, "config", "accounts.json")


def load_account(account_id: str) -> dict:
    """加载账号配置"""
    with open(ACCOUNTS_FILE) as f:
        accounts = json.load(f).get("accounts", [])
    acc = next((a for a in accounts if a.get("id") == account_id), None)
    if not acc:
        raise ValueError(f"账号不存在: {account_id}")
    return acc


def _load_writing_style(style_id: str) -> dict:
    """Load a writing style by id, returns dict with 'description' and/or 'articles'"""
    styles_file = os.path.join(ARTBOT_DIR, "config", "writing_styles.json")
    if not os.path.exists(styles_file):
        return {}
    try:
        with open(styles_file) as f:
            data = json.load(f)
        ws = next((s for s in data.get("styles", []) if s.get("id") == style_id), None)
        return ws or {}
    except Exception:
        return {}


def _load_writing_style_articles(style_id: str) -> list:
    """Load reference articles for a writing style (legacy compat)"""
    ws = _load_writing_style(style_id)
    return ws.get("articles", [])


HOTSPOT_RATIO_DESC = {
    "hot_dominant": "标题以热点事件为主（约70%），融入账号视角（约30%）",
    "balanced": "标题均衡融合热点事件和账号自身视角（各约50%）",
    "self_dominant": "标题以账号自身视角为主（约70%），热点仅作为切入点（约30%）",
    "self_only": "标题完全从账号自身视角出发，热点仅作为创作灵感，标题中不直接体现热点",
}


def build_title_prompt(account: dict, keyword: str, source_platform: str = "") -> str:
    """构建标题生成 prompt"""
    profile = account.get("profile", {})
    style = profile.get("writing_style", {})
    tc = profile.get("title_config", {})
    platform = "公众号" if account.get("platform") == "wechat_mp" else "小红书"

    domain = style.get("domain", "通用")
    persona = style.get("persona", "")
    audience = style.get("audience", "")

    style_desc = tc.get("style_desc", "")
    ratio = HOTSPOT_RATIO_DESC.get(tc.get("hotspot_ratio", "balanced"),
                                    HOTSPOT_RATIO_DESC["balanced"])
    extra = tc.get("extra", "")

    prompt = f"""为以下热点主题生成{platform}文章标题。

热点主题：{keyword}
{f'热点来源：{source_platform}' if source_platform else ''}

## 账号定位
- 领域：{domain}
- 人设：{persona}
- 受众：{audience}

## 标题风格要求
{style_desc if style_desc else '（未指定，请根据账号定位自由发挥）'}

## 热点融合策略
{ratio}

{f'## 额外约束' + chr(10) + extra if extra else ''}

请生成 3 个候选标题，每个标题换行输出，不要编号。"""

    return prompt


def build_article_prompt(account: dict, keyword: str, extra_prompt: str = "",
                         search_context: str = "") -> str:
    """构建文章生成 prompt"""
    profile = account.get("profile", {})
    style = profile.get("writing_style", {})
    platform = "公众号" if account.get("platform") == "wechat_mp" else "小红书"

    domain = style.get("domain", "通用")
    persona = style.get("persona", "")
    audience = style.get("audience", "")
    tone = style.get("tone", "真诚分享")
    keywords = style.get("keywords", [])
    if isinstance(keywords, list):
        keywords = "、".join(keywords)
    reference = style.get("reference", "")
    extra_inst = style.get("extra_instructions", "")

    prompt = f"""你是一位{platform}内容创作者。

## 账号定位
- 领域：{domain}
- 人设：{persona}
- 受众：{audience}
- 语气：{tone}
- 调性关键词：{keywords}
{f'- 风格参考：{reference}' if reference else ''}

## 任务
请根据以下主题，创作一篇高质量{platform}文章。

主题/关键词：{keyword}
{f'背景资料：{search_context}' if search_context else ''}
{f'额外要求：{extra_prompt}' if extra_prompt else ''}

## 输出格式要求
请严格按以下 JSON 格式输出（不要输出其他内容）：

```json
{{
  "title": "文章标题",
  "digest": "一句话摘要（30字以内）",
  "subtitle": "开头引言/副标题",
  "sections": [
    {{
      "title": "段落标题",
      "paragraphs": ["段落1", "段落2", ...]
    }},
    ...
  ]
}}
```

## 写作要求
1. 标题要有吸引力和点击欲
2. 内容有深度、有观点、有价值
3. 结构清晰，分3-5个段落
4. 符合{platform}平台的内容规范
5. 最后一段可以是总结/感悟/呼吁
{f'6. {extra_inst}' if extra_inst else ''}"""

    # Append style description or reference articles
    if reference:
        ws = _load_writing_style(reference)
        style_desc_text = ws.get("description", "")
        ref_articles = ws.get("articles", [])
        if style_desc_text:
            prompt += "\n\n## 写作风格指南\n请严格按照以下风格要求来写作：\n\n"
            prompt += style_desc_text[:5000]  # Limit length
            prompt += "\n"
        elif ref_articles:
            prompt += "\n\n## 风格参考（仅参考语言风格和文章结构，不要抄袭内容）\n"
            prompt += "以下是该风格的参考文章，请学习其语言特点、行文节奏、段落结构和表达方式：\n\n"
            for i, art in enumerate(ref_articles[:5], 1):
                snippet = art[:1500] if len(art) > 1500 else art
                prompt += f"--- 参考文章 {i} ---\n{snippet}\n\n"
            prompt += "⚠️ 注意：仅参考上述文章的写作风格（语气、节奏、结构），内容必须围绕给定主题原创。\n"

    return prompt


def build_cover_prompt(account: dict, title: str, digest: str) -> str:
    """构建封面图 prompt"""
    profile = account.get("profile", {})
    img = profile.get("image", {})
    platform = "公众号" if account.get("platform") == "wechat_mp" else "小红书"
    ratio = "3:4竖版" if account.get("platform") == "xhs" else "16:9横版"
    extra = img.get("cover_prompt", "")

    prompt = f"为文章生成封面图。标题：{title}。摘要：{digest}。"
    prompt += f" 要求：基于文章语义，视觉吸引力强，适合{platform}信息流，{ratio}比例。"
    if extra:
        prompt += f" 风格：{extra}"
    return prompt


def build_inline_prompt(account: dict, title: str, section_title: str,
                        section_summary: str) -> str:
    """构建插图 prompt"""
    profile = account.get("profile", {})
    img = profile.get("image", {})
    extra = img.get("inline_prompt", "")

    prompt = f"为文章段落生成配图。文章：{title}。段落：{section_title}。"
    prompt += f" 内容概要：{section_summary}。"
    prompt += " 要求：与段落语义强相关，视觉吸引力强，1024x1024。"
    if extra:
        prompt += f" 风格：{extra}"
    return prompt


def make_output_dir(account_id: str) -> str:
    """创建输出目录，自动编号避免冲突"""
    date_str = datetime.now().strftime("%Y%m%d")
    base = f"{account_id}_{date_str}"

    # Find next available number
    existing = [d for d in os.listdir(OUTPUT_DIR) if d.startswith(base) and os.path.isdir(os.path.join(OUTPUT_DIR, d))]
    num = len(existing) + 1
    dirname = f"{base}_{num:02d}"
    path = os.path.join(OUTPUT_DIR, dirname)
    os.makedirs(path, exist_ok=True)
    return dirname, path


def save_article(account_id: str, article_data: dict, theme: str = None,
                 source_topic: str = "", source_platform: str = "") -> dict:
    """保存文章并渲染 HTML

    Args:
        account_id: 账号ID
        article_data: {"title", "digest", "subtitle", "sections"}
        theme: 排版主题
        source_topic: 来源热点
        source_platform: 来源平台

    Returns: {"dirname", "html_path", "json_path", "preview_url", "title"}
    """
    from scripts.html_renderer import render_article

    acc = load_account(account_id)
    profile = acc.get("profile", {})
    if not theme:
        theme = profile.get("layout_style_id", "snow-cold")

    dirname, outpath = make_output_dir(account_id)

    # Render HTML
    html = render_article(
        title=article_data["title"],
        subtitle=article_data.get("subtitle", ""),
        sections=article_data.get("sections", []),
        theme=theme,
    )

    html_path = os.path.join(outpath, "article.html")
    with open(html_path, "w") as f:
        f.write(html)

    # Save metadata
    meta = {
        **article_data,
        "theme": theme,
        "account_id": account_id,
        "source_topic": source_topic,
        "source_platform": source_platform,
        "created_at": datetime.now().isoformat(),
    }
    json_path = os.path.join(outpath, "article.json")
    with open(json_path, "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {
        "dirname": dirname,
        "html_path": html_path,
        "json_path": json_path,
        "preview_url": f"/art/api/preview/{dirname}",
        "title": article_data["title"],
        "digest": article_data.get("digest", ""),
    }


def create_generation_task(account_id: str, keyword: str, theme: str = None,
                           num_images: int = 2, extra_prompt: str = "",
                           push_to_draft: bool = False,
                           source: str = "manual",
                           source_platform: str = "") -> dict:
    """创建文章生成任务（统一入口）

    三条路径都调用此函数：
    1. Jobs手动 → source="manual"
    2. 自动选题自动模式 → source="autotopic_auto"
    3. 自动选题人工确认 → source="autotopic_manual"

    Returns: 任务描述 dict，包含所有 prompt 和元数据
    """
    acc = load_account(account_id)
    profile = acc.get("profile", {})
    img = profile.get("image", {})

    if not theme:
        theme = profile.get("layout_style_id", "snow-cold")

    task = {
        "task_id": f"{account_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "account_id": account_id,
        "account_name": acc.get("name", ""),
        "platform": acc.get("platform", ""),
        "keyword": keyword,
        "theme": theme,
        "num_images": num_images,
        "push_to_draft": push_to_draft,
        "source": source,
        "source_platform": source_platform,
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        # Prompts
        "title_prompt": build_title_prompt(acc, keyword, source_platform),
        "article_prompt": build_article_prompt(acc, keyword, extra_prompt),
        "cover_prompt_template": build_cover_prompt(acc, "{title}", "{digest}"),
        "inline_prompt_template": build_inline_prompt(acc, "{title}", "{section_title}", "{section_summary}"),
        "inline_count": img.get("inline_count", num_images),
    }

    # Save task file
    task_file = os.path.join(OUTPUT_DIR, "pending_tasks.json")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Append to task queue
    tasks = []
    if os.path.exists(task_file):
        try:
            with open(task_file) as f:
                tasks = json.load(f)
        except Exception:
            tasks = []

    tasks.append(task)
    with open(task_file, "w") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

    return task


def execute_generation_task(task: dict) -> dict:
    """执行一个生成任务：AI写文章 → 保存 → 生图 → 排版HTML

    Returns: updated task dict with status="done" and output paths
    """
    import re as _re
    from scripts.llm import chat
    from scripts.pipeline import execute_pipeline

    account_id = task["account_id"]
    keyword = task["keyword"]
    task_id = task["task_id"]

    # 1. AI 生成文章
    article_prompt = task.get("article_prompt", "")
    if not article_prompt:
        acc = load_account(account_id)
        article_prompt = build_article_prompt(acc, keyword)

    raw = chat(article_prompt, model="moonshot-v1-32k", temperature=0.7, max_tokens=3000)
    m = _re.search(r'\{.*\}', raw, _re.DOTALL)
    if not m:
        task["status"] = "error"
        task["error"] = "AI 返回无法解析的内容"
        _update_task_status(task)
        return task

    article_data = json.loads(m.group())
    title = article_data.get("title", keyword)
    digest = article_data.get("digest", "")
    subtitle = article_data.get("subtitle", "")
    sections = article_data.get("sections", [])

    # 2. Save article
    result = save_article(account_id, article_data, keyword, task.get("source_platform", ""))
    dirname = result["dirname"]
    output_dir = os.path.join(OUTPUT_DIR, dirname)

    # 3. Run pipeline (images + HTML)
    acc = load_account(account_id)
    profile = acc.get("profile", {})
    img_cfg = profile.get("image", {})
    theme = task.get("theme", profile.get("layout_style_id", "snow-cold"))

    cover_prompt = task.get("cover_prompt_template", "").replace("{title}", title).replace("{digest}", digest)
    style_prefix = img_cfg.get("cover_prompt", "")
    inline_style = img_cfg.get("inline_prompt", "")
    inline_count = task.get("inline_count", img_cfg.get("inline_count", 2))

    try:
        cred = (acc.get("credentials") or {})
        pip_result = execute_pipeline(
            title=title, digest=digest, subtitle=subtitle, sections=sections,
            cover_prompt=cover_prompt, theme=theme, push_draft=task.get("push_to_draft", False),
            style_prefix=style_prefix or None,
            inline_count=inline_count,
            inline_prompt_extra=inline_style or None,
            output_dir_override=output_dir,
            wechat_appid=cred.get("appid"),
            wechat_secret=cred.get("secret"),
        )
        task["status"] = "done"
        task["dirname"] = dirname
        task["title"] = title
        task["preview_url"] = f"/art/api/preview/{dirname}"
        task["images"] = len(pip_result.get("images", []))
        task["done_at"] = datetime.now().isoformat()
    except Exception as e:
        task["status"] = "error"
        task["error"] = str(e)

    _update_task_status(task)
    return task


def _update_task_status(task: dict):
    """Update a task's status in pending_tasks.json"""
    task_file = os.path.join(OUTPUT_DIR, "pending_tasks.json")
    tasks = []
    if os.path.exists(task_file):
        try:
            with open(task_file) as f:
                tasks = json.load(f)
        except Exception:
            tasks = []

    for i, t in enumerate(tasks):
        if t.get("task_id") == task.get("task_id"):
            tasks[i] = task
            break

    with open(task_file, "w") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # Test
    task = create_generation_task(
        account_id="mp_chaguan",
        keyword="二手回收乱象再曝光",
        source="autotopic_manual",
        source_platform="百度热搜",
    )
    print(json.dumps(task, ensure_ascii=False, indent=2))
