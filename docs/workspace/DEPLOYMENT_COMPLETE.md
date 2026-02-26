# OpenClaw 域名部署 - 完整配置说明

## 🎉 部署完成

OpenClaw 已通过域名 `chengong.net` 部署，包含以下功能：

---

## 🌐 访问地址

| 地址 | 功能 | 说明 |
|------|------|------|
| **https://chengong.net** | OpenClaw Web 界面 | 需密码认证，自动加 token |
| **https://chengong.net/wx** | 微信公众号回调 | 公开访问，供微信服务器调用 |

---

## 🔐 登录信息

- **密码**: `chengong1`
- **用户名**: 不需要（仅密码验证）
- **记住登录**: 7 天（Cookie 缓存）
- **安全限制**: 每天 3 次错误后封禁 24 小时

---

## 📋 服务架构

```
用户访问
    ↓
Nginx (443端口) 
    ↓
├─ /wx → 公众号服务 (5000端口)
└─ /   → 认证代理 (8080端口) → OpenClaw (18789端口)
```

### 1. 认证代理服务 (auth-proxy)
- **端口**: 8080
- **功能**: 
  - 仅密码验证（无需用户名）
  - IP 限流（每天3次错误封禁24小时）
  - Cookie 会话管理（7天缓存）
  - 自动添加 OpenClaw token
  - 代理到 OpenClaw Gateway
- **systemd**: `auth-proxy.service`

### 2. OpenClaw Gateway
- **端口**: 18789
- **功能**: OpenClaw 原生 Web 界面
- **访问**: 仅通过认证代理

### 3. 微信公众号服务
- **端口**: 5000
- **功能**: 接收微信消息，执行指令
- **systemd**: `mp-server.service`
- **公开路径**: /wx

### 4. Nginx 反向代理
- **端口**: 80/443
- **功能**: SSL 终止、请求分发、限流
- **配置**: `/etc/nginx/sites-enabled/chengong.net`

---

## 📝 配置详情

### OpenClaw Token
```
482f546bebd72d46a90425116f8e4a3238469a5ecc333e36
```

### 微信公众号 Token
```
opencode2024
```

### 公众号 AppID
```
wx2fea7359a7fe4a5d
```

---

## 🚀 使用方法

### 1. 访问 OpenClaw Web 界面

1. 浏览器打开: https://chengong.net
2. 看到登录页面，输入密码: `chengong1`
3. 进入 OpenClaw Web 界面
4. 登录状态保持 7 天

### 2. 配置微信公众号回调

1. 访问测试号管理: https://mp.weixin.qq.com/debug/cgi-bin/sandbox
2. 找到「接口配置信息修改」
3. 填写:
   - **URL**: `https://chengong.net/wx`
   - **Token**: `opencode2024`
4. 点击「提交」完成验证

### 3. 通过公众号与 OpenClaw 交互

用个人微信给公众号发消息：
```
help      # 显示帮助菜单
status    # 查看系统状态
echo 内容  # 回声测试
time      # 当前时间
weather 北京  # 查询天气
wechat 消息   # 发送消息到微信
```

---

## 🔧 管理命令

### 查看所有服务状态
```bash
sudo systemctl status nginx auth-proxy mp-server
```

### 重启服务
```bash
# 重启 Nginx
sudo systemctl restart nginx

# 重启认证代理
sudo systemctl restart auth-proxy

# 重启公众号服务
sudo systemctl restart mp-server
```

### 查看日志
```bash
# Nginx 日志
sudo tail -f /var/log/nginx/chengong.net.access.log
sudo tail -f /var/log/nginx/chengong.net.error.log

# 认证代理日志
sudo journalctl -u auth-proxy -f

# 公众号服务日志
sudo journalctl -u mp-server -f
```

### 修改密码
编辑 `~/.openclaw/workspace/auth_proxy.py`:
```python
CONFIG = {
    "password": "新密码",  # 修改这里
    ...
}
```
然后重启服务:
```bash
sudo systemctl restart auth-proxy
```

---

## ⚠️ 安全特性

### 已启用
- ✅ HTTPS (Let's Encrypt SSL)
- ✅ 仅密码验证（无需用户名）
- ✅ IP 限流和封禁（每天3次错误后封禁24小时）
- ✅ Cookie 会话管理（7天缓存）
- ✅ 安全响应头
- ✅ WebSocket 支持

### 访问限制示例
```
IP: 192.168.1.100
- 第一次错误: 剩余 2 次
- 第二次错误: 剩余 1 次
- 第三次错误: 已封禁，24小时后重试
```

---

## 📁 重要文件

| 文件 | 说明 |
|------|------|
| `/etc/nginx/sites-available/chengong.net` | Nginx 主配置 |
| `~/.openclaw/workspace/auth_proxy.py` | 认证代理服务 |
| `~/.openclaw/workspace/mp_server.py` | 公众号服务 |
| `~/.openclaw/workspace/.mp_server_config` | 公众号 Token 配置 |
| `/etc/systemd/system/auth-proxy.service` | 认证代理 systemd |
| `/etc/systemd/system/mp-server.service` | 公众号服务 systemd |

---

## ❓ 故障排除

### 无法访问 https://chengong.net
```bash
# 检查服务状态
sudo systemctl status nginx auth-proxy

# 检查端口监听
sudo ss -tlnp | grep -E ':(443|8080|18789)'

# 测试本地访问
curl -s http://127.0.0.1:8080/login | head -5
```

### 密码错误次数过多
- 等待 24 小时后自动解封
- 或清除封禁数据: `sudo rm /tmp/opencode_auth_data.json`

### 微信公众号验证失败
```bash
# 查看日志
sudo journalctl -u mp-server -f

# 检查配置
cat ~/.openclaw/workspace/.mp_server_config

# 确保 URL 是 https://chengong.net/wx
# 确保 Token 是 opencode2024
```

### SSL 证书问题
```bash
# 测试证书续期
sudo certbot renew --dry-run

# 手动续期
sudo certbot renew
```

---

## 💡 提示

1. **首次访问**: 输入密码 `chengong1`，登录后会自动跳转到 OpenClaw
2. **Token 自动添加**: 无需手动添加 token，系统会自动处理
3. **Cookie 记住**: 登录后 7 天内无需重复输入密码
4. **安全退出**: 访问 https://chengong.net/logout 可立即退出

---

## 📞 技术支持

如有问题，请检查:
1. 所有服务状态: `sudo systemctl status nginx auth-proxy mp-server`
2. Nginx 配置: `sudo nginx -t`
3. 日志文件: `/var/log/nginx/` 和 `journalctl`
4. 端口监听: `sudo ss -tlnp`
