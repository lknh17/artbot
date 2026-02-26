#!/usr/bin/env bash
#
# md2wechat OpenClaw Skill Installer (Simplified)
#
# Just copies skill files to ~/.openclaw/skills/md2wechat
# For ClawHub users: clawhub install md2wechat
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/geekjourneyx/md2wechat-skill/main/scripts/install-openclaw.sh | bash
#

set -e

REPO="geekjourneyx/md2wechat-skill"
SKILL_NAME="md2wechat"
INSTALL_DIR="${HOME}/.openclaw/skills/${SKILL_NAME}"
GITHUB_ARCHIVE="https://github.com/${REPO}/archive/refs/heads/main.tar.gz"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { printf "${BLUE}ℹ${NC} %s\n" "$1"; }
success() { printf "${GREEN}✓${NC} %s\n" "$1"; }
warn()    { printf "${YELLOW}⚠${NC} %s\n" "$1"; }
error()   { printf "${RED}✗${NC} %s\n" "$1" >&2; exit 1; }

# Header
printf "\n"
printf "${BLUE}========================================${NC}\n"
printf "${BLUE}   md2wechat OpenClaw Skill Installer${NC}\n"
printf "${BLUE}========================================${NC}\n"
printf "\n"

# Check for ClawHub first
if command -v clawhub &>/dev/null; then
    info "检测到 clawhub CLI / ClawHub CLI detected"
    printf "\n"
    printf "推荐使用 ClawHub 安装 / Recommend using ClawHub:\n"
    printf "  ${GREEN}clawhub install md2wechat${NC}\n"
    printf "\n"
    read -p "继续手动安装？/ Continue manual install? [y/N] " -n 1 -r
    printf "\n"
    [[ ! $REPLY =~ ^[Yy]$ ]] && exit 0
fi

# Check prerequisites
command -v curl &>/dev/null || command -v wget &>/dev/null || \
    error "需要 curl 或 wget / Need curl or wget"

# Check if OpenClaw is installed (optional warning)
if [[ ! -d "${HOME}/.openclaw" ]]; then
    warn "未检测到 OpenClaw 安装 / OpenClaw not detected"
    info "请先安装 OpenClaw: https://openclaw.ai/"
    info "Install OpenClaw first: https://openclaw.ai/"
    printf "\n"
    read -p "仍要继续安装技能？/ Continue installing skill anyway? [y/N] " -n 1 -r
    printf "\n"
    [[ ! $REPLY =~ ^[Yy]$ ]] && exit 0
fi

# Handle existing installation
if [[ -d "$INSTALL_DIR" ]]; then
    warn "已存在安装 / Existing installation: $INSTALL_DIR"
    read -p "覆盖？/ Overwrite? [y/N] " -n 1 -r
    printf "\n"
    [[ ! $REPLY =~ ^[Yy]$ ]] && exit 0
    rm -rf "$INSTALL_DIR"
fi

# Download and extract
info "下载技能文件 / Downloading skill files..."

TEMP_DIR=$(mktemp -d)
ARCHIVE="${TEMP_DIR}/repo.tar.gz"

if command -v curl &>/dev/null; then
    curl -fsSL "$GITHUB_ARCHIVE" -o "$ARCHIVE"
else
    wget -q "$GITHUB_ARCHIVE" -O "$ARCHIVE"
fi

tar -xzf "$ARCHIVE" -C "$TEMP_DIR"

# Find extracted directory
EXTRACTED=$(find "$TEMP_DIR" -maxdepth 1 -type d -name "md2wechat-skill-*" | head -n 1)
[[ -z "$EXTRACTED" ]] && error "下载失败 / Download failed"

# Install
mkdir -p "$INSTALL_DIR"
cp -r "${EXTRACTED}/skills/md2wechat/"* "$INSTALL_DIR/"
chmod +x "${INSTALL_DIR}/scripts/"*.sh 2>/dev/null || true

# Cleanup
rm -rf "$TEMP_DIR"

success "安装完成 / Installation complete!"

# Show configuration instructions
printf "\n"
printf "${BLUE}========================================${NC}\n"
printf "${BLUE}   配置说明 / Configuration${NC}\n"
printf "${BLUE}========================================${NC}\n"
printf "\n"

CONFIG_FILE="${HOME}/.openclaw/openclaw.json"

if [[ -f "$CONFIG_FILE" ]]; then
    # Existing config - show merge instructions
    printf "${YELLOW}检测到已有配置文件 / Existing config found${NC}\n"
    printf "\n"
    printf "请在 ${GREEN}~/.openclaw/openclaw.json${NC} 的 skills.entries 中添加:\n"
    printf "Add to skills.entries in your existing config:\n"
    printf "\n"
    printf "${GREEN}"
    cat << 'EOF'
"md2wechat": {
  "enabled": true,
  "env": {
    "WECHAT_APPID": "your-appid",
    "WECHAT_SECRET": "your-secret"
  }
}
EOF
    printf "${NC}\n"
    printf "\n"
    printf "示例（合并后）/ Example (after merge):\n"
    printf "${BLUE}"
    cat << 'EOF'
{
  "skills": {
    "entries": {
      "existing-skill": { ... },
      "md2wechat": {
        "enabled": true,
        "env": {
          "WECHAT_APPID": "your-appid",
          "WECHAT_SECRET": "your-secret"
        }
      }
    }
  }
}
EOF
    printf "${NC}\n"
else
    # No existing config - show full structure
    printf "创建配置文件 / Create config file:\n"
    printf "${GREEN}~/.openclaw/openclaw.json${NC}\n"
    printf "\n"
    printf "${GREEN}"
    cat << 'EOF'
{
  "skills": {
    "entries": {
      "md2wechat": {
        "enabled": true,
        "env": {
          "WECHAT_APPID": "your-appid",
          "WECHAT_SECRET": "your-secret"
        }
      }
    }
  }
}
EOF
    printf "${NC}\n"
fi

printf "\n"
printf "${YELLOW}注意 / Note:${NC}\n"
printf "  • WECHAT_APPID/SECRET 仅草稿上传需要，预览转换可不配置\n"
printf "  • 图片生成需额外配置 IMAGE_API_KEY\n"
printf "\n"
printf "安装路径 / Installed to: ${GREEN}%s${NC}\n" "$INSTALL_DIR"
printf "文档 / Documentation: https://github.com/${REPO}#readme\n"
printf "OpenClaw 官网 / OpenClaw: https://openclaw.ai/\n"
printf "ClawHub 技能市场 / ClawHub: https://clawhub.ai/\n"
printf "\n"
