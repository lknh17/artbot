# 微信公众号 → 个人微信 消息推送配置

## 🎯 方案说明

通过微信公众号向关注者（你的个人微信）发送消息，实现 OpenClaw 与个人的互通。

**优势：**
- ✅ 你自己是管理员，完全可控
- ✅ 配置简单，无需企业资质
- ✅ 个人微信关注后即可接收消息
- ✅ 支持客服消息（48小时内可无限回复）

---

## 📋 需要的配置信息

### 1. 公众号 AppID 和 AppSecret

**获取步骤：**
1. 登录 [微信公众平台](https://mp.weixin.qq.com/)
2. 左侧菜单 → 「开发」→ 「基本配置」
3. 找到：
   - **开发者ID (AppID)** - 类似 `wx1234567890abcdef`
   - **开发者密码 (AppSecret)** - 点击「重置」获取（仅显示一次，请保存）

**⚠️ 重要：**
- AppSecret 只会显示一次，请妥善保存
- 如果忘记了，需要点击「重置」重新获取

### 2. 你的 OpenID（用户标识）

OpenID 是公众号用来标识用户的唯一 ID。

**获取方法（推荐）：**

**方法一：通过公众号后台查看**
1. 公众平台 → 「用户管理」
2. 找到你的个人微信（通常是第一个，或搜索昵称）
3. 点击用户详情，URL 中包含 OpenID

**方法二：通过接口获取（配置好后自动获取）**
配置好脚本后，发送任意消息到公众号，脚本可以捕获你的 OpenID。

### 3. 服务器配置（可选，用于接收消息）

如果你需要双向通信（个人微信 → OpenClaw），需要配置服务器：
1. 公众平台 → 「开发」→ 「基本配置」→ 「服务器配置」
2. 填写服务器 URL、Token、EncodingAESKey
3. 启用服务器配置

**如果只是单向推送（OpenClaw → 个人微信），可以跳过此步骤。**

---

## 🚀 快速配置步骤

### 步骤 1：获取 AppID 和 AppSecret

登录公众平台，记录：
```
AppID: wx1234567890abcdef
AppSecret: 1234567890abcdef1234567890abcdef
```

### 步骤 2：配置脚本

运行配置向导：
```bash
python3 ~/.openclaw/workspace/mp_setup.py setup
```

按提示输入 AppID 和 AppSecret。

### 步骤 3：获取你的 OpenID

**方式 A - 如果你知道 OpenID：**
```bash
python3 ~/.openclaw/workspace/mp_setup.py set-openid "你的OpenID"
```

**方式 B - 通过发送消息获取：**
1. 用个人微信给公众号发一条消息（如"测试"）
2. 如果配置了服务器，OpenID 会自动显示在日志中
3. 或者使用临时接口获取

### 步骤 4：测试发送

```bash
python3 ~/.openclaw/workspace/mp_to_personal.py "你好，这是一条来自 OpenClaw 的消息"
```

---

## 📱 消息类型说明

### 1. 客服消息（推荐）
- **条件**：用户关注后，48 小时内有过交互
- **限制**：48 小时内可无限制发送
- **适用**：即时通知、对话场景

### 2. 模板消息
- **条件**：需要申请模板
- **限制**：每月有一定额度
- **适用**：固定格式的通知

### 3. 群发消息
- **条件**：订阅号每天1条，服务号每月4条
- **限制**：有频次限制
- **适用**：广播通知

---

## 🔧 配置好后使用方法

### 发送文本消息
```bash
python3 ~/.openclaw/workspace/mp_to_personal.py "消息内容"
```

### 发送图文消息
```bash
python3 ~/.openclaw/workspace/mp_to_personal.py -t news \
  --title "标题" \
  --desc "描述" \
  --url "https://example.com"
```

### 查看配置
```bash
python3 ~/.openclaw/workspace/mp_to_personal.py -l
```

---

## ⚠️ 重要限制

1. **需要关注公众号**
   - 个人微信必须先关注你的公众号
   - 如果取消关注，无法接收消息

2. **客服消息 48 小时限制**
   - 用户最后交互后 48 小时内可无限制发送
   - 超过 48 小时需要使用模板消息
   - 每次用户发消息/点击菜单，48小时重新计算

3. **防止骚扰**
   - 频繁发送可能导致用户取消关注
   - 建议只在重要通知时使用

---

## 💡 建议的使用场景

✅ **适合发送：**
- 重要任务完成通知
- 定时提醒（结合 cron）
- 监控告警
- 每日摘要

❌ **不适合：**
- 高频实时对话（超过48小时限制）
- 大量日志输出
- 敏感信息（公众号消息可能被审查）

---

## 📚 相关链接

- [微信公众平台](https://mp.weixin.qq.com/)
- [公众号开发文档](https://developers.weixin.qq.com/doc/offiaccount/Getting_Started/Overview.html)
- [客服消息接口](https://developers.weixin.qq.com/doc/offiaccount/Message_Management/Service_Center_messages.html)

---

## ❓ 下一步

请提供以下信息，我来帮你完成配置：

1. **公众号 AppID**：wx...
2. **公众号 AppSecret**：...
3. **你的 OpenID**（如果知道的话，不知道可以后续获取）

或者你可以先运行配置向导，按步骤操作：
```bash
python3 ~/.openclaw/workspace/mp_setup.py setup
```
