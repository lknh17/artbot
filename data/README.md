# data/

本目录用于落地“数据资产化”的四类库（默认被 gitignore 忽略）：

- 灵感库 inspirations（人/热点/评论/素材片段）
- 选题池 topics（孵化后的 12 条候选：7 常规 + 5 热点）
- 草稿库 drafts（已生成但未发布/待推送）
- 已发布库 published（发布后归档，用于去重与复盘）

## 约定

- 默认存储为 JSONL（每行一个对象），便于追加写入和增量处理。
- 该目录下除 `README.md` 外默认不纳入 Git 版本管理。
- 结构化日志/metrics 也写入 `data/metrics/`。

> 运行脚手架命令会自动创建 `data/gzh/` 与 `data/metrics/`。
