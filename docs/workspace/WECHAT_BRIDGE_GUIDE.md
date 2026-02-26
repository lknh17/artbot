# 企业微信 ↔ 个人微信 互通配置指南

## 🎯 目标
实现企业微信与个人微信的消息互通，让 OpenClaw 可以通过企业微信向你的个人微信发送消息。

---

## 📋 方案对比

### 方案 1: Webhook（已配置，最简单）
- ✅ 无需企业认证
- ✅ 即开即用
- ❌ 只能发送到群，不能直接发给个人微信
- ❌ 不支持外部联系人

### 方案 2: 企业微信应用 API（推荐）
- ✅ 可以向外部联系人（个人微信）发消息
- ✅ 功能完整
- ⚠️ 需要配置企业 ID、应用凭证
- ⚠️ 需要个人微信添加企业成员为好友

---

## 🔧 方案 2 配置步骤

### 步骤 1: 获取企业 ID

1. 登录 [企业微信管理后台](https://work.weixin.qq.com/wework_admin)
2. 点击「我的企业」→ 底部找到「企业ID」
3. 复制保存（格式：wwxxxxxxxxxxxxxxxx）

### 步骤 2: 创建应用

1. 管理后台 → 「应用管理」→ 「创建应用」
2. 填写应用信息：
   - 应用名称：OpenClay助手
   - 应用介绍：AI助手消息推送
   - 可见成员：选择你的企业微信账号
3. 创建后获取：
   - **AgentId**（如：1000002）
   - **Secret**（点击「查看」获取）

### 步骤 3: 配置应用权限

1. 进入刚创建的应用详情页
2. 点击「企业可信IP」→ 添加你服务器的公网 IP
3. 点击「接收消息」→ 设置消息回调（可选）

### 步骤 4: 添加个人微信为外部联系人

1. 打开手机上的「企业微信」App
2. 点击右上角「+」→ 「添加客户」→ 「从微信好友中添加」
3. 选择要互通的个人微信好友，发送添加请求
4. 在个人微信上确认添加

**重要**：只有添加为外部联系人后，才能通过 API 发消息。

### 步骤 5: 获取外部联系人 ID

```bash
# 获取企业成员的外部联系人列表
python3 wecom_bridge.py --list-contacts --userid "你的企业成员ID"
```

外部联系人 ID 格式：`wmxxxxxxxxxxxxxxxx`

### 步骤 6: 配置脚本

编辑 `wecom_bridge.py`，填入以下信息：

```python
CORP_ID = "wwxxxxxxxxxxxxxxxx"      # 你的企业ID
CORP_SECRET = "xxxxxxxxxxxxxxxxxxx" # 应用的Secret
AGENT_ID = "1000002"                 # 应用的AgentId
```

---

## 🚀 使用方法

### 发送消息到个人微信

```bash
# 发送文本消息
python3 wecom_bridge.py -u "wmxxxxxxxxxxxxxxxx" "你好，这是从企业微信发来的消息"

# 发送 Markdown 消息
python3 wecom_bridge.py -u "wmxxxxxxxxxxxxxxxx" -t markdown "**粗体** 和 *斜体*"

# 发送图文消息
python3 wecom_bridge.py -u "wmxxxxxxxxxxxxxxxx" -t news \
  --title "消息标题" \
  --url "https://example.com" \
  "消息描述内容"
```

---

## 📱 互通功能说明

### 可以实现：
- ✅ 企业微信 → 个人微信：发送消息
- ✅ 个人微信 → 企业微信：接收回复
- ✅ 发送文本、图片、文件、图文
- ✅ 查看消息已读状态

### 限制：
- ❌ 不能发送语音、视频通话
- ❌ 个人微信端显示「企业微信」标识
- ❌ 需要对方同意添加为外部联系人
- ❌ 有频次限制（免费版）

---

## ⚠️ 常见问题

### Q: 发送消息提示 "not allow to access this external contact"
A: 该个人微信未添加为外部联系人，需要先在手机上添加。

### Q: 提示 "not in allow list"
A: 企业可信 IP 未配置，需要在应用管理中添加服务器 IP。

### Q: 个人微信收不到消息？
A: 检查：
1. 是否已添加为外部联系人
2. 企业微信应用是否可见
3. Access Token 是否有效

### Q: 如何获取自己的外部联系人 ID？
A: 联系企业管理员在后台查看，或通过 API 获取列表。

---

## 🔒 安全提示

- **Secret 密钥不要泄露** - 相当于应用密码
- **配置可信 IP** - 限制只有特定 IP 可以调用 API
- **定期轮换密钥** - 建议每 3 个月更换一次
- **只在明确命令时发送消息**

---

## 📚 相关链接

- [企业微信开发者中心](https://developer.work.weixin.qq.com/)
- [发送消息到外部联系人 API](https://developer.work.weixin.qq.com/document/path/90236)
- [获取外部联系人列表 API](https://developer.work.weixin.qq.com/document/path/90316)

---

## 💡 下一步

1. 选择使用 **Webhook（简单）** 还是 **应用 API（功能完整）**
2. 如果选择应用 API，请提供：
   - 企业 ID
   - 应用的 AgentId 和 Secret
   - 目标个人微信的外部联系人 ID

我来帮你完成配置！
