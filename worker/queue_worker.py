#!/usr/bin/env python3
"""Queue worker for artbot pending_tasks.json

Problem
- autotopic/manual selection creates tasks in output/pending_tasks.json
- nothing consumes them -> Jobs shows nothing

This worker:
- polls pending_tasks.json
- for each task with status=pending, sends a Feishu message to the group to trigger the OpenClaw "central" (this agent)
- marks task as dispatched to avoid duplicate notifications

It does NOT generate content itself (LLM lives in the OpenClaw agent).

Run:
  cd /home/lighthouse/.openclaw/workspace/artbot
  nohup python3 worker/queue_worker.py > output/queue_worker.nohup.log 2>&1 &

Env:
- FEISHU_TARGET: defaults to chat:oc_c853e1bd8e54b506e6c9870642dbc7e0
- ARTBOT_QUEUE_POLL: seconds (default 10)
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "output"
QUEUE_FILE = OUTPUT_DIR / "pending_tasks.json"
LOG_FILE = OUTPUT_DIR / "queue_worker.log"

POLL_SECONDS = int(os.environ.get("ARTBOT_QUEUE_POLL", "10"))

DEFAULT_TARGET = "chat:oc_c853e1bd8e54b506e6c9870642dbc7e0"


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def read_queue() -> list:
    if not QUEUE_FILE.exists():
        return []
    try:
        return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def write_queue(tasks: list):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, QUEUE_FILE)


def send_feishu(msg: str) -> str:
    target = os.environ.get("FEISHU_TARGET") or DEFAULT_TARGET
    proc = subprocess.run(
        [
            "openclaw",
            "message",
            "send",
            "--channel",
            "feishu",
            "--target",
            target,
            "--message",
            msg,
        ],
        cwd=str(PROJECT_ROOT.parent),
        timeout=30,
        capture_output=True,
        text=True,
    )
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    # best-effort parse
    mid = ""
    import re

    m = re.search(r"Message ID:\s*(\S+)", out)
    if m:
        mid = m.group(1)
    return mid


def main():
    log(f"queue_worker started. poll={POLL_SECONDS}s")
    while True:
        try:
            tasks = read_queue()
            changed = False
            for t in tasks:
                if t.get("status") != "pending":
                    continue

                # dispatch once
                msg = (
                    f"[artbot-queue] 检测到待执行任务：{t.get('task_id','')}\n"
                    f"账号：{t.get('account_name','')}\n"
                    f"标题/关键词：{t.get('keyword','')}\n"
                    f"请由中枢执行：读取 artbot/output/pending_tasks.json 中该 task_id，完成生成并落盘到 output/<dir>/article.html。\n"
                    f"(自动触发消息，勿手动重复提交)"
                )

                mid = send_feishu(msg)
                t["status"] = "dispatched"
                t["dispatched_at"] = datetime.now().isoformat()
                if mid:
                    t["dispatch_message_id"] = mid
                changed = True
                log(f"dispatched task_id={t.get('task_id')} message_id={mid}")

            if changed:
                write_queue(tasks)
        except Exception as e:
            log(f"loop error: {e}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
