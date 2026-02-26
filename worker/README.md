# artbot worker

一个轻量级常驻 worker：

- 轮询 `output/pending_task.json`（旧单任务机制）
- 轮询 `output/pending_tasks.json`（新队列机制，autotopic/manual 会写入这里）
- 自动重试通知飞书（避免 web 提交后无人消费）
- 一旦发现 `output/draft.json` 已经生成，自动调用 `create_draft` 推送到公众号草稿箱

## 启动

```bash
cd /home/lighthouse/.openclaw/workspace/artbot
python3 worker/worker.py

# 新队列 worker（推荐）
nohup python3 worker/queue_worker.py > output/queue_worker.nohup.log 2>&1 &
```

## 可选环境变量

- `FEISHU_TARGET`：例如 `chat:oc_xxx`
- `ARTBOT_WORKER_POLL`：轮询间隔秒（默认 10）
- `ARTBOT_NOTIFY_COOLDOWN`：通知冷却秒（默认 60）

## 说明

这个 worker **不负责写文章/生图**（那部分仍由 agent/流水线生成到 `draft.json`），它只负责把已生成的 `draft.json` 推到公众号草稿箱，并确保任务不会“提交后静默丢失”。
