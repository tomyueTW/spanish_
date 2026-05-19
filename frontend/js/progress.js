// 進度 + F0 題項精熟模型 + Markdown codec（原生 ES module、零依賴、可離線）。
//
// 這是 PRODUCT_PLAN.md Phase 1 的地基（F0）：把原本散在 index.html 的
// progress 狀態與 MD codec 收斂進單一模組，並新增「每個題項學會了沒」
// 的精熟資料模型。一切進度可見性 / 弱項出題 / SRS 都將以此為基礎。
//
// 相容性：MD 新增的「# 題項精熟」區塊向下相容——舊的 progress/*.md
// 沒有該區塊時 items 視為空，既有 frontmatter / 測驗歷史格式不變。

import { createStore } from './store.js';

// ── 精熟門檻（owner 已拍板：預設連續答對 3 次；設定頁可調）──
export const DEFAULT_MASTERY_STREAK = 3;

// 單一狀態來源（progress 切片）
const store = createStore({
  global: { totalAnswered: 0, totalCorrect: 0, sessions: 0 },
  banks: {},   // key → { name, answered, correct, sessions, lastPracticed, history[], items{} }
});

export const subscribe = store.subscribe;
export const getState = store.get;
export const getGlobal = () => store.get().global;
export const getBanks = () => store.get().banks;

export function pct(correct, answered) {
  return answered ? Math.round((correct / answered) * 100) : 0;
}

// ── 狀態 hydrate / 匯出（localStorage 備援用）──
function normalizeBank(b) {
  return {
    name: b && b.name || '',
    answered: (b && b.answered) || 0,
    correct: (b && b.correct) || 0,
    sessions: (b && b.sessions) || 0,
    lastPracticed: (b && b.lastPracticed) || '',
    history: Array.isArray(b && b.history) ? b.history : [],
    items: (b && b.items && typeof b.items === 'object') ? b.items : {},
  };
}

// 從 localStorage 解析出的物件 hydrate（沿用舊 loadState 的相容邏輯）
export function loadSnapshot(data) {
  store.update((s) => {
    if (data && data.progress && data.progress.global) {
      s.global = data.progress.global;
      const banks = data.progress.banks || {};
      s.banks = {};
      for (const [k, v] of Object.entries(banks)) s.banks[k] = normalizeBank(v);
    } else if (data && data.stats) {
      // 更舊版本：stats → global
      s.global = data.stats;
      s.banks = {};
    }
    return s;
  });
}

// 給 saveState 序列化（含 items，localStorage 即為備援）
export function snapshot() {
  return store.get();
}

function ensureBank(key, name) {
  const s = store.get();
  if (!s.banks[key]) {
    s.banks[key] = normalizeBank({ name });
  } else if (name) {
    s.banks[key].name = name;
  }
  return s.banks[key];
}

// ── F0 題項穩定鍵 ──
// builtin：用既有穩定 id（vocab vx_ / listening lx_·l\d / grammar gx_·g\d）。
// custom：無穩定 id（parseBankMd 每次載入給隨機 id），退回 bankKey|typ|es。
const STABLE_ID = /^(vx_|lx_|gx_|sx_|l\d|g\d|s\d)/;

export function itemKey(bankKey, typ, item, isBuiltin) {
  const id = item && item.id ? String(item.id) : '';
  if (isBuiltin && id && STABLE_ID.test(id)) return `${typ}:${id}`;
  const es = String((item && item.es) || '').trim().toLowerCase();
  return `${bankKey}|${typ}|${es}`;
}

// ── 記錄：整場測驗結果（沿用舊 recordQuizResult 的狀態變更，不含持久化）──
export function recordQuiz(key, name, mode, score, total, nowIso) {
  store.update((s) => {
    s.global.totalAnswered += total;
    s.global.totalCorrect += score;
    s.global.sessions += 1;
    const b = ensureBank(key, name);
    b.answered += total;
    b.correct += score;
    b.sessions += 1;
    b.lastPracticed = nowIso;
    b.history.push({ date: nowIso, mode, score, total });
    if (b.history.length > 200) b.history = b.history.slice(-200);
    return s;
  });
}

// ── 記錄：單一題項作答（F0 核心）──
export function recordItem(key, name, ik, correct, nowIso) {
  if (!ik) return;
  store.update((s) => {
    const b = ensureBank(key, name);
    let it = b.items[ik];
    if (!it) {
      it = b.items[ik] = {
        seen: 0, correct: 0, wrong: 0, streak: 0,
        lastSeen: '', ease: 2.5, due: '',
      };
    }
    it.seen += 1;
    it.lastSeen = nowIso;
    if (correct) { it.correct += 1; it.streak += 1; }
    else { it.wrong += 1; it.streak = 0; }
    return s;
  });
}

// ── 模型查詢：精熟分佈（供 F1 顯示用，本階段尚未接 UI）──
// allKeys：該題庫所有題項的 itemKey 陣列。
export function masteryCounts(key, allKeys, threshold = DEFAULT_MASTERY_STREAK) {
  const items = (store.get().banks[key] || {}).items || {};
  let mastered = 0, learning = 0;
  for (const k of allKeys) {
    const it = items[k];
    if (it && it.seen > 0) {
      if (it.streak >= threshold) mastered += 1;
      else learning += 1;
    }
  }
  const total = allKeys.length;
  return { mastered, learning, unseen: Math.max(0, total - mastered - learning), total };
}

// ── Markdown codec ───────────────────────────────────────────────
function frontmatterLines(obj) {
  return Object.entries(obj).map(([k, v]) => `${k}: ${v}`);
}

