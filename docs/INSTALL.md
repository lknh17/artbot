# 安装指南

本文档详细说明 md2wechat 的各种安装方式。

## 目录

- [系统要求](#系统要求)
- [方式一：Go 工具链安装](#方式一go-工具链安装推荐)
- [方式二：预编译二进制](#方式二预编译二进制)
- [方式三：从源码编译](#方式三从源码编译)
- [方式四：Docker](#方式四docker)
- [验证安装](#验证安装)
- [卸载](#卸载)

---

## 系统要求

- **操作系统**：Linux / macOS / Windows
- **Go 版本**：1.24 或更高（如果从源码编译）
- **网络**：需要访问微信公众号 API

---

## 方式一：Go 工具链安装（推荐）

### 前置条件

确保已安装 Go 1.24+：

```bash
go version
# 输出示例：go version go1.24.0 linux/amd64
```

如果没有安装 Go，请访问 [golang.org/dl](https://golang.org/dl/) 下载。

### 安装步骤

1. **使用 go install 安装**

```bash
go install github.com/geekjourneyx/md2wechat-skill/cmd/md2wechat@latest
```

2. **确保 GOPATH/bin 在 PATH 中**

```bash
# 添加到 ~/.bashrc 或 ~/.zshrc
export PATH=$PATH:$(go env GOPATH)/bin

# 重新加载配置
source ~/.bashrc  # 或 source ~/.zshrc
```

3. **验证安装**

```bash
md2wechat --version
md2wechat --help
```

---

## 方式二：预编译二进制

### 下载地址

访问 [Releases](https://github.com/geekjourneyx/md2wechat-skill/releases) 页面下载适合你系统的版本。

| 系统 | 文件名 |
|------|--------|
| Linux (amd64) | `md2wechat-linux-amd64` |
| Linux (arm64) | `md2wechat-linux-arm64` |
| macOS (Intel) | `md2wechat-darwin-amd64` |
| macOS (Apple Silicon) | `md2wechat-darwin-arm64` |
| Windows (64位) | `md2wechat-windows-amd64.exe` |

### 安装步骤

#### Linux / macOS

```bash
# 1. 下载
wget https://github.com/geekjourneyx/md2wechat-skill/releases/latest/download/md2wechat-linux-amd64

# 2. 添加执行权限
chmod +x md2wechat-linux-amd64

# 3. 移动到 PATH
sudo mv md2wechat-linux-amd64 /usr/local/bin/md2wechat

# 4. 验证
md2wechat --help
```

#### Windows

```powershell
# 1. 下载到当前目录
# 使用浏览器或 curl 下载

# 2. 添加到 PATH
# 将文件移动到某个 PATH 目录，或将其所在目录添加到 PATH

# 3. 验证
md2wechat.exe --help
```

---

## 方式三：从源码编译

### 前置条件

- Go 1.24+
- Git

### 编译步骤

```bash
# 1. 克隆仓库
git clone https://github.com/geekjourneyx/md2wechat-skill.git
cd md2wechat-skill

# 2. 下载依赖
go mod download

# 3. 编译
go build -o md2wechat ./cmd/md2wechat

# 4. 安装（可选）
sudo mv md2wechat /usr/local/bin/  # Linux/macOS
# 或将当前目录添加到 PATH
```

### 交叉编译

为其他平台编译：

```bash
# Linux amd64
GOOS=linux GOARCH=amd64 go build -o md2wechat-linux-amd64 ./cmd/md2wechat

# macOS arm64 (Apple Silicon)
GOOS=darwin GOARCH=arm64 go build -o md2wechat-darwin-arm64 ./cmd/md2wechat

# Windows amd64
GOOS=windows GOARCH=amd64 go build -o md2wechat-windows-amd64.exe ./cmd/md2wechat
```

---

## 方式四：Docker

### 拉取镜像

```bash
docker pull ghcr.io/geekjourneyx/md2wechat:latest
```

### 使用方式

```bash
# 基础用法
docker run --rm -v $(pwd):/workspace md2wechat convert article.md

# 带配置文件
docker run --rm -v $(pwd):/workspace md2wechat config init
```

### Dockerfile

如果需要自己构建镜像：

```dockerfile
FROM golang:1.24-alpine AS builder
WORKDIR /app
COPY . .
RUN go build -o md2wechat ./cmd/md2wechat

FROM alpine:latest
COPY --from=builder /app/md2wechat /usr/local/bin/
ENTRYPOINT ["md2wechat"]
```

---

## 验证安装

运行以下命令验证安装成功：

```bash
# 查看版本
md2wechat --help

# 查看所有命令
md2wechat help

# 测试配置
md2wechat config validate
```

预期输出：

```
md2wechat converts Markdown articles to WeChat Official Account format
...
```

---

## 卸载

### Go 工具链安装

```bash
rm $(go env GOPATH)/bin/md2wechat
```

### 预编译二进制

```bash
# Linux/macOS
sudo rm /usr/local/bin/md2wechat

# Windows
# 删除安装目录下的 md2wechat.exe
```

### Docker

```bash
docker rmi ghcr.io/geekjourneyx/md2wechat:latest
```

---

## 下一步

安装完成后，请继续阅读 [配置指南](CONFIG.md) 和 [使用教程](USAGE.md)。
