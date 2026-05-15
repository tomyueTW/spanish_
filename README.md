# 🇪🇸 西班牙語學習工具

一個全端的西班牙語測驗練習應用，內建 600+ 單字、30 句型文法、100 句聽力，並支援從 YouTube 影片自動產生客製化題目。

## ✨ 功能

### 基本題庫（內建）
- **單字測驗**：632 個單字（分 19 類：問候、家庭、食物、動物、職業、形容詞、動詞 等）
- **句型文法**：30 題（ser/estar、動詞變位、冠詞、形容詞配合、過去式、虛擬式入門 等）
- **聽力練習**：100 句日常對話（問候、購物、問路、餐廳、旅館、感受 等）

### 擴充題庫（AI 自動產生）
- 🎬 **YouTube 連結匯入**：貼上連結 → 後端抓字幕 → Claude AI 產生單字題和聽力題
- 📄 **字幕檔上傳**：支援 SRT / VTT
- ✍️ **直接貼文本**：歌詞、文章、對話皆可

### 學習功能
- 西班牙語語音朗讀（瀏覽器內建 Web Speech API）
- 每題即時解釋（文法規則、單字類別）
- 錯題自動彙整複習
- 學習進度統計（總答題數、正確率、完成測驗次數）
- 進度可匯出/匯入 JSON 跨裝置同步

## 🚀 快速開始

### 1. 環境需求
- Python 3.10+
- Anthropic API key（[申請連結](https://console.anthropic.com)）

### 2. 設定 API key

複製 `.env.example` 為 `.env`：
```bash
cp .env.example .env
```

編輯 `.env`，填入你的 API key：
```
ANTHROPIC_API_KEY=sk-ant-api03-你的key
```

### 3. 啟動

```bash
./start.sh
```

腳本會自動：
1. 建立虛擬環境
2. 安裝套件（fastapi, yt-dlp, anthropic 等）
3. 啟動後端伺服器

開啟瀏覽器訪問：**http://localhost:8000**

### 手動啟動（若不想用腳本）

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
cd backend && python main.py
```

## 📂 專案結構

```
spanish_app/
├── backend/
│   ├── main.py              # FastAPI 後端
│   └── requirements.txt
├── frontend/
│   └── index.html           # 單頁應用（HTML + JS + CSS）
├── data/
│   ├── vocab_500.json       # 632 個單字
│   ├── grammar_30.json      # 30 個文法題
│   └── listening_100.json   # 100 句聽力
├── start.sh                 # 啟動腳本
├── .env.example
└── README.md
```

## 🛠 API 端點

| 端點 | 方法 | 說明 |
|---|---|---|
| `/api/banks` | GET | 取得所有內建題庫 |
| `/api/health` | GET | 健康檢查 |
| `/api/youtube/quiz` | POST | YouTube 連結 → 題目（一鍵） |
| `/api/youtube/fetch` | POST | 僅抓字幕 |
| `/api/generate` | POST | 從文本產題目 |
| `/api/upload/subtitle` | POST | 上傳 SRT/VTT |

## 💾 資料儲存

- **內建題庫**：後端 JSON 檔案
- **自製題庫 + 進度**：瀏覽器 localStorage（自動保存）
- **跨裝置同步**：在「題庫管理」匯出 JSON 檔，到另一台裝置匯入

## ⚠️ 常見問題

**Q: YouTube 抓不到字幕？**
A: 影片必須有西班牙語字幕（人工或自動）。可在 YouTube 影片頁右下角的設定 → 字幕中確認。

**Q: AI 產的題目品質？**
A: 用 Claude Opus 4.5 模型，品質不錯。但 AI 可能偶爾產出不太理想的題目，可隨時刪除整個題庫重新匯入。

**Q: 沒有 API key 可以用嗎？**
A: 可以！沒 API key 仍能使用所有內建題庫（單字/文法/聽力），只是無法使用 YouTube 匯入功能。

**Q: 為什麼後端需要 yt-dlp 而不能用純前端？**
A: 瀏覽器有 CORS 限制，無法直接抓 YouTube 字幕。yt-dlp 是 Python 套件，能處理各種影片平台。

## 🔧 自訂

- 改 `data/vocab_500.json` 加自己的單字（永久內建）
- 改 `data/grammar_30.json` 新增文法題
- 改 `backend/main.py` 中的 `GENERATION_PROMPT` 調整 AI 出題風格

## 📜 授權

自由使用、修改、分享。
