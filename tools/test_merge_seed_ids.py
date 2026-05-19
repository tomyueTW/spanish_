"""merge_seed.py 行為測試：新合併的 vocab 會配到 vx_<LID>_NNN 且冪等。

零依賴（只用 stdlib unittest），對 tmp 夾具跑 merge_seed.merge_one：

    python3 tools/test_merge_seed_ids.py
"""
import json
import tempfile
import unittest
from pathlib import Path

import merge_seed  # 同目錄


def write(p: Path, obj):
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


class MergeSeedVocabId(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.data = root / "data" / "levels"
        self.seed = root / "tools" / "seed"
        self.data.mkdir(parents=True)
        self.seed.mkdir(parents=True)
        # merge_seed 用模組層級常數，測試時改指向 tmp
        self._orig = (merge_seed.DATA, merge_seed.SEED)
        merge_seed.DATA, merge_seed.SEED = self.data, self.seed

    def tearDown(self):
        merge_seed.DATA, merge_seed.SEED = self._orig
        self.tmp.cleanup()

    def test_new_vocab_gets_vx_id_and_is_idempotent(self):
        # 既有 1 筆已帶 id（模擬遷移後狀態），target=3 → 還能收 2 筆
        write(self.data / "L1.json", {
            "id": "L1", "name": "t", "cefr": "A1.1",
            "vocab": [{"id": "vx_L1_001", "es": "hola", "zh": "你好",
                       "ipa": "", "cat": ""}],
            "grammar": [], "listening": [],
            "gaps": {"vocab": 2, "grammar": 0, "listening": 0},
            "targets": {"vocab": 3, "grammar": 0, "listening": 0},
        })
        write(self.seed / "L1.json", {"vocab": [
            {"es": "gracias", "zh": "謝謝", "ipa": "", "cat": ""},
            {"es": "hola", "zh": "你好", "ipa": "", "cat": ""},  # 重複 → 跳過
            {"es": "adiós", "zh": "再見", "ipa": "", "cat": ""},
        ]})

        merge_seed.merge_one("L1")
        d = json.loads((self.data / "L1.json").read_text(encoding="utf-8"))
        ids = [w["id"] for w in d["vocab"]]

        self.assertEqual(len(d["vocab"]), 3, "應補到 target=3（dup 被跳過）")
        self.assertEqual(ids, ["vx_L1_001", "vx_L1_002", "vx_L1_003"],
                         "新 vocab 應續編 vx_L1_NNN")
        self.assertEqual(list(d["vocab"][1].keys())[0], "id", "id 應為首鍵")

        # 冪等：再跑一次不應改變（已達 target，且 dedup 生效）
        before = (self.data / "L1.json").read_text(encoding="utf-8")
        merge_seed.merge_one("L1")
        after = (self.data / "L1.json").read_text(encoding="utf-8")
        self.assertEqual(before, after, "重跑應為 no-op")


if __name__ == "__main__":
    unittest.main(verbosity=2)
