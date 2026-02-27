#!/usr/bin/env python3
"""
主流水线编排模块
串联所有模块，提供完整的文章生成流水线
注意：文章撰写和语义分析由 AI 中枢完成，此模块负责执行层编排
"""
import json
import os
import sys
from datetime import datetime
from . import config
from .image_gen import generate_cover, generate_inline
from .wechat_uploader import upload_image, create_draft
from .html_renderer import render_article, list_themes


def execute_pipeline(
    title: str,
    digest: str,
    subtitle: str,
    sections: list,
    cover_prompt: str,
    inline_prompts: list = None,
    theme: str = None,
    push_draft: bool = True,
    style_prefix: str = None,
    cover_resolution: str | None = None,
    inline_resolution: str | None = None,
    inline_count: int | None = None,
    inline_prompt_extra: str | None = None,
    output_dir_override: str | None = None,
    wechat_appid: str | None = None,
    wechat_secret: str | None = None,
    debug_extras: dict | None = None,
) -> dict:
    """
    执行文章发布流水线（生图→上传→排版→推送）
    
    AI 中枢负责：写文章、选主题、写提示词、选插图位置
    本函数负责：调用工具执行
    
    Args:
        title: 文章标题
        digest: 文章摘要
        subtitle: 开头引言
        sections: [{"title": "段标题", "paragraphs": ["p1"...], "type": "normal"}]
        cover_prompt: 封面图提示词（不含风格前缀）
        inline_prompts: [{"after_section": 0, "prompt": "...", "caption": "..."}]
        theme: 主题名，None 则用配置默认
        push_draft: 是否推送到微信草稿箱
        style_prefix: 图片风格前缀覆盖
    
    Returns: {title, media_id, draft_url, images, html_path, ...}
    """
    cfg = config.load_config()
    output_dir = output_dir_override or cfg["output_dir"]
    os.makedirs(output_dir, exist_ok=True)
    
    theme = theme or cfg.get("default_theme", "snow-cold")
    inline_prompts = inline_prompts or []

    # If caller didn't provide inline_prompts but requested images, auto-create prompts
    if (not inline_prompts) and (inline_count is not None and inline_count > 0):
        # evenly pick sections to attach images
        picks = []
        if sections:
            step = max(1, len(sections) // max(1, inline_count))
            idx = 0
            while len(picks) < inline_count and idx < len(sections):
                picks.append(idx)
                idx += step

        # Always place the first inline image right after header for better公众号体验
        if inline_count and inline_count > 0:
            if not picks:
                picks = [-1]
            else:
                picks[0] = -1
        # fallback: after_section 0..inline_count-1
        if not picks:
            picks = list(range(inline_count))

        extra = (inline_prompt_extra or "").strip()
        for i, si in enumerate(picks, 1):
            if si == -1:
                sec = {}
                sec_title = ""
                base_topic = title
            else:
                sec = sections[min(si, len(sections)-1)] if sections else {}
                sec_title = (sec.get("title") or "").strip()
                # Keep prompts short: Hunyuan rejects overly-long text.
                # Avoid pasting paragraph text; use title-like semantic keywords instead.
                base_topic = sec_title or title
            base_prompt = f"{base_topic}，扁平插画，主体明确，留白干净，视觉吸引力强"

            # Avoid duplicating style prefix: style_prefix will be applied in image_gen.
            full = base_prompt
            if extra and (extra not in full) and (extra != cfg.get("image_style_prefix", "")):
                full = (full + "。" + extra).strip()

            # Hard clamp to reduce TextLengthExceed risks.
            if len(full) > 120:
                full = full[:120]
            inline_prompts.append({
                "after_section": min(si, max(0, len(sections)-1)) if sections else 0,
                "prompt": full,
                "caption": sec_title or "",
            })

    result = {"title": title, "theme": theme, "images": []}

    # Write a debug snapshot early (will be updated later)
    debug_path = os.path.join(output_dir, "pipeline_debug.json")
    debug = {
        "title": title,
        "theme": theme,
        "push_draft": push_draft,
        "style_prefix": style_prefix,
        "cover_resolution": cover_resolution,
        "inline_resolution": inline_resolution,
        "inline_count": inline_count,
        "inline_prompt_extra": inline_prompt_extra,
        "cover_prompt": cover_prompt,
        "inline_prompts": inline_prompts,
        "created_at": datetime.now().isoformat(),
    }
    if isinstance(debug_extras, dict) and debug_extras:
        # Shallow-merge, caller controlled.
        debug.update(debug_extras)
    try:
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(debug, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    
    # 1. 生成封面图
    print("[pipeline] Step 1: Generating cover image...", file=sys.stderr)
    cover = generate_cover(cover_prompt, output_dir, style_prefix, resolution=cover_resolution)
    result["images"].append({"type": "cover", **cover})
    debug["cover"] = {**cover}
    
    # 2. 生成插图
    for i, ip in enumerate(inline_prompts):
        print(f"[pipeline] Step 2.{i+1}: Generating inline image {i+1}...", file=sys.stderr)
        img = generate_inline(ip["prompt"], output_dir, i+1, style_prefix, resolution=inline_resolution)
        result["images"].append({"type": "inline", "after_section": ip["after_section"], **img})
        debug.setdefault("inline_images", []).append({"after_section": ip["after_section"], **img})
    
    # 3. 上传所有图片到微信（如果失败则降级为本地预览链接）
    print("[pipeline] Step 3: Uploading images to WeChat...", file=sys.stderr)

    def _local_preview_url(path: str) -> str:
        # Convert /.../output/<dir>/<file> -> /art/api/preview/<dir>/<file>
        try:
            rel = os.path.relpath(path, cfg["output_dir"]).replace("\\", "/")
        except Exception:
            rel = os.path.basename(path)
        return f"/art/api/preview/{rel}"

    cover_upload = {"media_id": "", "wechat_url": ""}
    try:
        cover_upload = upload_image(cover["path"], wechat_appid=wechat_appid, wechat_secret=wechat_secret)
        result["cover_media_id"] = cover_upload.get("media_id", "")
    except Exception as e:
        result["cover_media_id"] = ""
        result["cover_upload_error"] = str(e)

    image_inserts = []
    for i, ip in enumerate(inline_prompts):
        img_path = os.path.join(output_dir, f"inline_{i+1}.jpg")
        url = ""
        try:
            upload_result = upload_image(img_path, wechat_appid=wechat_appid, wechat_secret=wechat_secret)
            url = upload_result.get("wechat_url", "")
            debug.setdefault("inline_uploads", []).append({"index": i+1, **upload_result})
        except Exception as e:
            # fallback to local preview url
            url = _local_preview_url(img_path)
            result.setdefault("inline_upload_errors", []).append({"index": i+1, "error": str(e)})
            debug.setdefault("inline_upload_errors", []).append({"index": i+1, "error": str(e)})
        image_inserts.append({
            "after_section": ip["after_section"],
            "url": url,
            "caption": ip.get("caption", ""),
        })
    
    # 4. HTML 渲染
    print("[pipeline] Step 4: Rendering HTML...", file=sys.stderr)
    cover_url = cover_upload.get("wechat_url", "") if cover_upload else ""
    if not cover_url:
        cover_url = _local_preview_url(cover.get("path", ""))

    html = render_article(title, subtitle, sections, image_inserts, theme, cover_url=cover_url, include_cover_in_body=False)
    
    html_path = os.path.join(output_dir, "article.html")
    with open(html_path, "w") as f:
        f.write(html)
    result["html_path"] = html_path
    
    # 5. 推送草稿（需要 cover_media_id）
    if push_draft:
        if not result.get("cover_media_id"):
            result["draft"] = {"success": False, "error": "cover_media_id 为空（图片上传失败），无法创建微信草稿"}
            debug["draft"] = result["draft"]
        else:
            print("[pipeline] Step 5: Creating WeChat draft...", file=sys.stderr)
            draft = create_draft(title, html, result["cover_media_id"], digest, wechat_appid=wechat_appid, wechat_secret=wechat_secret)
            result["draft"] = draft
            debug["draft"] = draft
            try:
                with open(os.path.join(output_dir, "wechat_draft.json"), "w", encoding="utf-8") as f:
                    json.dump(draft, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
    
    # Update debug file at the end
    try:
        debug["done_at"] = datetime.now().isoformat()
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(debug, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    print("[pipeline] Done!", file=sys.stderr)
    return result


if __name__ == "__main__":
    print("Pipeline module. Use via AI orchestrator or import.")
    print(f"Available themes: {json.dumps(list_themes(), ensure_ascii=False)}")
