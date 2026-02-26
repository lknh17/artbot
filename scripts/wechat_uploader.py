#!/usr/bin/env python3
"""微信上传与草稿管理模块"""
import json
import os
import subprocess
import sys
from . import config


def _extract_json_objects(text: str) -> list:
    """Extract JSON objects from a mixed stdout stream.

    md2wechat may print:
    - structured logs (each line is a JSON object)
    - a final *pretty-printed* JSON response spanning multiple lines

    This helper scans the whole text and returns any JSON objects it can decode.
    """
    objs = []
    dec = json.JSONDecoder()
    i = 0
    n = len(text)
    while i < n:
        # Find next object start
        j = text.find("{", i)
        if j == -1:
            break
        try:
            obj, end = dec.raw_decode(text[j:])
            if isinstance(obj, dict):
                objs.append(obj)
            i = j + end
        except json.JSONDecodeError:
            # Not a valid JSON object at this position; continue searching
            i = j + 1
    return objs


def _run_md2wechat(*args, wechat_appid: str | None = None, wechat_secret: str | None = None) -> dict:
    """调用 md2wechat 命令行。

    重要：不能按“逐行 json.loads”解析 stdout，因为最终结果通常是多行 pretty JSON。

    Credentials priority:
    - explicit wechat_appid/wechat_secret (per-account)
    - config.json defaults
    """
    cfg = config.load_config()
    run_sh = cfg["md2wechat_run_sh"]

    env = os.environ.copy()
    env["WECHAT_APPID"] = (wechat_appid or cfg.get("wechat_appid") or "")
    env["WECHAT_SECRET"] = (wechat_secret or cfg.get("wechat_secret") or "")

    cmd = ["bash", run_sh] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)

    if result.returncode != 0:
        raise RuntimeError(f"md2wechat failed: {result.stderr}")

    stdout = result.stdout or ""
    objs = _extract_json_objects(stdout)

    # Prefer the last object that looks like an API response
    for obj in reversed(objs):
        if isinstance(obj, dict) and ("data" in obj or "success" in obj):
            return obj

    # Fallback: try to parse the last JSON block from the end (covers some edge cases)
    tail = stdout.strip()
    if tail.endswith("}"):
        k = tail.rfind("{")
        if k != -1:
            try:
                obj = json.loads(tail[k:])
                if isinstance(obj, dict):
                    return obj
            except Exception:
                pass

    return {"raw_output": stdout}


def upload_image(image_path: str, wechat_appid: str | None = None, wechat_secret: str | None = None) -> dict:
    """上传图片到微信素材库，返回 {media_id, wechat_url}"""
    result = _run_md2wechat("upload_image", image_path, wechat_appid=wechat_appid, wechat_secret=wechat_secret)
    data = result.get("data", result)
    return {
        "media_id": data.get("media_id", ""),
        "wechat_url": data.get("wechat_url", ""),
    }


def create_draft(title: str, content_html: str, cover_media_id: str, digest: str, wechat_appid: str | None = None, wechat_secret: str | None = None) -> dict:
    """创建微信草稿"""
    cfg = config.load_config()
    output_dir = cfg["output_dir"]
    os.makedirs(output_dir, exist_ok=True)
    
    draft_path = os.path.join(output_dir, "draft.json")
    draft = {
        "articles": [{
            "title": title,
            "thumb_media_id": cover_media_id,
            "digest": digest,
            "content": content_html,
        }]
    }
    with open(draft_path, "w") as f:
        json.dump(draft, f, ensure_ascii=False)
    
    result = _run_md2wechat("create_draft", draft_path, wechat_appid=wechat_appid, wechat_secret=wechat_secret)
    data = result.get("data", result)
    return {
        "media_id": data.get("media_id", ""),
        "draft_url": data.get("draft_url", ""),
        "success": result.get("success", False),
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.wechat_uploader upload <image_path>")
        print("       python -m scripts.wechat_uploader draft <html_file> <cover_media_id> <title> <digest>")
        sys.exit(1)
    
    action = sys.argv[1]
    if action == "upload":
        r = upload_image(sys.argv[2])
    elif action == "draft":
        with open(sys.argv[2]) as f:
            html = f.read()
        r = create_draft(sys.argv[4], html, sys.argv[3], sys.argv[5] if len(sys.argv)>5 else "")
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)
    print(json.dumps(r, ensure_ascii=False, indent=2))
