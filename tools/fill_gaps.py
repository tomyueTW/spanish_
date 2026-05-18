"""Phase 1b：用 Claude 補齊 7 階段基本題庫缺口。

特性：
- 冪等可續跑：gap 由當前檔案實際內容計算，重跑會接著補。
- 分批 + 去重：每批排除既有項目，只接受不重複者。
- 逐 (level,type) 存檔：中途失敗損失最小。

用法：
    python3 tools/fill_gaps.py                # 全量
    python3 tools/fill_gaps.py L1 listening   # 只跑單一 level/type（pilot 用）
    python3 tools/fill_gaps.py L1             # 只跑 L1 三型
"""
from __future__ import annotations
import json
import os
import re
import sys
import time
from pathlib import Path

from anthropic import Anthropic

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "levels"
MODEL = "claude-sonnet-4-6"

LEVELS = {
    "L1": {"cefr": "A1.1", "theme": "問候與基礎自介",
           "grammar": "ser/estar、規則動詞現在式、定/不定冠詞、主格代名詞"},
    "L2": {"cefr": "A1.2", "theme": "日常生活",
           "grammar": "常見不規則現在式、tener/ir、反身動詞、現在進行式"},
    "L3": {"cefr": "A2.1", "theme": "食衣住行",
           "grammar": "形容詞性數配合、gustar 類結構、所有格、ir + a 近未來"},
    "L4": {"cefr": "A2.2", "theme": "交通出行",
           "grammar": "簡單過去式 pretérito indefinido（規則 + 常見不規則）"},
    "L5": {"cefr": "B1.1", "theme": "意見與感受",
           "grammar": "未完成過去式 imperfecto、indefinido vs imperfecto、比較級/最高級"},
    "L6": {"cefr": "B1.2", "theme": "計畫與未來",
           "grammar": "未來式、命令式（tú/usted）、現在完成式"},
    "L7": {"cefr": "B2", "theme": "進階表達",
           "grammar": "虛擬式（現在/過去）、條件式、por/para、複合句"},
}

BATCH = {"vocab": 50, "listening": 25, "grammar": 14}
MAX_ROUNDS = 6

client = None


def load_api_key() -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if key:
        return key
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*ANTHROPIC_API_KEY\s*=\s*(.+)\s*", line)
            if m:
                return m.group(1).strip()
    raise SystemExit("找不到 ANTHROPIC_API_KEY（環境變數或 .env）")


def norm(s: str) -> str:
    return re.sub(r"[\s¿?¡!.,;:]", "", str(s or "")).lower()


def call_claude(prompt: str) -> list:
    msg = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return v
        return []
    return data if isinstance(data, list) else []


def prompt_vocab(meta, n, existing_es):
    return f"""你是西班牙語教材編輯。為 CEFR {meta['cefr']} 階段、主題「{meta['theme']}」的中文母語學習者，產生 {n} 個實用西班牙語單字。

要求：
- 單字給原型（去冠詞、去動詞變位）
- 附 IPA 音標
- zh 為繁體中文意思
- cat 為主題下的子分類（繁體中文，例如「食物」「動詞」「形容詞」）
- 難度符合 {meta['cefr']}，圍繞主題「{meta['theme']}」
- 不可與下列既有單字重複：{', '.join(existing_es) if existing_es else '（無）'}

只回 JSON 陣列，不要任何說明或 markdown：
[{{"es":"...","zh":"...","ipa":"...","cat":"..."}}]"""


def prompt_listening(meta, n, existing_es):
    return f"""你是西班牙語教材編輯。為 CEFR {meta['cefr']} 階段、主題「{meta['theme']}」的中文母語學習者，產生 {n} 句適合聽力練習的西班牙語日常句子。

要求：
- 每句 5–15 個詞，自然口語、難度符合 {meta['cefr']}
- 圍繞主題「{meta['theme']}」
- zh 為繁體中文翻譯
- topic 為該句的小主題（繁體中文）
- 不可與下列既有句子重複：{', '.join(existing_es) if existing_es else '（無）'}

只回 JSON 陣列，不要任何說明或 markdown：
[{{"es":"...","zh":"...","topic":"..."}}]"""


def prompt_grammar(meta, n, existing_topics):
    return f"""你是西班牙語教材編輯。為 CEFR {meta['cefr']} 階段的中文母語學習者，產生 {n} 題文法選擇題。

文法重點（必須圍繞這些）：{meta['grammar']}

要求：
- q 為填空句，空格用 ___ 表示（每題剛好一個空格）
- opts 為 4 個選項字串
- a 為正確選項的索引（0–3 的整數）
- zh 為該句的繁體中文翻譯
- exp 為繁體中文文法解釋（說明為何此答案正確）
- 難度符合 {meta['cefr']}，題型多樣
- topic 為文法點名稱；盡量不要與既有重複過多：{', '.join(existing_topics) if existing_topics else '（無）'}

只回 JSON 陣列，不要任何說明或 markdown：
[{{"topic":"...","q":"... ___ ...","zh":"...","opts":["..","..","..",".."],"a":0,"exp":"..."}}]"""


