#!/usr/bin/env python3
"""
自动选题引擎 - 核心流程：
1. 读取每日热点数据（trend项目的SQLite数据库）
2. 结合每个账号的领域/人设，筛选合适话题
3. 为每个账号生成标题候选列表
4. 格式化为飞书确认消息 或 自动选择top N
"""
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

TREND_DB_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__)))),
    "trend", "output", "news"
)

PLATFORM_NAMES = {
    "toutiao": "今日头条", "baidu": "百度热搜", "weibo": "微博",
    "zhihu": "知乎", "bilibili-hot-search": "B站", "douyin": "抖音",
    "thepaper": "澎湃新闻", "wallstreetcn-hot": "华尔街见闻",
    "cls-hot": "财联社", "ifeng": "凤凰网", "tieba": "贴吧",
}


def _latest_trend_date() -> str:
    """Find the latest available trend db date (YYYY-MM-DD)."""
    try:
        if not os.path.isdir(TREND_DB_DIR):
            return ""
        files = sorted([p.name for p in Path(TREND_DB_DIR).glob("*.db")], reverse=True)
        if not files:
            return ""
        return files[0].replace(".db", "")
    except Exception:
        return ""


def load_today_hot(date: str = None, sources: list = None) -> list:
    """从 trend 数据库读取热点列表。

    - 默认读取“今天”的库；若今天没有数据，则回退到最新可用日期。

    Returns: [{"title": str, "platform": str, "rank": int, "url": str}, ...]
    """
    date = date or datetime.now().strftime("%Y-%m-%d")
    db_path = os.path.join(TREND_DB_DIR, f"{date}.db")
    if not os.path.exists(db_path):
        latest = _latest_trend_date()
        if latest:
            db_path = os.path.join(TREND_DB_DIR, f"{latest}.db")
        if not os.path.exists(db_path):
            return []

    # normalize sources (aliases)
    src = None
    if sources:
        src = []
        for s in sources:
            s = (s or "").strip()
            if not s:
                continue
            src.append(s)
            if s == "bilibili":
                src.append("bilibili-hot-search")
        # de-dup keep order
        seen = set(); _u=[]
        for s in src:
            if s not in seen:
                seen.add(s); _u.append(s)
        src = _u

    db = sqlite3.connect(db_path)
    rows = db.execute(
        "SELECT title, platform_id, rank, url FROM news_items ORDER BY platform_id, rank"
    ).fetchall()
    db.close()

    items = []
    for title, pid, rank, url in rows:
        if src and pid not in src:
            continue
        items.append({
            "title": title,
            "platform": pid,
            "platform_name": PLATFORM_NAMES.get(pid, pid),
            "rank": rank,
            "url": url or "",
        })

    # If user configured sources but it filtered out everything (misconfig), fallback to all.
    if sources and not items:
        return load_today_hot(date=date, sources=None)

    return items


def filter_hot(items: list, include_kw: list = None, exclude_kw: list = None) -> list:
    """按关键词过滤热点。"""
    result = items
    if include_kw:
        result = [i for i in result if any(k in i["title"] for k in include_kw)]
    if exclude_kw:
        result = [i for i in result if not any(k in i["title"] for k in exclude_kw)]
    return result


def deduplicate(items: list) -> list:
    """去重（标题相似度 > 80% 视为重复）。简单实现：完全相同标题去重。"""
    seen = set()
    result = []
    for item in items:
        t = item["title"].strip()
        if t not in seen:
            seen.add(t)
            result.append(item)
    return result


