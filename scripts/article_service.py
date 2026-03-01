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

    # --- Writing mode switch ---
    article_mode = (style.get("article_mode") or "").strip().lower()

    tone_flag_conflict = ("情绪" in (tone or "")) or ("冲突" in (tone or ""))
    enable_emotion_conflict = article_mode in ("emotion_conflict", "emotional_conflict", "conflict") or tone_flag_conflict

    tone_flag_healing = ("疗愈" in (tone or "")) or ("松一口气" in (tone or ""))
    enable_healing = article_mode in ("healing", "healing_emotion", "emotion_healing", "soothing") or tone_flag_healing


    enable_zen = article_mode in ("zen", "zen_reflection", "reflection", "deep", "single_topic")
    emotion_rules = ""
    if enable_healing:
        emotion_rules = f"""

## 写法（情绪疗愈型｜必须执行）
- 目标：让读者“被看见→松一口气→拿到可执行边界”。不要鸡汤，不要说教。
- 开头 120 字：用一个真实到刺痛的职场瞬间（夜里、屏幕光、消息提示音、心里那句“完了”），立刻点出读者的感受。
- 情绪优先：先准确命名情绪（委屈/焦虑/内耗/害怕背锅/不被认可），再解释原因（权责不清=不确定性）。
- 内容必须有“工具感”，但表达要温和：
  - 文章至少 4 个模块：被看见 → 解释真相 → 给框架 → 给话术/行动
  - 给出一个固定框架：澄清三问 + 风险三线（红/黄/绿）
  - 至少 2 组可照抄话术，用「」标：A) 向上澄清；B) 向下同步团队
  - 至少 3 条可执行建议，用 1/2/3 输出
- 节奏：短句+留白可以，但每个模块至少 4 段 paragraphs；允许 1 段 80-140字把逻辑讲透。
- 至少 3 句 *斜体金句*（更像真话，不像格言）
- 结尾必须包含：一段安抚 + 一个 3 分钟小练习 + 一个问题引导评论
"""
    elif enable_emotion_conflict:
        emotion_rules = f"""

## 写法（情绪冲突型｜必须执行）
- 开头 120 字内：直接给一个【具体场景】+【一句原话/对话】+【情绪爆点】（让读者立刻代入）
- 文章必须有“冲突升级”节奏：误解 → 爆发 → 冷战/内耗 → 反思 → 破局
- 节奏是短句+留白，但内容要“讲清楚、有含量”，故事只是“引子/载体”，不能代替观点：
  - 每个 section 至少 4 段 paragraphs（不要只写 2-3 句就结束）
  - 每个 section 至少 1 段要有【具体细节/例子】（人物/时间/场景/动作）
  - 每个 section 必须输出 1 个【可复用的方法/框架】（比如：三步法、清单、判断题、心智模型）
  - 至少给出 3 条“可执行建议”，用编号 1/2/3 写在 paragraphs 里
  - 允许一段稍长（80-140字）用于把逻辑讲透
- 多用反问/对话/内心独白；每段不超过 3 行
- 文章里至少出现 3 句可摘抄的“金句”，用 *斜体* 标出来（放在 paragraphs 里）
- 禁止空话套话：不要“在快节奏时代/不难发现/越来越…”这种泛化句
- 至少给 2 组可照抄的【话术模板】（用「」标出来，分别对应：向上澄清/向下落地）
- 结尾必须包含：
  - 一句“核心原则”总结（可摘抄）
  - 一个“今晚就能做”的小动作（30秒-3分钟）
  - 一个问题引导评论
"""


    elif enable_zen:
        emotion_rules = f"""

## 写法（禅意深挖型｜必须执行）
- 目标：只讲透一个主题，让读者读完心里安静下来。
- 单主题：全文不要发散到‘团队管理/向上向下/背锅话术’等通用职场模板；除非主题明确是职场管理。
- 开头 100-140 字：用一个真实生活镜头开场（时间/光线/动作/一句话），不要编夸张故事。
- 深挖：给出 1 个核心洞见，并用 2-3 层递进讲透（情绪 → 机制 → 选择）。
- 结构建议 5 个模块：
  1) 场景（被看见）
  2) 命名情绪（你在怕什么/舍不得什么）
  3) 深一层（为什么会这样：关系/身份/控制感/期待）
  4) 小练习/小动作（3分钟内完成，具体到步骤）
  5) 收束（安抚 + 提问引导评论）
- 排版必须好读：
  - 每个 paragraph 尽量 ≤ 60 个汉字，超过就拆成两段
  - 多留白：重要句子单独成段
  - 允许 1 处清单（1/2/3），但必须紧贴主题
- 至少 2 句 *斜体真话*（像真话，不像格言）
- 结尾必须包含：一段安抚 + 3分钟小练习 + 一个问题引导评论
"""
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
{emotion_rules}

## 输出格式要求
请严格按以下 JSON 格式输出（不要输出其他内容）：

