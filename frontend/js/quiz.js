// 出題引擎（原生 ES module、零 build、可離線）。Tier-1 重構：把出題挑選 /
// 題目建構 / 複習·到期出題從 index.html 抽出隔離，行為與原本完全一致。
//
// 以 configure(ctx) 注入 App 相依（避免與 inline App 形成循環）：
//   ctx = { getActiveBank, progressKey, isBuiltinActive, getSettings }
// progress.js 直接 import（本就是模組）。

import * as Progress from './progress.js';

let ctx = null;
export function configure(c) { ctx = c; }

// 純工具（與 index.html 同義，模組內自帶以保持獨立可測）
const shuffle = arr => [...arr].sort(() => Math.random() - 0.5);
function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

// F0 題項穩定鍵：交給 progress.js（builtin 用 vx_/lx_/gx_ id，custom 退回 es）
function qItemKey(typ, item) {
  return Progress.itemKey(ctx.progressKey(), typ, item, ctx.isBuiltinActive());
}

// F2：依精熟度加權挑出本題的焦點題項；設定關閉時退回均勻隨機。
function pickTarget(pool, typ) {
  const s = ctx.getSettings();
  if (!s.weightedSelection || pool.length < 2) {
    return pool[Math.floor(Math.random() * pool.length)];
  }
  const key = ctx.progressKey();
  const ms = s.masteryStreak;
  const weights = pool.map(it => Progress.itemWeight(key, qItemKey(typ, it), ms));
  let total = 0;
  for (const w of weights) total += w;
  let r = Math.random() * total;
  for (let i = 0; i < pool.length; i++) {
    r -= weights[i];
    if (r <= 0) return pool[i];
  }
  return pool[pool.length - 1];
}

// 由指定 correct 題項建構題目（出題挑選與題目建構分離，供 F2 加權與 F3 複習共用）
function buildVocabQ(correct, pool) {
  if (pool.length < 4) return null;
  const distractors = shuffle(pool.filter(o => o !== correct)).slice(0, 3);
  const opts = shuffle([correct, ...distractors]);
  return {
    type: 'vocab',
    prompt: correct.zh,
    promptLabel: `「${correct.zh}」的西班牙語是？`,
    options: opts.map(o => o.es),
    answer: opts.findIndex(o => o.es === correct.es),
    explanation: `<strong>${correct.es}</strong> = ${correct.zh}${correct.cat ? '（' + correct.cat + '）' : ''}`,
    speakText: correct.es,
    source: correct.source,
    sourceName: correct.bankName,
    itemKey: qItemKey('vocab', correct),
  };
}

function buildListenSentenceQ(correct, sentencePool) {
  const others = shuffle(sentencePool.filter(s => s !== correct && s.zh !== correct.zh)).slice(0, 3);
  if (others.length < 3) return null;
  const opts = shuffle([correct, ...others]);
  return {
    type: 'listen',
    prompt: correct.es,
    promptLabel: '聽聽看，這句話的意思是？',
    options: opts.map(o => o.zh),
    answer: opts.findIndex(o => o.zh === correct.zh),
    explanation: `<strong>${correct.es}</strong><br>${correct.zh}${correct.topic ? '（' + correct.topic + '）' : ''}`,
    speakText: correct.es,
    source: correct.source,
    sourceName: correct.bankName,
    topic: correct.topic,
    itemKey: qItemKey('listen', correct),
  };
}

function buildListenVocabQ(correct, pool) {
  if (pool.length < 4) return null;
  const distractors = shuffle(pool.filter(o => o !== correct)).slice(0, 3);
  const opts = shuffle([correct, ...distractors]);
  return {
    type: 'listen',
    prompt: correct.es,
    promptLabel: '聽聽看，這個西班牙語的意思是？',
    options: opts.map(o => o.zh),
    answer: opts.findIndex(o => o.zh === correct.zh),
    explanation: `<strong>${correct.es}</strong> = ${correct.zh}`,
    speakText: correct.es,
    source: correct.source,
    // 底層仍是 vocab 詞，鍵為 vocab → 與單字模式共享該字精熟度
    itemKey: qItemKey('vocab', correct),
  };
}

function buildGrammarQ(item) {
  if (!item) return null;
  return {
    type: 'grammar',
    promptLabel: `<div class="topic-tag">${escapeHtml(item.topic || '')}</div>${item.q} <span style="color:#6b7280;font-size:14px;">(${escapeHtml(item.zh || '')})</span>`,
    options: item.opts,
    answer: item.a,
    explanation: item.exp,
    source: 'default',
    itemKey: qItemKey('grammar', item),
  };
}