export function parseFrontmatter(text) {
  const out = {};
  const m = text.match(/^---\n([\s\S]*?)\n---\n?/);
  if (m) {
    m[1].split('\n').forEach((line) => {
      const mm = line.match(/^([\w-]+):\s*(.*)$/);
      if (mm) out[mm[1]] = mm[2].trim();
    });
  }
  return out;
}

export function formatSummaryMd(nowIso) {
  const { global: g, banks } = store.get();
  const lines = [
    '---',
    `updated: ${nowIso}`,
    `totalAnswered: ${g.totalAnswered}`,
    `totalCorrect: ${g.totalCorrect}`,
    `sessions: ${g.sessions}`,
    '---',
    '',
    '# 總計',
    '',
    `- 完成測驗：${g.sessions}`,
    `- 總答題數：${g.totalAnswered}`,
    `- 答對：${g.totalCorrect}`,
    `- 正確率：${pct(g.totalCorrect, g.totalAnswered)}%`,
    '',
    '# 各題庫',
    '',
    '| 題庫 | 答題 | 正確率 | 完成次數 | 最後練習 |',
    '|---|---|---|---|---|',
  ];
  for (const [key, b] of Object.entries(banks)) {
    const last = b.lastPracticed ? b.lastPracticed.slice(0, 10) : '-';
    lines.push(`| ${key} ${b.name ? '· ' + b.name : ''} | ${b.answered} | ${pct(b.correct, b.answered)}% | ${b.sessions} | ${last} |`);
  }
  return lines.join('\n') + '\n';
}

export function formatBankProgressMd(key) {
  const b = store.get().banks[key];
  if (!b) return '';
  const lines = [
    '---',
    ...frontmatterLines({
      bankId: key,
      name: b.name || '',
      answered: b.answered,
      correct: b.correct,
      sessions: b.sessions,
      lastPracticed: b.lastPracticed || '',
    }),
    '---',
    '',
    '# 測驗歷史',
    '',
    '| 日期 | 模式 | 分數 |',
    '|---|---|---|',
  ];
  (b.history || []).forEach((h) => {
    lines.push(`| ${h.date} | ${h.mode} | ${h.score}/${h.total} |`);
  });
  // F0：題項精熟區塊（向下相容——舊檔無此區塊，讀回時 items 為空）
  lines.push('', '# 題項精熟', '');
  lines.push('| 題項 | 次數 | 對 | 錯 | 連對 | 最後 |');
  lines.push('|---|---|---|---|---|---|');
  const items = b.items || {};
  for (const ik of Object.keys(items).sort()) {
    const it = items[ik];
    const last = it.lastSeen ? it.lastSeen.slice(0, 10) : '-';
    lines.push(`| ${ik} | ${it.seen} | ${it.correct} | ${it.wrong} | ${it.streak} | ${last} |`);
  }
  return lines.join('\n') + '\n';
}

export function parseSummaryGlobal(text) {
  const fm = parseFrontmatter(text);
  if (!('totalAnswered' in fm)) return null;
  return {
    totalAnswered: parseInt(fm.totalAnswered) || 0,
    totalCorrect: parseInt(fm.totalCorrect) || 0,
    sessions: parseInt(fm.sessions) || 0,
  };
}

// 區段感知（向下相容）：依 # 標題切換 history / items 解析。
export function parseBankProgress(text) {
  const fm = parseFrontmatter(text);
  const entry = normalizeBank({
    name: fm.name || '',
    answered: parseInt(fm.answered) || 0,
    correct: parseInt(fm.correct) || 0,
    sessions: parseInt(fm.sessions) || 0,
    lastPracticed: fm.lastPracticed || '',
  });
  // 跳過 frontmatter 區塊再逐行掃描
  const m = text.match(/^---\n[\s\S]*?\n---\n?/);
  const body = m ? text.slice(m[0].length) : text;
  let section = null;
  body.split('\n').forEach((raw) => {
    const line = raw.trim();
    if (line.startsWith('#')) {
      const h = line.replace(/^#+\s*/, '');
      if (h.includes('測驗歷史')) section = 'history';
      else if (h.includes('題項精熟')) section = 'items';
      else section = null;
      return;
    }
    if (!line.startsWith('|')) return;
    const cells = line.split('|').map((s) => s.trim())
      .filter((_, i, a) => i > 0 && i < a.length - 1);
    if (section === 'history') {
      if (cells.length !== 3) return;
      if (cells[0] === '日期' || /^-+$/.test(cells[0])) return;
      const sc = (cells[2] || '').split('/');
      entry.history.push({
        date: cells[0], mode: cells[1],
        score: parseInt(sc[0]) || 0, total: parseInt(sc[1]) || 0,
      });
    } else if (section === 'items') {
      if (cells.length !== 6) return;
      if (cells[0] === '題項' || /^-+$/.test(cells[0])) return;
      entry.items[cells[0]] = {
        seen: parseInt(cells[1]) || 0,
        correct: parseInt(cells[2]) || 0,
        wrong: parseInt(cells[3]) || 0,
        streak: parseInt(cells[4]) || 0,
        lastSeen: cells[5] && cells[5] !== '-' ? cells[5] : '',
        ease: 2.5, due: '',
      };
    }
  });
  return entry;
}

// 給資料夾載入流程：以 MD 解析出的 banks / global 取代記憶體狀態
export function setGlobal(g) {
  store.update((s) => { if (g) s.global = g; return s; });
}
export function setBanks(banks) {
  store.update((s) => {
    s.banks = {};
    for (const [k, v] of Object.entries(banks || {})) s.banks[k] = normalizeBank(v);
    return s;
  });
}
