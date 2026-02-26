# 常见问题 (FAQ)

本文档收集了用户最常遇到的问题和解决方案。

## 目录

- [安装问题](#安装问题)
- [配置问题](#配置问题)
- [转换问题](#转换问题)
- [图片问题](#图片问题)
- [微信 API 问题](#微信-api-问题)
- [高级问题](#高级问题)

---

## 安装问题

### Q1: 提示 "command not found: md2wechat"

**原因**：二进制文件不在 PATH 中

**解决方案 A**：添加到 PATH

```bash
# 临时添加
export PATH=$PATH:/usr/local/bin

# 永久添加（添加到 ~/.bashrc）
echo 'export PATH=$PATH:/usr/local/bin' >> ~/.bashrc
source ~/.bashrc
```

**解决方案 B**：使用完整路径

```bash
/usr/local/bin/md2wechat --help
```

---

### Q2: Go 安装失败 "go: module not found"

**原因**：网络问题或模块路径错误

**解决方案**：

```bash
# 1. 设置 Go 代理（中国大陆用户）
export GOPROXY=https://goproxy.cn,direct

# 2. 清理缓存
go clean -modcache

# 3. 重新安装
go install github.com/geekjourneyx/md2wechat-skill/cmd/md2wechat@latest
```

---

### Q3: macOS 提示 "无法打开，因为无法验证开发者"

**原因**：macOS 安全限制

**解决方案**：

```bash
# 允许任何来源的的应用（系统偏好设置 > 安全性与隐私）
# 或使用命令行
sudo xattr -cr /Applications/md2wechat
```

---

## 配置问题

### Q4: 提示 "WECHAT_APPID is required"

**原因**：未配置微信公众号凭证

**解决方案 A**：使用配置文件

```bash
md2wechat config init
# 编辑生成的 md2wechat.yaml，填入：
# wechat:
#   appid: "your_appid"
#   secret: "your_secret"
```

**解决方案 B**：使用环境变量

```bash
export WECHAT_APPID="wx1234567890abcdef"
export WECHAT_SECRET="your_secret_here"
```

**如何获取 AppID 和 Secret**：

1. 访问 **[微信开发者平台](https://developers.weixin.qq.com/platform)**

   > 注：开发接口管理已于 2025 年 12 月迁移至微信开发者平台

2. 登录后，选择你的公众号（如果没有，请先注册）

3. 进入 **「开发接口管理」**

4. 在「开发者ID」区域可以看到：
   - **开发者ID(AppID)**：直接复制即可
   - **开发者密码(AppSecret)**：点击「重置」按钮获取

   > **警告**：AppSecret 非常重要，请妥善保管，不要泄露给他人！

5. 复制这两个值到配置文件或环境变量中

---

### Q5: 配置文件不生效

**原因**：配置文件位置或格式错误

**解决方案**：

```bash
# 1. 检查配置文件位置
md2wechat config show

# 2. 验证配置文件格式
cat md2wechat.yaml

# 3. 重新初始化配置
md2wechat config init
```

**支持的配置文件位置**：
- `./md2wechat.yaml`（当前目录，优先级最高）
- `~/.md2wechat.yaml`
- `~/.config/md2wechat/config.yaml`

---

### Q6: API 模式提示需要 API Key

**原因**：API 模式需要 [md2wechat.cn](https://md2wechat.cn) 的 API Key

**解决方案 A**：获取 API Key

1. 访问 [md2wechat.cn](https://md2wechat.cn)
2. 注册账号并获取 API Key
3. 配置：

```bash
export MD2WECHAT_API_KEY="your_key"
```

**解决方案 B**：使用 AI 模式（不需要 md2wechat API Key）

```bash
md2wechat convert article.md --mode ai --theme autumn-warm
```

---

## 转换问题

### Q7: 转换结果为空或乱码

**可能原因 1**：Markdown 文件编码问题

**解决方案**：

```bash
# 检查文件编码
file article.md

# 转换为 UTF-8
iconv -f GBK -t UTF-8 article.md > article-utf8.md
```

**可能原因 2**：Markdown 格式错误

**解决方案**：使用 Markdown 检查工具

```bash
# 安装 markdownlint
npm install -g markdownlint-cli

# 检查文件
markdownlint article.md
```

---

### Q8: AI 模式转换失败

**原因**：AI API Key 未配置或无效

**解决方案**：

```bash
# 1. 设置 Claude API Key
export IMAGE_API_KEY="your_claude_api_key"

# 2. 验证
md2wechat config validate

# 3. 重试
md2wechat convert article.md --mode ai
```

---

### Q9: HTML 样式在微信中显示不正常

**原因**：微信编辑器会过滤部分 CSS

**解决方案**：

1. **使用 API 模式**（更稳定）

```bash
md2wechat convert article.md --mode api
```

2. **检查是否使用了内联样式**

微信只支持内联 style 属性，不支持 `<style>` 标签。

3. **尝试简化 Markdown**

```markdown
<!-- 避免复杂嵌套 -->
## 简单标题

这是段落内容。

> 这是引用
```

---

## 图片问题

### Q10: 图片上传失败 "upload material failed"

**可能原因 1**：图片格式不支持

**解决方案**：

```bash
# 支持的格式：jpg, png, gif, bmp, webp
# 转换图片格式
convert input.tiff output.jpg
```

**可能原因 2**：图片太大

**解决方案**：

```bash
# 程序会自动压缩，但可以先手动压缩
# 配置压缩参数
# md2wechat.yaml:
image:
  compress: true
  max_width: 1920
  max_size_mb: 5
```

**可能原因 3**：微信 API 频率限制

**解决方案**：等待几分钟后重试

```bash
# 分批上传图片
md2wechat upload_image image1.jpg
sleep 5
md2wechat upload_image image2.jpg
```

---

### Q11: AI 生成图片失败

**原因**：图片生成 API Key 未配置或额度不足

**解决方案**：

```bash
# 1. 设置 API Key
export IMAGE_API_KEY="your_openai_or_claude_key"

# 2. 验证
md2wechat generate_image "test prompt"

# 3. 检查 API 额度
# 登录对应的 API 提供商查看剩余额度
```

---

### Q12: 图片链接未被替换

**原因**：未使用 `--upload` 参数

**解决方案**：

```bash
# 必须使用 --upload 参数
md2wechat convert article.md --upload -o output.html
```

---

## 微信 API 问题

### Q13: 第一次调用 API 提示 "IP 不在白名单中"

**现象**：第一次调用微信 API 时，返回错误：
```
ip xxx.xxx.xxx.xxx not in whitelist
```

**原因**：微信为了安全，要求服务器 IP 必须在白名单中才能调用 API。

**解决方案**：

1. **获取你的服务器 IP 地址**

```bash
# 查看你的公网 IP
curl ifconfig.me
# 或
curl ip.sb
# 或
curl ipinfo.io/ip
```

2. **添加 IP 到微信白名单**

   - 访问 [微信开发者平台](https://developers.weixin.qq.com/platform)
   - 选择你的公众号 → 开发接口管理
   - 找到 **「IP白名单」** 区域
   - 点击「设置」
   - 输入你的服务器 IP 地址（多个 IP 用回车分隔）
   - 点击「确定」保存

3. **等待生效并重试**

```bash
# 白名单配置通常几分钟内生效
# 等待 5 分钟后重试
sleep 300
md2wechat convert article.md --upload --draft
```

> **注意**：
> - 如果你使用本地电脑测试，需要添加你本地网络的公网 IP
> - 如果使用云服务器，添加云服务器的公网 IP
> - 如果使用 GitHub Actions 等动态 IP 环境，建议使用固定 IP 的服务器

---

### Q14: 提示 "access_token expired"

**原因**：微信 access_token 过期（通常 2 小时）

**解决方案**：程序会自动刷新，如果持续失败：

```bash
# 1. 检查 AppID 和 Secret 是否正确
md2wechat config show --show-secret

# 2. 重新配置
md2wechat config init
```

---

### Q15: 草稿创建失败 "create draft failed"

**可能原因 1**：公众号权限不足

**解决方案**：
- 确保公众号已认证
- 确保有素材管理权限
- 检查是否超过草稿数量限制

**可能原因 2**：内容包含敏感词

**解决方案**：
- 检查文章内容
- 尝试简化内容后重试

```bash
# 先保存为 JSON，检查内容
md2wechat convert article.md --save-draft draft.json
cat draft.json
```

---

### Q16: API 调用频率限制

**现象**：提示 "api freq limit"

**解决方案**：

```bash
# 方案 1：等待后重试
sleep 60

# 方案 2：分批处理
for file in articles/*.md; do
  md2wechat convert "$file" --draft
  sleep 5
done
```

---

## 高级问题

### Q17: 如何在 CI/CD 中使用？

**解决方案**：使用环境变量或 Secrets

```yaml
# .github/workflows/publish.yml
name: Publish to WeChat
on: [push]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install md2wechat
        run: go install github.com/geekjourneyx/md2wechat-skill/cmd/md2wechat@latest
      - name: Convert and publish
        env:
          WECHAT_APPID: ${{ secrets.WECHAT_APPID }}
          WECHAT_SECRET: ${{ secrets.WECHAT_SECRET }}
        run: |
          md2wechat convert article.md --upload --draft
```

---

### Q18: 如何自定义主题？

**解决方案**：使用 custom-prompt

```bash
md2wechat convert article.md --mode ai --custom-prompt "
请使用以下配色：
- 主色：#e53e3e（红色）
- 副色：#3182ce（蓝色）
- 背景：#f7fafc（浅灰）
- 字体：16px，行高 1.8

请确保：
1. 所有 CSS 使用内联 style
2. 图片使用占位符 <!-- IMG:index -->
3. 不使用外部样式表
"
```

---

### Q19: 如何批量转换多个文件？

**解决方案**：使用 Shell 脚本

```bash
#!/bin/bash
# batch-convert.sh

for file in articles/*.md; do
  echo "Converting $file..."

  md2wechat convert "$file" \
    --mode ai \
    --theme autumn-warm \
    --upload \
    --draft

  echo "Waiting 5 seconds..."
  sleep 5
done
```

---

### Q19: 如何调试问题？

**解决方案**：启用详细日志

```bash
# 方案 1：查看命令输出
md2wechat convert article.md --preview 2>&1 | tee debug.log

# 方案 2：逐步测试
md2wechat config validate       # 1. 验证配置
md2wechat upload_image test.jpg  # 2. 测试图片上传
md2wechat convert test.md --preview  # 3. 测试转换
```

---

### Q20: 如何获取帮助？

**解决方案**：

1. **查看命令帮助**

```bash
md2wechat --help
md2wechat convert --help
```

2. **查看文档**

- [安装指南](INSTALL.md)
- [配置指南](CONFIG.md)
- [使用教程](USAGE.md)

3. **提交 Issue**

访问 [GitHub Issues](https://github.com/geekjourneyx/md2wechat-skill/issues)

---

## 仍然无法解决？

请提供以下信息：

1. **版本信息**
   ```bash
   md2wechat --version
   go version
   ```

2. **配置信息**
   ```bash
   md2wechat config show
   ```

3. **错误信息**
   ```bash
   md2wechat convert article.md 2>&1
   ```

4. **系统信息**
   ```bash
   uname -a  # Linux/macOS
   # 或
   systeminfo  # Windows
   ```

将以上信息提交到 [GitHub Issues](https://github.com/geekjourneyx/md2wechat-skill/issues)，我们会尽快回复。
