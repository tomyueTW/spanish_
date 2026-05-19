# 🇪🇸 西班牙語學習工具

一個全端的西班牙語測驗練習應用，內建 **7 階段 CEFR 分級題庫**（A1.1 → B2，共 1050 單字 / 98 文法 / 210 聽力），並支援從 YouTube 影片、字幕檔或文本自動產生客製化題庫。學習進度與自製題庫以 Markdown 檔存放在你自選的本機資料夾，方便用雲端硬碟跨裝置同步。

## ✨ 功能

### 基本題庫（內建，7 階段分級）

每階段各 **150 單字 / 14 文法 / 30 聽力**：

| 階段 | 主題 | CEFR |
|---|---|---|
| L1 | 問候與基礎自介 | A1.1 |
| L2 | 日常生活 | A1.2 |
| L3 | 食衣住行 | A2.1 |
| L4 | 交通出行 | A2.2 |
| L5 | 意見與感受 | B1.1 |
| L6 | 計畫與未來 | B1.2 |
| L7 | 進階表達 | B2 |

題型：**單字測驗**、**句型文法**（ser/estar、動詞變位、冠詞、形容詞配合、過去式、虛擬式入門 等）、**聽力練習**（日常對話）。

### 擴充題庫（AI 自動產生，選用）

> 需設定 Anthropic API key，未設定時仍可使用全部內建題庫。

- 🎬 **YouTube 連結匯入**：貼上連結 → 後端抓字幕 → Claude AI 產生單字題與聽力題
- 📄 **字幕檔上傳**：支援 SRT / VTT
- ✍️ **直接貼文本**：歌詞、文章、對話皆可

### 學習功能

- 西班牙語語音朗讀（瀏覽器內建 Web Speech API）
- 每題即時解釋（文法規則、單字類別）
- 錯題自動彙整複習
- 學習進度統計（總答題數、正確率、完成測驗次數，且**逐題庫保留練習歷史**）
- 進度與自製題庫以 `.md` 檔存於本機資料夾，可用雲端硬碟跨裝置同步

## 🚀 快速開始

### 1. 環境需求

