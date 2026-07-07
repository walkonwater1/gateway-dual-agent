#!/usr/bin/env bash
# ============================================================================
# Agent Runtime — 一键启动脚本
#
# 用法:
#   chmod +x start.sh
#   ./start.sh                    # 使用 config.local.yaml
#   ./start.sh --check            # 仅检查环境，不启动
#   ./start.sh --mock             # 离线模式（不需要机器人和 LLM）
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ---------------------------------------------------------------------------
# 颜色
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠${NC} $1"; }
fail() { echo -e "  ${RED}✗${NC} $1"; }
info() { echo -e "  ${BLUE}→${NC} $1"; }

print_banner() {
    echo ""
    echo -e "${BOLD}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}║       🤖 Agent Runtime — Demo Launcher      ║${NC}"
    echo -e "${BOLD}╚══════════════════════════════════════════════════╝${NC}"
    echo ""
}

# ---------------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------------
CHECK_ONLY=false
MOCK_MODE=false
DEMO_MODE=false

for arg in "$@"; do
    case "$arg" in
        --check) CHECK_ONLY=true ;;
        --mock)  MOCK_MODE=true ;;
        --demo)  DEMO_MODE=true ;;
        --help|-h)
            echo "用法: ./start.sh [--check] [--mock] [--demo]"
            echo "  --check  仅检查环境，不启动"
            echo "  --mock   离线模式，跳过 MQTT/LLM 检查"
            echo "  --demo   启动后进入演示菜单模式"
            exit 0
            ;;
    esac
done

# ---------------------------------------------------------------------------
# 1. Python 环境
# ---------------------------------------------------------------------------
print_banner
echo -e "${BOLD}[1/5] Python 环境${NC}"

PYTHON=""
for py in python3 python; do
    if command -v "$py" &>/dev/null; then
        PYTHON="$py"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    fail "未找到 Python，请安装 Python >= 3.10"
    exit 1
fi

PY_VER=$("$PYTHON" --version 2>&1 | awk '{print $2}')
ok "Python: $PY_VER"

# ---------------------------------------------------------------------------
# 2. 依赖检查
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[2/5] 依赖检查${NC}"

MISSING_PKGS=""

check_pkg() {
    local pkg="$1"
    local import="$2"
    if "$PYTHON" -c "import $import" 2>/dev/null; then
        ok "$pkg"
    else
        fail "$pkg — 未安装"
        MISSING_PKGS="$MISSING_PKGS $pkg"
    fi
}

check_pkg "paho-mqtt" "paho.mqtt.client"
check_pkg "openai"    "openai"
check_pkg "pyyaml"    "yaml"

if [ -n "$MISSING_PKGS" ]; then
    echo ""
    warn "缺少依赖，正在安装..."
    "$PYTHON" -m pip install --user -r requirements.txt 2>&1 | tail -3
    # 重新检查
    FAILED=false
    "$PYTHON" -c "import paho.mqtt.client" 2>/dev/null || FAILED=true
    "$PYTHON" -c "import openai" 2>/dev/null || FAILED=true
    "$PYTHON" -c "import yaml" 2>/dev/null || FAILED=true
    if $FAILED; then
        fail "依赖安装失败，请手动执行: pip install -r requirements.txt"
        exit 1
    fi
    ok "依赖安装完成"
fi

# ---------------------------------------------------------------------------
# 3. 配置文件
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[3/5] 配置文件${NC}"

if [ -f "config.local.yaml" ]; then
    ok "config.local.yaml 存在"
else
    warn "config.local.yaml 不存在，从 config.example.yaml 复制..."
    cp config.example.yaml config.local.yaml
    fail "请编辑 config.local.yaml，填入真实的 MQTT IP 和 LLM 配置后重新运行"
    exit 1
fi

# 读出配置
MQTT_HOST=$("$PYTHON" -c "
import yaml
with open('config.local.yaml') as f:
    c = yaml.safe_load(f)
print(c['mqtt']['host'])
")
MQTT_PORT=$("$PYTHON" -c "
import yaml
with open('config.local.yaml') as f:
    c = yaml.safe_load(f)
print(c['mqtt']['port'])
")
LLM_URL=$("$PYTHON" -c "
import yaml
with open('config.local.yaml') as f:
    c = yaml.safe_load(f)
print(c['llm']['base_url'])
")

info "MQTT Broker: $MQTT_HOST:$MQTT_PORT"
info "LLM API:     $LLM_URL"

# ---------------------------------------------------------------------------
# 4. 连通性检查
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[4/5] 连通性检查${NC}"

if $MOCK_MODE; then
    warn "Mock 模式，跳过连通性检查"
else
    # MQTT 连通性
    if timeout 3 bash -c "echo >/dev/tcp/$MQTT_HOST/$MQTT_PORT" 2>/dev/null; then
        ok "MQTT $MQTT_HOST:$MQTT_PORT 可达"
    else
        warn "MQTT $MQTT_HOST:$MQTT_PORT 不可达"
        warn "机器人本体软件是否已启动？"
        if ! $CHECK_ONLY; then
            echo ""
            read -rp "  是否继续启动？(y/N) " yn
            case "$yn" in
                [yY]*) info "继续启动..." ;;
                *) exit 1 ;;
            esac
        fi
    fi

    # LLM 连通性
    LLM_HOST=$(echo "$LLM_URL" | sed -E 's|https?://([^:/]+).*|\1|')
    if [ -n "$LLM_HOST" ] && timeout 3 bash -c "echo >/dev/tcp/$LLM_HOST/11434" 2>/dev/null; then
        ok "LLM $LLM_HOST:11434 可达"
    else
        warn "LLM $LLM_URL 不可达"
        if ! $CHECK_ONLY; then
            echo ""
            read -rp "  是否继续启动？(对话功能将不可用) (y/N) " yn
            case "$yn" in
                [yY]*) info "继续启动..." ;;
                *) exit 1 ;;
            esac
        fi
    fi
fi

# ---------------------------------------------------------------------------
# 5. 仅检查模式
# ---------------------------------------------------------------------------
if $CHECK_ONLY; then
    echo ""
    echo -e "${GREEN}${BOLD}环境检查完成 ✓${NC}"
    exit 0
fi

# ---------------------------------------------------------------------------
# 5. 启动
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}[5/5] 启动 Agent Runtime${NC}"
echo ""

DEMO_ARG=""
if $DEMO_MODE; then
    DEMO_ARG="--demo"
fi
exec "$PYTHON" main.py $DEMO_ARG
