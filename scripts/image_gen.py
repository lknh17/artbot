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

    Fallback behavior:
    - If Hunyuan credentials are missing/invalid or API fails, generate a local placeholder JPG
      so the pipeline can continue (HTML preview still works; WeChat upload may still fail).
    """

    def _parse_res(res: str) -> tuple[int, int]:
        try:
            w, h = (res or "").split(":", 1)
            return int(w), int(h)
        except Exception:
            return 1024, 1024

    def _make_placeholder(path: str, res: str, text: str) -> None:
        from PIL import Image, ImageDraw, ImageFont

        w, h = _parse_res(res)
        img = Image.new("RGB", (w, h), (245, 245, 245))
        draw = ImageDraw.Draw(img)

        # Basic typography: use default bitmap font (portable)
        font = ImageFont.load_default()
        pad = 24
        msg = (text or "").strip()[:200]
        msg = "[placeholder image]\n" + msg

        # crude wrapping
        lines = []
        line = ""
        for ch in msg:
            if ch == "\n":
                lines.append(line)
                line = ""
                continue
            if len(line) >= 48:
                lines.append(line)
                line = ""
            line += ch
        if line:
            lines.append(line)

        y = pad
        for ln in lines[:18]:
            draw.text((pad, y), ln, fill=(60, 60, 60), font=font)
            y += 16

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        img.save(path, format="JPEG", quality=92)

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

    # Fast path: missing creds -> placeholder
    if not os.environ.get("HUNYUAN_SECRET_ID") or not os.environ.get("HUNYUAN_SECRET_KEY"):
        _make_placeholder(output_path, resolution, full_prompt)
        return {
            "success": True,
            "url": "",
            "path": output_path,
            "prompt": full_prompt,
            "fallback": "placeholder_missing_hunyuan_credentials",
        }

    try:
        job_id = submit_job(full_prompt, resolution)
        url = poll_job(job_id)
        download(url, output_path)
        return {"success": True, "url": url, "path": output_path, "prompt": full_prompt}
    except SystemExit:
        # hunyuan_image uses sys.exit(1) on API errors
        _make_placeholder(output_path, resolution, full_prompt)
        return {
            "success": True,
            "url": "",
            "path": output_path,
            "prompt": full_prompt,
            "fallback": "placeholder_hunyuan_error",
        }
    except Exception as e:
        _make_placeholder(output_path, resolution, full_prompt)
        return {
            "success": True,
            "url": "",
            "path": output_path,
            "prompt": full_prompt,
            "fallback": "placeholder_exception",
            "error": str(e),
        }


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
