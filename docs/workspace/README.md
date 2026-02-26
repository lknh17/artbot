# Workspace 目录结构

本目录按功能模块化组织，便于维护和管理。

## 📁 目录结构

```
~/.openclaw/workspace/
│
├── 📂 tools/                  # 工具脚本和程序
│   └── 📂 browser/            # 浏览器自动化工具
│       ├── browser_controller.py    # 浏览器控制类
│       ├── start_browser.sh         # 快速启动脚本
│       └── README.md                # 工具说明
│
├── 📂 artbot/docs/workspace/  # 已归档的 workspace 文档（与公众号/自动化相关）
│   ├── BROWSER_SETUP.md       # 浏览器设置文档
│   └── ...
│
├── 📂 assets/                 # 生成的资源文件
│   └── 📂 screenshots/        # 网页截图
│       ├── baidu_screenshot.png
│       ├── test_headless.png
│       └── test_headed.png
│
├── 📂 memory/                 # 记忆和日志文件
│
├── 📂 skills/                 # OpenClaw 技能
│
├── 📂 qqbot/                  # QQ 机器人相关
│
├── 📂 templates/              # 模板文件
│
├── 📂 venv/                   # Python 虚拟环境
│
└── 📄 README.md               # 本文档
```

## 🚀 快速导航

### 浏览器自动化
```bash
# 快速启动浏览器环境
~/.openclaw/workspace/tools/browser/start_browser.sh

# 使用浏览器控制器
python3 ~/.openclaw/workspace/tools/browser/browser_controller.py --help

# 查看文档
cat ~/.openclaw/workspace/artbot/docs/workspace/BROWSER_SETUP.md
```

### 截图文件
```bash
# 查看所有截图
ls -la ~/.openclaw/workspace/assets/screenshots/
```

## 📝 注意事项

1. **不要直接在根目录添加新文件** - 请按功能放入对应子目录
2. **截图和临时文件** - 请放入 `assets/` 目录
3. **文档** - 公众号/自动化相关文档统一放入 `artbot/docs/`
4. **工具脚本** - 请放入 `tools/` 目录，按功能分子目录

## 🔧 维护

如需整理文件，请遵循以下原则：
- 按功能/用途分类
- 保持目录层级不超过 3 层
- 每个目录添加 README.md 说明用途
