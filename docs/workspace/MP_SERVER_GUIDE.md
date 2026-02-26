# OpenClaw 微信公众号交互服务

实现微信公众号自动回复功能，让 OpenClaw 可以通过公众号与你交互。

## 🎯 功能

- ✅ 接收用户发送的消息
- ✅ 自动解析并执行指令
- ✅ 返回执行结果到个人微信
- ✅ 支持多种内置指令（天气、时间、状态等）

## 📋 前提条件

1. 微信公众号（测试号已配置）
2. **公网可访问的 URL** 或 **内网穿透工具**
3. Python 3 + Flask

---

## 🚀 快速开始

### 步骤 1：配置服务

```bash
~/.openclaw/workspace/mp_server_setup.sh
```

按提示设置 Token（用于微信验证）。

### 步骤 2：解决网络问题（关键）

微信服务器需要能访问你的服务。你有以下选择：

#### 方案 A：使用 ngrok（推荐测试）

```bash
# 安装 ngrok
# 访问 https://ngrok.com 注册并下载

# 启动内网穿透
ngrok http 5000
```

启动后会显示公网 URL，如：
```
Forwarding  https://abc123.ngrok.io -> http://localhost:5000
```

#### 方案 B：使用云服务器

如果你有云服务器：
1. 在服务器上部署此服务
2. 开放防火墙端口（如 5000）
3. 使用服务器公网 IP

#### 方案 C：使用 cpolar（国内推荐）

```bash
# 安装 cpolar
# 访问 https://cpolar.com

cpolar http 5000
```

### 步骤 3：配置微信服务器

1. 访问测试号管理页面：
   ```
   https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login
   ```

2. 找到「接口配置信息修改」

3. 填写：
   - **URL**: `https://你的地址/wx`（如 `https://abc123.ngrok.io/wx`）
   - **Token**: 你在配置向导中设置的 Token（默认 `openclaw2024`）

4. 点击「提交」，微信会验证服务器

### 步骤 4：启动服务

```bash
python3 ~/.openclaw/workspace/mp_server.py
```

服务启动后，保持运行状态。

---

## 💬 使用方法

### 发送指令到公众号

用你的个人微信给公众号发消息：

```
help          # 显示帮助菜单
status        # 查看系统状态
echo 你好     # 回声测试
time          # 当前时间
weather 北京  # 查询天气
gmail         # 检查邮件
wechat 测试   # 发送消息到微信
```

### 自定义指令

编辑 `~/.openclaw/workspace/mp_server.py`，在 `process_message` 函数中添加新指令：

```python
elif cmd == 'mycommand':
    # 执行你的逻辑
    reply_content = "执行结果"
```

---

## 🔧 高级配置

### 后台运行

使用 screen 或 nohup：

```bash
# 使用 screen
screen -S mp_server
python3 ~/.openclaw/workspace/mp_server.py
# 按 Ctrl+A, D  detach

# 重新连接
screen -r mp_server
```

或使用 systemd 服务（推荐生产环境）：

```bash
sudo tee /etc/systemd/system/mp-server.service << 'EOF'
[Unit]
Description=OpenClaw WeChat MP Server
After=network.target

[Service]
Type=simple
User=你的用户名
WorkingDirectory=/home/你的用户名/.openclaw/workspace
ExecStart=/usr/bin/python3 mp_server.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable mp-server
sudo systemctl start mp-server
```

### 安全建议

1. **修改默认 Token**
   ```bash
   nano ~/.openclaw/workspace/.mp_server_config
   ```

2. **使用 HTTPS**
   - 生产环境务必使用 HTTPS
   - 可以使用 nginx 反向代理 + SSL 证书

3. **限制访问 IP**
   - 微信服务器 IP 列表：https://developers.weixin.qq.com/doc/offiaccount/Basic_Information/IP_White_List.html
   - 在防火墙中限制只允许这些 IP 访问

---

## ❓ 常见问题

### Q: 微信验证失败？

A: 检查以下几点：
1. 服务是否已启动
2. URL 是否可公网访问（用手机流量测试）
3. Token 是否一致
4. 路径是否为 `/wx`

### Q: 收不到回复？

A: 检查：
1. 服务是否在运行
2. 查看日志输出
3. 微信是否有 5 秒超时限制（复杂操作需异步处理）

### Q: 如何支持复杂指令？

A: 对于耗时操作，使用异步处理：

```python
import threading

def long_task(user_id, param):
    # 耗时操作
    result = do_something(param)
    # 通过客服消息发送结果
    send_text_message(token, user_id, result)

# 在 process_message 中
threading.Thread(target=long_task, args=(from_user, param)).start()
return build_reply_xml(from_user, to_user, "任务已开始，请稍候...")
```

---

## 📚 相关链接

- [微信公众号开发文档](https://developers.weixin.qq.com/doc/offiaccount/Getting_Started/Overview.html)
- [消息加解密说明](https://developers.weixin.qq.com/doc/offiaccount/Message_Management/Message_encryption_and_decryption_instructions.html)
- [Flask 文档](https://flask.palletsprojects.com/)

---

## 💡 下一步

1. 运行 `mp_server_setup.sh` 完成配置
2. 解决网络访问问题（ngrok/云服务器）
3. 在微信公众号后台配置服务器 URL
4. 开始通过公众号与 OpenClaw 交互！