def match_topics_for_account(hot_items: list, account: dict, count: int = 5) -> list:
    """为单个账号匹配合适的话题。
    
    根据账号的领域、人设、受众来打分排序。
    Phase 1: 简单关键词匹配 + rank权重。
    后续可接入 AI 语义匹配。
    
    Args:
        hot_items: 去重后的热点列表
        account: 账号配置（含 profile.writing_style）
        count: 返回数量
    
    Returns: [{"title": str, "platform": str, "score": float, ...}, ...]
    """
    style = (account.get("profile") or {}).get("writing_style") or {}
    domain = style.get("domain", "")
    persona = style.get("persona", "")
    keywords = style.get("keywords") or []
    if isinstance(keywords, str):
        keywords = [k.strip() for k in keywords.split(",") if k.strip()]
    
    # 所有领域相关关键词
    match_words = keywords + [domain] + [w for w in persona.split() if len(w) >= 2]
    match_words = [w for w in match_words if w]
    
    scored = []
    for item in hot_items:
        title = item["title"]
        score = 0.0
        # Rank bonus: top items get higher base score
        rank = item.get("rank", 50)
        score += max(0, (30 - rank)) * 0.5  # top 1 = 14.5, top 10 = 10
        
        # Keyword match bonus
        for kw in match_words:
            if kw.lower() in title.lower():
                score += 10
        
        # Platform diversity bonus (prefer major platforms)
        major = {"weibo", "baidu", "toutiao", "zhihu", "thepaper"}
        if item["platform"] in major:
            score += 3
        
        scored.append({**item, "score": score})
    
    # Sort by score desc, then rank asc
    scored.sort(key=lambda x: (-x["score"], x["rank"]))
    
    # Platform diversity: limit same platform to max 2 items
    platform_counts = {}
    diverse_result = []
    for item in scored:
        platform = item.get("platform", "unknown")
        if platform_counts.get(platform, 0) >= 2:
            continue
        platform_counts[platform] = platform_counts.get(platform, 0) + 1
        diverse_result.append(item)
        if len(diverse_result) >= count:
            break
    
    # If diversity filter returned too few, fallback to original sorted list
    return diverse_result if len(diverse_result) >= min(count, 3) else scored[:count]


def _load_writer_formulas(writer_key: str = "") -> list:
    """Load title formulas from writers/*.yaml.

    Returns a list of dicts: {type, template, examples?}
    """
    if not writer_key:
        return []
    try:
        import yaml
        writers_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "writers")
        path = os.path.join(writers_dir, f"{writer_key}.yaml")
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data.get("title_formulas") or []
    except Exception:
        return []


def _fill_template(tpl: str, values: dict) -> str:
    s = tpl
    for k, v in values.items():
        s = s.replace("{" + k + "}", str(v))
    return s


def _extract_hot_phrase(base: str) -> str:
    """Extract a short phrase from the hot title to anchor the final title."""
    b = (base or "").strip()
    if not b:
        return ""
    # remove common brackets
    for ch in "【】()（）[]<>《》“”\"":
        b = b.replace(ch, "")
    # take before colon-like separators
    for sep in ["：", ":", "-", "—", "|", "｜"]:
        if sep in b:
            b = b.split(sep, 1)[0].strip()
    # clamp: keep shorter to avoid long titles
    return b[:14]


def _trim_title(s: str, max_len: int | None) -> str:
    if not max_len:
        return s
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    # try to cut at punctuation near max_len
    cut = max_len
    for ch in ["，", "。", "：", ":", "；", ";", "（", "("]:
        p = s.rfind(ch, 0, max_len)
        if p >= 8:
            cut = p
            break
    return s[:cut].rstrip("，。：；:;（(").strip()


def _title_hook_score(title: str, domain: str = "", hot_phrase: str = "") -> float:
    t = title or ""
    score = 0.0
    # Hot relevance (must feel related)
    if hot_phrase and hot_phrase in t:
        score += 6

    # Hook signals
    if "？" in t or "?" in t:
        score += 2
    if any(x in t for x in ["别再", "真相", "后悔", "避雷", "警惕", "一定要", "你可能", "其实", "为什么", "到底"]):
        score += 3

    # Numbers perform well on XHS and sometimes MP
    import re
    if re.search(r"\d+", t):
        score += 2

    # Domain relevance
    if domain and domain in t:
        score += 2

    # Penalize overly generic therapy-like titles when no hot anchor
    if not hot_phrase or hot_phrase not in t:
        if any(x in t for x in ["焦虑", "内耗", "自我怀疑"]):
            score -= 4

    # Keep titles not too long
    if len(t) <= 30:
        score += 1
    if len(t) > 42:
        score -= 2
    return score


