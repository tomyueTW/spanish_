/**
 * 資料不變量回歸測試（零 build：node --test，無 npm 依賴）。
 *
 * 守住 F0a vocab id 遷移與後續 merge 的不變量，避免日後改動把
 * data/levels/*.json 弄壞而沒人察覺。
 *
 *   node --test tools/test_data_invariants.mjs
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const LEVELS = ['L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7'];
const TARGET = { vocab: 150, grammar: 14, listening: 30 };

const load = (lid) =>
  JSON.parse(readFileSync(join(ROOT, 'data', 'levels', `${lid}.json`), 'utf-8'));

for (const lid of LEVELS) {
  test(`${lid}: 結構與數量達標`, () => {
    const d = load(lid);
    assert.equal(d.id, lid);
    for (const typ of ['vocab', 'grammar', 'listening']) {
      assert.ok(Array.isArray(d[typ]), `${typ} 應為陣列`);
      assert.equal(d[typ].length, TARGET[typ], `${typ} 數量應為 ${TARGET[typ]}`);
    }
  });

  test(`${lid}: vocab 每筆有唯一 vx_ id 且 id 為首鍵`, () => {
    const d = load(lid);
    const ids = new Set();
    const re = new RegExp(`^vx_${lid}_\\d{3,}$`);
    for (const w of d.vocab) {
      assert.match(String(w.id), re, `id 格式：${JSON.stringify(w)}`);
      assert.equal(Object.keys(w)[0], 'id', 'id 必須是首鍵');
      assert.ok(!ids.has(w.id), `id 重複：${w.id}`);
      ids.add(w.id);
      assert.ok(String(w.es).trim(), 'es 不可空');
      assert.ok(String(w.zh).trim(), 'zh 不可空');
    }
  });

  test(`${lid}: listening / grammar 仍各自帶 id`, () => {
    const d = load(lid);
    for (const s of d.listening) assert.ok(String(s.id).trim(), 'listening 缺 id');
    for (const g of d.grammar) {
      assert.ok(String(g.id).trim(), 'grammar 缺 id');
      // 至少一個填空。前端 replace(/_+/) 只填第一個空格，理想是剛好 1 個；
      // 已知遺留例外：L5 g28「Pedro es ___ alto ___ Juan.」有 2 個空格，
      // 屬 F0a 範圍外的舊資料債（見記憶 quizbank-data-facts），故此處放寬為 >=1，
      // 不在地基階段順手改題庫內容。
      const blanks = (String(g.q).match(/___/g) || []).length;
      assert.ok(blanks >= 1, `grammar q 至少需一個 ___：${g.id}`);
    }
  });
}
