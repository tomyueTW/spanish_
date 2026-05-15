"""
西班牙語學習工具 - 後端服務
功能：
1. 提供基本題庫（500單字 / 30文法 / 100聽力）
2. 從 YouTube 連結抓取西班牙語字幕
3. 用 Anthropic Claude API 從字幕產生題目
"""
import json
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp
from anthropic import Anthropic

# ─────────── 設定 ───────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
FRONTEND_DIR = BASE_DIR / "frontend"

# Anthropic API key 從環境變數讀取
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

app = FastAPI(title="西班牙語學習工具 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────── 載入題庫 ───────────
def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


LEVELS_DIR = DATA_DIR / "levels"
LEVEL_IDS = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]
LEVELS = [load_json(LEVELS_DIR / f"{lid}.json") for lid in LEVEL_IDS]


# ─────────── API 路由 ───────────
@app.get("/api/banks")
def get_banks():
    """回傳 7 階段基本題庫"""
    return {"levels": LEVELS}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "has_api_key": bool(ANTHROPIC_API_KEY),
        "levels": [
            {
                "id": lv["id"],
                "name": lv["name"],
                "cefr": lv["cefr"],
                "vocab": len(lv.get("vocab", [])),
                "grammar": len(lv.get("grammar", [])),
                "listening": len(lv.get("listening", [])),
            }
            for lv in LEVELS
        ],
        "totals": {
            "vocab": sum(len(lv.get("vocab", [])) for lv in LEVELS),
            "grammar": sum(len(lv.get("grammar", [])) for lv in LEVELS),
            "listening": sum(len(lv.get("listening", [])) for lv in LEVELS),
        },
    }


# ─────────── YouTube 字幕抓取 ───────────
class YouTubeRequest(BaseModel):
    url: str
    lang: str = "es"  # 預設西班牙語

def extract_video_id(url: str) -> Optional[str]:
    """從各種格式的 YouTube URL 中抽取影片 ID"""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def fetch_youtube_subtitles(url: str, lang: str = "es") -> dict:
    """用 yt-dlp 抓取 YouTube 字幕"""
    video_id = extract_video_id(url)
    if not video_id:
        raise HTTPException(status_code=400, detail="無效的 YouTube 連結")

    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": [lang, f"{lang}-ES", f"{lang}-MX", "es-419"],
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"無法取得影片資訊：{e}")

    title = info.get("title", "")
    duration = info.get("duration", 0)

    # 優先用人工字幕，再用自動字幕
    subs = info.get("subtitles", {}) or {}
    auto = info.get("automatic_captions", {}) or {}

    sub_url = None
    sub_source = None
    for candidate_lang in [lang, f"{lang}-ES", f"{lang}-MX", "es-419"]:
        if candidate_lang in subs:
            for fmt in subs[candidate_lang]:
                if fmt.get("ext") in ("vtt", "srv3", "json3"):
                    sub_url = fmt["url"]
                    sub_source = "manual"
                    break
            if sub_url:
                break

    if not sub_url:
        for candidate_lang in [lang, f"{lang}-ES", f"{lang}-MX", "es-419"]:
            if candidate_lang in auto:
                for fmt in auto[candidate_lang]:
                    if fmt.get("ext") in ("vtt", "srv3", "json3"):
                        sub_url = fmt["url"]
                        sub_source = "auto"
                        break
                if sub_url:
                    break

    if not sub_url:
        raise HTTPException(
            status_code=404,
            detail=f"此影片沒有 {lang} 字幕（也沒有自動字幕）",
        )

    # 下載字幕內容
    import urllib.request
    try:
        with urllib.request.urlopen(sub_url, timeout=30) as resp:
            sub_content = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下載字幕失敗：{e}")

    # 解析 VTT/SRV3 為純文字
    text = parse_subtitle_to_text(sub_content)

    return {
        "title": title,
        "video_id": video_id,
        "duration": duration,
        "source": sub_source,
        "text": text,
        "char_count": len(text),
    }


def parse_subtitle_to_text(content: str) -> str:
    """把 VTT / SRV3 字幕轉成乾淨的純文字"""
    # 如果是 JSON 格式 (srv3/json3)
    if content.lstrip().startswith("{"):
        try:
            data = json.loads(content)
            events = data.get("events", [])
            lines = []
            for ev in events:
                segs = ev.get("segs", [])
                line = "".join(s.get("utf8", "") for s in segs)
                line = line.strip()
                if line and line != "\n":
                    lines.append(line)
            return " ".join(lines)
        except Exception:
            pass

    # VTT 格式
    lines = []
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("WEBVTT") or line.startswith("NOTE") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if "-->" in line:
            continue
        if re.match(r"^\d+$", line):
            continue
        # 移除 <c> 等 HTML 標籤
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"&[a-z]+;", "", line)
        if line:
            lines.append(line)

    # 去重連續重複行（自動字幕常有的問題）
    deduped = []
    for ln in lines:
        if not deduped or deduped[-1] != ln:
            deduped.append(ln)
    return " ".join(deduped)


