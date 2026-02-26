# OpenClaw 浏览器自动化方案

## 概述

成功在服务端部署了基于 **Xvfb + Chromium** 的浏览器自动化方案，支持两种运行模式：

1. **无头模式 (Headless)** - 纯后台运行，无需图形界面
2. **有头模式 (Headed)** - 使用 Xvfb 虚拟桌面，支持可视化操作

## 安装组件

```bash
# 安装 Xvfb 和 Chromium
sudo apt-get update
sudo apt-get install -y xvfb chromium-browser

# 安装 Python 依赖
pip3 install websocket-client requests --break-system-packages
```

## 核心脚本位置

```
~/.openclaw/workspace/
├── tools/browser/
│   ├── browser_controller.py  # 浏览器控制类
│   └── start_browser.sh       # 快速启动脚本
├── docs/
│   └── BROWSER_SETUP.md       # 本文档
└── assets/screenshots/        # 截图存放
```

**`browser_controller.py`** - 浏览器控制类，支持：
- 启动/停止 Xvfb 虚拟桌面
- 启动/停止 Chromium 浏览器
- 导航到指定 URL
- 截取屏幕截图
- 获取页面信息

## 使用方式

### 1. 无头模式（推荐用于自动化任务）

```bash
python3 ~/.openclaw/workspace/tools/browser/browser_controller.py \
  --mode headless \
  --url https://www.example.com \
  --screenshot ~/.openclaw/workspace/assets/screenshots/example.png
```

### 2. 有头模式（需要 Xvfb）

```bash
python3 ~/.openclaw/workspace/tools/browser/browser_controller.py \
  --mode headed \
  --url https://www.example.com \
  --screenshot ~/.openclaw/workspace/assets/screenshots/example.png
```

### 3. 快速启动浏览器环境

```bash
~/.openclaw/workspace/tools/browser/start_browser.sh
```

## 集成到 OpenClaw

### 方法 1: 使用 browser 工具直接控制

OpenClaw 已配置 browser 工具，可以直接使用：

```bash
# 查看浏览器状态
openclaw browser status

# 启动浏览器（使用 Xvfb 环境）
export DISPLAY=:99
openclaw browser start

# 导航到网页
openclaw browser navigate --url https://www.baidu.com

# 截图
openclaw browser screenshot
```

### 方法 2: 使用 Python 脚本

在 OpenClaw 会话中直接调用：

```python
import sys
sys.path.insert(0, '~/.openclaw/workspace/tools/browser')

# 导入浏览器控制器
from browser_controller import BrowserController

# 创建实例
browser = BrowserController()

# 启动 Xvfb（有头模式）
browser.start_xvfb()

# 启动 Chromium
browser.start_chromium(headless=False)

# 导航
browser.navigate("https://www.example.com")

# 截图到 assets 目录
browser.screenshot("~/.openclaw/workspace/assets/screenshots/example.png")

# 清理
browser.stop()
```

### 方法 3: 使用 Playwright（推荐）

```bash
# 安装 Playwright
pip3 install playwright --break-system-packages
playwright install chromium

# 使用 Playwright 代码
python3 -c "
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # 无头模式
    browser = p.chromium.launch(headless=True)
    
    # 有头模式（使用 Xvfb）
    # browser = p.chromium.launch(headless=False)
    
    page = browser.new_page()
    page.goto('https://www.baidu.com')
    page.screenshot(path='/tmp/playwright_screenshot.png')
    browser.close()
"
```

## Xvfb 持久化运行

如果需要长期保持 Xvfb 运行：

```bash
# 启动 Xvfb 后台进程
Xvfb :99 -screen 0 1920x1080x24 -ac +extension RANDR &

# 设置环境变量
export DISPLAY=:99

# 现在可以在该会话中运行任何 GUI 程序
chromium-browser &
```

## 测试结果

✅ **无头模式测试** - 成功
- 浏览器: Chrome/145.0.7632.109
- 截图: `~/.openclaw/workspace/assets/screenshots/test_headless.png` ✓

✅ **有头模式测试** - 成功
- Xvfb 显示: `:99`
- 截图: `~/.openclaw/workspace/assets/screenshots/test_headed.png` ✓

✅ **百度截图测试** - 成功
- 截图: `~/.openclaw/workspace/assets/screenshots/baidu_screenshot.png` ✓

## 可用端口和配置

| 组件 | 端口/路径 | 说明 |
|------|----------|------|
| Xvfb | `:99` | 虚拟显示 |
| Chromium CDP | `9222` | Chrome DevTools Protocol |
| OpenClaw CDP | `18792` | OpenClaw 默认端口 |

## 常见问题

### 1. WebSocket 403 错误
**解决**: 启动 Chromium 时添加 `--remote-allow-origins=*`

### 2. Xvfb 无法启动
**解决**: 检查是否已有 Xvfb 实例在运行
```bash
ps aux | grep Xvfb
```

### 3. Chromium 无法找到显示
**解决**: 确保设置了 `DISPLAY` 环境变量
```bash
export DISPLAY=:99
```

## 应用场景

1. **网页截图** - 自动化生成网页预览
2. **网页抓取** - 动态内容抓取（JavaScript 渲染）
3. **自动化测试** - Web 应用 UI 测试
4. **PDF 生成** - 网页转 PDF
5. **图像生成** - 配合图像生成服务（如 Pollinations AI）

## 下一步建议

1. 安装 Playwright 以获得更强大的浏览器自动化能力
2. 配置 OpenClaw 的 `browser` 工具使用 Xvfb 环境
3. 创建定时任务定期抓取网页截图
4. 集成图像生成服务（如果需要生成 AI 图像）

## 参考链接

- [Chrome DevTools Protocol](https://chromedevtools.github.io/devtools-protocol/)
- [Playwright Documentation](https://playwright.dev/python/)
- [Xvfb Manual](https://www.x.org/releases/X11R7.6/doc/man/man1/Xvfb.1.xhtml)
