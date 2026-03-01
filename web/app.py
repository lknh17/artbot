#!/usr/bin/env python3
"""
公众号文章生成系统 - Web 配置面板
运行在 chengong.net/art
"""
import json
import os
import sys
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, request, jsonify, send_from_directory
from scripts.config import load_config, save_config, CONFIG_FILE
from scripts.html_renderer import THEMES
from scripts.wechat_uploader import create_draft
from tools.store.json_store import load_json, save_json

# GZH 4-stage pipeline stores
from scripts.gzh_store import ensure_dirs, iter_jsonl, add_inspiration, add_published
from scripts.gzh_benchmarks import ingest_text as bm_ingest_text, ingest_url as bm_ingest_url, ingest_pdf as bm_ingest_pdf

app = Flask(__name__, static_folder="static")

# Avoid stale UI from aggressive caches / reverse proxies
@app.after_request
def _cache_control(resp):
    """API 响应不缓存，静态资源允许缓存"""
    try:
        if request.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
        elif request.path.startswith("/static/"):
            # index.html is the entrypoint and changes frequently; avoid stale UI.
            if request.path.endswith("/static/index.html"):
                resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                resp.headers["Pragma"] = "no-cache"
            else:
                resp.headers["Cache-Control"] = "public, max-age=3600"
        # preview / other HTML: browser default caching
    except Exception:
        pass
    return resp

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ACCOUNTS_FILE = os.path.join(PROJECT_ROOT, "config", "accounts.json")
STYLES_FILE = os.path.join(PROJECT_ROOT, "config", "writing_styles.json")
TOPIC_BANKS_DIR = os.path.join(PROJECT_ROOT, "config", "topic_banks")

# Data assets root
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/config", methods=["GET"])
def get_config():
    cfg = load_config()
    # 脱敏
    safe = dict(cfg)
    for key in ["wechat_secret", "hunyuan_secret_key"]:
        if safe.get(key):
            safe[key] = safe[key][:6] + "***"
    return jsonify(safe)


@app.route("/api/config", methods=["POST"])
def update_config():
    data = request.json
    cfg = load_config()
    
    # 只更新非空、非脱敏的字段
    for key, val in data.items():
        if val and "***" not in str(val):
            cfg[key] = val
    
    save_config(cfg)
    return jsonify({"success": True})


AUTOTOPIC_FILE = os.path.join(PROJECT_ROOT, "config", "autotopic.json")

