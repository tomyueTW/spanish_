#!/bin/bash
# 西班牙語學習工具 - 啟動腳本
set -e

cd "$(dirname "$0")"

# 檢查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 找不到 python3，請先安裝 Python 3.10+"
    exit 1
fi

# 建立虛擬環境（如果還沒）
if [ ! -d "venv" ]; then
    echo "📦 建立虛擬環境..."
    python3 -m venv venv
fi

source venv/bin/activate

# 安裝套件
echo "📦 安裝依賴..."
pip install -q -r backend/requirements.txt

# 檢查 API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    if [ -f .env ]; then
        set -a
        . ./.env
        set +a
    fi
fi

if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo ""
    echo "⚠️  警告：未設定 ANTHROPIC_API_KEY 環境變數"
    echo "   YouTube/文本匯入功能將無法使用"
    echo "   請在 .env 檔案中設定：ANTHROPIC_API_KEY=sk-ant-..."
    echo "   或執行：export ANTHROPIC_API_KEY=sk-ant-..."
    echo ""
fi

# 啟動
echo ""
echo "🚀 啟動西班牙語學習工具..."
echo "📖 開啟瀏覽器訪問: http://localhost:8000"
echo "🛑 按 Ctrl+C 停止"
echo ""

cd backend
exec python main.py
