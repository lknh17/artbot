#!/usr/bin/env python3
"""HTML排版渲染模块 - 多主题支持"""
import json
import sys

THEMES = {
    # === 经典卡片系列 ===
    "snow-cold": {
        "name": "雪日冷调",
        "bg": "#f5f7fa",
        "card_bg": "#ffffff",
        "primary": "#4a6fa5",
        "accent": "#3a5a8c",
        "text": "#3a4a5c",
        "shadow": "rgba(100,130,180,0.3)",
        "quote_bg": "#eef3fa",
        "layout": "card",
    },
    "autumn-warm": {
        "name": "秋日暖光",
        "bg": "#faf9f5",
        "card_bg": "#ffffff",
        "primary": "#d97758",
        "accent": "#c06b4d",
        "text": "#4a413d",
        "shadow": "rgba(217,119,88,0.4)",
        "quote_bg": "#fef4e7",
        "layout": "card",
    },
    "spring-fresh": {
        "name": "春日清新",
        "bg": "#f5faf5",
        "card_bg": "#ffffff",
        "primary": "#5a9e6f",
        "accent": "#4a8a5f",
        "text": "#3a4a3d",
        "shadow": "rgba(90,158,111,0.3)",
        "quote_bg": "#eef7f0",
        "layout": "card",
    },
    "deep-ocean": {
        "name": "深海静谧",
        "bg": "#f0f4f8",
        "card_bg": "#ffffff",
        "primary": "#2c5282",
        "accent": "#1a365d",
        "text": "#2d3748",
        "shadow": "rgba(44,82,130,0.3)",
        "quote_bg": "#ebf4ff",
        "layout": "card",
    },
    "sunset-glow": {
        "name": "落日余晖",
        "bg": "#fdf8f4",
        "card_bg": "#ffffff",
        "primary": "#c05621",
        "accent": "#9c4221",
        "text": "#4a3728",
        "shadow": "rgba(192,86,33,0.3)",
        "quote_bg": "#fef0e4",
        "layout": "card",
    },
    # === 杂志风系列 - 大标题+左侧色条 ===
    "magazine-noir": {
        "name": "杂志·黑金",
        "bg": "#1a1a2e",
        "card_bg": "#16213e",
        "primary": "#e2b714",
        "accent": "#f0c040",
        "text": "#e0e0e0",
        "shadow": "rgba(226,183,20,0.15)",
        "quote_bg": "#1a1a2e",
        "layout": "magazine",
        "border_left": "#e2b714",
        "title_size": "32px",
    },
    "magazine-rose": {
        "name": "杂志·玫瑰",
        "bg": "#fff5f5",
        "card_bg": "#ffffff",
        "primary": "#c53030",
        "accent": "#9b2c2c",
        "text": "#4a2020",
        "shadow": "rgba(197,48,48,0.12)",
        "quote_bg": "#fff5f5",
        "layout": "magazine",
        "border_left": "#c53030",
        "title_size": "30px",
    },
    # === 极简系列 - 无卡片无阴影 ===
    "minimal-ink": {
        "name": "极简·水墨",
        "bg": "#fafafa",
        "card_bg": "transparent",
        "primary": "#333333",
        "accent": "#666666",
        "text": "#333333",
        "shadow": "none",
        "quote_bg": "#f5f5f5",
        "layout": "minimal",
        "divider": "1px solid #e0e0e0",
        "font_serif": True,
    },
    "minimal-cyan": {
        "name": "极简·青瓷",
        "bg": "#f8fffe",
        "card_bg": "transparent",
        "primary": "#0d9488",
        "accent": "#115e59",
        "text": "#334155",
        "shadow": "none",
        "quote_bg": "#f0fdfa",
        "layout": "minimal",
        "divider": "1px solid #99f6e4",
        "font_serif": False,
    },
    # === 渐变头图系列 ===
    "gradient-purple": {
        "name": "渐变·星空紫",
        "bg": "#f5f3ff",
        "card_bg": "#ffffff",
        "primary": "#7c3aed",
        "accent": "#5b21b6",
        "text": "#3b2e58",
        "shadow": "rgba(124,58,237,0.15)",
        "quote_bg": "#ede9fe",
        "layout": "gradient",
        "gradient": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
    },
    "gradient-ocean": {
        "name": "渐变·深海蓝",
        "bg": "#f0f9ff",
        "card_bg": "#ffffff",
        "primary": "#0369a1",
        "accent": "#075985",
        "text": "#1e3a5f",
        "shadow": "rgba(3,105,161,0.12)",
        "quote_bg": "#e0f2fe",
        "layout": "gradient",
        "gradient": "linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%)",
    },
    "gradient-sunset": {
        "name": "渐变·晚霞橙",
        "bg": "#fffbeb",
        "card_bg": "#ffffff",
        "primary": "#d97706",
        "accent": "#b45309",
        "text": "#451a03",
        "shadow": "rgba(217,119,6,0.12)",
        "quote_bg": "#fef3c7",
        "layout": "gradient",
        "gradient": "linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)",
    },
    # === 小红书专属系列 ===
    "xhs-sweet": {
        "name": "小红书·甜系粉",
        "bg": "#fff5f7",
        "card_bg": "#ffffff",
        "primary": "#ec4899",
        "accent": "#db2777",
        "text": "#4a2040",
        "shadow": "rgba(236,72,153,0.15)",
        "quote_bg": "#fce7f3",
        "layout": "xhs",
        "emoji_accent": True,
        "rounded": "20px",
    },
    "xhs-forest": {
        "name": "小红书·森系绿",
        "bg": "#f0fdf4",
        "card_bg": "#ffffff",
        "primary": "#16a34a",
        "accent": "#15803d",
        "text": "#1a3a2a",
        "shadow": "rgba(22,163,74,0.12)",
        "quote_bg": "#dcfce7",
        "layout": "xhs",
        "emoji_accent": True,
        "rounded": "20px",
    },
    "xhs-cream": {
        "name": "小红书·奶油白",
        "bg": "#fffdf7",
        "card_bg": "#ffffff",
        "primary": "#92400e",
        "accent": "#78350f",
        "text": "#44403c",
        "shadow": "rgba(146,64,14,0.1)",
        "quote_bg": "#fef9ee",
        "layout": "xhs",
        "emoji_accent": True,
        "rounded": "20px",
    },
}