def _should_web_search_hot(item: dict, account: dict) -> bool:
    """Heuristic: decide whether a hot topic is worth fetching details.

    We only search a small subset to avoid overfitting to热点 and to control latency.
    """
    try:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        rank = int(item.get("rank") or 99)
        pid = item.get("platform") or ""
        if not url:
            return False
        # only consider top ranks
        if rank > 5:
            return False
        # keywords that benefit from concrete facts
        kw = [
            "通报", "回应", "事故", "爆炸", "起火", "致", "死亡", "受伤",
            "裁员", "降薪", "停工", "欠薪",
            "教育", "学校", "老师", "学生", "高考", "中考",
            "医院", "医生", "手术", "药", "疫苗",
            "房贷", "利率", "银行", "房地产",
            "政策", "新规", "税", "补贴",
        ]
        if any(k in title for k in kw):
            return True
        # major platforms, very top rank: still worth
        if pid in {"weibo", "baidu", "toutiao", "zhihu", "thepaper"} and rank <= 3:
            return True
        return False
    except Exception:
        return False


def generate_title_candidates(account: dict, matched_topics: list) -> list:
    """为每个匹配话题生成“最终文章标题”候选（不是原热点标题复读）。

    目标：结合账号人设/领域，生成更吸睛、更想点的标题。

    Strategy (Phase 1):
    - Use writer.title_formulas if available (writers/*.yaml)
    - Fallback to platform defaults (wechat_mp: dan-koe; xhs: xiaohongshu)
    - Fill templates with lightweight heuristics + account writing_style

    Returns: [{original_title, suggested_title, source, url, score, title_score}, ...]
    """
    profile = account.get("profile") or {}
    ws = profile.get("writing_style") or {}
    domain = ws.get("domain", "")
    persona = ws.get("persona", "")
    platform = account.get("platform", "")

    tc = profile.get("title_config") or {}
    title_len_min = tc.get("len_min")
    title_len_max = tc.get("len_max")
    # Reasonable defaults
    if not title_len_max:
        title_len_max = 28 if platform != "xhs" else 30

    # Determine formula source
    writer_key = profile.get("writer") or ""
    formulas = _load_writer_formulas(writer_key)
    if not formulas:
        # Platform defaults
        formulas = _load_writer_formulas("xiaohongshu" if platform == "xhs" else "dan-koe")

    import random
    results = []

    # Track used patterns to reduce homogeneity inside one run
    used_starts = set()
    used_norms = set()

    for topic in matched_topics:
        base = (topic.get("title") or "").strip()
        hot_phrase = _extract_hot_phrase(base)

        # lightweight values for templates (now includes hot anchoring)
        values = {
            "领域": domain or "生活",
            "内容": hot_phrase or (base[:10] if base else (domain or "一个真相")),
            "热点": hot_phrase or base[:18],
            "事件": hot_phrase or base[:18],
            "短时间": random.choice(["1天", "3天", "7天", "一个周末", "30分钟"]),
            "巨大成果": random.choice([
                "看清关键处",
                "少走10年弯路",
                "把局面想明白",
                "别再被带节奏",
            ]),
            "困境": random.choice(["情绪起伏", "总在内耗", "被信息裹挟", "对未来迷茫"]),
            "时间": random.choice(["3个月", "半年", "1年"]),
            "行动": random.choice(["盲目站队", "跟风转发", "只看情绪不看事实", "把问题简单化"]),
            "常见概念": random.choice(["情绪稳定", "努力", "成长", "自律"]),
            "否定词": random.choice(["陷阱", "误区", "幻觉"]),
            "反常识观点": random.choice(["真正重要的是证据", "先看结构再看情绪", "别急着下结论"]),
            "现象": random.choice(["越刷越焦虑", "明明很忙却没成果", "总被情绪带着走"]),
            "感受": random.choice(["沉默", "警醒", "不适"]),
            "数字": random.choice(["3", "5", "7", "10"]),
            "物品": random.choice(["清单", "方法", "框架", "心法"]),
            "正面评价": random.choice(["清醒", "有用", "靠谱", "省心"]),
            "身份/经历": random.choice(["职场人", "普通人", "经历过低谷的人", "中年人"]) if persona else random.choice(["普通人", "职场人"]),
        }

        suggestions = []

        # 1) template-based suggestions (randomize a bit for diversity)
        pool = list(formulas)
        random.shuffle(pool)
        for f in pool[:10]:
            tpl = (f or {}).get("template")
            if not tpl:
                continue
            s = _fill_template(tpl, values)
            s = s.replace("！！", "！").strip()
            # Encourage anchoring to hot phrase
            if hot_phrase and hot_phrase not in s and "{" not in tpl:
                # if template doesn't have placeholders, skip
                pass
            suggestions.append(s)

        # 2) hot-anchored deterministic fallbacks (sample to avoid same pattern every time)
        if hot_phrase:
            fallback_pool = [
                f"{hot_phrase}背后：普通人最容易忽略的3个信号",
                f"从{hot_phrase}看社会：别只看热闹，要看这件事的结构",
                f"{hot_phrase}刷屏之后，我更想提醒你这1点",
                f"{hot_phrase}这件事，最该问的其实是：谁在承担代价？",
                f"围观{hot_phrase}时，请先记住这条底线",
            ]
            suggestions += random.sample(fallback_pool, k=min(2, len(fallback_pool)))
        if base:
            suggestions.append(f"{base}：别急着站队，先把关键点看清")

        # Rank and pick best 1 per topic (prefer hot-anchored & diverse starts)
        best = None
        best_score = -999
        for s in suggestions:
            # enforce title length preference
            s2 = _trim_title(s, title_len_max)
            ts = _title_hook_score(s2, domain, hot_phrase=hot_phrase)

            # soft preference for min length (avoid too short)
            if title_len_min and len(s2) < int(title_len_min):
                ts -= 2

            start = s2[:10]
            if start in used_starts:
                ts -= 3

            # penalize reused normalized patterns like "{HOT}背后：..."
            norm = s2
            if hot_phrase and hot_phrase in norm:
                norm = norm.replace(hot_phrase, "{HOT}")
            norm = norm.replace("03个", "3个")
            if norm in used_norms:
                ts -= 6

            if ts > best_score:
                best_score = ts
                best = s2

        if best:
            used_starts.add(best[:10])
            norm_best = best.replace(hot_phrase, "{HOT}") if hot_phrase else best
            used_norms.add(norm_best)

        results.append({
            "original_title": base,
            "suggested_title": best or base,
            "source": topic.get("platform_name", topic.get("platform", "")),
            "url": topic.get("url", ""),
            "score": topic.get("score", 0),
            "title_score": best_score,
        })

    # Sort by title score first, then topic score
    results.sort(key=lambda x: (-(x.get("title_score") or 0), -(x.get("score") or 0)))
    return results