```json
{{
  "title": "文章标题",
  "digest": "一句话摘要（30字以内）",
  "subtitle": "开头引言/副标题（短、狠、能代入）",
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
1. 标题要有吸引力和点击欲（更偏口语、有冲突、有画面）
2. 内容有深度、有观点、有价值（但表达要短、狠、准）
3. 结构清晰，分4-6个段落模块更好（每段落 2-4 个短段）
4. 符合{platform}平台的内容规范
5. 最后一段必须有“行动+提问”
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

    # Keep cover prompt SHORT: Hunyuan has strict text length limits.
    # Style is handled by style_prefix in image_gen, so avoid verbose重复描述.
    core = (title or "").strip()
    if len(core) > 26:
        core = core[:26]
    prompt = f"{platform}封面插画，主题：{core}，{ratio}，干净留白，主体明确，少字或无字。"
    if extra:
        # Keep extra very short
        extra2 = extra.strip()
        if len(extra2) > 20:
            extra2 = extra2[:20]
        prompt += f" 风格：{extra2}"
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
                           source_platform: str = "",
                           hot_title: str = "",
                           hot_url: str = "",
                           do_web_search: bool = False,
                           enqueue: bool = True) -> dict:
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
        "extra_prompt": extra_prompt,
        # optional hotspot context (may be used to fetch concrete facts)
        "hot_title": hot_title,
        "hot_url": hot_url,
        "hot_source": source_platform,
        "do_web_search": bool(do_web_search),
        # Prompts
        "title_prompt": build_title_prompt(acc, keyword, source_platform),
        "article_prompt": build_article_prompt(acc, keyword, extra_prompt),
        "cover_prompt_template": build_cover_prompt(acc, "{title}", "{digest}"),
        "inline_prompt_template": build_inline_prompt(acc, "{title}", "{section_title}", "{section_summary}"),
        "inline_count": img.get("inline_count", num_images),
    }

    # Optionally enqueue to task queue (for async processing by queue_worker)
    if enqueue:
        task_file = os.path.join(OUTPUT_DIR, "pending_tasks.json")
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        tasks = []
        if os.path.exists(task_file):
            try:
                with open(task_file, encoding="utf-8") as f:
                    tasks = json.load(f)
            except Exception:
                tasks = []

        tasks.append(task)
        with open(task_file, "w", encoding="utf-8") as f:
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

    # Optional: enrich with hotspot/news context (only when task requests it)
    search_meta = {}
    if task.get("do_web_search") and (task.get("hot_title") or task.get("hot_url")):
        try:
            # Prefer Tavily (richer search across sources)
            from scripts.tavily_search import tavily_search
            tr = tavily_search(task.get("hot_title") or task.get("hot_url"), max_results=5)
            if tr.ok and tr.results:
                lines = []
                for it in tr.results[:5]:
                    lines.append(f"- {it.get('title','')}\n  {it.get('url','')}\n  摘要：{(it.get('content','') or '')[:220]}")
                search_context = "热点扩展检索结果（只抽取事实细节/数据/时间线，不要复述新闻）：\n" + "\n".join(lines)
                acc2 = load_account(account_id)
                article_prompt = build_article_prompt(
                    acc2, keyword,
                    extra_prompt=task.get("extra_prompt", ""),
                    search_context=search_context,
                )
                search_meta = {
                    "engine": "tavily",
                    "query": tr.query,
                    "ok": True,
                    "results": tr.results,
                    "searched_at": tr.searched_at,
                    "hot_title": task.get("hot_title", ""),
                    "hot_source": task.get("hot_source", ""),
                    "hot_url": task.get("hot_url", ""),
                }
            else:
                # Fallback: fetch_url_text when Tavily is not configured
                from scripts.news_fetch import fetch_url_text
                fr = fetch_url_text(task.get("hot_url"), max_chars=1200)
                if fr.ok and fr.text:
                    acc2 = load_account(account_id)
                    search_context = f"热点参考（请只抽取事实细节，不要复述新闻）：\n- 标题：{task.get('hot_title','')}\n- 来源：{task.get('hot_source','')}\n- URL：{fr.url}\n- 摘要：{fr.text}"
                    article_prompt = build_article_prompt(acc2, keyword, extra_prompt=task.get("extra_prompt", ""), search_context=search_context)
                    search_meta = {
                        "engine": "fetch_url_text",
                        "hot_title": task.get("hot_title", ""),
                        "hot_source": task.get("hot_source", ""),
                        "hot_url": fr.url,
                        "fetch_ok": fr.ok,
                        "status": fr.status,
                        "content_type": fr.content_type,
                        "snippet_len": len(fr.text),
                        "fetched_at": fr.fetched_at,
                        "tavily_ok": False,
                        "tavily_error": tr.error,
                    }
                else:
                    search_meta = {
                        "engine": "tavily",
                        "query": tr.query,
                        "ok": False,
                        "error": tr.error,
                        "fallback_ok": False,
                        "hot_url": task.get("hot_url"),
                        "fetch_error": fr.error,
                    }
        except Exception as e:
            search_meta = {"ok": False, "error": str(e), "hot_url": task.get("hot_url"), "hot_title": task.get("hot_title", "")}

    # Reset per-article text LLM metrics so pipeline_debug can report clean counts.
    try:
        from scripts import llm as _llm
        _llm.reset_metrics()
    except Exception:
        pass

    raw = chat(article_prompt, model="moonshot-v1-32k", temperature=0.7, max_tokens=3000)

    # Prefer fenced json block if exists
    m = _re.search(r"```json\s*(\{.*?\})\s*```", raw, _re.DOTALL | _re.IGNORECASE)
    if m:
        json_text = m.group(1)
    else:
        m = _re.search(r"\{.*\}", raw, _re.DOTALL)
        if not m:
            task["status"] = "error"
            task["error"] = "AI 返回无法解析的内容"
            _update_task_status(task)
            return task
        json_text = m.group()

    # Some models occasionally output raw control chars inside JSON strings (invalid JSON).
    # We sanitize and retry once.
    try:
        article_data = json.loads(json_text)
    except Exception:
        cleaned = _re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", json_text)
        article_data = json.loads(cleaned)

    title = article_data.get("title", keyword)
    digest = article_data.get("digest", "")
    subtitle = article_data.get("subtitle", "")
    sections = article_data.get("sections", [])


    def _split_long_paragraph(p: str, max_len: int = 60) -> list[str]:
        p = (p or '').strip()
        if not p:
            return []
        if len(p) <= max_len:
            return [p]
        # split by Chinese sentence punctuation first
        parts = re.split(r'([。！？!?])', p)
        buf = ''
        out = []
        for i in range(0, len(parts), 2):
            seg = parts[i]
            punct = parts[i+1] if i+1 < len(parts) else ''
            piece = (seg + punct).strip()
            if not piece:
                continue
            if len(buf) + len(piece) <= max_len:
                buf = (buf + piece).strip()
            else:
                if buf:
                    out.append(buf)
                buf = piece
        if buf:
            out.append(buf)
        # final clamp: hard cut
        final = []
        for x in out:
            x = x.strip()
            while len(x) > max_len:
                final.append(x[:max_len])
                x = x[max_len:]
            if x:
                final.append(x)
        return [x for x in final if x]




    # split long paragraphs for readability (better公众号排版)
    try:
        new_sections = []
        for sec in sections if isinstance(sections, list) else []:
            title2 = sec.get('title') if isinstance(sec, dict) else ''
            paras = sec.get('paragraphs') if isinstance(sec, dict) else []
            out_paras = []
            for pp in (paras or []):
                if isinstance(pp, str):
                    out_paras.extend(_split_long_paragraph(pp, max_len=60))
            # ensure some breathing room
            out_paras = [x.strip() for x in out_paras if x and x.strip()]
            new_sections.append({"title": title2, "paragraphs": out_paras})
        sections = new_sections
        article_data["sections"] = sections
    except Exception:
        pass

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
        debug_extras = {}
        # Attach text LLM metrics (separate from image calls).
        try:
            from scripts import llm as _llm2
            debug_extras.setdefault("metrics", {}).update(_llm2.get_metrics())
        except Exception:
            pass

        if search_meta:
            debug_extras["web_search"] = {
                "enabled": True,
                **search_meta,
            }
        pip_result = execute_pipeline(
            title=title, digest=digest, subtitle=subtitle, sections=sections,
            cover_prompt=cover_prompt, theme=theme, push_draft=task.get("push_to_draft", False),
            style_prefix=style_prefix or None,
            inline_count=inline_count,
            inline_prompt_extra=inline_style or None,
            output_dir_override=output_dir,
            wechat_appid=cred.get("appid"),
            wechat_secret=cred.get("secret"),
            debug_extras=debug_extras or None,
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

    # Update history for de-dup/diversity controls
    try:
        hist_path = os.path.join(OUTPUT_DIR, "topic_history.json")
        hist = {}
        if os.path.exists(hist_path):
            with open(hist_path, "r", encoding="utf-8") as f:
                hist = json.load(f) or {}
        acc_hist = hist.get(account_id) or {}
        # recent keywords (suggested titles)
        rk = acc_hist.get("recent_keywords") or []
        rk = [x for x in rk if x and x != keyword]
        rk.insert(0, keyword)
        acc_hist["recent_keywords"] = rk[:30]
        # recent hot titles
        ht = (task.get("hot_title") or "").strip()
        if ht:
            rh = acc_hist.get("recent_hot") or []
            rh = [x for x in rh if x and x != ht]
            rh.insert(0, ht)
            acc_hist["recent_hot"] = rh[:30]
        acc_hist["updated_at"] = datetime.now().isoformat()
        hist[account_id] = acc_hist
        with open(hist_path, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

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