def _card(content: str, t: dict) -> str:
    return f'''<section style="max-width: 800px; width: 100%; padding: 25px; background-color: {t['card_bg']}; border: 1px solid rgba(0,0,0,0.05); box-shadow: 0 10px 30px rgba(0,0,0,0.04), 0 0 15px {t['shadow']}; border-radius: 18px;">
{content}
</section>'''


def _image_block(url: str, caption: str = "") -> str:
    cap = f'\n<p style="color: rgba(0,0,0,0.3); font-size: 12px; margin-top: 8px;">{caption}</p>' if caption else ""
    return f'''<section style="max-width: 800px; width: 100%; text-align: center; padding: 5px 0;">
<img src="{url}" style="max-width: 100%; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.08);" />{cap}
</section>'''


def _placeholder_img(width=800, height=400, label="", primary="#4a6fa5"):
    """生成 SVG 占位图（内嵌 data URI，无需外部请求）"""
    label = label or "插图"
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
    <defs><linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
    <stop offset="0%" style="stop-color:{primary};stop-opacity:0.15"/>
    <stop offset="100%" style="stop-color:{primary};stop-opacity:0.05"/>
    </linearGradient></defs>
    <rect width="{width}" height="{height}" fill="url(#g)" rx="12"/>
    <text x="50%" y="45%" text-anchor="middle" fill="{primary}" font-family="sans-serif" font-size="24" opacity="0.6">📷 {label}</text>
    <text x="50%" y="58%" text-anchor="middle" fill="{primary}" font-family="sans-serif" font-size="14" opacity="0.35">{width}×{height}</text>
    </svg>'''
    import base64
    encoded = base64.b64encode(svg.encode()).decode()
    return f"data:image/svg+xml;base64,{encoded}"


def render_article(title: str, subtitle: str, sections: list, images: list = None, theme: str = "snow-cold", cover_url: str | None = None) -> str:
    """
    渲染完整文章HTML
    
    Args:
        title: 文章标题
        subtitle: 开头引言/副标题
        sections: [{"title": "段落标题", "paragraphs": ["p1", "p2"], "type": "normal"}]
                  type: normal, list, quote, highlight
        images: [{"after_section": 0, "url": "...", "caption": "..."}]
        theme: 主题名
    
    Returns: 完整 HTML 字符串
    """
    t = THEMES.get(theme, THEMES["snow-cold"])
    layout = t.get("layout", "card")
    images = images or []
    image_map = {img["after_section"]: img for img in images}

    # Auto-insert placeholder images if none provided (for preview)
    if not images and len(sections) >= 2:
        # Insert after section 0 and after the middle section
        mid = len(sections) // 2
        # Layout preview should show *inline* images (not cover-first)
        image_map[0] = {"url": _placeholder_img(800, 400, "文中插图 1", t["primary"]), "caption": "与段落内容相关的辅助配图"}
        image_map[mid] = {"url": _placeholder_img(800, 360, "文中插图 2", t["primary"]), "caption": "与段落内容相关的辅助配图"}
    
    font = "'Noto Serif SC', 'Source Han Serif CN', Georgia, serif" if t.get("font_serif") else "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    rounded = t.get("rounded", "18px")

    parts = [f'<div style="background-color: {t["bg"]}; padding: 40px 10px; font-family: {font}; font-size: 16px; line-height: 1.75; letter-spacing: 0.5px; display: flex; flex-direction: column; align-items: center; gap: {"24px" if layout == "minimal" else "40px"};">']
    
    # === GRADIENT layout: big gradient header ===
    if layout == "gradient":
        gradient = t.get("gradient", f"linear-gradient(135deg, {t['primary']} 0%, {t['accent']} 100%)")
        parts.append(f'''<section style="max-width: 800px; width: 100%; border-radius: {rounded}; overflow: hidden; box-shadow: 0 10px 40px {t['shadow']};">
