"""F0a 一次性遷移：替 data/levels/<LID>.json 的 vocab 補穩定 id。

決策（PRODUCT_PLAN.md §5 已拍板）：內建 vocab 改用穩定 id 而非 es 字串鍵，
日後修改西語拼寫時學習歷史不會斷。id 慣例沿用 listening(lx_)/grammar(gx_)：

    vx_<LID>_<NNN>     例：vx_L1_001、vx_L3_087

特性：
- 冪等：已有非空 id 的 vocab 一律保留、不重新編號；重跑只補沒 id 的。
- 不重排：嚴格依現有陣列順序編號，不動既有內容/順序。
- id 置於每筆首鍵（與 listening/grammar 一致）；其餘欄位順序不變。
- 寫回格式與 merge_seed.py 完全一致（ensure_ascii=False, indent=2, 無尾換行）。

用法：
    python3 tools/add_vocab_ids.py            # 全部 L1..L7
    python3 tools/add_vocab_ids.py L1 L3      # 只跑指定 level
    python3 tools/add_vocab_ids.py --check    # 只檢查、不寫回（CI/驗證用）
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "levels"
LEVEL_IDS = ["L1", "L2", "L3", "L4", "L5", "L6", "L7"]

# vocab 欄位輸出順序（id 置首，與 listening/grammar 一致）
VOCAB_ORDER = ["id", "es", "zh", "ipa", "cat"]


def reorder_vocab(item: dict) -> dict:
    """回傳依 VOCAB_ORDER 排序的新 dict，未列入的欄位接在後面（保險）。"""
    out = {k: item[k] for k in VOCAB_ORDER if k in item}
    for k, v in item.items():
        if k not in out:
            out[k] = v
    return out


def next_index(arr: list, lid: str) -> int:
    """目前 arr 中已存在的 vx_<lid>_ id 最大序號 + 1（穩定續編）。"""
    mx = 0
    pat = re.compile(rf"^vx_{re.escape(lid)}_(\d+)$")
    for w in arr:
        m = pat.match(str(w.get("id", "")))
        if m:
            mx = max(mx, int(m.group(1)))
    return mx + 1


def migrate_one(lid: str, check: bool) -> dict:
    path = DATA / f"{lid}.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    arr = d.get("vocab", [])

    idx = next_index(arr, lid)
    added = 0
    new_arr = []
    for w in arr:
        cur = str(w.get("id", "")).strip()
        if not cur:
            w = {**w, "id": f"vx_{lid}_{idx:03d}"}
            idx += 1
            added += 1
        new_arr.append(reorder_vocab(w))

    # 不變量自檢
    ids = [w["id"] for w in new_arr]
    assert len(ids) == len(set(ids)), f"{lid}: vocab id 重複"
    assert all(re.match(rf"^vx_{lid}_\d{{3,}}$", i) for i in ids), f"{lid}: id 格式異常"
    assert len(new_arr) == len(arr), f"{lid}: vocab 數量改變"

    report = {"count": len(new_arr), "added": added, "already": len(arr) - added}

    if not check and added:
        d["vocab"] = new_arr
        path.write_text(json.dumps(d, ensure_ascii=False, indent=2),
                         encoding="utf-8")
        report["written"] = True
    else:
        report["written"] = False
    return report


def main():
    args = [a for a in sys.argv[1:]]
    check = "--check" in args
    levels = [a.upper() for a in args if a.upper() in LEVEL_IDS] or LEVEL_IDS

    print(f"模式：{'CHECK（不寫回）' if check else '寫回'}　範圍：{levels}\n")
    total_added = 0
    for lid in levels:
        r = migrate_one(lid, check)
        total_added += r["added"]
        flag = ("（已寫回）" if r["written"]
                else "（無需變更）" if r["added"] == 0 else "（CHECK：未寫回）")
        print(f"  {lid} vocab: {r['count']:3d}  +{r['added']} 補 id, "
              f"{r['already']} 已有 {flag}")
    print(f"\n=== 共補 {total_added} 個 vocab id "
          f"{'（CHECK 模式，未寫檔）' if check else ''} ===")


if __name__ == "__main__":
    main()
