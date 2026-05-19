"""手動補齊：把 tools/seed/<LID>.json 的人工內容合併進 data/levels/<LID>.json。

與 tools/fill_gaps.py 同一套合併規則，差別只在資料來源是「人工種子檔」而非
Claude API：
- norm() 正規化去重（vocab/listening 比 es，grammar 比 q）
- vocab 給 vx_<LID>_<NNN>、listening 給 lx_<LID>_<NNN>、grammar 給 gx_<LID>_<NN>
  流水號，grammar 補 level
- 達 targets 即停（多餘緩衝忽略）
- 重算 gaps，逐 Level 寫回
- 冪等：重跑只會補不足、不會重複寫入

用法：
    python3 tools/merge_seed.py            # 全部 L1..L7
    python3 tools/merge_seed.py L1 L7      # 只跑指定 level
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "levels"
SEED = ROOT / "tools" / "seed"
LEVEL_IDS = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]


def norm(s: str) -> str:
    return re.sub(r"[\s¿?¡!.,;:]", "", str(s or "")).lower()


def merge_one(lid: str) -> dict:
    dpath = DATA / f"{lid}.json"
    spath = SEED / f"{lid}.json"
    d = json.loads(dpath.read_text(encoding="utf-8"))
    if not spath.exists():
        seed = {}
    else:
        seed = json.loads(spath.read_text(encoding="utf-8"))

    report = {}
    for typ in ("vocab", "grammar", "listening"):
        arr = d.get(typ, [])
        target = d["targets"][typ]
        items = seed.get(typ, []) or []

        if typ == "grammar":
            seen = {norm(x.get("q", "")) for x in arr}
        else:
            seen = {norm(x.get("es", "")) for x in arr}

        added = 0
        skipped_dup = 0
        skipped_bad = 0
        for it in items:
            if len(arr) >= target:
                break
            try:
                if typ == "vocab":
                    es = str(it["es"]).strip()
                    if not es:
                        skipped_bad += 1
                        continue
                    if norm(es) in seen:
                        skipped_dup += 1
                        continue
                    seen.add(norm(es))
                    idx = len([1 for x in arr
                               if str(x.get("id", "")).startswith(f"vx_{lid}_")]) + 1
                    arr.append({
                        "id": f"vx_{lid}_{idx:03d}",
                        "es": es,
                        "zh": str(it["zh"]).strip(),
                        "ipa": str(it.get("ipa", "")).strip(),
                        "cat": str(it.get("cat", "")).strip(),
                    })
                elif typ == "listening":
                    es = str(it["es"]).strip()
                    if not es:
                        skipped_bad += 1
                        continue
                    if norm(es) in seen:
                        skipped_dup += 1
                        continue
                    seen.add(norm(es))
                    idx = len([1 for x in arr
                               if str(x.get("id", "")).startswith(f"lx_{lid}_")]) + 1
                    arr.append({
                        "id": f"lx_{lid}_{idx:03d}",
                        "es": es,
                        "zh": str(it["zh"]).strip(),
                        "topic": str(it.get("topic", "")).strip(),
                    })
                else:  # grammar
                    q = str(it["q"]).strip()
                    if q.count("___") != 1:
                        skipped_bad += 1
                        continue
                    if norm(q) in seen:
                        skipped_dup += 1
                        continue
                    opts = [str(o).strip() for o in it["opts"]]
                    a = int(it["a"])
                    if len(opts) != 4 or not (0 <= a <= 3):
                        skipped_bad += 1
                        continue
                    seen.add(norm(q))
                    idx = len([1 for x in arr
                               if str(x.get("id", "")).startswith(f"gx_{lid}_")]) + 1
                    arr.append({
                        "id": f"gx_{lid}_{idx:02d}",
                        "topic": str(it.get("topic", "")).strip(),
                        "q": q,
                        "zh": str(it.get("zh", "")).strip(),
                        "opts": opts,
                        "a": a,
                        "exp": str(it.get("exp", "")).strip(),
                        "level": lid,
                    })
                added += 1
            except (KeyError, ValueError, TypeError):
                skipped_bad += 1
                continue

        d[typ] = arr
        report[typ] = {
            "count": len(arr),
            "target": target,
            "added": added,
            "dup": skipped_dup,
            "bad": skipped_bad,
        }

    d["gaps"] = {
        "vocab": d["targets"]["vocab"] - len(d["vocab"]),
        "grammar": d["targets"]["grammar"] - len(d["grammar"]),
        "listening": d["targets"]["listening"] - len(d["listening"]),
    }
    dpath.write_text(json.dumps(d, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    report["gaps"] = d["gaps"]
    return report


def main():
    args = [a.upper() for a in sys.argv[1:]]
    levels = [l for l in args if l in LEVEL_IDS] or LEVEL_IDS

    all_full = True
    for lid in levels:
        r = merge_one(lid)
        for typ in ("vocab", "grammar", "listening"):
            t = r[typ]
            print(f"  {lid} {typ:9s}: {t['count']:3d}/{t['target']:<3d} "
                  f"(+{t['added']} dup{t['dup']} bad{t['bad']})")
        g = r["gaps"]
        short = g["vocab"] + g["grammar"] + g["listening"]
        flag = "  ✅" if short == 0 else f"  ⚠️ 仍缺 {g}"
        if short != 0:
            all_full = False
        print(f"  {lid} gaps={g}{flag}\n")

    print("=== 全部達標 ===" if all_full else "=== 仍有缺口（請補種子檔後重跑）===")


if __name__ == "__main__":
    main()
