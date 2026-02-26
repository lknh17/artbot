#!/usr/bin/env python3
"""图片生成模块 - 封装混元3.0 API"""
import os
import sys
from . import config
from .hunyuan_image import submit_job, poll_job, download

def generate_image(prompt: str, output_path: str, resolution="1024:1024", style_prefix=None) -> dict:
    """生成单张图片。

    - style_prefix: preferred from account profile (per-account)
    - fallback to legacy global config.image_style_prefix
    """
    cfg = config.load_config()
    if style_prefix is None:
        style_prefix = cfg.get("image_style_prefix", "")

    style_prefix = (style_prefix or "").strip()
    prompt = (prompt or "").strip()
    full_prompt = (style_prefix + " " + prompt).strip() if style_prefix else prompt
    
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    
    print(f"[image_gen] Generating: {full_prompt[:60]}...", file=sys.stderr)
    
    # 设置环境变量供 hunyuan_image 使用
    os.environ.setdefault("HUNYUAN_SECRET_ID", cfg.get("hunyuan_secret_id", ""))
    os.environ.setdefault("HUNYUAN_SECRET_KEY", cfg.get("hunyuan_secret_key", ""))
    
    job_id = submit_job(full_prompt, resolution)
    url = poll_job(job_id)
    download(url, output_path)
    
    return {"success": True, "url": url, "path": output_path, "prompt": full_prompt}


def generate_cover(prompt: str, output_dir: str, style_prefix=None, resolution: str | None = None) -> dict:
    """生成封面图（横版）"""
    cfg = config.load_config()
    path = os.path.join(output_dir, "cover.jpg")
    res = resolution or cfg.get("cover_resolution", "1024:768")
    return generate_image(prompt, path, res, style_prefix)


def generate_inline(prompt: str, output_dir: str, index: int, style_prefix=None, resolution: str | None = None) -> dict:
    """生成文中插图（方形）"""
    cfg = config.load_config()
    path = os.path.join(output_dir, f"inline_{index}.jpg")
    res = resolution or cfg.get("inline_resolution", "1024:1024")
    return generate_image(prompt, path, res, style_prefix)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.image_gen <prompt> [output] [resolution]")
        sys.exit(1)
    result = generate_image(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else "test.jpg", sys.argv[3] if len(sys.argv)>3 else "1024:1024")
    import json; print(json.dumps(result, ensure_ascii=False))