def run_autotopic(config: dict = None, accounts: list = None) -> dict:
    """执行完整的自动选题流程。

    功能：
    - 🔥 热点类：基于趋势数据挑选若干热点，并生成“符合账号人设”的标题候选
    - ✨ 自主类：不依赖热点，基于账号定位自主生成标题候选

    Returns: {
        "accounts": {
            "A": {
                "account_id": str,
                "account_name": str,
                "platform": str,
                "candidates": [...],  # unified 10 titles
            },
        },
        "mode": "manual" | "auto",
        "message": "格式化的飞书确认消息",
    }
    """
    if config is None:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "autotopic.json")
        with open(config_path) as f:
            config = json.load(f)
    
    if accounts is None:
        accounts_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "accounts.json")
        with open(accounts_path) as f:
            accounts = json.load(f).get("accounts", [])
    
    mode = config.get("mode", "manual")

    # New strategy: generate a unified list of candidates (mostly from topic bank,
    # optionally mixed with a few hot-driven titles).
    total_title_count = int((config.get('manual_title_count', 12) if mode == 'manual' else config.get('title_count', 10)) or 10)
    hot_mix_count = int(config.get("hot_mix_count", 5) or 5)
    hot_title_count = max(0, min(hot_mix_count, total_title_count))

    # In auto mode, how many articles to auto-generate/push per account
    auto_count = int(config.get("auto_count", 3) or 3)
    sources = config.get("hot_sources") or None  # None = all
    include_kw = config.get("filter_keywords") or None
    exclude_kw = config.get("exclude_keywords") or None
    
    # 1. Load hot data (optional)
    hot_items = load_today_hot(sources=sources if sources else None)
    if not hot_items:
        # Allow bank-only mode when trend DB is empty/unavailable.
        hot_items = []

    # 2. Filter (only if we have hot items)
    if hot_items:
        hot_items = filter_hot(hot_items, include_kw, exclude_kw)
        hot_items = deduplicate(hot_items)
        # If filtering wipes out all hot items, still continue with bank-only.
        if not hot_items:
            hot_items = []
    
    # 3. For each enabled account, match topics
    enabled_accounts = [a for a in accounts if a.get("enabled", True)]

    # Recent topic history (avoid repeating same hot titles for an account)
    try:
        project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        hist_path = os.path.join(project_root, "output", "topic_history.json")
        with open(hist_path, "r", encoding="utf-8") as f:
            topic_history = json.load(f)
    except Exception:
        topic_history = {}
    if not enabled_accounts:
        return {"error": "无启用的账号", "accounts": {}, "message": ""}
    
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    result_accounts = {}
    
    # Helper: try LLM-based title rewrite to better match persona
    def _llm_rewrite_titles(acc: dict, topic_title: str, source_platform: str = "") -> list:
        try:
            from scripts.article_service import build_title_prompt
            from scripts.llm import chat
            prompt = build_title_prompt(acc, topic_title, source_platform=source_platform)
            out = chat(prompt, temperature=0.85, max_tokens=300)
            import re
            lines = []
            for l in out.splitlines():
                l = l.strip()
                if not l:
                    continue
                l = l.strip(" \t-•")
                # remove leading numbering like "1." / "1、" / "（1）"
                l = re.sub(r"^\(?\s*\d+\s*[\.、)]\s*", "", l).strip()
                l = re.sub(r"^\[\s*\d+\s*\]\s*", "", l).strip()
                if l:
                    lines.append(l)
            return lines[:3]
        except Exception:
            return []

    def _llm_bank_titles(acc: dict, count: int) -> list:
        if count <= 0:
            return []
        try:
            from scripts.topic_banks import load_topic_bank, flatten_atoms
            from scripts.llm import chat
            bank = load_topic_bank(acc.get("id", ""))
            atoms = flatten_atoms(bank)

            ws = (acc.get("profile") or {}).get("writing_style") or {}
            domain = ws.get("domain", "")
            persona = ws.get("persona", "")
            audience = ws.get("audience", "")
            tone = ws.get("tone", "")

            platform = "公众号" if acc.get("platform") == "wechat_mp" else "小红书"

            prompt = f"""你是一位{platform}内容创作者，请为账号生成 {count} 个“爆款潜力标题”。

账号定位：
- 领域：{domain}
- 人设：{persona}
- 读者：{audience}
- 语气：{tone}

选题库素材（参考这些场景/冲突的风格和角度，但请结合当前社会情绪自由发散，不要局限于这些具体素材）：
- 痛点：{atoms.get('problems', [])[:12]}
- 场景：{atoms.get('scenes', [])[:12]}
- 冲突：{atoms.get('conflicts', [])[:12]}
- 动作：{atoms.get('actions', [])[:12]}

发散要求：
- 不要机械照搬上述素材，要结合账号定位，从"健康焦虑、父母养老、社交关系、自我成长"等新角度自由发散
- 每个标题必须基于"具体场景"或"情绪冲突"，禁止空泛（如"快节奏时代""不难发现""越来越…"）
- 避免连续多天重复同样的场景（如不要每天都是"家长群""书桌前"）

格式要求：
1) 标题适合 30-45 岁读者（婚姻/育儿/职场/父母/健康/房贷/中年转型等）
2) 10-22 字为主，口语化、有立场（你以为/其实/别再/真正/到底…）
3) 所有标题必须是中文，禁止英文或混合
4) 每行一个标题，不要编号，不要解释。

请输出 {count} 个标题："""

            out = chat(prompt, temperature=0.9, max_tokens=700)
            import re
            raw = []
            for l in out.splitlines():
                l = l.strip()
                if not l:
                    continue
                l = l.strip(" \t-•")
                l = re.sub(r"^\(?\s*\d+\s*[\.、)]\s*", "", l).strip()
                l = re.sub(r"^\[\s*\d+\s*\]\s*", "", l).strip()
                if l:
                    raw.append(l)
            # de-duplicate while keeping order
            seen = set(); uniq = []
            for t in raw:
                if t not in seen:
                    seen.add(t); uniq.append(t)
            return uniq[:count]
        except Exception:
            return []

    def _bank_titles_no_llm(acc: dict, count: int) -> list:
        """Generate candidate titles from topic bank atoms WITHOUT calling LLM."""
        if count <= 0:
            return []
        try:
            from scripts.topic_banks import load_topic_bank, flatten_atoms
            import random

            bank = load_topic_bank(acc.get('id', ''))
            atoms = flatten_atoms(bank)
            problems = atoms.get('problems') or []
            scenes = atoms.get('scenes') or []
            conflicts = atoms.get('conflicts') or []
            actions = atoms.get('actions') or []

            # Gentle fallbacks if atoms are sparse
            if not scenes:
                scenes = ['回家的路上', '周日晚上', '饭桌上', '电梯里', '凌晨手机亮起那一刻']
            if not problems:
                problems = ['焦虑', '害怕', '内耗', '不安', '委屈']
            if not conflicts:
                conflicts = ['不敢开口', '怕被否定', '怕关系更僵', '不知道怎么说', '怕被误解']
            if not actions:
                actions = ['好好说', '把话说清', '先伸手', '先停一下', '先照顾自己']

            templates = [
                '{scene}那一刻你{conflict}：你怕的不是{problem}，是{action}',
                '{scene}之后你突然沉默：你以为在{action}，其实在躲{problem}',
                '{scene}最难的不是{problem}，是{conflict}怎么开口',
                '{scene}里那句“算了”：你不是认输，是{conflict}',
                '{scene}你想{action}，却被{conflict}卡住：先别怪自己',
            ]

            out = []
            for _ in range(count * 4):
                t = random.choice(templates).format(
                    scene=random.choice(scenes),
                    problem=random.choice(problems),
                    conflict=random.choice(conflicts),
                    action=random.choice(actions),
                ).strip()
                if len(t) > 26:
                    t = t[:26]
                if t and t not in out:
                    out.append(t)
                if len(out) >= count:
                    break
            return out[:count]
        except Exception:
            return []


    def _llm_daily_candidates_once(acc: dict, hot_for_prompt: list, hot_count: int, regular_count: int) -> list:
        """Generate today's candidates with ONE LLM call per account.

        Returns a list of candidate dicts with category=hot|bank.
        """
        total = max(0, int(hot_count or 0)) + max(0, int(regular_count or 0))
        if total <= 0:
            return []
        try:
            from scripts.topic_banks import load_topic_bank, flatten_atoms
            from scripts.llm import chat
            import re

            ws = (acc.get('profile') or {}).get('writing_style') or {}
            domain = ws.get('domain', '')
            persona = ws.get('persona', '')
            audience = ws.get('audience', '')
            tone = ws.get('tone', '')
            platform = '公众号' if acc.get('platform') == 'wechat_mp' else '小红书'

            bank = load_topic_bank(acc.get('id', ''))
            atoms = flatten_atoms(bank)

            hot_lines = []
            for i, it in enumerate((hot_for_prompt or [])[:6], 1):
                title = (it.get('title') or '').strip()
                src = (it.get('platform_name') or it.get('platform') or it.get('source') or '').strip()
                if title:
                    hot_lines.append('{} . {}（{}）'.format(i, title, src))
            hot_part = '\n'.join(hot_lines) if hot_lines else '（无）'

            prompt = f"""你是一位{platform}内容创作者，请为账号生成今日候选标题：热点结合 {hot_count} 个 + 常规 {regular_count} 个。\n\n账号定位：\n- 领域：{domain}\n- 人设：{persona}\n- 读者：{audience}\n- 语气：{tone}\n\n今日热点（仅作灵感，不强制写进标题）：\n{hot_part}\n\n账号选题素材（用于生成具体、不空泛的标题）：\n- 痛点：{(atoms.get('problems') or [])[:10]}\n- 场景：{(atoms.get('scenes') or [])[:10]}\n- 冲突：{(atoms.get('conflicts') or [])[:10]}\n- 动作：{(atoms.get('actions') or [])[:10]}\n\n要求：\n1) 10-22字为主，口语化，有画面/情绪冲突\n2) 允许提问/反差：你以为/其实/到底/别再\n3) 禁止空泛句（快节奏时代/不难发现/越来越…）\n4) 每行一个标题，不要编号，不要解释，不要任何前后缀。\n\n必须严格输出可解析的JSON对象（不要Markdown/不要解释/不要多余文字），只输出JSON本体。
JSON必须包含两个字段：
- hot: 数组，元素为对象，字段 original_title 与 title
- regular: 字符串数组
数量要求：hot=hot_count，regular=regular_count。
"""

            out = chat(prompt, temperature=0.75, max_tokens=900)
            import json as _json
            try:
                data = _json.loads(out)
            except Exception:
                # fallback: try extract json object
                m2 = re.search(r"\{[\s\S]*\}", out)
                data = _json.loads(m2.group(0)) if m2 else {"hot": [], "regular": []}

            hot = data.get('hot') or []
            regular = data.get('regular') or []

            candidates = []
            # hot candidates
            for it in hot[:max(0, int(hot_count or 0))]:
                ot = (it.get('original_title') or '').strip() if isinstance(it, dict) else ''
                tt = (it.get('title') or '').strip() if isinstance(it, dict) else ''
                if tt:
                    candidates.append({
                        'category': 'hot',
                        'original_title': ot,
                        'suggested_title': tt,
                        'source': (hot_for_prompt[0].get('platform_name') or hot_for_prompt[0].get('platform') or hot_for_prompt[0].get('source') or '') if hot_for_prompt else '',
                        'url': '',
                        'rank': None,
                        'platform': '',
                        'score': 0,
                        'search_suggested': True,
                    })

            # regular candidates
            # normalize regular as strings
            reg_lines = []
            if isinstance(regular, list):
                for l in regular:
                    if isinstance(l, str) and l.strip():
                        reg_lines.append(l.strip())
            # de-dup keep order
            seen=set()
            reg_uniq=[]
            for t in reg_lines:
                if t not in seen:
                    seen.add(t)
                    reg_uniq.append(t)

            for t in reg_uniq[:max(0, int(regular_count or 0))]:
                candidates.append({
                    'category': 'bank',
                    'original_title': '',
                    'suggested_title': t,
                    'source': 'topic_bank',
                    'url': '',
                    'rank': None,
                    'platform': '',
                    'score': 0,
                    'search_suggested': False,
                })

            return candidates

        except Exception:
            return []


    for idx, acc in enumerate(enabled_accounts):
        label = labels[idx] if idx < len(labels) else str(idx)

        # One-call strategy: generate today's titles with a single LLM call per account.
        # This replaces per-hot rewrite (N calls) + bank brainstorming (1 call).
        hot_for_prompt = hot_items[:max(0, hot_title_count)] if hot_items else []
        regular_count = max(0, total_title_count - max(0, hot_title_count))

        candidates = _llm_daily_candidates_once(acc, hot_for_prompt, hot_title_count, regular_count)
        if not candidates:
            # fallback: generate regular titles without LLM
            titles = _bank_titles_no_llm(acc, total_title_count)
            candidates = [{
                'category': 'bank',
                'original_title': '',
                'suggested_title': t,
                'source': 'topic_bank',
                'url': '',
                'rank': None,
                'platform': '',
                'score': 0,
                'search_suggested': False,
            } for t in titles]

        result_accounts[label] = {
            "account_id": acc.get("id", ""),
            "account_name": acc.get("name", ""),
            "platform": acc.get("platform", ""),
            "candidates": candidates,
        }
    
    # 4. Format message
    if mode == "manual":
        msg = format_manual_message(result_accounts)
    else:
        msg = format_auto_message(result_accounts, auto_count)

    # 5. Persist state for later selection parsing (Feishu replies / web UI)
    # NOTE: cron runner and message delivery rely on this state.
    try:
        project_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        out_dir = os.path.join(project_root, "output")
        os.makedirs(out_dir, exist_ok=True)

        state = {
            "mode": mode,
            "accounts": result_accounts,
            "message": msg,
            "total_hot": len(hot_items),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "updated_at": datetime.now().isoformat(),
        }
        with open(os.path.join(out_dir, "autotopic_state.json"), "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        with open(os.path.join(out_dir, "autotopic_pending_msg.txt"), "w", encoding="utf-8") as f:
            f.write(msg)
    except Exception:
        # best-effort; don't block
        pass

    return {
        "mode": mode,
        "accounts": result_accounts,
        "message": msg,
        "total_hot": len(hot_items),
        "date": datetime.now().strftime("%Y-%m-%d"),
    }


def format_manual_message(accounts: dict) -> str:
    """格式化人工确认消息。
    
    示例：
    📋 今日选题候选（人工确认模式）
    
    A - 公众号-科技号
    A1. 食品百货公司碰瓷宇树被最高法谴责（今日头条）
    A2. Anthropic出手缓解AI担忧...（华尔街见闻）
    ...
    
    B - 小红书-生活号
    B1. ...
    
    请回复选择，如：A1,B3（每个账号选一篇）
    """
    lines = [f"📋 今日选题候选（{datetime.now().strftime('%m月%d日')}）\n"]
    
    for label, data in accounts.items():
        acc_name = data["account_name"] or data["account_id"]
        lines.append(f"【{label}】{acc_name}")

        cands = data.get("candidates") or []
        if cands:
            for i, c in enumerate(cands, 1):
                tag = "📚" if c.get("category") == "bank" or c.get("source") == "topic_bank" else ("🔥" if c.get("category") == "hot" else "")
                source = f"（{c['source']}）" if c.get("source") and c.get("source") not in ("topic_bank", "self") else ""
                ref = f"\n      参考：{c['original_title']}" if c.get("original_title") else ""
                hint = " 🔎" if c.get("search_suggested") else ""
                hot_mark = "【热点结合：无】"
                if c.get("category") == "hot" and c.get("original_title"):
                    hot_mark = f"【热点结合：{c.get('source','')}｜{c.get('original_title','')}】"
                lines.append(f"  {label}{i}. {tag}{c['suggested_title']}{source} {hot_mark}{hint}{ref}")
        else:
            lines.append("  （暂无候选）")

        lines.append("")
    
    lines.append("💬 请回复选择，如：A1,B3（每个账号选一篇，即开始生成）")
    return "\n".join(lines)


def format_auto_message(accounts: dict, auto_count: int = 3) -> str:
    """格式化自动模式消息（已自动选择 top N，待确认推送）。"""
    lines = [f"🤖 自动选题完成（{datetime.now().strftime('%m月%d日')}）\n"]
    lines.append(f"已为每个账号自动选择 Top {auto_count} 话题并生成文章：\n")
    
    for label, data in accounts.items():
        acc_name = data["account_name"] or data["account_id"]
        lines.append(f"【{label}】{acc_name}")
        for i, c in enumerate(data["candidates"][:auto_count], 1):
            source = f"（{c['source']}）" if c.get("source") else ""
            ref = f"\n      参考：{c['original_title']}" if c.get("original_title") else ""
            lines.append(f"  {label}{i}. {c['suggested_title']}{source}{ref}")
        lines.append("")
    
    lines.append("💬 请回复要推送的文章，如：A1,B2（选定的将推送到对应平台）")
    lines.append("回复「全部」= 全部推送")
    return "\n".join(lines)


def parse_selection(text: str, accounts: dict) -> list:
    """解析用户选择回复。
    
    输入如 "A1,B3" 或 "A1 B3" 或 "全部"
    
    Returns: [{"label": "A", "index": 0, "account_id": str, "title": str}, ...]
    """
    text = text.strip()
    
    if text in ("全部", "all", "ALL"):
        result = []
        for label, data in accounts.items():
            for i, c in enumerate(data["candidates"]):
                result.append({
                    "label": label,
                    "index": i,
                    "account_id": data["account_id"],
                    "account_name": data["account_name"],
                    "platform": data["platform"],
                    "title": c["suggested_title"],
                    "url": c.get("url", ""),
                })
        return result
    
    import re
    selections = re.findall(r'([A-Za-z])(\d+)', text)
    result = []
    for label, num in selections:
        label = label.upper()
        idx = int(num) - 1
        if label in accounts and 0 <= idx < len(accounts[label]["candidates"]):
            c = accounts[label]["candidates"][idx]
            result.append({
                "label": label,
                "index": idx,
                "account_id": accounts[label]["account_id"],
                "account_name": accounts[label]["account_name"],
                "platform": accounts[label]["platform"],
                "title": c["suggested_title"],
                "url": c.get("url", ""),
                "original_title": c.get("original_title", ""),
                "source": c.get("source", ""),
                "search_suggested": bool(c.get("search_suggested")),
                "rank": c.get("rank"),
            })
    return result


if __name__ == "__main__":
    # CLI test
    result = run_autotopic()
    if result.get("error"):
        print(f"Error: {result['error']}")
    else:
        print(result["message"])
        print(f"\n--- Total hot items: {result['total_hot']}, Date: {result['date']} ---")
