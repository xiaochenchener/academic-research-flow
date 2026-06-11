#!/bin/bash
# ============================================================
# Academic Research Flow - 一键启动脚本
# ============================================================
#
# 使用方式:
#   ./run.sh                        交互式问答模式
#   ./run.sh "研究方向"               快速检索（用默认参数）
#   ./run.sh "研究方向" "创新点"      快速检索 + 创新点验证
#   ./run.sh -- -t "..." --from-year 2020  透传原始参数
#
# ============================================================

set -e

# 项目根目录（脚本所在目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 颜色
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# 激活虚拟环境
activate_venv() {
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    else
        echo -e "${YELLOW}⚠ 虚拟环境未找到，正在创建...${NC}"
        python3 -m venv .venv
        source .venv/bin/activate
        python3 -m pip install -r requirements.txt -q
        echo -e "${GREEN}✅ 环境安装完成${NC}"
    fi
}

# 显示横幅
banner() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║      ${GREEN}☕ Academic Research Flow${BLUE}          ║${NC}"
    echo -e "${BLUE}║   ${CYAN}一杯咖啡的功夫，完成一篇文献综述${BLUE}       ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
    echo ""
}

# 交互式问答模式
interactive_mode() {
    banner
    echo -e "${CYAN}📋 交互式配置模式${NC}"
    echo -e "（直接按回车使用默认值）"
    echo ""

    # 1. 研究方向（必填）
    while true; do
        echo -ne "${YELLOW}1. 研究方向:${NC} "
        read -r TOPIC
        if [ -n "$TOPIC" ]; then
            break
        fi
        echo -e "   ${YELLOW}⚠ 研究方向不能为空${NC}"
    done
    echo ""

    # 2. 创新点（可选）
    echo -ne "${YELLOW}2. 创新点描述 (可选):${NC} "
    read -r INNOVATION
    echo ""

    # 3. 年份范围
    echo -ne "${YELLOW}3. 检索起始年份 [2020]:${NC} "
    read -r FROM_YEAR
    FROM_YEAR=${FROM_YEAR:-2020}

    echo -ne "${YELLOW}4. 检索结束年份 [2026]:${NC} "
    read -r TO_YEAR
    TO_YEAR=${TO_YEAR:-2026}
    echo ""

    # 4. 检索模式
    echo -e "${YELLOW}5. 检索模式:${NC}"
    echo "   [1] 快速检索 (无 AI，只做检索+分类+导出)"
    echo "   [2] 完整 AI 分析 (选题分析+文献综述+引用句，推荐)"
    echo "   [3] 极简模式 (最小检索量，快速预览)"
    echo "   [4] 自定义参数"
    echo -ne "   ${CYAN}选择 [2]:${NC} "
    read -r MODE
    MODE=${MODE:-2}
    echo ""

    # 6. 输出目录（可选）
    echo -ne "${YELLOW}6. 输出目录名 (可选，留空自动生成):${NC} "
    read -r OUT_DIR
    echo ""

    # 构建命令
    CMD="python3 scripts/main.py -t \"$TOPIC\" --from-year $FROM_YEAR --to-year $TO_YEAR"

    if [ -n "$INNOVATION" ]; then
        CMD="$CMD -i \"$INNOVATION\""
    fi

    case $MODE in
        1)
            CMD="$CMD --skip-deepseek --skip-enrichment --skip-citations --skip-journal-info"
            ;;
        2)
            # 默认完整模式，不添加 skip 参数
            ;;
        3)
            CMD="$CMD --classic-count 10 --recent-count 10 --skip-deepseek --skip-enrichment --skip-verification --skip-citations --skip-journal-info --skip-snowballing"
            ;;
        4)
            echo -ne "${YELLOW}   自定义参数:${NC} "
            read -r EXTRA_ARGS
            CMD="$CMD $EXTRA_ARGS"
            ;;
    esac

    if [ -n "$OUT_DIR" ]; then
        CMD="$CMD --output-dir outputs/$OUT_DIR"
    fi

    echo ""
    echo -e "${CYAN}────────────────────────────────────────${NC}"
    echo -e "${GREEN}🚀 执行命令:${NC}"
    echo -e "   $CMD"
    echo -e "${CYAN}────────────────────────────────────────${NC}"
    echo ""
    echo -ne "${YELLOW}确认执行? [Y/n]:${NC} "
    read -r CONFIRM
    if [ "$CONFIRM" = "n" ] || [ "$CONFIRM" = "N" ]; then
        echo "已取消"
        exit 0
    fi

    echo ""
    eval "$CMD"
}

# 快速模式: ./run.sh "研究方向"
quick_mode() {
    TOPIC="$1"
    INNOVATION="${2:-}"

    banner
    echo -e "${CYAN}⚡ 快速检索模式${NC}"
    echo -e "   研究方向: ${GREEN}$TOPIC${NC}"
    if [ -n "$INNOVATION" ]; then
        echo -e "   创新点:   ${GREEN}$INNOVATION${NC}"
    fi
    echo -e "   年份范围: 2020-2026 (默认)"
    echo ""

    CMD="python3 scripts/main.py -t \"$TOPIC\" --from-year 2020 --to-year 2026"
    if [ -n "$INNOVATION" ]; then
        CMD="$CMD -i \"$INNOVATION\""
    fi

    echo -e "${GREEN}🚀 开始检索...${NC}"
    echo ""
    eval "$CMD"
}

# ============================================================
# 主入口
# ============================================================
activate_venv

# 检查 .env 是否存在
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠ .env 文件未找到，将使用纯脚本模式（无 AI 功能）${NC}"
    echo -e "  如需 AI 功能，请执行: ${CYAN}cp .env.example .env${NC} 并填入 API Key"
    echo ""
fi

case $# in
    0)
        # 无参数 → 交互式模式
        interactive_mode
        ;;
    1)
        if [ "$1" = "--" ]; then
            # ./run.sh -- → 交互式
            interactive_mode
        elif [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
            banner
            echo "使用方式:"
            echo ""
            echo "  ./run.sh                         交互式问答模式"
            echo "  ./run.sh \"研究方向\"                快速检索"
            echo "  ./run.sh \"研究方向\" \"创新点\"       快速检索 + 创新点验证"
            echo "  ./run.sh -- <原始参数>             透传给 main.py"
            echo ""
            echo "示例:"
            echo "  ./run.sh"
            echo "  ./run.sh \"双层日光温室热湿环境动态模型\""
            echo "  ./run.sh \"相变电热地板\" \"新型微胶囊PCM封装\""
            echo "  ./run.sh -- -t \"solar greenhouse\" --from-year 2015 --skip-deepseek"
        else
            quick_mode "$1"
        fi
        ;;
    2)
        if [ "$1" = "--" ]; then
            shift
            banner
            python3 scripts/main.py "$@"
        else
            quick_mode "$1" "$2"
        fi
        ;;
    *)
        if [ "$1" = "--" ]; then
            shift
            banner
            python3 scripts/main.py "$@"
        else
            echo "用法: ./run.sh [研究方向] [创新点]"
            echo "      ./run.sh -- [原始参数]"
            echo "      ./run.sh  (交互式模式)"
        fi
        ;;
esac
