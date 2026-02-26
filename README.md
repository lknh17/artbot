# ArtBot 🤖🎨

AI 驱动的公众号内容创作系统。从热点追踪、智能选题、AI 写作、AI 配图到一键发布草稿箱，全流程自动化。

## 工作流程

```
热点采集(trend) → 智能选题 → AI 写作 → AI 配图 → HTML 排版 → 推送草稿箱
     9:00           10:00      ← 飞书群确认后自动执行 →
```

### 三种生成模式

1. **自动选题 · 人工确认** — 每天定时推送选题到飞书群，回复编号（如 `A1`）即开始生成
2. **自动选题 · 全自动** — 系统自动选择 Top N 话题，直接生成文章
3. **手动指定** — 通过 Web 控制台 Jobs 页面输入关键词触发

## 系统架构

```
┌─────────────────────────────────────────────────┐
│  OpenClaw Agent (调度中枢)                        │
│  · 定时触发 (cron)                                │
│  · 飞书群交互                                     │
│  · 任务编排                                       │
└──────────┬──────────────────────────────┬────────┘
           │                              │
    ┌──────▼──────┐              ┌────────▼────────┐
    │  Web 控制台  │              │  Python 后端     │
    │  Flask + SPA │              │                  │
    │  /art        │              │  autotopic.py    │ ← 选题引擎
    └─────────────┘              │  article_service │ ← 文章生成
                                 │  pipeline.py     │ ← 流水线编排
                                 │  llm.py          │ ← LLM 调用
                                 │  image_gen.py    │ ← AI 配图
                                 │  html_renderer   │ ← 排版渲染
                                 │  wechat_uploader │ ← 公众号 API
                                 └─────────────────┘
```

## 目录结构

```
artbot/
├── web/                    # Web 控制台
│   ├── app.py              # Flask 应用 (API + 静态文件)
│   └── static/index.html   # 单页前端 (Jobs/Accounts/Profiles/Layouts/选题/Stats/Settings)
│
├── scripts/                # 核心业务逻辑
│   ├── autotopic.py        # 自动选题引擎 (热点匹配 + AI 标题生成)
│   ├── article_service.py  # 统一文章生成入口 (prompt 构建 + 任务管理)
│   ├── pipeline.py         # 流水线编排 (写作→配图→排版→发布)
│   ├── llm.py              # LLM 调用 (Moonshot API)
│   ├── image_gen.py        # AI 图片生成调度
│   ├── hunyuan_image.py    # 腾讯混元图片生成 API
│   ├── html_renderer.py    # HTML 排版引擎 (15+ 主题)
│   ├── wechat_uploader.py  # 微信公众号 API (上传素材 + 创建草稿)
│   ├── config.py           # 配置加载
│   └── self_topics.py      # 自主话题生成
│
├── config/                 # 配置文件 (gitignore)
│   ├── accounts.json       # 公众号账号配置 (AppID/Secret/Profile)
│   ├── autotopic.json      # 自动选题配置 (模式/调度/热点源/过滤)
│   └── writing_styles.json # 写作风格配置
│
├── themes/                 # 排版主题 YAML (15+ 主题)
├── writers/                # 写作风格模板
├── tools/store/            # JSON 持久化工具
├── tests/                  # 测试套件
│
├── output/                 # 生成产物 (gitignore)
│   └── {account}_{date}_{nn}/
│       ├── article.html    # 排版后的文章
│       ├── article.json    # 文章元数据
│       ├── cover.jpg       # 封面图
│       └── inline_*.jpg    # 插图
│
└── skills/md2wechat/       # OpenClaw Skill (Markdown→公众号转换)
```

## Web 控制台

运行在 `http://localhost:5100`，包含以下页面：

| 页面 | 功能 |
|------|------|
| **Jobs** | 手动触发文章生成，查看草稿列表，推送到公众号草稿箱 |
| **Accounts** | 管理公众号账号 (AppID/Secret)，支持多账号 |
| **Profiles** | 配置账号人设、领域、受众、语气、写作风格 |
| **Layouts** | 预览 15+ 排版主题，实时 iframe 渲染 |
| **自动选题** | 配置选题模式、调度时间、热点源、关键词过滤 |
| **Stats** | 公众号已发布文章统计 |
| **Settings** | 全局配置 (混元 API 等) |

## 快速开始

### 1. 环境准备

```bash
pip install flask requests
```

### 2. 配置账号

复制示例配置并填入公众号凭证：

```bash
cp config/accounts.schema.json config/accounts.json
# 编辑 accounts.json，填入 AppID 和 Secret
```

### 3. 配置环境变量

```bash
export HUNYUAN_SECRET_ID="your-tencent-cloud-secret-id"
export HUNYUAN_SECRET_KEY="your-tencent-cloud-secret-key"
```

### 4. 启动 Web 控制台

```bash
python web/app.py
# → http://localhost:5100
```

### 5. 配合 OpenClaw 使用

项目设计为与 [OpenClaw](https://github.com/openclaw/openclaw) Agent 配合使用：
- Agent 通过 cron 定时触发热点采集和自动选题
- 选题结果推送到飞书群，用户回复编号确认
- Agent 调用生成 pipeline 完成文章创作和发布

## API 参考

| 方法 | 路径 | 说明 |
|------|------|------|
| GET/POST | `/api/autotopic` | 自动选题配置 |
| POST | `/api/autotopic/run_once` | 执行一次选题 |
| POST | `/api/autotopic/generate` | 为选定项生成文章 |
| POST | `/api/generate` | 手动生成文章 |
| GET | `/api/drafts` | 草稿列表 |
| POST | `/api/drafts/<name>/push` | 推送到公众号草稿箱 |
| GET | `/api/status` | 任务队列状态 |
| POST | `/api/layout/preview` | 主题预览 |
| GET | `/api/preview/<path>` | 文章预览 |
| GET | `/api/accounts` | 账号列表 |
| GET | `/api/writers` | 写作风格列表 |
| GET | `/api/platforms` | 平台列表 |
| GET | `/api/stats/wechat` | 公众号统计 |

## 技术栈

- **后端**: Python 3 / Flask
- **前端**: 原生 HTML + CSS + JS (单文件 SPA)
- **LLM**: Moonshot API (文章写作 + 标题生成)
- **图片生成**: 腾讯混元
- **排版**: 自研 HTML 渲染引擎 (15+ 主题)
- **调度**: OpenClaw Cron
- **交互**: 飞书群消息

## License

MIT
