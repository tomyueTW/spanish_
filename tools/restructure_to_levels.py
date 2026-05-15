"""一次性遷移腳本：把現有 vocab/grammar/listening 拆成 7 個 CEFR 階段。

執行：
    python3 tools/restructure_to_levels.py

輸出：data/levels/L1.json ... L7.json
不會刪除原本的 vocab_500.json / grammar_30.json / listening_100.json。
"""
from __future__ import annotations
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "levels"
OUT.mkdir(parents=True, exist_ok=True)

# 階段定義（CEFR 主軸 + 主題）
LEVELS = [
    {"id": "L1", "name": "問候與基礎自介",  "cefr": "A1.1", "target_vocab": 150, "target_grammar": 14, "target_listening": 30},
    {"id": "L2", "name": "日常生活",         "cefr": "A1.2", "target_vocab": 150, "target_grammar": 14, "target_listening": 30},
    {"id": "L3", "name": "食衣住行",         "cefr": "A2.1", "target_vocab": 150, "target_grammar": 14, "target_listening": 30},
    {"id": "L4", "name": "交通出行",         "cefr": "A2.2", "target_vocab": 150, "target_grammar": 14, "target_listening": 30},
    {"id": "L5", "name": "意見與感受",       "cefr": "B1.1", "target_vocab": 150, "target_grammar": 14, "target_listening": 30},
    {"id": "L6", "name": "計畫與未來",       "cefr": "B1.2", "target_vocab": 150, "target_grammar": 14, "target_listening": 30},
    {"id": "L7", "name": "進階表達",         "cefr": "B2",   "target_vocab": 150, "target_grammar": 14, "target_listening": 30},
]

# 單字類別 → 階段
VOCAB_PARTITION = {
    "L1": ["問候與寒暄", "代名詞與人稱", "數字", "家庭"],
    "L2": ["食物與飲料", "身體與健康", "衣物"],
    "L3": ["家與住所", "動物", "顏色", "時間與日期"],
    "L4": ["交通與旅行", "城市與場所", "職業", "天氣與自然"],
    "L5": ["形容詞", "疑問詞與連接詞"],
    "L6": ["常用動詞", "其他常用名詞"],
    "L7": [],   # B2 進階：新內容（Phase 1b AI 補）
}

# 文法 topic → 階段（match 用 substring contains，因 topic 字串會帶副資訊）
GRAMMAR_PARTITION = {
    "L1": ["ser", "定冠詞", "不定冠詞", "所有格"],
    "L2": ["estar", "-ar 規則", "-er 規則", "-ir 規則", "tener", "反身動詞", "現在進行式"],
    "L3": ["形容詞性數", "gustar", "ir + a"],
    "L4": ["簡單過去式", "未完成過去式"],
    "L5": ["比較級", "最高級", "疑問詞"],
    "L6": ["未來式", "命令式", "現在完成式"],
    "L7": ["虛擬式"],
}

# 聽力 topic → 階段
LISTENING_PARTITION = {
    "L1": ["問候", "時間", "日常"],
    "L2": ["食物", "健康", "讚美", "祝賀"],
    "L3": ["購物", "旅館", "天氣"],
    "L4": ["問路", "交通"],
    "L5": ["感受", "情感"],
    "L6": ["意見", "溝通"],
    "L7": ["緊急"],
}


def assign_grammar_level(topic: str) -> str | None:
    for level_id, keys in GRAMMAR_PARTITION.items():
        for key in keys:
            if key in topic:
                return level_id
    return None


def main():
    vocab_src = json.loads((DATA / "vocab_500.json").read_text(encoding="utf-8"))
    grammar_src = json.loads((DATA / "grammar_30.json").read_text(encoding="utf-8"))
    listen_src = json.loads((DATA / "listening_100.json").read_text(encoding="utf-8"))

    # 將 vocab 攤平為 list（每項標記 cat）
    flat_vocab: list[dict] = []
    for cat, words in vocab_src["categories"].items():
        for w in words:
            flat_vocab.append({**w, "cat": w.get("cat", cat)})

    summary = []

    for level in LEVELS:
        lid = level["id"]
        vocab_cats = VOCAB_PARTITION[lid]
        listen_topics = LISTENING_PARTITION[lid]

        v_items = [w for w in flat_vocab if w.get("cat") in vocab_cats]
        g_items = [it for it in grammar_src["items"] if assign_grammar_level(it.get("topic", "")) == lid]
        # 給每個 grammar item 一個穩定的 level 標記
        for it in g_items:
            it.setdefault("level", lid)

        l_items = [it for it in listen_src["items"] if any(t in it.get("topic", "") for t in listen_topics)]

        out = {
            "id": lid,
            "name": level["name"],
            "cefr": level["cefr"],
            "vocab": v_items,
            "grammar": g_items,
            "listening": l_items,
            "gaps": {
                "vocab": level["target_vocab"] - len(v_items),
                "grammar": level["target_grammar"] - len(g_items),
                "listening": level["target_listening"] - len(l_items),
            },
            "targets": {
                "vocab": level["target_vocab"],
                "grammar": level["target_grammar"],
                "listening": level["target_listening"],
            },
        }
        path = OUT / f"{lid}.json"
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        summary.append((lid, level["cefr"], level["name"], len(v_items), len(g_items), len(l_items), out["gaps"]))

    # 印出摘要
    print(f"{'L':<4}{'CEFR':<6}{'主題':<14}{'單字':>6}{'文法':>6}{'句型':>6}  缺口")
    print("-" * 70)
    for lid, cefr, name, v, g, l, gaps in summary:
        print(f"{lid:<4}{cefr:<6}{name:<14}{v:>6}{g:>6}{l:>6}  v+{gaps['vocab']} g+{gaps['grammar']} l+{gaps['listening']}")
    tot_v = sum(s[3] for s in summary)
    tot_g = sum(s[4] for s in summary)
    tot_l = sum(s[5] for s in summary)
    print("-" * 70)
    print(f"{'總計':<4}{'':<6}{'':<14}{tot_v:>6}{tot_g:>6}{tot_l:>6}")


if __name__ == "__main__":
    main()