- Python 3.10+
- （選用）Anthropic API key — 僅 YouTube/字幕/文本匯入功能需要（[申請連結](https://console.anthropic.com)）
- （選用）支援 File System Access API 的瀏覽器（Chrome / Edge）— 用於把進度與自製題庫寫入本機資料夾；其他瀏覽器會自動退回 localStorage 備援

### 2.（選用）設定 API key

複製 `.env.example` 為 `.env`：

```bash
cp .env.example .env
```

編輯 `.env`，填入你的 API key：

```
ANTHROPIC_API_KEY=sk-ant-api03-你的key
```

不設定也能啟動，只是無法使用 AI 匯入功能。

### 3. 啟動

```bash
./start.sh
```

腳本會自動：
1. 建立虛擬環境
2. 安裝套件（fastapi, yt-dlp, anthropic 等）
3. 載入 `.env`（若存在）並啟動後端伺服器

開啟瀏覽器訪問：**http://localhost:8000**

### 手動啟動（若不想用腳本）

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # 選用
cd backend && python main.py
```

## 📂 專案結構

```
spanish_app/
├── backend/
│   ├── main.py              # FastAPI 後端
│   └── requirements.txt
├── frontend/
│   └── index.html           # 單頁應用（HTML + JS + CSS，無建置步驟）
├── data/
│   ├── levels/
│   │   └── L1.json … L7.json # 7 階段 CEFR 分級題庫（執行時實際使用）
│   ├── vocab_500.json        # 舊單檔題庫（已由 levels/ 取代，保留備查）
│   ├── grammar_30.json       #   同上
│   └── listening_100.json    #   同上
├── tools/
│   ├── seed/L1.json … L7.json # 人工種子題庫
│   ├── merge_seed.py          # 把 seed 合併進 data/levels（去重、補 id）
│   ├── fill_gaps.py           # 缺口偵測/補題輔助
│   └── restructure_to_levels.py
├── start.sh                 # 啟動腳本
├── .env.example
└── README.md
```

> 註：`data/vocab_500.json`、`grammar_30.json`、`listening_100.json` 為早期單一題庫，目前後端**不再讀取**，僅保留作歷史備查。執行時使用的是 `data/levels/L1.json` ~ `L7.json`。

## 🛠 API 端點

| 端點 | 方法 | 說明 |
|---|---|---|
| `/api/banks` | GET | 取得 7 階段內建題庫（`{ "levels": [...] }`） |
| `/api/health` | GET | 健康檢查（各階段與總計題數、是否已設定 API key） |
| `/api/youtube/quiz` | POST | YouTube 連結 → 題目（一鍵） |
| `/api/youtube/fetch` | POST | 僅抓字幕，不產題目 |
| `/api/generate` | POST | 從文本產題目 |
| `/api/upload/subtitle` | POST | 上傳 SRT/VTT 字幕檔 → 產題目 |

> 後端在啟動時一次性載入 L1–L7 並快取於記憶體。**編輯 `data/levels/*.json` 後需重啟後端**，否則 `/api/banks` 與 `/api/health` 會回傳舊資料。

## 💾 資料儲存

- **內建題庫**：後端 JSON 檔（`data/levels/L1.json` ~ `L7.json`）
- **自製題庫**：寫入你選定資料夾下的 `banks/*.md`（每個題庫一個 `.md` 檔）
- **學習進度**：寫入同資料夾下的 `progress/_summary.md`（聚合）與 `progress/<題庫>.md`（逐題庫歷史）
- **備援**：若瀏覽器不支援 File System Access API，進度會改存 localStorage（仍可正常使用，只是不寫檔）
- **跨裝置同步**：把選定的資料夾放在雲端硬碟（iCloud / Google Drive / Dropbox 等），在另一台裝置選同一個資料夾即可，不需手動匯出/匯入

## ⚠️ 常見問題

**Q: 沒有 API key 可以用嗎？**
A: 可以。沒 API key 仍能使用全部 7 階段內建題庫（單字/文法/聽力），只是無法使用 YouTube/字幕/文本 AI 匯入。

**Q: 改了 `data/levels/*.json` 但題數沒變？**
A: 後端啟動時就把題庫快取在記憶體，請重啟後端（重新執行 `./start.sh` 或 `python main.py`）。

**Q: 進度沒有跨裝置同步？**
A: 第一次使用時要在前端授權選擇一個本機資料夾；把該資料夾放在雲端硬碟，並在每台裝置選同一個資料夾。未授權資料夾時進度只會存在該瀏覽器的 localStorage。

**Q: 為什麼進度寫不進檔案？**
A: File System Access API 目前主要支援 Chrome / Edge。其他瀏覽器會自動退回 localStorage 備援，功能仍可用。

**Q: YouTube 抓不到字幕？**
A: 影片必須有西班牙語字幕（人工或自動）。可在 YouTube 影片頁的設定 → 字幕中確認。

**Q: AI 產的題目品質？**
A: 使用 Claude Opus 模型，品質不錯。偶爾可能產出不理想的題目，可隨時刪除整個自製題庫重新匯入。

**Q: 為什麼後端需要 yt-dlp 而不能用純前端？**
A: 瀏覽器有 CORS 限制，無法直接抓 YouTube 字幕。yt-dlp 是 Python 套件，能處理各種影片平台。

## 🔧 自訂

- **擴充內建題庫**：把人工題目寫入 `tools/seed/L<N>.json`，執行 `venv/bin/python tools/merge_seed.py L<N>` 合併進 `data/levels/`（自動去重、補 id），再重啟後端
- **調整 AI 出題風格**：改 `backend/main.py` 中的 `GENERATION_PROMPT`

## 📜 授權

自由使用、修改、分享。