@app.route("/api/export", methods=["GET"])
def export_all_config():
    """一键导出全部配置（config.json + accounts.json + writing_styles.json + autotopic.json）"""
    bundle = {
        "_meta": {
            "version": 1,
            "exported_at": datetime.now().isoformat(),
            "description": "ArtBot full config backup",
        },
        "config": load_config(),
        "accounts": load_json(ACCOUNTS_FILE, {"accounts": []}),
        "writing_styles": load_json(STYLES_FILE, {"styles": []}),
        "autotopic": load_json(AUTOTOPIC_FILE, {}),
    }
    return app.response_class(
        json.dumps(bundle, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="artbot-config-{datetime.now().strftime("%Y%m%d_%H%M%S")}.json"'},
    )


@app.route("/api/import", methods=["POST"])
def import_all_config():
    """一键恢复全部配置（上传之前导出的 JSON 文件）"""
    try:
        if request.content_type and "multipart" in request.content_type:
            f = request.files.get("file")
            if not f:
                return jsonify({"success": False, "error": "未上传文件"}), 400
            bundle = json.loads(f.read().decode("utf-8"))
        else:
            bundle = request.json
        
        if not bundle or "_meta" not in bundle:
            return jsonify({"success": False, "error": "无效的配置文件（缺少 _meta 字段）"}), 400
        
        # Backup current config before overwriting
        backup_dir = os.path.join(PROJECT_ROOT, "output", ".config_backups")
        os.makedirs(backup_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        for name, path in [("config", CONFIG_FILE), ("accounts", ACCOUNTS_FILE),
                           ("styles", STYLES_FILE), ("autotopic", AUTOTOPIC_FILE)]:
            if os.path.exists(path):
                shutil.copy2(path, os.path.join(backup_dir, f"{name}_{ts}.json"))
        
        # Restore each section
        restored = []
        if "config" in bundle:
            save_config(bundle["config"])
            restored.append("config")
        if "accounts" in bundle:
            save_json(ACCOUNTS_FILE, bundle["accounts"])
            restored.append("accounts")
        if "writing_styles" in bundle:
            save_json(STYLES_FILE, bundle["writing_styles"])
            restored.append("writing_styles")
        if "autotopic" in bundle:
            save_json(AUTOTOPIC_FILE, bundle["autotopic"])
            restored.append("autotopic")
        
        return jsonify({
            "success": True,
            "restored": restored,
            "backup_dir": backup_dir,
            "message": f"已恢复 {len(restored)} 项配置，旧配置已备份到 {backup_dir}",
        })
    except json.JSONDecodeError:
        return jsonify({"success": False, "error": "文件格式错误，请上传有效的 JSON 文件"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/themes", methods=["GET"])
def get_themes():
    """List themes.

    Query params:
      - platform: wechat_mp | xhs | all (default: wechat_mp)

    We classify themes by their metadata (layout == 'xhs' => xhs, else wechat_mp).
    """
    platform = (request.args.get("platform") or "wechat_mp").strip()

    items = {}
    for k, v in THEMES.items():
        layout = v.get("layout", "card")
        p = "xhs" if layout == "xhs" or str(k).startswith("xhs-") else "wechat_mp"
        if platform not in ("all", p):
            continue
        items[k] = {
            "name": v.get("name", k),
            "primary": v.get("primary", "#4a6fa5"),
            "bg": v.get("bg", "#ffffff"),
            "layout": layout,
            "platform": p,
        }

    return jsonify(items)


# -----------------------------
# New modular config (Phase 1)
# -----------------------------

@app.route("/api/accounts", methods=["GET"])
def list_accounts():
    data = load_json(ACCOUNTS_FILE, {"accounts": []})
    # Minimal masking for common secret fields
    for a in data.get("accounts", []):
        cred = a.get("credentials") or {}
        for k in ["secret", "appsecret", "token", "password", "hunyuan_secret_key"]:
            if cred.get(k):
                s = str(cred[k])
                cred[k] = s[:6] + "***" if len(s) > 6 else "***"
        a["credentials"] = cred
    return jsonify(data)


@app.route("/api/accounts", methods=["POST"])
def save_accounts():
    payload = request.json or {}
    if "accounts" not in payload or not isinstance(payload["accounts"], list):
        return jsonify({"success": False, "error": "accounts must be a list"}), 400

    # Merge rule: do not overwrite masked secrets (***).
    current = load_json(ACCOUNTS_FILE, {"accounts": []})
    current_map = {a.get("id"): a for a in current.get("accounts", []) if a.get("id")}

    merged = []
    for acc in payload["accounts"]:
        if not isinstance(acc, dict):
            continue
        acc_id = acc.get("id")
        if not acc_id:
            continue
        prev = current_map.get(acc_id, {})
        prev_cred = prev.get("credentials") or {}
        cred = acc.get("credentials") or {}
        for k, v in list(cred.items()):
            if isinstance(v, str) and "***" in v:
                # keep previous
                if k in prev_cred:
                    cred[k] = prev_cred[k]
                else:
                    cred.pop(k, None)
        acc["credentials"] = {**prev_cred, **cred}
        merged.append(acc)

    save_json(ACCOUNTS_FILE, {"accounts": merged})
    return jsonify({"success": True})


@app.route("/api/topic_banks", methods=["GET"])
def get_topic_bank():
    """Get topic bank JSON for an account.

    Query params:
      - account_id: required
    """
    account_id = (request.args.get("account_id") or "").strip()
    if not account_id:
        return jsonify({"success": False, "error": "account_id is required"}), 400

    path = os.path.join(TOPIC_BANKS_DIR, f"{account_id}.json")
    if not os.path.exists(path):
        return jsonify({
            "success": True,
            "data": {
                "account_id": account_id,
                "version": 1,
                "updated_at": datetime.now().isoformat(),
                "banks": [],
            }
        })

    return jsonify({"success": True, "data": load_json(path, {})})


@app.route("/api/topic_banks", methods=["POST"])
def save_topic_bank():
    """Save topic bank JSON for an account."""
    payload = request.json or {}
    account_id = (payload.get("account_id") or "").strip()
    if not account_id:
        return jsonify({"success": False, "error": "account_id is required"}), 400

    data = payload.get("data")
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "data must be an object"}), 400

    os.makedirs(TOPIC_BANKS_DIR, exist_ok=True)
    data.setdefault("account_id", account_id)
    data.setdefault("version", 1)
    data["updated_at"] = datetime.now().isoformat()

    path = os.path.join(TOPIC_BANKS_DIR, f"{account_id}.json")
    save_json(path, data)
    return jsonify({"success": True})


@app.route("/api/generate", methods=["POST"])
def generate_article():
    """统一文章生成入口 - Jobs 手动触发"""
    from scripts.article_service import create_generation_task

    data = request.json
    keyword = data.get("keyword", "")
    if not keyword:
        return jsonify({"success": False, "error": "请输入关键词"}), 400

    account_id = data.get("account_id", "")
    if not account_id:
        return jsonify({"success": False, "error": "请选择账号"}), 400

    try:
        task = create_generation_task(
            account_id=account_id,
            keyword=keyword,
            theme=data.get("theme", None),
            num_images=int(data.get("num_images", 2)),
            extra_prompt=data.get("extra_prompt", ""),
            push_to_draft=data.get("push_to_draft", False),
            source="manual",
        )
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    return jsonify({
        "success": True,
        "task_id": task["task_id"],
        "message": f"任务已创建：{keyword}。等待 AI 生成中...",
        "article_prompt_preview": task["article_prompt"][:200] + "...",
    })


@app.route("/api/status", methods=["GET"])
def get_status():
    """获取任务状态（pending_tasks.json 队列）"""
    tasks_file = os.path.join(PROJECT_ROOT, "output", "pending_tasks.json")
    if os.path.exists(tasks_file):
        tasks = load_json(tasks_file, [])
        pending = [t for t in tasks if t.get("status") == "pending"]
        if pending:
            latest = pending[-1]
            return jsonify({
                "status": "pending",
                "step": f"等待生成：{latest.get('keyword', '')}",
                "pending_count": len(pending),
                "task_id": latest.get("task_id", ""),
            })
    # Legacy single task file
    task_file = os.path.join(PROJECT_ROOT, "output", "pending_task.json")
    if os.path.exists(task_file):
        with open(task_file) as f:
            return jsonify(json.load(f))
    return jsonify({"status": "idle"})


@app.route("/api/drafts", methods=["GET"])
def list_drafts():
    """列出最近的草稿（扫描 output/ 下的子目录和 html 文件）

    Query:
      - page: 1-based
      - limit: page size (default 10)
    """
    output_dir = os.path.join(PROJECT_ROOT, "output")
    page = max(int(request.args.get("page", 1)), 1)
    limit = min(max(int(request.args.get("limit", 10)), 1), 50)

    drafts = []

    # Scan subdirectories containing article.html
    for d in sorted(os.listdir(output_dir), reverse=True):
        subdir = os.path.join(output_dir, d)
        if os.path.isdir(subdir):
            html_path = os.path.join(subdir, "article.html")
            json_path = os.path.join(subdir, "article.json")
            if os.path.exists(html_path):
                meta = {}
                if os.path.exists(json_path):
                    try:
                        with open(json_path, encoding="utf-8") as f:
                            meta = json.load(f)
                    except Exception:
                        pass
                drafts.append({
                    "name": d,
                    "title": meta.get("title", d),
                    "digest": meta.get("digest", ""),
                    "account_id": meta.get("account_id", ""),
                    "source_topic": meta.get("source_topic", ""),
                    "size": os.path.getsize(html_path),
                    "modified": os.path.getmtime(html_path),
                })

    # Also scan loose .html files (legacy)
    for f in sorted(os.listdir(output_dir), reverse=True):
        if f.endswith(".html"):
            path = os.path.join(output_dir, f)
            drafts.append({
                "name": f,
                "title": f,
                "size": os.path.getsize(path),
                "modified": os.path.getmtime(path),
            })

    total = len(drafts)
    start = (page - 1) * limit
    end = start + limit
    items = drafts[start:end]
    return jsonify({"success": True, "items": items, "total": total, "page": page, "limit": limit})


@app.route("/api/push_latest_draft", methods=["POST"])
def push_latest_draft():
    """把 output/draft.json 推送到公众号草稿箱

    说明：artbot 的 AI 写作/生图/排版完成后会落地 output/draft.json。
    这个接口只负责把该文件推到公众号草稿箱（create_draft）。
    """
    output_dir = os.path.join(PROJECT_ROOT, "output")
    draft_path = os.path.join(output_dir, "draft.json")
    if not os.path.exists(draft_path):
        return jsonify({"success": False, "error": "draft.json 不存在，请先生成文章"}), 400

    with open(draft_path) as f:
        payload = json.load(f)

    try:
        article = (payload.get("articles") or [])[0]
        title = article.get("title", "")
        digest = article.get("digest", "")
        cover_media_id = article.get("thumb_media_id", "")
        content_html = article.get("content", "")
        if not (title and cover_media_id and content_html):
            return jsonify({"success": False, "error": "draft.json 字段不完整（title/thumb_media_id/content）"}), 400

        draft = create_draft(title, content_html, cover_media_id, digest)
        return jsonify({"success": True, "data": draft})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/drafts/<name>", methods=["DELETE"])
def delete_draft(name):
    """Delete a generated draft.

    Safety: soft-delete by moving into output/.trash/<timestamp>_<name>.
    """
    output_dir = os.path.join(PROJECT_ROOT, "output")
    subdir = os.path.join(output_dir, name)
    file_path = os.path.join(output_dir, name)

    trash_dir = os.path.join(output_dir, ".trash")
    os.makedirs(trash_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        if os.path.isdir(subdir):
            target = os.path.join(trash_dir, f"{ts}_{name}")
            shutil.move(subdir, target)
            return jsonify({"success": True, "moved_to": target})
        elif os.path.isfile(file_path) and name.endswith('.html'):
            target = os.path.join(trash_dir, f"{ts}_{name}")
            shutil.move(file_path, target)
            return jsonify({"success": True, "moved_to": target})
        else:
            return jsonify({"success": False, "error": "draft not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/drafts/<name>/push_mp", methods=["POST"])
def draft_push_mp(name):
    """Push a generated draft directory to WeChat MP draft box.

    This re-uploads cover/inline images under output/<name>/ and creates a new MP draft.
    """
    from scripts.wechat_uploader import upload_image, create_draft
    from scripts.html_renderer import render_article

    output_dir = os.path.join(PROJECT_ROOT, "output")
    subdir = os.path.join(output_dir, name)
    if not os.path.isdir(subdir):
        return jsonify({"success": False, "error": "draft not found"}), 404

    meta_path = os.path.join(subdir, "article.json")
    if not os.path.exists(meta_path):
        return jsonify({"success": False, "error": "article.json not found"}), 400

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    # load account credentials from accounts.json (only mp_chaguan currently)
    accounts_data = load_json(ACCOUNTS_FILE, {"accounts": []})
    acc = (accounts_data.get("accounts") or [{}])[0]
    cred = acc.get("credentials") or {}
    appid = cred.get("appid")
    secret = cred.get("secret")
    if not (appid and secret):
        return jsonify({"success": False, "error": "公众号 AppID/Secret 未配置"}), 400

    # upload cover + inline
    cover_path = os.path.join(subdir, "cover.jpg")
    if not os.path.exists(cover_path):
        return jsonify({"success": False, "error": "cover.jpg not found"}), 400

    try:
        cover_up = upload_image(cover_path, wechat_appid=appid, wechat_secret=secret)
    except Exception as e:
        return jsonify({"success": False, "error": f"封面上传失败: {e}"}), 500

    inline_uploads = []
    i = 1
    while os.path.exists(os.path.join(subdir, f"inline_{i}.jpg")):
        p = os.path.join(subdir, f"inline_{i}.jpg")
        up = upload_image(p, wechat_appid=appid, wechat_secret=secret)
        inline_uploads.append(up)
        i += 1

    # build html for MP with mmbiz urls
    sections = meta.get("sections") or []
    inserts = []
    # place inline images evenly
    if inline_uploads:
        if len(sections) > 0:
            step = max(1, len(sections) // max(1, len(inline_uploads)))
            idx = 0
            for up in inline_uploads:
                inserts.append({"after_section": min(idx, len(sections)-1), "url": up.get("wechat_url", ""), "caption": ""})
                idx += step
        else:
            for up in inline_uploads:
                inserts.append({"after_section": 0, "url": up.get("wechat_url", ""), "caption": ""})

    html = render_article(
        meta.get("title", name),
        meta.get("subtitle", ""),
        sections,
        images=inserts,
        theme=meta.get("theme", "snow-cold"),
        cover_url=cover_up.get("wechat_url", ""),
    )

    try:
        draft = create_draft(
            meta.get("title", name),
            html,
            cover_up.get("media_id", ""),
            meta.get("digest", ""),
            wechat_appid=appid,
            wechat_secret=secret,
        )
        return jsonify({"success": True, "draft": draft})
    except Exception as e:
        return jsonify({"success": False, "error": f"创建草稿失败: {e}"}), 500


@app.route("/api/drafts/<name>/debug", methods=["GET"])
def draft_debug(name):
    """Return debug info for a generated draft.

    Sources (best-effort):
    - output/<name>/article.json
    - output/<name>/pipeline_debug.json
    - output/pending_tasks.json (match by dirname or title)
    """
    output_dir = os.path.join(PROJECT_ROOT, "output")
    subdir = os.path.join(output_dir, name)
    if not os.path.isdir(subdir):
        return jsonify({"success": False, "error": "draft not found"}), 404

    def _load_json(path, default=None):
        if default is None:
            default = {}
        if not os.path.exists(path):
            return default
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default

    meta = _load_json(os.path.join(subdir, "article.json"), {})
    pipe = _load_json(os.path.join(subdir, "pipeline_debug.json"), {})

    # Find task in queue
    tasks = []
    tasks_file = os.path.join(output_dir, "pending_tasks.json")
    if os.path.exists(tasks_file):
        try:
            with open(tasks_file, encoding="utf-8") as f:
                tasks = json.load(f) or []
        except Exception:
            tasks = []

    matched = None
    for t in reversed(tasks):
        if t.get("dirname") == name:
            matched = t
            break
    if not matched and meta.get("title"):
        for t in reversed(tasks):
            if t.get("title") == meta.get("title"):
                matched = t
                break

    # Add file stats
    html_path = os.path.join(subdir, "article.html")
    stats = {}
    if os.path.exists(html_path):
        stats = {"html_size": os.path.getsize(html_path), "html_mtime": os.path.getmtime(html_path)}

    # Build a best-effort consolidated debug payload (restore as many fields as possible)
    final = {
        "name": name,
        "title": meta.get("title") or pipe.get("title") or (matched or {}).get("title") or name,
        "digest": meta.get("digest") or (matched or {}).get("digest") or "",
        "subtitle": meta.get("subtitle") or "",
        "account_id": meta.get("account_id") or (matched or {}).get("account_id") or "",
        "source_topic": meta.get("source_topic") or (matched or {}).get("keyword") or "",
        "source_platform": meta.get("source_platform") or (matched or {}).get("source_platform") or "",
        "theme": meta.get("theme") or pipe.get("theme") or (matched or {}).get("theme") or "",
        "created_at": meta.get("created_at") or pipe.get("created_at") or (matched or {}).get("created_at") or "",
        "done_at": pipe.get("done_at") or (matched or {}).get("done_at") or "",
    }

    # Prompts (prefer task originals; fall back to pipeline recorded prompts)
    title_prompt = (matched or {}).get("title_prompt", "")
    article_prompt = (matched or {}).get("article_prompt", "")

    cover_prompt = pipe.get("cover_prompt") or ""
    if not cover_prompt:
        tpl = (matched or {}).get("cover_prompt_template", "")
        if tpl:
            cover_prompt = tpl.replace("{title}", final["title"]).replace("{digest}", final["digest"])

    inline_prompts = pipe.get("inline_prompts")
    if not inline_prompts:
        inline_prompts = (matched or {}).get("inline_prompts") or []

    # Image gen / upload details
    images = {
        "cover": pipe.get("cover") or {},
        "inline_images": pipe.get("inline_images") or [],
        "cover_upload": pipe.get("cover_upload") or {},
        "cover_upload_error": pipe.get("cover_upload_error") or "",
        "inline_uploads": pipe.get("inline_uploads") or [],
        "inline_upload_errors": pipe.get("inline_upload_errors") or [],
    }

    final_debug = {
        "final": final,
        "prompts": {
            "title_prompt": title_prompt,
            "article_prompt": article_prompt,
            "cover_prompt": cover_prompt,
            "inline_prompts": inline_prompts,
            "inline_prompt_template": (matched or {}).get("inline_prompt_template", ""),
        },
        "style": {
            "style_prefix": pipe.get("style_prefix") or "",
            "inline_prompt_extra": pipe.get("inline_prompt_extra") or "",
            "cover_resolution": pipe.get("cover_resolution"),
            "inline_resolution": pipe.get("inline_resolution"),
            "inline_count": pipe.get("inline_count"),
        },
        "images": images,
        "wechat_draft": pipe.get("draft") or (matched or {}).get("draft") or {},
        "stats": stats,
    }

    return jsonify({
        "success": True,
        "name": name,
        "stats": stats,
        "meta": meta,
        "pipeline": pipe,
        "task": matched or {},
        "debug": final_debug,
    })


@app.route("/api/preview/<path:filepath>")
def preview(filepath):
    """预览草稿文件。支持 preview/dirname 和 preview/dirname/file

    NOTE:
    - WeChat image URLs (mmbiz.qpic.cn) often cannot be hot-linked in browser previews.
    - For preview only, if local cover/inline images exist in the same output dir,
      we rewrite <img src> to relative filenames (cover.jpg / inline_1.jpg ...)
      so the browser can load them via this endpoint.
    """
    output_dir = os.path.join(PROJECT_ROOT, "output")
    full = os.path.join(output_dir, filepath)

    # If filepath is a directory name, serve article.html inside it (with preview rewrite)
    if os.path.isdir(full):
        html_path = os.path.join(full, "article.html")
        try:
            with open(html_path, "r", encoding="utf-8") as f:
                html = f.read()
            # If local images exist, rewrite mmbiz urls to local filenames for preview
            local_order = []
            if os.path.exists(os.path.join(full, "cover.jpg")):
                local_order.append("cover.jpg")
            i = 1
            while os.path.exists(os.path.join(full, f"inline_{i}.jpg")):
                local_order.append(f"inline_{i}.jpg")
                i += 1

            if local_order and ("mmbiz.qpic.cn" in html):
                import re
                idx = 0

                def _repl(m):
                    nonlocal idx
                    src = m.group(1)
                    if "mmbiz.qpic.cn" in src and idx < len(local_order):
                        rep = local_order[idx]
                        idx += 1
                        return f'src="{rep}"'
                    return m.group(0)

                html = re.sub(r'src="([^"]+)"', _repl, html)

            return html, 200, {"Content-Type": "text/html; charset=utf-8"}
        except Exception:
            # Fallback to static file
            return send_from_directory(full, "article.html")

    return send_from_directory(output_dir, filepath)


@app.route("/api/hot", methods=["GET"])
def get_hot_topics():
    """从 trend 项目读取热点数据"""
    import sqlite3
    from datetime import datetime, timedelta
    
    TREND_DB_DIR = os.path.join(os.path.dirname(PROJECT_ROOT), "trend", "output", "news")
    PLATFORM_NAMES = {
        "toutiao": "今日头条", "baidu": "百度热搜", "weibo": "微博",
        "zhihu": "知乎", "bilibili-hot-search": "B站", "douyin": "抖音",
        "thepaper": "澎湃新闻", "wallstreetcn-hot": "华尔街见闻",
        "cls-hot": "财联社", "ifeng": "凤凰网", "tieba": "贴吧",
    }
    
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    top_n = min(int(request.args.get("top", 10)), 30)
    keyword = request.args.get("q", "").strip()
    
    db_path = os.path.join(TREND_DB_DIR, f"{date}.db")
    if not os.path.exists(db_path):
        return jsonify({"platforms": {}, "dates": _get_trend_dates(TREND_DB_DIR), "current_date": date, "message": f"{date} 暂无数据"})
    
    db = sqlite3.connect(db_path)
    if keyword:
        keywords = keyword.split()
        where = " AND ".join(["title LIKE ?" for _ in keywords])
        params = [f"%{k}%" for k in keywords] + [200]
        rows = db.execute(f"SELECT title, platform_id, rank, url FROM news_items WHERE {where} ORDER BY rank LIMIT ?", params).fetchall()
    else:
        rows = db.execute("SELECT title, platform_id, rank, url FROM news_items ORDER BY platform_id, rank").fetchall()
    db.close()
    
    platforms = {}
    for title, pid, rank, url in rows:
        pname = PLATFORM_NAMES.get(pid, pid)
        platforms.setdefault(pname, [])
        if len(platforms[pname]) < top_n:
            platforms[pname].append({"title": title, "rank": rank, "url": url or ""})
    
    return jsonify({
        "platforms": platforms,
        "dates": _get_trend_dates(TREND_DB_DIR),
        "current_date": date,
        "total": sum(len(v) for v in platforms.values()),
    })


def _get_trend_dates(db_dir):
    """获取可用日期列表"""
    if not os.path.exists(db_dir):
        return []
    files = sorted([f[:-3] for f in os.listdir(db_dir) if f.endswith(".db")], reverse=True)
    return files[:30]


# -------------------------------------------------
# Layout preview API
# -------------------------------------------------

@app.route("/api/layout/preview", methods=["POST"])
def layout_preview():
    """渲染一篇示例文章用于主题预览"""
    data = request.json or {}
    theme = data.get("theme", "snow-cold")
    platform = data.get("platform", "wechat")

    from scripts.html_renderer import render_article

    if platform == "xhs":
        # 小红书风格预览
        title = "5个超实用的效率神器推荐 🚀"
        subtitle = ""
        sections = [
            {"title": "", "paragraphs": [
                "姐妹们！今天必须把我的压箱底好物分享出来 💕",
                "用了大半年，每一个都是真心推荐，绝对不踩雷！",
            ]},
            {"title": "1️⃣ 专注番茄钟", "paragraphs": [
                "这个App也太好用了吧！界面超简洁，",
                "设定25分钟专注+5分钟休息，效率直接翻倍 📈",
                "而且完全免费无广告！",
            ]},
            {"title": "2️⃣ 笔记整理术", "paragraphs": [
                "把所有灵感都记在一个地方，再也不怕忘记 ✨",
                "支持标签分类，搜索超方便",
            ]},
            {"title": "3️⃣ 日程管理", "paragraphs": [
                "「时间块」管理法真的改变了我的生活节奏 🕐",
                "每天花5分钟规划，一整天都很从容",
            ]},
            {"title": "", "paragraphs": [
                "以上就是我的真心推荐啦～",
                "你们还有什么好用的工具？评论区一起聊聊吧 💬",
                "",
                "#效率工具 #好物推荐 #自律生活 #学习方法 #职场干货",
            ]},
        ]
    else:
        # 公众号风格预览
        title = "为什么你总是半途而废？答案可能让你不舒服"
        subtitle = "真正的改变不是控制行为，而是升级欲望。"
        sections = [
            {"title": "一、你不是缺自律，是不想要", "paragraphs": [
                "说实话，我也曾经这样。每年初信心满满定目标，然后三月份就忘得一干二净。",
                "后来我才明白，问题不在于毅力不够——而在于我内心深处，并不真的想要那些东西。",
                "*所以关键不是坚持，而是找到你没办法不做的事。*",
            ]},
            {"title": "二、拖延是一种自我保护", "paragraphs": [
                "你有没有想过，为什么明知道该做，就是做不动？",
                "因为拖延不是懒。它是你在保护自己——免受失败的恐惧、完美主义的压力。",
                "**当你理解了这一点，你就不会再自责了。**",
            ]},
            {"title": "三、小行动，大改变", "paragraphs": [
                "如果你看到这里，我建议你做一件事：",
                "今天花 5 分钟，写下一个你「没办法不做」的事。",
                "不需要很多，5 分钟就够了。但这 5 分钟可能改变你接下来的一整年。",
            ]},
        ]

    if platform == "xhs":
        # Mimic Xiaohongshu: top image carousel + bottom text block
        # (Phase 1 preview only; real publishing adapter comes later)
        accent = "#ff2741"
        bg = "#ffffff"
        if theme in ("xhs-night",):
            bg = "#0b0f1a"
        elif theme in ("xhs-cream",):
            bg = "#fff7f2"

        # Use lightweight placeholders (no external image deps)
        html = f"""<!doctype html>
<html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<title>XHS Preview</title>
</head>
<body style='margin:0; font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica Neue,Arial; background:{bg};'>
<div style='max-width:420px;margin:0 auto; padding:16px;'>
  <div style='display:flex;align-items:center;gap:10px;margin-bottom:12px;'>
    <div style='width:34px;height:34px;border-radius:50%;background:{accent};'></div>
    <div>
      <div style='font-weight:700; font-size:14px; color:{"#e5e7eb" if bg.startswith('#0b') else "#111827"};'>小红书笔记预览</div>
      <div style='font-size:12px; color:{"#9ca3af" if bg.startswith('#0b') else "#6b7280"};'>横滑大图 · 下方正文</div>
    </div>
  </div>

  <div style='overflow-x:auto; display:flex; gap:10px; scroll-snap-type:x mandatory; padding-bottom:8px;'>
    {''.join([f"<div style=\"flex:0 0 86%; height:320px; border-radius:14px; background:linear-gradient(135deg,{accent},#111827); scroll-snap-align:start; position:relative;\"><div style=\"position:absolute; bottom:12px; left:12px; right:12px; color:white; font-weight:700;\">图 {i+1}</div></div>" for i in range(3)])}
  </div>

  <div style='margin-top:12px; padding:14px; border-radius:14px; background:{"rgba(255,255,255,0.06)" if bg.startswith('#0b') else "#ffffff"}; border:1px solid {"rgba(255,255,255,0.08)" if bg.startswith('#0b') else "#e5e7eb"};'>
    <div style='font-size:16px; font-weight:800; line-height:1.4; color:{"#f9fafb" if bg.startswith('#0b') else "#111827"}; margin-bottom:10px;'>5个超实用的效率神器推荐</div>
    <div style='font-size:14px; line-height:1.7; color:{"#e5e7eb" if bg.startswith('#0b') else "#111827"};'>
      姐妹们！今天必须把我的压箱底好物分享出来。用了大半年，每一个都是真心推荐，绝对不踩雷！\n\n
      1）专注番茄钟：25分钟专注+5分钟休息，效率直接翻倍。\n
      2）笔记整理术：所有灵感集中管理，搜索超方便。\n
      3）日程管理：时间块法让一天更从容。\n\n
      #效率工具 #好物推荐 #自律生活
    </div>
  </div>
</div>
</body></html>"""
        return jsonify({"html": html, "theme": theme, "platform": platform})

    html = render_article(title, subtitle, sections, theme=theme)
    return jsonify({"html": html, "theme": theme, "platform": platform})


@app.route("/api/platforms", methods=["GET"])
def list_platforms():
    """列出可用平台及其配置"""
    import yaml
    platforms_dir = os.path.join(PROJECT_ROOT, "platforms")
    result = {}
    if os.path.exists(platforms_dir):
        for f in os.listdir(platforms_dir):
            if f.endswith(".yaml"):
                with open(os.path.join(platforms_dir, f)) as fh:
                    p = yaml.safe_load(fh) or {}
                    result[p.get("id", f[:-5])] = p
    return jsonify(result)


@app.route("/api/writers", methods=["GET"])
def list_writers():
    """列出可用写作风格"""
    import yaml
    writers_dir = os.path.join(PROJECT_ROOT, "writers")
    result = {}
    if os.path.exists(writers_dir):
        for f in os.listdir(writers_dir):
            if f.endswith(".yaml"):
                with open(os.path.join(writers_dir, f)) as fh:
                    w = yaml.safe_load(fh) or {}
                    key = f[:-5]
                    result[key] = {
                        "name": w.get("name", key),
                        "description": w.get("description", ""),
                        "platform": w.get("platform", ""),
                        "category": w.get("category", ""),
                    }
    return jsonify(result)


# -------------------------------------------------
# Auto-topic config API
# -------------------------------------------------

AUTOTOPIC_FILE = os.path.join(PROJECT_ROOT, "config", "autotopic.json")

@app.route("/api/autotopic", methods=["GET"])
def get_autotopic():
    data = load_json(AUTOTOPIC_FILE, {
        "enabled": False,
        "mode": "auto",
        "auto_count": 3,
        "manual_title_count": 5,
        "schedule": "0 9 * * *",
        "timezone": "Asia/Shanghai",
        "hot_sources": ["weibo", "zhihu", "baidu", "toutiao"],
        "search_engine": "brave",
        "search_supplement": True,
        "filter_keywords": [],
        "exclude_keywords": [],
        "target_platforms": ["wechat"],
    })
    return jsonify(data)


@app.route("/api/autotopic", methods=["POST"])
def save_autotopic():
    data = request.json or {}
    save_json(AUTOTOPIC_FILE, data)
    return jsonify({"success": True})


# -------------------------------------------------
# GZH 4-stage pipeline assets APIs (data/)
# -------------------------------------------------

def _safe_tail_jsonl(path: str, limit: int = 200) -> list:
    """Read JSONL tail (best-effort)."""
    items = []
    try:
        for obj in iter_jsonl(path, limit=None):
            items.append(obj)
        if limit and len(items) > limit:
            items = items[-limit:]
    except Exception:
        items = []
    return items


@app.route("/api/gzh/settings", methods=["GET"])
def gzh_get_settings():
    cfg = load_config()
    return jsonify({"success": True, "gzh": cfg.get("gzh") or {}})


@app.route("/api/gzh/settings", methods=["POST"])
def gzh_update_settings():
    """Update config.gzh with a shallow merge.

    Payload: {gzh: {...}} or direct object.
    """
    payload = request.json or {}
    incoming = payload.get("gzh") if isinstance(payload, dict) and "gzh" in payload else payload
    if not isinstance(incoming, dict):
        return jsonify({"success": False, "error": "payload must be an object"}), 400

    cfg = load_config()
    cur = cfg.get("gzh") or {}

    def _merge(a: dict, b: dict) -> dict:
        out = dict(a)
        for k, v in b.items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = _merge(out[k], v)
            else:
                out[k] = v
        return out

    cfg["gzh"] = _merge(cur, incoming)
    save_config(cfg)
    return jsonify({"success": True, "gzh": cfg["gzh"]})


@app.route("/api/gzh/sop", methods=["GET"])
def gzh_get_sop():
    """Return current SOP markdown (read-only)."""
    cfg = load_config()
    sop = (cfg.get("gzh") or {}).get("sop") or {}
    path = sop.get("path") or os.path.join(PROJECT_ROOT, "docs", "SOP_GZH.md")
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "path": path}), 500
    return jsonify({"success": True, "id": sop.get("id", ""), "path": path, "markdown": text})


@app.route("/api/gzh/library/<kind>", methods=["GET"])
def gzh_list_library(kind):
    """List JSONL items from data/gzh/*.jsonl

    kind: inspirations|topics|drafts|published
    """
    ensure_dirs()
    limit = min(max(int(request.args.get("limit", 200)), 1), 2000)
    account_id = (request.args.get("account_id") or "").strip()
    q = (request.args.get("q") or "").strip()

    file_map = {
        "inspirations": os.path.join(PROJECT_ROOT, "data", "gzh", "inspirations.jsonl"),
        "topics": os.path.join(PROJECT_ROOT, "data", "gzh", "topics.jsonl"),
        "drafts": os.path.join(PROJECT_ROOT, "data", "gzh", "drafts.jsonl"),
        "published": os.path.join(PROJECT_ROOT, "data", "gzh", "published.jsonl"),
    }
    if kind not in file_map:
        return jsonify({"success": False, "error": "invalid kind"}), 400

    items = _safe_tail_jsonl(file_map[kind], limit=limit)

    def _match(it: dict) -> bool:
        if account_id and (it.get("account_id") or "") != account_id:
            return False
        if q:
            blob = json.dumps(it, ensure_ascii=False)
            return q in blob
        return True

    items2 = [it for it in items if isinstance(it, dict) and _match(it)]
    return jsonify({"success": True, "kind": kind, "items": items2, "count": len(items2)})


@app.route("/api/gzh/inspirations", methods=["POST"])
def gzh_add_inspiration_api():
    ensure_dirs()
    payload = request.json or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"success": False, "error": "text is required"}), 400
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {"type": payload.get("source_type") or "manual"}
    tags = payload.get("tags") if isinstance(payload.get("tags"), list) else []
    rec = add_inspiration(text=text, source=source, tags=tags)
    return jsonify({"success": True, "item": rec})




@app.route("/api/gzh/benchmarks/ingest", methods=["POST"])
def gzh_benchmarks_ingest_api():
    # multipart form fields: url | text | file(PDF)
    ensure_dirs()
    url = (request.form.get("url") or "").strip()
    text_in = (request.form.get("text") or "").strip()
    f = request.files.get("file")

    try:
        if url:
            res = bm_ingest_url(url)
        elif text_in:
            res = bm_ingest_text(text_in, source={"type": "text", "from": "web"})
        elif f is not None and getattr(f, 'filename', ''):
            updir = os.path.join(PROJECT_ROOT, "output", ".uploads")
            os.makedirs(updir, exist_ok=True)
            tmp = os.path.join(updir, f"bm_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(f.filename)}")
            f.save(tmp)
            res = bm_ingest_pdf(tmp, filename=f.filename)
        else:
            return jsonify({"success": False, "error": "请提供 url 或 text 或 PDF 文件"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    return jsonify({"success": True, "result": res})


@app.route("/api/gzh/benchmarks", methods=["GET"])
def gzh_benchmarks_list_api():
    ensure_dirs()
    limit = min(max(int(request.args.get("limit", 50)), 1), 500)
    path = os.path.join(PROJECT_ROOT, "data", "gzh", "benchmarks.jsonl")
    items = []
    try:
        for obj in iter_jsonl(path, limit=None):
            items.append(obj)
        if len(items) > limit:
            items = items[-limit:]
    except Exception:
        items = []
    return jsonify({"success": True, "items": items, "count": len(items)})


@app.route("/api/gzh/benchmark_prompts", methods=["GET"])
def gzh_benchmark_prompts_list_api():
    ensure_dirs()
    path = os.path.join(PROJECT_ROOT, "data", "gzh", "benchmark_prompts.jsonl")
    latest = {}
    try:
        for obj in iter_jsonl(path, limit=None):
            cat = (obj.get("category") or "").strip()
            if not cat:
                continue
            latest[cat] = obj
    except Exception:
        latest = {}
    items = [latest[k] for k in sorted(latest.keys())]
    return jsonify({"success": True, "items": items, "count": len(items)})
@app.route("/api/gzh/published", methods=["POST"])
def gzh_add_published_api():
    ensure_dirs()
    payload = request.json or {}
    account_id = (payload.get("account_id") or "").strip()
    title = (payload.get("title") or "").strip()
    if not account_id or not title:
        return jsonify({"success": False, "error": "account_id and title are required"}), 400
    wechat = payload.get("wechat") if isinstance(payload.get("wechat"), dict) else {"url": (payload.get("url") or "").strip()}
    rec = add_published(account_id=account_id, title=title, wechat=wechat, source=payload.get("source") if isinstance(payload.get("source"), dict) else {"from": "web"})
    return jsonify({"success": True, "item": rec})

@app.route("/api/gzh/topic_incubate", methods=["POST"])
def gzh_topic_incubate_api():
    """Generate today's topic candidates and append to data/gzh/topics.jsonl.

    Web button for “再生产/生成选题（落库）”. Safe to click repeatedly:
    - exact duplicates are skipped
    - similarity info is recorded in dedup metadata
    """
    ensure_dirs()
    payload = request.json or {}
    account_id = (payload.get("account_id") or "").strip()
    try:
        from scripts.gzh_four_stage import cmd_topic_incubate
        import argparse
        import io, contextlib, json as _json
        ns = argparse.Namespace(account_id=account_id)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cmd_topic_incubate(ns)
        out = buf.getvalue().strip()
        data = _json.loads(out) if out else {"ok": True}
        return jsonify({"success": True, "result": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



@app.route("/api/autotopic/run_once", methods=["POST"])
def autotopic_run_once():
    """手动触发一次自动选题流程。"""
    from scripts.autotopic import run_autotopic
    import subprocess

    config = load_json(AUTOTOPIC_FILE, {})
    accounts_data = load_json(ACCOUNTS_FILE, {"accounts": []})
    accounts = accounts_data.get("accounts", [])

    result = run_autotopic(config=config, accounts=accounts)

    if result.get("error"):
        return jsonify({"success": False, "error": result["error"]})

    # Save state for later selection parsing
    state_file = os.path.join(PROJECT_ROOT, "output", "autotopic_state.json")
    save_json(state_file, {
        "accounts": result["accounts"],
        "mode": result["mode"],
        "date": result.get("date", ""),
        "created_at": __import__('datetime').datetime.now().isoformat(),
    })

    # Compose message
    msg = result["message"]

    # Persist for debugging / later selection parsing
    pending_file = os.path.join(PROJECT_ROOT, "output", "autotopic_pending_msg.txt")
    os.makedirs(os.path.dirname(pending_file), exist_ok=True)
    with open(pending_file, "w", encoding="utf-8") as f:
        f.write(msg)

    # Send to Feishu group (sync so user gets immediate feedback)
    log_path = os.path.join(PROJECT_ROOT, "output", "notify.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    sent_message_id = ""
    try:
        with open(log_path, "a", encoding="utf-8") as logf:
            proc = subprocess.run(
                [
                    os.path.expanduser("~/.npm-global/bin/openclaw"), "message", "send",
                    "--channel", "feishu",
                    "--target", "chat:oc_c853e1bd8e54b506e6c9870642dbc7e0",
                    "--message", msg,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd="/home/lighthouse/.openclaw/workspace",
                timeout=30,
            )
            logf.write(proc.stdout + "\n")
            import re
            m = re.search(r"Message ID:\s*(\S+)", proc.stdout)
            if m:
                sent_message_id = m.group(1)
    except Exception as e:
        return jsonify({"success": False, "error": f"飞书发送失败: {e}"}), 500

    return jsonify({
        "success": True,
        "mode": result["mode"],
        "total_hot": result.get("total_hot", 0),
        "accounts_count": len(result.get("accounts", {})),
        "sent_message_id": sent_message_id,
        "message": msg,
    })


@app.route("/api/autotopic/self_prompts", methods=["GET"])
def autotopic_self_prompts():
    """获取自我生成类的 prompt（供 agent 调 AI 后回填）"""
    state_file = os.path.join(PROJECT_ROOT, "output", "autotopic_state.json")
    state = load_json(state_file, {})
    prompts = {}
    for label, data in state.get("accounts", {}).items():
        if data.get("self_prompt"):
            prompts[label] = {
                "account_id": data["account_id"],
                "account_name": data.get("account_name", ""),
                "self_title_count": data.get("self_title_count", 3),
                "prompt": data["self_prompt"],
            }
    return jsonify(prompts)


@app.route("/api/autotopic/self_titles", methods=["POST"])
def autotopic_fill_self_titles():
    """Agent 回填 AI 生成的自我选题标题"""
    data = request.json or {}
    # data: {"A": ["标题1", "标题2"], "B": ["标题1"]}
    state_file = os.path.join(PROJECT_ROOT, "output", "autotopic_state.json")
    state = load_json(state_file, {})

    from scripts.self_topics import save_title_to_history

    for label, titles in data.items():
        if label in state.get("accounts", {}):
            self_candidates = []
            for t in titles:
                t = t.strip()
                if t:
                    self_candidates.append({
                        "suggested_title": t,
                        "original_title": "",
                        "source": "自主选题",
                        "category": "self",
                        "score": 0,
                        "title_score": 0,
                    })
                    save_title_to_history(state["accounts"][label]["account_id"], t, "self")
            state["accounts"][label]["self_candidates"] = self_candidates

    save_json(state_file, state)

    # Re-generate message with self titles filled
    from scripts.autotopic import format_manual_message
    msg = format_manual_message(state.get("accounts", {}))

    # Save updated message
    pending_file = os.path.join(PROJECT_ROOT, "output", "autotopic_pending_msg.txt")
    with open(pending_file, "w") as f:
        f.write(msg)

    return jsonify({"success": True, "message": msg})


@app.route("/api/autotopic/select", methods=["POST"])
def autotopic_select():
    """解析用户选择（如 A1,B3），返回选定的文章任务列表。"""
    from scripts.autotopic import parse_selection

    data = request.json or {}
    text = data.get("selection", "").strip()
    if not text:
        return jsonify({"success": False, "error": "请提供选择，如 A1,B3"})

    state_file = os.path.join(PROJECT_ROOT, "output", "autotopic_state.json")
    state = load_json(state_file, {})
    accounts = state.get("accounts", {})
    if not accounts:
        return jsonify({"success": False, "error": "没有待选择的选题（请先执行选题）"})

    selections = parse_selection(text, accounts)
    if not selections:
        return jsonify({"success": False, "error": f"无法解析选择: {text}"})

    return jsonify({
        "success": True,
        "selections": selections,
        "count": len(selections),
    })


@app.route("/api/autotopic/generate", methods=["POST"])
def autotopic_generate():
    """为自动选题的选定文章创建并执行生成任务。

    请求体:
    - selections: [{"account_id", "title", "platform", ...}]  (来自 /select)
    - 或 mode: "auto" (自动模式，直接从 state 取 top N)
    """
    from scripts.article_service import create_generation_task, execute_generation_task

    data = request.json or {}
    tasks = []
    results = []

    if data.get("mode") == "auto":
        state_file = os.path.join(PROJECT_ROOT, "output", "autotopic_state.json")
        state = load_json(state_file, {})
        at_config = load_json(AUTOTOPIC_FILE, {})
        auto_count = at_config.get("auto_count", 3)

        for label, acc_data in state.get("accounts", {}).items():
            all_candidates = acc_data.get("candidates", []) + acc_data.get("self_candidates", [])
            for c in all_candidates[:auto_count]:
                try:
                    task = create_generation_task(
                        account_id=acc_data["account_id"],
                        keyword=c["suggested_title"],
                        source="autotopic_auto",
                        source_platform=c.get("source", ""),
                        hot_title=c.get("original_title", ""),
                        hot_url=c.get("url", ""),
                        do_web_search=bool(c.get("search_suggested")),
                    )
                    result = execute_generation_task(task)
                    results.append(result)
                except Exception as e:
                    results.append({"error": str(e), "keyword": c.get("suggested_title", "")})
    else:
        selections = data.get("selections", [])
        if not selections:
            return jsonify({"success": False, "error": "无选择项"})

        for sel in selections:
            try:
                task = create_generation_task(
                    account_id=sel["account_id"],
                    keyword=sel["title"],
                    source="autotopic_manual",
                    source_platform=sel.get("platform", ""),
                    hot_title=sel.get("original_title", ""),
                    hot_url=sel.get("url", ""),
                    do_web_search=bool(sel.get("search_suggested")),
                    push_to_draft=(sel.get("platform") == "wechat_mp"),
                    enqueue=False,
                )
                result = execute_generation_task(task)
                results.append(result)
            except Exception as e:
                results.append({"error": str(e), "keyword": sel.get("title", "")})

    return jsonify({
        "success": True,
        "tasks": [{
            "task_id": t.get("task_id", ""),
            "status": t.get("status", ""),
            "title": t.get("title", ""),
            "preview_url": t.get("preview_url", ""),
            "account_id": t.get("account_id", ""),
            "keyword": t.get("keyword", ""),
            "error": t.get("error"),
        } for t in results],
        "count": len(results),
    })


# -------------------------------------------------
# Writing Styles (风格模板) API
# -------------------------------------------------

@app.route("/api/writing_styles", methods=["GET"])
def get_writing_styles():
    """获取所有写作风格模板"""
    styles = load_json(STYLES_FILE, {"styles": []})
    return jsonify(styles.get("styles", []))


@app.route("/api/writing_styles", methods=["POST"])
def save_writing_styles():
    """保存全部写作风格模板"""
    data = request.json
    if isinstance(data, list):
        save_json(STYLES_FILE, {"styles": data})
    else:
        return jsonify({"success": False, "error": "需要数组格式"}), 400
    return jsonify({"success": True})


@app.route("/api/writing_style_preset/<preset_id>", methods=["GET"])
def get_writing_style_preset(preset_id):
    """获取预设写作风格（从 writers/*.yaml 加载）"""
    import yaml
    preset_file = os.path.join(PROJECT_ROOT, "writers", f"{preset_id}.yaml")
    if not os.path.exists(preset_file):
        return jsonify({"error": "预设不存在"}), 404
    with open(preset_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # Build style object with description from writing_prompt
    style = {
        "id": preset_id,
        "name": data.get("name", preset_id),
        "description": data.get("writing_prompt", ""),
    }
    # Append title formulas and quote templates to description
    extras = []
    if data.get("title_formulas"):
        extras.append("\n\n## 标题公式库\n")
        for tf in data["title_formulas"]:
            extras.append(f"### {tf.get('type', '')}")
            extras.append(f"模板：{tf.get('template', '')}")
            for ex in tf.get("examples", []):
                extras.append(f"  - {ex}")
    if data.get("quote_templates"):
        extras.append("\n\n## 金句模板\n")
        for q in data["quote_templates"]:
            extras.append(f"- {q}")
    if extras:
        style["description"] += "\n".join(extras)
    return jsonify(style)


# -------------------------------------------------
# Stats API — read from WeChat API
# -------------------------------------------------

@app.route("/api/stats/wechat", methods=["GET"])
def wechat_stats():
    """获取公众号已发布文章统计"""
    account_id = request.args.get("account_id", "")

    # Find account credentials
    accounts_data = load_json(ACCOUNTS_FILE, {"accounts": []})
    acc = None
    for a in accounts_data.get("accounts", []):
        if a.get("id") == account_id and a.get("platform") == "wechat_mp":
            acc = a
            break

    if not acc:
        cfg = load_config()
        appid = cfg.get("wechat_appid", "")
        secret = cfg.get("wechat_secret", "")
    else:
        cred = acc.get("credentials", {})
        appid = cred.get("appid", "")
        secret = cred.get("secret", "")

    if not appid or not secret:
        return jsonify({"success": False, "error": "未配置公众号凭证（请在 Accounts 页面填写 AppID 和 Secret）", "articles": []})

    try:
        import urllib.request
        # Get access_token
        token_url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={appid}&secret={secret}"
        with urllib.request.urlopen(token_url, timeout=10) as resp:
            token_data = json.loads(resp.read().decode())

        access_token = token_data.get("access_token")
        if not access_token:
            errmsg = token_data.get("errmsg", "unknown")
            errcode = token_data.get("errcode", "")
            return jsonify({"success": False, "error": f"获取token失败: {errmsg} (errcode={errcode})", "articles": []})

        # Get published articles (freepublish/batchget) — NOT drafts
        pub_url = f"https://api.weixin.qq.com/cgi-bin/freepublish/batchget?access_token={access_token}"
        req = urllib.request.Request(pub_url, data=json.dumps({"offset": 0, "count": 20, "no_content": 1}).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=10) as resp:
            pub_data = json.loads(resp.read().decode())

        articles = []
        for item in pub_data.get("item", []):
            for art in item.get("content", {}).get("news_item", []):
                articles.append({
                    "title": art.get("title", ""),
                    "digest": art.get("digest", ""),
                    "update_time": item.get("update_time", 0),
                    "url": art.get("url", ""),
                })

        return jsonify({
            "success": True,
            "account_id": account_id or "global",
            "total_count": pub_data.get("total_count", 0),
            "articles": articles[:20],
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e), "articles": []})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5100, debug=False, threaded=True)
