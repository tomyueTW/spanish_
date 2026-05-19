/**
 * quiz.js 出題引擎回歸測試（node --test，零 build）。
 *
 *   node --test tools/test_quiz_engine.mjs
 *
 * Tier-1 抽出 quiz.js 後，守住「出題行為不變」：題型正確、選項 4 個、
 * 答案索引有效且指向正確項、itemKey 規則、review/due 只就指定題項出題。
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const base = join(dirname(fileURLToPath(import.meta.url)), '..', 'frontend', 'js');
const Q = await import(join(base, 'quiz.js'));
const P = await import(join(base, 'progress.js'));

const mk = (n, f) => Array.from({ length: n }, (_, i) => f(i + 1));
const BANK = {
  kind: 'builtin', id: 'LT',
  vocab: mk(8, i => ({ id: `vx_LT_00${i}`, es: `es${i}`, zh: `中${i}`, cat: 'c', source: 'default' })),
  listening: mk(5, i => ({ id: `lx_LT_00${i}`, es: `Frase ${i}`, zh: `句${i}`, topic: 't', source: 'default' })),
  grammar: mk(3, i => ({ id: `gx_LT_0${i}`, topic: 'g', q: `___ ${i}`, zh: `g${i}`, opts: ['a', 'b', 'c', 'd'], a: i % 4, exp: 'e' })),
};
let weighted = false;
Q.configure({
  getActiveBank: () => BANK,
  progressKey: () => 'LT',
  isBuiltinActive: () => true,
  getSettings: () => ({ weightedSelection: weighted, masteryStreak: 3 }),
});

function assertWellFormed(q) {
  assert.ok(['vocab', 'listen', 'grammar'].includes(q.type), `type: ${q.type}`);
  assert.equal(q.options.length, 4, '必有 4 個選項');
  assert.ok(Number.isInteger(q.answer) && q.answer >= 0 && q.answer <= 3, `answer 索引有效: ${q.answer}`);
  assert.ok(q.itemKey && /^(vocab|listen|grammar):/.test(q.itemKey), `itemKey: ${q.itemKey}`);
}

test('vocab：5 題、格式正確、答案指向正確 es', () => {
  const qs = Q.generateQuestions('vocab', 5);
  assert.equal(qs.length, 5);
  for (const q of qs) {
    assertWellFormed(q);
    assert.equal(q.type, 'vocab');
    const es = q.itemKey.slice('vocab:'.length);
    const w = BANK.vocab.find(v => v.id === es);
    assert.equal(q.options[q.answer], w.es, '正解選項應為該字 es');
  }
});

test('listen / grammar / mixed 題型與數量', () => {
  for (const q of Q.generateQuestions('listen', 5)) { assertWellFormed(q); assert.equal(q.type, 'listen'); }
  const g = Q.generateQuestions('grammar', 3);
  assert.equal(g.length, 3);
  for (const q of g) {
    assertWellFormed(q);
    assert.equal(q.type, 'grammar');
    const it = BANK.grammar.find(x => `grammar:${x.id}` === q.itemKey);
    assert.deepEqual(q.options, it.opts);
    assert.equal(q.answer, it.a);
  }
  const m = Q.generateQuestions('mixed', 12);
  assert.equal(m.length, 12);
  m.forEach(assertWellFormed);
});

test('weighted on 仍產生合法題（加權路徑）', () => {
  weighted = true;
  try {
    const qs = Q.generateQuestions('vocab', 6);
    assert.equal(qs.length, 6);
    qs.forEach(assertWellFormed);
  } finally { weighted = false; }
});

test('review：只就錯題出題', () => {
  P.recordItem('LT', 'LT', 'vocab:vx_LT_003', false, '2026-01-01T00:00:00Z');
  const keys = Q.currentMistakeKeys();
  assert.ok(keys.includes('vocab:vx_LT_003'));
  const qs = Q.generateQuestions('review', 5);
  assert.ok(qs.length >= 1);
  for (const q of qs) {
    assertWellFormed(q);
    assert.equal(q.itemKey, 'vocab:vx_LT_003', 'review 只出錯題');
  }
});

test('due：只就到期題出題', () => {
  // 以很久以前的日期作答 → due 必過期
  P.recordItem('LT', 'LT', 'listen:lx_LT_002', true, '2020-01-01T00:00:00Z');
  const due = Q.currentDueKeys();
  assert.ok(due.includes('listen:lx_LT_002'), '過期項應到期');
  const qs = Q.generateQuestions('due', 5);
  assert.ok(qs.length >= 1);
  qs.forEach(assertWellFormed);
});
