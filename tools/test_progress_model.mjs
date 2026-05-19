/**
 * F0 題項精熟模型 + MD codec 回歸測試（node --test，零 build）。
 *
 *   node --test tools/test_progress_model.mjs
 *
 * 守住：itemKey 穩定鍵規則、recordItem streak/seen 計數、
 * MD round-trip（含新「# 題項精熟」區塊）、以及對舊格式檔的向下相容。
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const P = join(dirname(fileURLToPath(import.meta.url)),
  '..', 'frontend', 'js', 'progress.js');
const M = await import(P);

test('itemKey：builtin 用穩定 id，custom 退回 es', () => {
  assert.equal(M.itemKey('L1', 'vocab', { id: 'vx_L1_007', es: 'hola' }, true),
    'vocab:vx_L1_007');
  assert.equal(M.itemKey('L1', 'listen', { id: 'l001', es: 'Hola' }, true),
    'listen:l001');
  assert.equal(M.itemKey('L1', 'grammar', { id: 'g01' }, true), 'grammar:g01');
  // custom：isBuiltin=false 一律 es 退回（即使有隨機 id）
  assert.equal(M.itemKey('bank_x', 'vocab', { id: 'l_ab12', es: ' Gracias ' }, false),
    'bank_x|vocab|gracias');
  // builtin 但 id 非穩定格式 → 也退回 es
  assert.equal(M.itemKey('L1', 'vocab', { id: 'weird', es: 'sí' }, true),
    'L1|vocab|sí');
});

test('recordItem：seen/correct/wrong/streak 計數正確', () => {
  const k = 'L1', ik = 'vocab:vx_L1_001';
  M.recordItem(k, 'L1', ik, true, '2026-05-19T00:00:00Z');
  M.recordItem(k, 'L1', ik, true, '2026-05-19T00:01:00Z');
  M.recordItem(k, 'L1', ik, false, '2026-05-19T00:02:00Z'); // 答錯歸零 streak
  M.recordItem(k, 'L1', ik, true, '2026-05-19T00:03:00Z');
  const it = M.getBanks()[k].items[ik];
  assert.equal(it.seen, 4);
  assert.equal(it.correct, 3);
  assert.equal(it.wrong, 1);
  assert.equal(it.streak, 1, '答錯後 streak 應重置再累加');
});

test('masteryCounts：依 streak 門檻分類', () => {
  const k = 'Lm';
  // a：連對 3 → 精熟；b：seen 但未達 → 學習中；c：從未出現 → 未開始
  for (let i = 0; i < 3; i++) M.recordItem(k, 'Lm', 'vocab:a', true, 't');
  M.recordItem(k, 'Lm', 'vocab:b', false, 't');
  const r = M.masteryCounts(k, ['vocab:a', 'vocab:b', 'vocab:c'], 3);
  assert.deepEqual(r, { mastered: 1, learning: 1, unseen: 1, total: 3 });
});

test('itemWeight：未學>答錯>學習中>>已精熟', () => {
  const k = 'Lw';
  // unseen（無紀錄）
  assert.equal(M.itemWeight(k, 'vocab:none', 3), 6);
  // 答錯過、未精熟
  M.recordItem(k, 'Lw', 'vocab:wrong', false, 't');
  assert.equal(M.itemWeight(k, 'vocab:wrong', 3), 4);
  // 學習中（答對 1 次，未達門檻、無錯）
  M.recordItem(k, 'Lw', 'vocab:learn', true, 't');
  assert.equal(M.itemWeight(k, 'vocab:learn', 3), 2);
  // 已精熟（連對 3）→ 低權重但非 0
  for (let i = 0; i < 3; i++) M.recordItem(k, 'Lw', 'vocab:done', true, 't');
  assert.equal(M.itemWeight(k, 'vocab:done', 3), 0.5);
});

test('mistakeKeySet：答錯且未重新精熟才算錯題', () => {
  const k = 'Lms';
  M.recordItem(k, 'Lms', 'vocab:bad', false, 't');          // 錯 → 入列
  M.recordItem(k, 'Lms', 'vocab:fixed', false, 't');        // 先錯
  for (let i = 0; i < 3; i++) M.recordItem(k, 'Lms', 'vocab:fixed', true, 't'); // 再連對 3 → 出列
  M.recordItem(k, 'Lms', 'vocab:ok', true, 't');            // 從未錯 → 不入列
  const set = M.mistakeKeySet(k, 3);
  assert.ok(set.has('vocab:bad'));
  assert.ok(!set.has('vocab:fixed'), '重新精熟後應移出錯題');
  assert.ok(!set.has('vocab:ok'));
});

test('MD round-trip：formatBankProgressMd ⇄ parseBankProgress（含題項）', () => {
  const k = 'Lrt';
  M.recordQuiz(k, '回測庫', 'vocab', 8, 10, '2026-05-19T12:00:00Z');
  M.recordItem(k, '回測庫', 'vocab:vx_Lrt_001', true, '2026-05-19T12:00:00Z');
  M.recordItem(k, '回測庫', 'listen:lx_Lrt_003', false, '2026-05-19T12:01:00Z');

  const md = M.formatBankProgressMd(k);
  assert.match(md, /# 測驗歷史/);
  assert.match(md, /# 題項精熟/);

  const parsed = M.parseBankProgress(md);
  assert.equal(parsed.answered, 10);
  assert.equal(parsed.correct, 8);
  assert.equal(parsed.history.length, 1);
  assert.equal(parsed.history[0].mode, 'vocab');
  assert.equal(parsed.items['vocab:vx_Lrt_001'].correct, 1);
  assert.equal(parsed.items['vocab:vx_Lrt_001'].streak, 1);
  assert.equal(parsed.items['listen:lx_Lrt_003'].wrong, 1);
  assert.equal(parsed.items['listen:lx_Lrt_003'].streak, 0);
});

test('向下相容：舊格式（無題項精熟區塊）解析為 items={}', () => {
  const oldMd = [
    '---',
    'bankId: L1',
    'name: 舊庫',
    'answered: 20',
    'correct: 15',
    'sessions: 2',
    'lastPracticed: 2026-05-01T00:00:00Z',
    '---',
    '',
    '# 測驗歷史',
    '',
    '| 日期 | 模式 | 分數 |',
    '|---|---|---|',
    '| 2026-05-01T00:00:00Z | mixed | 7/10 |',
    '| 2026-05-01T01:00:00Z | vocab | 8/10 |',
    '',
  ].join('\n');
  const p = M.parseBankProgress(oldMd);
  assert.equal(p.answered, 20);
  assert.equal(p.history.length, 2);
  assert.deepEqual(p.items, {}, '舊檔無題項區塊 → items 必須為空物件');
});

test('parseSummaryGlobal：缺欄位回傳 null', () => {
  assert.equal(M.parseSummaryGlobal('# 沒有 frontmatter'), null);
  const g = M.parseSummaryGlobal(
    '---\ntotalAnswered: 30\ntotalCorrect: 21\nsessions: 3\n---\n');
  assert.deepEqual(g, { totalAnswered: 30, totalCorrect: 21, sessions: 3 });
});