<div style="background: {gradient}; padding: 50px 40px; text-align: center;">
<h1 style="font-size: 28px; font-weight: 800; color: #ffffff; margin: 0 0 12px 0; line-height: 1.4; text-shadow: 0 2px 10px rgba(0,0,0,0.2);">{title}</h1>
{f'<p style="color: rgba(255,255,255,0.85); font-size: 15px; margin:0; font-style:italic;">{subtitle}</p>' if subtitle else ''}
</div></section>''')
    # === MAGAZINE layout: big title + left border ===
    elif layout == "magazine":
        bl = t.get("border_left", t["primary"])
        ts = t.get("title_size", "30px")
        parts.append(f'''<section style="max-width: 800px; width: 100%; border-left: 6px solid {bl}; padding: 30px 35px; background: {t['card_bg']}; border-radius: 0 {rounded} {rounded} 0; box-shadow: 0 8px 30px {t['shadow']};">
<h1 style="font-size: {ts}; font-weight: 900; color: {t['primary']}; margin: 0 0 16px 0; line-height: 1.3; letter-spacing: 1px;">{title}</h1>
{f'<p style="color: {t["accent"]}; font-size: 16px; margin: 0 0 16px 0; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 16px; font-style: italic;">{subtitle}</p>' if subtitle else ''}
</section>''')
    # === MINIMAL layout: no card ===
    elif layout == "minimal":
        divider = t.get("divider", "1px solid #e0e0e0")
        parts.append(f'''<section style="max-width: 720px; width: 100%; padding: 20px 0;">
<h1 style="font-size: 26px; font-weight: 700; color: {t['primary']}; text-align: center; margin: 0 0 12px 0; line-height: 1.4;">{title}</h1>
{f'<p style="color: {t["accent"]}; text-align: center; font-size: 15px; margin: 0 0 20px 0; font-style: italic;">{subtitle}</p>' if subtitle else ''}
<hr style="border: none; border-top: {divider}; margin: 0;">
</section>''')
    # === XHS layout: rounded, emoji-friendly ===
    elif layout == "xhs":
        parts.append(f'''<section style="max-width: 720px; width: 100%; background: {t['card_bg']}; border-radius: {rounded}; padding: 28px 24px; box-shadow: 0 8px 25px {t['shadow']};">