function makeVocabQ(pool) {
  if (pool.length < 4) return null;
  return buildVocabQ(pickTarget(pool, 'vocab'), pool);
}

function makeListenQ(vocabPool, sentencePool) {
  // 70% 用句子，30% 用單字（依比例調整）
  const useSentence = sentencePool.length > 0 && Math.random() < 0.7;
  if (useSentence) {
    const q = buildListenSentenceQ(pickTarget(sentencePool, 'listen'), sentencePool);
    if (q) return q;
  }
  return makeListenQFromVocab(vocabPool);
}

function makeListenQFromVocab(pool) {
  if (pool.length < 4) return null;
  return buildListenVocabQ(pickTarget(pool, 'vocab'), pool);
}

function makeGrammarQ(grammarPool) {
  if (!grammarPool || grammarPool.length === 0) return null;
  return buildGrammarQ(pickTarget(grammarPool, 'grammar'));
}

// F3：itemKey → {typ,item} 索引（與作答時的 qItemKey 規則一致）。
// 接受 bank 參數：index 與出題 pool 必須來自同一個 getActiveBank() 物件，
// 否則 buildXFrom 以 identity 排除 correct 會失效（出現重複選項）。
function bankItemIndex(bank) {
  bank = bank || ctx.getActiveBank();
  const idx = new Map();
  (bank.vocab || []).forEach(w => idx.set(qItemKey('vocab', w), { typ: 'vocab', item: w }));
  (bank.listening || []).forEach(s => idx.set(qItemKey('listen', s), { typ: 'listen', item: s }));
  (bank.grammar || []).forEach(g => idx.set(qItemKey('grammar', g), { typ: 'grammar', item: g }));
  return idx;
}

// 目前使用中題庫的錯題鍵（存在於本庫且尚未重新精熟）
export function currentMistakeKeys() {
  const idx = bankItemIndex();
  return [...Progress.mistakeKeySet(ctx.progressKey(), ctx.getSettings().masteryStreak)]
    .filter(k => idx.has(k));
}

// F4：目前使用中題庫今天到期的題項鍵
export function currentDueKeys() {
  const idx = bankItemIndex();
  return [...Progress.dueKeySet(ctx.progressKey(), new Date().toISOString())]
    .filter(k => idx.has(k));
}

// F3/F4：就一組題項鍵出題（複習錯題 / 到期複習共用）
function buildQuestionsFromKeys(keys, n) {
  const bank = ctx.getActiveBank();
  const vocabPool = bank.vocab || [];
  const sentencePool = bank.listening || [];
  const idx = bankItemIndex(bank);
  const qs = [];
  for (const k of shuffle(keys).slice(0, n)) {
    const e = idx.get(k);
    if (!e) continue;
    let q = null;
    if (e.typ === 'vocab') q = buildVocabQ(e.item, vocabPool);
    else if (e.typ === 'listen') q = buildListenSentenceQ(e.item, sentencePool) || buildListenVocabQ(e.item, vocabPool);
    else if (e.typ === 'grammar') q = buildGrammarQ(e.item);
    if (q) qs.push(q);
  }
  return qs;
}

export function generateQuestions(mode, n) {
  if (mode === 'review') return buildQuestionsFromKeys(currentMistakeKeys(), n);
  if (mode === 'due') return buildQuestionsFromKeys(currentDueKeys(), n);
  const bank = ctx.getActiveBank();
  const vocabPool = bank.vocab || [];
  const sentencePool = bank.listening || [];
  const grammarPool = bank.grammar || [];
  const hasGrammar = grammarPool.length > 0;

  const qs = [];
  for (let i = 0; i < n; i++) {
    let q = null;
    if (mode === 'vocab') q = makeVocabQ(vocabPool);
    else if (mode === 'listen') q = makeListenQ(vocabPool, sentencePool);
    else if (mode === 'grammar') q = makeGrammarQ(grammarPool);
    else if (mode === 'mixed') {
      const r = Math.random();
      if (hasGrammar) {
        if (r < 0.34) q = makeVocabQ(vocabPool);
        else if (r < 0.67) q = makeListenQ(vocabPool, sentencePool);
        else q = makeGrammarQ(grammarPool);
      } else {
        if (r < 0.5) q = makeVocabQ(vocabPool);
        else q = makeListenQ(vocabPool, sentencePool);
      }
    }
    if (q) qs.push(q);
  }
  return qs;
}