@app.post("/api/youtube/fetch")
def fetch_youtube(req: YouTubeRequest):
    """抓 YouTube 字幕（不產題目，純抓取）"""
    return fetch_youtube_subtitles(req.url, req.lang)


# ─────────── Claude 產題目 ───────────
class GenerateRequest(BaseModel):
    text: str
    title: str = ""
    num_vocab: int = 8
    num_listening: int = 5


GENERATION_PROMPT = """你是一位西班牙語教學助理。請從下列西班牙語文本中產出測驗題目，給「中文母語、初級到中級」的學習者使用。

文本標題：{title}

文本內容（西班牙語）：
{text}

請產出以下兩類題目，並嚴格用 JSON 格式回覆（不要有 markdown 標記，不要有額外說明文字）：

1. 單字題（{num_vocab} 題）：挑出文本中對學習者有用的常見單字（避免太罕見或專有名詞）
2. 聽力句子（{num_listening} 句）：從文本中挑出完整、適合作為聽力練習的句子（每句 5-20 個字之間，太長的句子不要）

回覆格式：
{{
  "vocab": [
    {{"es": "西語單字", "zh": "繁體中文意思", "cat": "從文本萃取"}}
  ],
  "listening": [
    {{"es": "完整的西語句子", "zh": "繁體中文翻譯", "topic": "從文本萃取"}}
  ]
}}

注意：
- 中文翻譯必須是繁體中文
- 單字要去掉冠詞和變位（給出原型）
- 句子要文本中實際出現的（或非常接近的）
- 只回 JSON，不要加任何說明
"""


@app.post("/api/generate")
def generate_questions(req: GenerateRequest):
    """從文本用 Claude 產題目"""
    if not anthropic_client:
        raise HTTPException(
            status_code=500,
            detail="伺服器未設定 ANTHROPIC_API_KEY 環境變數",
        )

    # 文本太長就截斷（保留前 8000 字）
    text = req.text[:8000]

    prompt = GENERATION_PROMPT.format(
        title=req.title or "(無標題)",
        text=text,
        num_vocab=req.num_vocab,
        num_listening=req.num_listening,
    )

    try:
        msg = anthropic_client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()

        # 移除可能的 markdown 標記
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        data = json.loads(raw)
        return {
            "vocab": data.get("vocab", []),
            "listening": data.get("listening", []),
            "source_title": req.title,
        }
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI 回應格式錯誤：{e}。原始回應：{raw[:300]}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"產生題目失敗：{e}")


# ─────────── 一鍵處理 YouTube ───────────
class YouTubeQuizRequest(BaseModel):
    url: str
    lang: str = "es"
    num_vocab: int = 8
    num_listening: int = 5


@app.post("/api/youtube/quiz")
def youtube_to_quiz(req: YouTubeQuizRequest):
    """一鍵：YouTube → 字幕 → 題目"""
    subs = fetch_youtube_subtitles(req.url, req.lang)
    if not subs["text"].strip():
        raise HTTPException(status_code=404, detail="抓到的字幕是空的")

    gen_req = GenerateRequest(
        text=subs["text"],
        title=subs["title"],
        num_vocab=req.num_vocab,
        num_listening=req.num_listening,
    )
    result = generate_questions(gen_req)
    result["video"] = {
        "title": subs["title"],
        "video_id": subs["video_id"],
        "duration": subs["duration"],
        "subtitle_source": subs["source"],
    }
    return result


# ─────────── 字幕檔上傳 ───────────
@app.post("/api/upload/subtitle")
async def upload_subtitle(
    file: UploadFile = File(...),
    num_vocab: int = 8,
    num_listening: int = 5,
):
    """上傳 SRT/VTT 字幕檔 → 產題目"""
    content = (await file.read()).decode("utf-8", errors="ignore")
    text = parse_subtitle_to_text(content)
    if not text.strip():
        # 嘗試當作 SRT 解析（簡易版）
        lines = []
        for line in content.split("\n"):
            line = line.strip()
            if not line or "-->" in line or re.match(r"^\d+$", line):
                continue
            line = re.sub(r"<[^>]+>", "", line)
            lines.append(line)
        text = " ".join(lines)

    if not text.strip():
        raise HTTPException(status_code=400, detail="無法解析字幕內容")

    return generate_questions(GenerateRequest(
        text=text,
        title=file.filename,
        num_vocab=num_vocab,
        num_listening=num_listening,
    ))


# ─────────── 靜態檔案（前端）───────────
@app.get("/")
def index():
    return FileResponse(FRONTEND_DIR / "index.html")

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
