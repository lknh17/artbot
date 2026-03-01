# SOP｜公众号爆款自动化四阶段管线（初版）

目标：把“灵感→选题→写作→归档”做成可复用、可观测、可迭代的数据资产管线，提升文章质量与稳定性。

> 原则：
> 1) 默认低成本（不主动抓取/不重搜索）；
> 2) 选题阶段保持单次 LLM 调用策略（每账号/每次孵化 1 次）；
> 3) 写作“单主题深挖”，避免泛化职场管理模板；
> 4) 去重/相似度检测贯穿全链路；
> 5) 指标/日志结构化，区分 text LLM calls 与 hunyuan image calls。

---

## 阶段 1：灵感入库（Inspiration Intake）

### 输入来源
- 手动：一句话灵感、对话、评论区片段、观察到的反常识点
- 热点：autotopic 读取 trend DB 的标题/链接（默认不抓正文）
- 链接：收藏文章/视频/讨论串（默认不抓正文，仅保存链接+你的一句话摘要）

### 动作
- 将灵感写入 `data/gzh/inspirations.jsonl`
- 标记来源、标签、状态（new/used/archived）
- 基础去重：同文本/高相似文本不重复入库（可配置阈值）

### 验收点
- 新增灵感会产生一条 JSONL 记录（含 id/created_at/text/source）
- 入库时不会触发任何 LLM 或重抓取（除非显式开启）

---

## 阶段 2：选题孵化（Topic Incubation）

### 目标输出
- 每个账号生成 **12 条候选**：**7 条常规 + 5 条热点**
- 严格保持“每账号单次 LLM 调用”策略（如需 LLM）

### 约束
- 热点部分来自 trend DB（标题/链接），不默认抓正文
- 常规部分来自 topic bank（`writers/` 与 `config/topic_bank*.json` 等既有机制）
- 与历史 drafts/published/topics 相似度过高的候选需：
  - 默认仅标记（warn）
  - 可配置为自动替换/重写/丢弃

### 验收点
- 生成结果落地 `data/gzh/topics.jsonl`（每条候选一行，带 category=hot|regular）
- topic 池中每账号必须满足 7+5（总 12）
- LLM 调用次数符合 1/account/孵化（可在 metrics 里核对）

---

## 阶段 3：写作生成（Writing）

### 目标
- 单主题深挖：一篇文章讲透一个核心洞见/一个冲突/一个机制
- 质量自检：结构/段落/结尾行动+提问/可摘抄金句 等
- 去模板化：避免泛化“向上管理/团队管理/职场话术”套娃，除非主题明确就是管理

### 自检（默认启发式，LLM 复检可选）
- 结构：4-6 个 sections；每 section ≥ 3-4 段短段
- 阅读性：段落长度控制（脚本自动拆分长段）
- 结尾：必须包含行动 + 提问

### 低分自动重写（可配置）
- 触发条件：质量分 < 阈值
- 动作：最多重写 1 次（可配置），并记录 rewrites 次数
- 默认关闭（避免成本与不确定性）

### 验收点
- 写作任务输出可解析 JSON（title/digest/subtitle/sections）
- text LLM calls 计数写入 metrics

---

## 阶段 4：归档（Archive & Feedback Loop）

### 草稿库
- 生成成功后写入 `data/gzh/drafts.jsonl`
- 记录 topic_id、输出目录、预览链接、指标、去重结果

### 已发布库
- 发布后写入 `data/gzh/published.jsonl`（可手动归档）
- 用于后续去重与复盘

### 验收点
- 草稿/已发布均可追溯到 topic/inspiration
- 同一账号在近周期内不会持续重复主题（可在去重记录中看到）

---

## Benchmarks（标杆）

- 不固定 28 篇标杆。
- 标杆文章应可配置：通过 `config/gzh_benchmarks.json` 指定一组参考文章（文本/链接/摘要）。
- 默认不加载、不抓取、不增加成本；仅在开启质量复检/风格对齐时参与 prompt。
