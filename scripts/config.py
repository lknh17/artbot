#!/usr/bin/env python3
"""统一配置管理"""
import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "..", "config.json")

_defaults = {
    "wechat_appid": "",
    "wechat_secret": "",
    "hunyuan_secret_id": "",
    "hunyuan_secret_key": "",
    "hunyuan_region": "ap-guangzhou",
    "default_theme": "snow-cold",
    "image_style_prefix": "简约中式动画风格，扁平插画，柔和色彩，干净线条，",
    "cover_resolution": "1024:768",
    "inline_resolution": "1024:1024",
    "num_inline_images": 2,
    "md2wechat_run_sh": os.path.join(os.path.dirname(__file__), "..", "skills", "md2wechat", "scripts", "run.sh"),
    "output_dir": os.path.join(os.path.dirname(__file__), "..", "output"),
    # Feishu notify target for artbot worker/web (optional)
    # Example: "chat:oc_xxx" (preferred). If empty, worker will fallback to current group.
    "feishu_target": "",

    # LLM routing (artbot)
    # - openclaw: route all LLM calls through a configured OpenClaw agent (uses token/OAuth login providers too)
    # - moonshot: direct API call (requires Moonshot API key)
    "llm_backend": "openclaw",
    "openclaw_agent_id": "writing",
    "openclaw_timeout": 90,
}

def load_config() -> dict:
    """Load config: file overrides defaults, env vars override file."""
    cfg = dict(_defaults)
    
    # Load from file
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            cfg.update(json.load(f))
    
    # Env overrides
    env_map = {
        "WECHAT_APPID": "wechat_appid",
        "WECHAT_SECRET": "wechat_secret",
        "HUNYUAN_SECRET_ID": "hunyuan_secret_id",
        "HUNYUAN_SECRET_KEY": "hunyuan_secret_key",
        "HUNYUAN_REGION": "hunyuan_region",
        "IMAGE_STYLE_PREFIX": "image_style_prefix",
        "DEFAULT_THEME": "default_theme",
    }
    for env_key, cfg_key in env_map.items():
        val = os.environ.get(env_key)
        if val:
            cfg[cfg_key] = val
    
    return cfg

def save_config(cfg: dict):
    """Save config to file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def get(key: str, default=None):
    return load_config().get(key, default)

if __name__ == "__main__":
    cfg = load_config()
    print(json.dumps({k: v[:10]+"..." if isinstance(v,str) and len(v)>20 else v for k,v in cfg.items()}, ensure_ascii=False, indent=2))
