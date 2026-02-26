#!/usr/bin/env python3
"""artbot lightweight worker

Goal
- Prevent "submitted but nothing happens" by retrying Feishu notifications
- Auto-push latest generated draft.json to WeChat draft box once available

This worker is intentionally lightweight:
- No DB
- No external deps
- Only reads/writes artbot/output/pending_task.json and calls existing modules

Run
  cd /home/lighthouse/.openclaw/workspace/artbot
  python3 worker/worker.py

Environment
- FEISHU_TARGET (optional): e.g. chat:oc_xxx
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Make `scripts.*` importable
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.config import load_config  # noqa: E402
from scripts.wechat_uploader import create_draft  # noqa: E402

OUTPUT_DIR = PROJECT_ROOT / "output"
TASK_FILE = OUTPUT_DIR / "pending_task.json"
DRAFT_FILE = OUTPUT_DIR / "draft.json"
LOG_FILE = OUTPUT_DIR / "worker.log"

POLL_SECONDS = int(os.environ.get("ARTBOT_WORKER_POLL", "10"))
NOTIFY_COOLDOWN_SECONDS = int(os.environ.get("ARTBOT_NOTIFY_COOLDOWN", "60"))


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def read_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def parse_iso(s: str):
    try:
        # Python 3.11+ supports fromisoformat without Z
        return datetime.fromisoformat(s)
    except Exception:
        return None


def should_notify(task: dict) -> bool:
    if task.get("status") not in ("pending", "notified", "processing"):
        return False
    last = task.get("last_notified_at")
    if not last:
        return True
    dt = parse_iso(last)
    if not dt:
        return True
    return (datetime.now() - dt).total_seconds() >= NOTIFY_COOLDOWN_SECONDS


def notify_feishu(task: dict):
    cfg = load_config()
    target = os.environ.get("FEISHU_TARGET") or cfg.get("feishu_target") or ""
    if not target:
        # fallback: legacy group id without prefix
        target = "chat:oc_c853e1bd8e54b506e6c9870642dbc7e0"

    keyword = task.get("keyword", "")
    theme = task.get("theme", "snow-cold")
    num_images = task.get("num_images", 2)
    extra = task.get("extra_prompt") or "无"

    msg = (
        f"[artbot任务] 检测到待处理任务（{task.get('status')}）。"
        f"关键词：{keyword}；主题：{theme}；插图数：{num_images}；额外要求：{extra}。\n"
        f"任务文件：{TASK_FILE}。\n"
        f"提示：生成完成后请写入 {DRAFT_FILE}（或调用推草稿接口/脚本）。"
    )

    try:
        # Use openclaw CLI (already in web/app.py) for consistency
        subprocess.run(
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
            timeout=15,
            capture_output=True,
            text=True,
        )
        log(f"Notified Feishu target={target} keyword={keyword}")
    except Exception as e:
        log(f"Notify failed: {e}")


def maybe_push_draft(task: dict) -> bool:
    """If draft.json exists and looks newer than task.created_at, push to WeChat draft box.

    Returns True if pushed successfully.
    """
    if not DRAFT_FILE.exists():
        return False

    created_at = parse_iso(task.get("created_at", ""))
    if created_at:
        mtime = datetime.fromtimestamp(DRAFT_FILE.stat().st_mtime)
        if mtime < created_at:
            return False

    payload = read_json(DRAFT_FILE)
    if not payload:
        return False

    try:
        article = (payload.get("articles") or [])[0]
        title = article.get("title", "")
        digest = article.get("digest", "")
        cover_media_id = article.get("thumb_media_id", "")
        content_html = article.get("content", "")
        if not (title and cover_media_id and content_html):
            log("draft.json missing required fields; skip push")
            return False

        draft = create_draft(title, content_html, cover_media_id, digest)
        task["status"] = "pushed"
        task["pushed_at"] = datetime.now().isoformat()
        task["wechat_draft"] = draft
        write_json(TASK_FILE, task)
        log(f"Pushed to WeChat draft box: {title}")
        return True
    except Exception as e:
        task["last_push_error"] = str(e)
        task["last_push_error_at"] = datetime.now().isoformat()
        write_json(TASK_FILE, task)
        log(f"Push failed: {e}")
        return False


def main():
    log(f"Worker started. poll={POLL_SECONDS}s cooldown={NOTIFY_COOLDOWN_SECONDS}s")
    while True:
        try:
            task = read_json(TASK_FILE)
            if not task:
                time.sleep(POLL_SECONDS)
                continue

            # 1) If we already have a draft.json for this task, push it
            if task.get("status") in ("pending", "notified", "processing"):
                maybe_push_draft(task)

            # 2) Keep notifying until someone processes
            if should_notify(task):
                notify_feishu(task)
                task["status"] = "notified" if task.get("status") == "pending" else task.get("status")
                task["last_notified_at"] = datetime.now().isoformat()
                task["notify_count"] = int(task.get("notify_count") or 0) + 1
                write_json(TASK_FILE, task)

        except Exception as e:
            log(f"Loop error: {e}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
