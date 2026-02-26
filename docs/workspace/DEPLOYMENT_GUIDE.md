# OpenClaw 域名部署配置文档

## 🎉 部署完成

OpenClaw 已成功部署到域名 `chengong.net`，支持 HTTPS 访问和微信公众号回调。

---

## 🌐 访问地址

| 服务 | 地址 | 认证 | 说明 |
|------|------|------|------|
| OpenClaw Web | https://chengong.net | ✅ 需要 | 主界面 |
| 公众号回调 | https://chengong.net/wx | ❌ 不需要 | 微信服务器调用 |
| Web 控制面板 | https://chengong.net/panel | ✅ 需要 | 备用面板 |

### 身份验证信息
- **用户名**: admin
- **密码**: openclaw2024

**⚠️ 建议立即修改默认密码：**
```bash
sudo htpasswd /etc/nginx/.htpasswd admin
```

---

## 📋 配置的服务

### 1. Nginx (反向代理 + SSL)
- **状态**: 运行中
- **配置**: `/etc/nginx/sites-enabled/chengong.net`
- **SSL**: Let's Encrypt 证书
- **功能**: 
  - HTTPS 加密传输
  - 基础身份验证
  - WebSocket 支持
  - 反向代理到后端服务

### 2. OpenClaw Gateway
- **地址**: http://127.0.0.1:18789
- **说明**: OpenClaw 原生 Web 界面
- **访问**: 通过 https://chengong.net (Nginx 代理)

### 3. 微信公众号服务 (Flask)
- **地址**: http://127.0.0.1:5000
- **路径**: /wx
- **功能**: 接收微信消息，执行指令
- **systemd**: `mp-server.service`

### 4. Web 控制面板 (Flask)
- **地址**: http://127.0.0.1:3000
- **路径**: /panel
- **功能**: 简易 Web 控制界面
- **systemd**: `openclaw-web.service`

---

## 🚀 使用方法

### 访问 OpenClaw Web 界面

1. 浏览器访问: https://chengong.net
2. 输入用户名: admin
3. 输入密码: openclaw2024
4. 开始使用 OpenClaw

### 配置微信公众号回调

1. 访问测试号管理: https://mp.weixin.qq.com/debug/cgi-bin/sandbox
2. 找到「接口配置信息修改」
3. 填写:
   - **URL**: `https://chengong.net/wx`
   - **Token**: `openclaw2024` (在 `~/.openclaw/workspace/.mp_server_config` 中)
4. 点击提交

### 通过公众号与 OpenClaw 交互

关注公众号后，发送指令:
- `help` - 查看帮助
- `status` - 系统状态
- `echo 内容` - 回声测试
- `time` - 当前时间

---

## 🔧 管理命令

### 查看服务状态
```bash
sudo systemctl status nginx mp-server openclaw-web
```

### 重启服务
```bash
# 重启 Nginx
sudo systemctl restart nginx

# 重启公众号服务
sudo systemctl restart mp-server

# 重启 Web 面板
sudo systemctl restart openclaw-web
```

### 查看日志
```bash
# Nginx 日志
sudo tail -f /var/log/nginx/chengong.net.access.log
sudo tail -f /var/log/nginx/chengong.net.error.log

# 公众号服务日志
sudo journalctl -u mp-server -f

# Web 面板日志
sudo journalctl -u openclaw-web -f
```

### 修改身份验证密码
```bash
# 修改密码
sudo htpasswd /etc/nginx/.htpasswd admin

# 添加新用户
sudo htpasswd /etc/nginx/.htpasswd 新用户名
```

---

## 📁 重要文件位置

| 文件/目录 | 说明 |
|-----------|------|
| `/etc/nginx/sites-available/chengong.net` | Nginx 主配置 |
| `/etc/nginx/.htpasswd` | 身份验证用户文件 |
| `/etc/letsencrypt/live/chengong.net/` | SSL 证书 |
| `~/.openclaw/workspace/.mp_config` | 公众号 AppID/Secret |
| `~/.openclaw/workspace/.mp_server_config` | 服务器 Token 配置 |
| `~/.openclaw/workspace/mp_server.py` | 公众号服务主程序 |
| `/etc/systemd/system/mp-server.service` | 公众号服务 systemd |
| `/etc/systemd/system/openclaw-web.service` | Web 面板 systemd |

---

## 🔒 安全配置

### 已启用
- ✅ HTTPS (Let's Encrypt SSL)
- ✅ 基础身份验证 (Basic Auth)
- ✅ 安全响应头
- ✅ WebSocket 支持

### 建议进一步加强
1. **修改默认密码**
   ```bash
   sudo htpasswd /etc/nginx/.htpasswd admin
   ```

2. **限制 IP 访问** (编辑 Nginx 配置)
   ```nginx
   location / {
       allow 你的IP地址;
       deny all;
       # ... 其他配置
   }
   ```

3. **启用 fail2ban** 防止暴力破解
   ```bash
   sudo apt install fail2ban
   ```

4. **定期更新 SSL 证书**
   ```bash
   sudo certbot renew --dry-run
   ```

---

## ❓ 故障排除

### 无法访问 https://chengong.net
1. 检查域名解析: `ping chengong.net`
2. 检查 Nginx: `sudo systemctl status nginx`
3. 检查防火墙: `sudo ufw status` 或 `sudo iptables -L`
4. 检查端口监听: `sudo ss -tlnp | grep :443`

### 微信公众号验证失败
1. 确保 URL 填写正确: `https://chengong.net/wx`
2. 检查 Token 是否一致
3. 查看日志: `sudo journalctl -u mp-server -f`
4. 测试本地访问: `curl http://127.0.0.1:5000/wx`

### SSL 证书过期
```bash
# 手动续期
sudo certbot renew

# 强制续期
sudo certbot renew --force-renewal
```

---

## 📝 更新记录

- **2026-02-21**: 初始部署完成
  - Nginx + SSL 配置
  - 身份验证
  - 微信公众号服务
  - Web 控制面板

---

## 💡 后续建议

1. **定期备份配置**
   ```bash
   sudo tar czf ~/nginx-config-backup.tar.gz /etc/nginx/
   ```

2. **监控服务状态**
   - 可以安装 uptime-kuma 或类似的监控工具

3. **日志轮转**
   ```bash
   sudo logrotate -f /etc/logrotate.d/nginx
   ```

4. **安全扫描**
   ```bash
   # 检查 SSL 配置
   https://www.ssllabs.com/ssltest/analyze.html?d=chengong.net
   ```

---

## 📞 支持

如有问题，请检查:
1. 服务状态: `sudo systemctl status nginx mp-server`
2. Nginx 配置: `sudo nginx -t`
3. 日志文件: `/var/log/nginx/` 和 `journalctl`