def fill_one(lid: str, typ: str):
    path = DATA / f"{lid}.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    meta = LEVELS[lid]
    target = d["targets"][typ]
    arr = d[typ]
    gap = target - len(arr)
    if gap <= 0:
        print(f"  {lid} {typ}: 已滿（{len(arr)}/{target}）")
        return

    if typ in ("vocab", "listening"):
        seen = {norm(x["es"]) for x in arr}
    else:
        seen_q = {norm(x.get("q", "")) for x in arr}

    rounds = 0
    while len(arr) < target and rounds < MAX_ROUNDS:
        rounds += 1
        need = target - len(arr)
        n = min(need + 3, BATCH[typ])  # 多要幾個以抵銷去重損耗
        try:
            if typ == "vocab":
                existing = [x["es"] for x in arr][-120:]
                items = call_claude(prompt_vocab(meta, n, existing))
            elif typ == "listening":
                existing = [x["es"] for x in arr][-120:]
                items = call_claude(prompt_listening(meta, n, existing))
            else:
                existing = sorted({x.get("topic", "") for x in arr})
                items = call_claude(prompt_grammar(meta, n, existing))
        except Exception as e:
            print(f"  {lid} {typ}: 第 {rounds} 輪呼叫失敗：{e}；3 秒後重試")
            time.sleep(3)
            continue

        added = 0
        for it in items:
            if len(arr) >= target:
                break
            try:
                if typ == "vocab":
                    es = str(it["es"]).strip()
                    if not es or norm(es) in seen:
                        continue
                    seen.add(norm(es))
                    arr.append({"es": es, "zh": str(it["zh"]).strip(),
                                "ipa": str(it.get("ipa", "")).strip(),
                                "cat": str(it.get("cat", meta["theme"])).strip()})
                elif typ == "listening":
                    es = str(it["es"]).strip()
                    if not es or norm(es) in seen:
                        continue
                    seen.add(norm(es))
                    idx = len([1 for x in arr if str(x.get("id", "")).startswith(f"lx_{lid}_")]) + 1
                    arr.append({"id": f"lx_{lid}_{idx:03d}", "es": es,
                                "zh": str(it["zh"]).strip(),
                                "topic": str(it.get("topic", meta["theme"])).strip()})
                else:
                    q = str(it["q"]).strip()
                    if "___" not in q or norm(q) in seen_q:
                        continue
                    opts = [str(o).strip() for o in it["opts"]]
                    a = int(it["a"])
                    if len(opts) != 4 or not (0 <= a <= 3):
                        continue
                    seen_q.add(norm(q))
                    idx = len([1 for x in arr if str(x.get("id", "")).startswith(f"gx_{lid}_")]) + 1
                    arr.append({"id": f"gx_{lid}_{idx:02d}",
                                "topic": str(it.get("topic", "")).strip(),
                                "q": q, "zh": str(it.get("zh", "")).strip(),
                                "opts": opts, "a": a,
                                "exp": str(it.get("exp", "")).strip(),
                                "level": lid})
                    continue
                added += 1
            except (KeyError, ValueError, TypeError):
                continue
        added = (added if typ != "grammar"
                 else len([x for x in arr if str(x.get("id", "")).startswith(f"gx_{lid}_")]))
        print(f"  {lid} {typ}: 第 {rounds} 輪後 {len(arr)}/{target}")

    d[typ] = arr
    d["gaps"] = {
        "vocab": d["targets"]["vocab"] - len(d["vocab"]),
        "grammar": d["targets"]["grammar"] - len(d["grammar"]),
        "listening": d["targets"]["listening"] - len(d["listening"]),
    }
    path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    short = target - len(arr)
    flag = "" if short <= 0 else f"  ⚠️ 仍缺 {short}（已達輪數上限）"
    print(f"  {lid} {typ}: 完成寫回 {len(arr)}/{target}{flag}")


def main():
    global client
    client = Anthropic(api_key=load_api_key())

    args = sys.argv[1:]
    target_levels = [a for a in args if a.upper() in LEVELS]
    target_types = [a for a in args if a in ("vocab", "grammar", "listening")]
    levels = [l.upper() for l in target_levels] or list(LEVELS)
    types = target_types or ["vocab", "grammar", "listening"]

    print(f"模型：{MODEL}　範圍：{levels} × {types}\n")
    for lid in levels:
        print(f"[{lid}] {LEVELS[lid]['cefr']} {LEVELS[lid]['theme']}")
        for typ in types:
            fill_one(lid, typ)
        print()

    print("=== 最終缺口摘要 ===")
    for lid in LEVELS:
        d = json.loads((DATA / f"{lid}.json").read_text(encoding="utf-8"))
        g = d["gaps"]
        print(f"  {lid}: vocab {len(d['vocab'])}/{d['targets']['vocab']} "
              f"grammar {len(d['grammar'])}/{d['targets']['grammar']} "
              f"listening {len(d['listening'])}/{d['targets']['listening']}  "
              f"gap={g}")


if __name__ == "__main__":
    main()