<h1 style="font-size: 22px; font-weight: 800; color: {t['primary']}; text-align: center; margin: 0 0 8px 0; line-height: 1.5;">{title}</h1>
{f'<p style="color: {t["accent"]}; text-align: center; font-size: 14px; margin: 0;">{subtitle}</p>' if subtitle else ''}
</section>''')
    # === CARD layout (default) ===
    else:
        header = f'<h1 style="font-size: 24px; font-weight: 700; color: {t["primary"]}; text-align: center; margin-bottom: 20px; line-height: 1.4;">{title}</h1>'
        if subtitle:
            header += f'\n<blockquote style="background-color: {t["quote_bg"]}; border-left: 5px solid {t["primary"]}; padding: 15px 20px; margin: 20px 0; border-radius: 0 12px 12px 0;">\n<p style="color: {t["text"]}; margin: 0; font-style: italic;">{subtitle}</p>\n</blockquote>'
        header += f'\n<hr style="border: none; height: 1px; background-color: rgba(0,0,0,0.08); margin: 30px 0;">'
        parts.append(_card(header, t))

    # Optional cover image (for preview/JOBS; WeChat draft uses thumb_media_id separately)
    if cover_url:
        parts.append(_image_block(cover_url, ""))
    
    # Sections
    for i, sec in enumerate(sections):
        sec_title = sec.get("title", "")
        paragraphs = sec.get("paragraphs", [])
        
        content = ""
        if sec_title:
            if layout == "magazine":
                content += f'<h2 style="font-size: 20px; font-weight: 800; color: {t["primary"]}; margin-bottom: 14px; letter-spacing: 0.5px;">{sec_title}</h2>\n'
            elif layout == "minimal":
                content += f'<h2 style="font-size: 19px; font-weight: 600; color: {t["primary"]}; margin-bottom: 12px; margin-top: 8px;">{sec_title}</h2>\n'
            elif layout == "xhs":
                content += f'<h2 style="font-size: 17px; font-weight: 700; color: {t["primary"]}; margin-bottom: 10px;">{sec_title}</h2>\n'
            else:
                content += f'<h2 style="font-size: 20px; font-weight: 700; margin-bottom: 18px; padding-bottom: 10px; border-bottom: 1px dashed rgba(0,0,0,0.15);"><span style="color: {t["primary"]};">▶ </span><span style="color: {t["primary"]};">{sec_title}</span></h2>\n'
        
        for j, p in enumerate(paragraphs):
            is_last = j == len(paragraphs) - 1
            mb = "0" if is_last else "16px"
            
            if p.startswith("**") and p.endswith("**"):
                text = p.strip("*")
                content += f'<p style="color: {t["text"]}; margin-bottom: {mb}; text-align: center; font-size: 18px;"><strong style="color: {t["accent"]};">{text}</strong></p>\n'
            elif p.startswith("- ") or p.startswith("• "):
                content += f'<ul style="color: {t["text"]}; margin-bottom: {mb}; padding-left: 20px;">\n'
                content += f'<li style="margin-bottom: 8px;">{p.lstrip("- •").strip()}</li>\n'
                content += '</ul>\n'
            else:
                content += f'<p style="color: {t["text"]}; margin-bottom: {mb};">{p}</p>\n'
        
        if layout == "minimal":
            parts.append(f'<section style="max-width: 720px; width: 100%; padding: 0 0;">{content}</section>')
        elif layout in ("magazine", "xhs"):
            parts.append(f'''<section style="max-width: {'720px' if layout=='xhs' else '800px'}; width: 100%; {'border-left: 6px solid '+t.get("border_left",t["primary"])+';' if layout=='magazine' else ''} padding: {'20px 24px' if layout=='xhs' else '20px 35px'}; background: {t['card_bg']}; border-radius: {'0 '+rounded+' '+rounded+' 0' if layout=='magazine' else rounded}; box-shadow: 0 4px 15px {t['shadow']};">{content}</section>''')
        else:
            parts.append(_card(content, t))
        
        # Insert image after this section
        if i in image_map:
            img = image_map[i]
            parts.append(_image_block(img["url"], img.get("caption", "")))
    
    # Footer
    end_color = "rgba(255,255,255,0.3)" if layout == "magazine" and "noir" in theme else "rgba(0,0,0,0.2)"
    parts.append(f'''<section style="max-width: 800px; width: 100%; text-align: center; padding: 15px;">
<p style="color: {end_color}; font-size: 12px; margin: 0;">— END —</p>
</section>''')
    
    parts.append('</div>')
    
    return "\n\n".join(parts)


def list_themes() -> dict:
    return {k: v["name"] for k, v in THEMES.items()}


if __name__ == "__main__":
    print("Available themes:")
    for k, v in THEMES.items():
        print(f"  {k}: {v['name']}")
