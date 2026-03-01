#!/usr/bin/env python3
"""GZH 4-stage pipeline scaffold (minimal viable).

Stages:
1) inspiration_add
2) topic_incubate (7 regular + 5 hot, single LLM call strategy preserved via scripts/autotopic.py)
3) write_one (generate article via scripts/article_service)
4) archive_published (manual)

All stores live under data/ (gitignored).
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime

from scripts.gzh_store import (
    ensure_dirs,
    add_inspiration,
    add_topic_candidate,
    add_draft,
    add_published,
    load_recent,
)
from scripts.gzh_similarity import nearest


def cmd_inspiration_add(args: argparse.Namespace) -> int:
    ensure_dirs()
    src = {
        "type": args.source_type or "manual",
        "url": args.url or "",
        "platform": args.platform or "",
        "title": args.source_title or "",
    }
    rec = add_inspiration(args.text, source=src, tags=args.tags or [])
    print(json.dumps(rec, ensure_ascii=False, indent=2))
    return 0


def cmd_topic_incubate(args: argparse.Namespace) -> int:
    ensure_dirs()

    from scripts.autotopic import run_autotopic

    # Keep existing strategy (single LLM call per account) inside autotopic.run_autotopic
    res = run_autotopic()
    accounts = res.get("accounts") or {}

    recent_topics = load_recent("topics", limit=2000)
    recent_drafts = load_recent("drafts", limit=800)
    recent_pubs = load_recent("published", limit=2000)

    # Exact-title dedup (so user can click "再生产" multiple times without filling the pool with identical titles)
    existing_titles: dict[str, set[str]] = {}
    for t in recent_topics:
        try:
            aid = (t.get("account_id") or "").strip()
            tt = (t.get("title") or "").strip()
            if not aid or not tt:
                continue
            existing_titles.setdefault(aid, set()).add(tt)
        except Exception:
            continue

    cfg_dedup = {}
    try:
        from scripts.config import load_config
        cfg_dedup = (load_config().get("gzh") or {}).get("dedup") or {}
    except Exception:
        cfg_dedup = {}
    th = float(cfg_dedup.get("similarity_threshold", 0.82) or 0.82)

    created = []
    today = datetime.now().strftime("%Y-%m-%d")

    for label, info in accounts.items():
        account_id = info.get("account_id") or ""
        platform = info.get("platform") or ""
        if args.account_id and account_id != args.account_id:
            continue
        cands = info.get("candidates") or []

        # enforce 12 candidates (7+5) coming from autotopic config
        if len(cands) < 12:
            # still proceed; but caller can see mismatch
            pass

        for c in cands[:12]:
            suggested = (c.get("suggested_title") or "").strip()
            if not suggested:
                continue
            category = "hot" if (c.get("category") == "hot") else "regular"
            if c.get("source") and c.get("source") != "topic_bank" and category != "hot":
                # safety: if source suggests hot but category missing
                pass

            # Skip exact duplicates already in pool
            if suggested in existing_titles.get(account_id, set()):
                continue

            # de-dup similarity check against previous assets
            best_score, best_item = nearest(suggested, recent_pubs, text_key="title")
            best_kind = "published"
            if best_score < 1e-9:
                best_item = None
            # also compare drafts/topic titles
            s2, it2 = nearest(suggested, recent_drafts, text_key="topic_title")
            if s2 > best_score:
                best_score, best_item, best_kind = s2, it2, "draft"
            s3, it3 = nearest(suggested, recent_topics, text_key="title")
            if s3 > best_score:
                best_score, best_item, best_kind = s3, it3, "topic"

            dedup = {
                "max_similarity": float(best_score),
                "nearest_id": (best_item or {}).get("id", "") if isinstance(best_item, dict) else "",
                "nearest_kind": best_kind if best_item else "",
                "threshold": th,
                "hit": bool(best_item and best_score >= th),
            }

            extra = {
                "platform": platform or "wechat_mp",
                "dedup": dedup,
            }

            rec = add_topic_candidate(
                account_id=account_id,
                title=suggested,
                category=category,
                source=c.get("source", ""),
                original_title=c.get("original_title", ""),
                url=c.get("url", ""),
                date=today,
                extra=extra,
            )
            created.append(rec)

    print(json.dumps({
        "ok": True,
        "date": today,
        "count": len(created),
        "items": created[-min(len(created), 50):],
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_write_one(args: argparse.Namespace) -> int:
    ensure_dirs()

    from scripts.article_service import create_generation_task, execute_generation_task

    topic_title = args.topic_title.strip()

    # Optional: find a topic_id from topics store
    topic_id = ""
    if args.topic_id:
        topic_id = args.topic_id
    else:
        for t in reversed(load_recent("topics", limit=1000)):
            if t.get("account_id") == args.account_id and (t.get("title") or "").strip() == topic_title:
                topic_id = t.get("id") or ""
                break

    task = create_generation_task(
        account_id=args.account_id,
        keyword=topic_title,
        source="gzh_4stage",
        source_platform=args.source_platform or "",
        hot_title=args.hot_title or "",
        hot_url=args.hot_url or "",
        do_web_search=bool(args.web_search),
        push_to_draft=bool(args.push_to_draft),
        enqueue=False,
    )

    done = execute_generation_task(task)

    # Archive into drafts store (best-effort)
    try:
        outputs = {
            "output_dir": done.get("dirname", ""),
            "preview_url": done.get("preview_url", ""),
        }
        metrics = {}
        try:
            # from pipeline_debug metrics etc.
            from scripts.llm import get_metrics
            metrics.update(get_metrics())
        except Exception:
            pass

        dedup = {}
        if topic_id:
            # pull dedup info from topic record
            for t in reversed(load_recent("topics", limit=1000)):
                if t.get("id") == topic_id:
                    dedup = t.get("dedup") or {}
                    break

        if done.get("status") == "done":
            article_stub = {
                "title": done.get("title") or topic_title,
                "digest": done.get("digest") or "",
                "subtitle": "",
                "sections": [],
            }
            # load article.json if exists
            try:
                art_json = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output", done.get("dirname"), "article.json")
                if os.path.exists(art_json):
                    with open(art_json, "r", encoding="utf-8") as f:
                        article_stub = json.load(f)
            except Exception:
                pass
            add_draft(
                account_id=args.account_id,
                topic_title=topic_title,
                article=article_stub,
                topic_id=topic_id,
                outputs=outputs,
                metrics={
                    "task": {
                        "status": done.get("status"),
                        "images": done.get("images"),
                    },
                    "quality": done.get("quality", {}),
                },
                dedup=dedup,
                status="pushed" if args.push_to_draft else "draft",
            )
    except Exception:
        pass

    print(json.dumps(done, ensure_ascii=False, indent=2))
    return 0


def cmd_archive_published(args: argparse.Namespace) -> int:
    ensure_dirs()
    wechat = {
        "url": args.wechat_url or "",
        "msgid": args.msgid or "",
        "publish_at": args.publish_at or "",
    }
    rec = add_published(
        account_id=args.account_id,
        title=args.title,
        wechat=wechat,
        source={"from": args.source or "manual"},
    )
    print(json.dumps(rec, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="gzh_four_stage")
    sub = p.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("inspiration_add", help="Add an inspiration into data/gzh/inspirations.jsonl")
    p1.add_argument("--text", required=True)
    p1.add_argument("--source-type", default="manual")
    p1.add_argument("--platform", default="")
    p1.add_argument("--url", default="")
    p1.add_argument("--source-title", default="")
    p1.add_argument("--tags", nargs="*", default=[])
    p1.set_defaults(func=cmd_inspiration_add)

    p2 = sub.add_parser("topic_incubate", help="Generate today's 12 candidates per account and store into data/gzh/topics.jsonl")
    p2.add_argument("--account-id", default="", help="Only incubate for one account_id")
    p2.set_defaults(func=cmd_topic_incubate)

    p3 = sub.add_parser("write_one", help="Write one article by topic title and archive into drafts")
    p3.add_argument("--account-id", required=True)
    p3.add_argument("--topic-title", required=True)
    p3.add_argument("--topic-id", default="")
    p3.add_argument("--push-to-draft", action="store_true")
    p3.add_argument("--web-search", action="store_true", help="Enable web search enrichment (costly) for hot topics")
    p3.add_argument("--source-platform", default="")
    p3.add_argument("--hot-title", default="")
    p3.add_argument("--hot-url", default="")
    p3.set_defaults(func=cmd_write_one)

    p4 = sub.add_parser("archive_published", help="Manually archive a published article into data/gzh/published.jsonl")
    p4.add_argument("--account-id", required=True)
    p4.add_argument("--title", required=True)
    p4.add_argument("--wechat-url", default="")
    p4.add_argument("--msgid", default="")
    p4.add_argument("--publish-at", default="")
    p4.add_argument("--source", default="manual")
    p4.set_defaults(func=cmd_archive_published)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
