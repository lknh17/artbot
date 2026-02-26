#!/usr/bin/env python3
"""ArtBot 测试套件

覆盖：article_service, autotopic, self_topics, html_renderer, config, llm
"""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.config import load_config, _defaults
from scripts.html_renderer import render_article, THEMES, list_themes
from scripts.article_service import (
    build_article_prompt, build_title_prompt, build_cover_prompt,
    build_inline_prompt, save_article,
)
from scripts.autotopic import (
    match_topics_for_account, format_manual_message, parse_selection,
)
from scripts.self_topics import build_self_title_prompt


# ─── Config ───────────────────────────────────────────────

class TestConfig(unittest.TestCase):
    def test_defaults_exist(self):
        for key in ["wechat_appid", "wechat_secret", "default_theme"]:
            self.assertIn(key, _defaults)

    def test_load_config(self):
        cfg = load_config()
        self.assertIsInstance(cfg, dict)
        self.assertIn("default_theme", cfg)

    def test_env_override(self):
        with patch.dict(os.environ, {"DEFAULT_THEME": "test-theme"}):
            self.assertEqual(load_config()["default_theme"], "test-theme")


# ─── HTML Renderer ────────────────────────────────────────

class TestHTMLRenderer(unittest.TestCase):
    def test_has_many_themes(self):
        self.assertGreater(len(THEMES), 10)

    def test_list_themes(self):
        self.assertIsInstance(list_themes(), dict)

    def test_render_basic(self):
        html = render_article("标题", "副标题",
            [{"title": "段落一", "paragraphs": ["正文"]}], [], "snow-cold")
        self.assertIn("标题", html)
        self.assertIn("正文", html)

    def test_render_all_themes(self):
        for key in THEMES:
            html = render_article("T", "S", [{"title": "S", "paragraphs": ["P"]}], [], key)
            self.assertGreater(len(html), 100)

    def test_render_with_images(self):
        html = render_article("T", "",
            [{"title": "S1", "paragraphs": ["P"]}, {"title": "S2", "paragraphs": ["P"]}],
            [{"after_section": 0, "url": "http://img/1.jpg", "caption": ""}], "snow-cold")
        self.assertIn("img", html)

    def test_cover_rendered_when_provided(self):
        html = render_article("T", "", [{"title": "S", "paragraphs": ["P"]}],
            [], "snow-cold", cover_url="http://example.com/cover.jpg")
        self.assertIn("example.com/cover.jpg", html)


# ─── Article Service ──────────────────────────────────────

class TestArticleService(unittest.TestCase):
    def setUp(self):
        self.acc = {
            "id": "test", "name": "测试", "platform": "wechat_mp",
            "profile": {
                "domain": "科技", "persona": "观察者", "audience": "程序员",
                "tone": "理性", "tone_keywords": "",
                "writing_style": {"mimic_style": ""},
                "title_config": {"style_desc": "简洁", "hotspot_ratio": "balanced", "extra": ""},
                "image": {"cover_prompt": "科技风格", "inline_prompt": "", "inline_count": 2},
            },
        }

    def test_build_article_prompt_contains_keyword(self):
        p = build_article_prompt(self.acc, "AI趋势")
        self.assertIn("AI趋势", p)
        self.assertIn("JSON", p)

    def test_build_title_prompt(self):
        p = build_title_prompt(self.acc, "AI趋势", "百度")
        self.assertIn("AI趋势", p)

    def test_build_cover_prompt(self):
        p = build_cover_prompt(self.acc, "标题", "摘要")
        self.assertIn("标题", p)

    def test_build_inline_prompt(self):
        p = build_inline_prompt(self.acc, "标题", "段落", "概要")
        self.assertIn("段落", p)

    def test_save_article(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("scripts.article_service.OUTPUT_DIR", tmpdir), \
                 patch("scripts.article_service.load_account", return_value=self.acc):
                r = save_article("test", {"title": "测试", "sections": []}, "kw", "manual")
                self.assertIn("dirname", r)
                self.assertTrue(os.path.exists(r["json_path"]))

    def test_hotspot_ratios_vary(self):
        prompts = {}
        for ratio in ["hot_dominant", "balanced", "self_dominant", "self_only"]:
            acc = json.loads(json.dumps(self.acc))
            acc["profile"]["title_config"]["hotspot_ratio"] = ratio
            prompts[ratio] = build_title_prompt(acc, "话题", "微博")
        # At least some should differ
        self.assertGreater(len(set(prompts.values())), 1)


# ─── Autotopic ────────────────────────────────────────────

class TestAutotopic(unittest.TestCase):
    def test_match_topics(self):
        hot = [{"title": "AI来了", "source": "百度", "score": 100, "platform": "百度热搜", "rank": 1}]
        acc = {"id": "t", "profile": {"domain": "科技", "persona": "x", "audience": "y"}}
        r = match_topics_for_account(hot, acc, count=2)
        self.assertIsInstance(r, list)

    def test_parse_selection(self):
        # Current behavior: for a single account label (A), only one selection is accepted.
        accounts = {
            "A": {
                "account_id": "mp", "account_name": "测试", "platform": "wechat_mp",
                "candidates": [{"suggested_title": "t1", "source": "百度"}],
                "self_candidates": [{"suggested_title": "t2", "source": "self"}],
            }
        }
        r = parse_selection("A1,A2", accounts)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0]["title"], "t1")

    def test_parse_selection_empty(self):
        self.assertEqual(parse_selection("", {}), [])

    def test_format_message(self):
        accounts = {
            "A": {
                "account_id": "mp", "account_name": "测试",
                "candidates": [{"suggested_title": "热点1", "source": "百度", "category": "hot"}],
                "self_candidates": [{"suggested_title": "自主1", "source": "self", "category": "self"}],
            }
        }
        msg = format_manual_message(accounts)
        # Message should include at least one candidate title
        self.assertTrue(("热点1" in msg) or ("自主1" in msg))


# ─── Self Topics ──────────────────────────────────────────

class TestSelfTopics(unittest.TestCase):
    def test_build_prompt(self):
        acc = {"id": "t", "profile": {"domain": "生活", "persona": "x", "audience": "y", "tone": "z"}}
        p = build_self_title_prompt(acc, count=3)
        self.assertIn("3", p)
        self.assertTrue(len(p) > 50)


# ─── LLM ──────────────────────────────────────────────────

class TestLLM(unittest.TestCase):
    @patch("scripts.llm.urllib.request.urlopen")
    def test_chat_mock(self, mock_urlopen):
        from scripts.llm import chat
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "回复"}}]}
        ).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        self.assertEqual(chat("hi"), "回复")


if __name__ == "__main__":
    unittest.main()
