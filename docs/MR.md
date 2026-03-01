# MR（变更记录 / 讨论记录）

> 目的：把关键决策、讨论结论、调用次数优化策略记录下来，方便回溯与对齐。

## 2026-03-01｜选题+发文调用次数优化（对话纪要）

### 背景
- 用户观察到：一次「选题 + 生成并推送一篇文章」看起来触发了约 8 次“大模型接口调用”。
- 实际拆解：通常是 **选题阶段多次文本LLM + 正文1次文本LLM + 生图(混元3.0)多次**。
- 诉求：
  1) 题库发散/扩充应当是“定期 1 次”，而不是每次选题都发散；
  2) 当天只需要生成 3 个具体标题（一次调用即可）；
  3) 正文 1 次固定；生图 3 次走混元3.0，但不应被误认为调用了 OpenClaw agent 的模型。

### 结论与改造方向
1. **选题阶段：改为单次生成候选标题（1 call / account / run）**
   - 取消「按热点逐条 rewrite」导致的 N 次调用。
   - 取消「题库即时发散」导致的额外调用（改为模板/题库抽样）。

2. **题库：新增周期扩充脚本（一次调用生成 N 条）**
   - 新增脚本：`scripts/topic_bank_expand.py`
   - 用途：周更/日更选题库标题池，日常选题不再为“发散标题”消耗 LLM 调用。

3. **指标拆分：文本LLM vs 图像模型**
   - 在 `pipeline_debug.json` 增加 metrics：`llm_image_calls` / `llm_image_provider`。
   - 在文本 LLM 中间层增加 metrics：`llm_text_calls` / `llm_backend`，并注入到 pipeline debug。

### 预期效果
- 日常「选题」阶段文本调用次数：从热点逐条 rewrite 的 N 次 → **1 次/账号**。
- 「发一篇」阶段文本调用次数：正文 **1 次**。
- 生图调用：仍为混元 3.0 的 **3 次**，但日志/指标将与文本调用分开统计。

## 2026-03-01｜选题配比 & 写作质量整改

### 新需求
1) 每日选题：7 个常规标题 + 5 个热点结合标题（共 12 个）。
2) 排版：避免“一个 paragraph 一大坨字”，段内也要有呼吸感/清晰结构。
3) 内容质量：禁止把不同主题强行套同一套“职场管理/向上向下/团队话术”模板；单篇文章要围绕主题讲深讲透。

### 对应改动
- autotopic：候选生成改为单次LLM输出结构化 JSON，产出 hot(5) + regular(7)。
- writing style：为净心茶社新增/切换到“单主题深挖·清明有光”（jingxin-zen-deep），并把 account 的 article_mode 改为 zen。
- article_service：新增 zen 写法规则；生成后对超长段落自动按中文标点拆段（max_len=60），提升阅读体验。

## 2026-03-01｜公众号爆款自动化四阶段管线（脚手架：数据资产化 + SOP + 质检）

### 关键决策
- 引入 4 类“库”（全部落地 `data/`，默认 gitignore）：
  - inspirations（灵感库）
  - topics（选题池）
  - drafts（草稿库）
  - published（已发布库）
- 选题阶段继续复用 `scripts/autotopic.py`：保持 **12 条候选（7 常规 + 5 热点）**，并保持 **每账号单次 LLM 调用**策略。
- 标杆文章不固定 28 篇，改为 `config/gzh_benchmarks.json` 可配置（默认关闭、默认不抓取正文）。

### 质量与去重
- 新增便宜的相似度检测（2-gram Jaccard），在孵化阶段对 topics 与历史 drafts/published 做相似度标记。
- 写作阶段新增启发式质量评分 + 可配置的“低分自动重写”（默认关闭）：
  - 先用启发式判断（0~1）
  - 可选开启 LLM 自检（额外调用）

### 指标/日志
- 在 `scripts/llm.py` 增加结构化事件 `llm_text_call`（写入 `data/metrics/*.jsonl`）。
- 在 `scripts/image_gen.py` 增加结构化事件 `llm_image_call`（写入 `data/metrics/*.jsonl`）。
- 仍保留 `pipeline_debug.json` 中的 `llm_image_calls` 统计。

### 新增脚手架入口
- `python -m scripts.gzh_four_stage inspiration_add ...`
- `python -m scripts.gzh_four_stage topic_incubate ...`
- `python -m scripts.gzh_four_stage write_one ...`
- `python -m scripts.gzh_four_stage archive_published ...`
