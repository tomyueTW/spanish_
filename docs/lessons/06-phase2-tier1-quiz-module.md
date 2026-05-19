# 教學文章 6 — Phase 2 Tier-1：抽出 quiz.js，行為不變的重構

> 對應 commit：`aa4b7f5`
> 範圍：何時抽模組、依賴注入避循環、行為保持重構、回歸測試策略

---

## 一、為什麼現在才抽、而不是一開始就抽

文章 1 講過架構原則：**重構只服務於功能，不獨立排期大重寫**。
出題邏輯（`pickTarget` / `build*` / `make*` / `generateQuestions` / 複習/到期）
在 F2、F3、F4 一路長大，到 Phase 2 末已是一坨約 190 行、跨多功能的核心。
這時候抽 `quiz.js` 才划算，因為：

- 它已經**穩定**（功能都做完了，不會邊抽邊變）。
- 它已經**夠複雜**（值得隔離、值得獨立測試）。
- 它有**清楚邊界**（出題是一個內聚的職責）。

過早抽（在 F2 之前）會邊抽邊改、白工；過晚抽（混進更多功能）會更難切。

> **關鍵學習**：抽模組的時機 = 「這塊**穩定了** + **夠複雜值得隔離** + **邊界清楚**」
> 三者同時成立。為了抽而抽、或在還在劇烈變動時抽，都是浪費。

---

## 二、核心難題：模組不能 import 內聯的 App

出題邏輯依賴一堆 App 內部狀態與函式：`getActiveBank()`、`progressKey()`、
`isBuiltinActive()`、`settings`。但 `App` 是 `index.html` 裡的內聯 IIFE，
**不是一個模組**——`quiz.js` 無法 `import` 它（也不該，會形成循環依賴）。

解法：**依賴注入（Dependency Injection）**。`quiz.js` 不去拿依賴，而是
讓外部把依賴「**設定**」進來：

```js
// quiz.js
let ctx = null;
export function configure(c) { ctx = c; }   // c = { getActiveBank, progressKey, isBuiltinActive, getSettings }
// 內部一律走 ctx.getActiveBank() / ctx.progressKey() / ctx.getSettings()...
```

```js
// index.html init()
QuizMod.configure({
  getActiveBank, progressKey, isBuiltinActive,
  getSettings: () => settings,   // 用 getter 包，確保拿到的是「當下」的 settings
});
```

`progress.js` 是真模組，`quiz.js` 直接 `import` 它沒問題。
只有「住在 inline App 裡的東西」才透過 `ctx` 注入。

幾個關鍵細節：

- **`getSettings: () => settings` 用函式包，不傳 `settings` 本身**。
  `settings` 會被 `beginQuiz` 重新賦值/修改；傳值會拿到舊快照，
  傳 getter 每次都拿當下值。
- **`configure` 必須在任何出題前呼叫**。放在 `init()` 開頭、
  在 `loadBanks()` 等 await 之前，確保時序安全。
- 純工具（`shuffle`、`escapeHtml`）在 `quiz.js` 內**自帶一份**，
  不為了省幾行去注入——降低耦合比消除少量重複更重要。

> **關鍵學習**：當 A 要被抽出、但 A 依賴一個「不是模組、不能被 import」的 B 時，
> **反轉依賴方向**：A 暴露 `configure(deps)`，由 B 在啟動時注入。
> 這就是「依賴注入」最樸素也最有用的形態，能打斷循環、讓 A 可獨立測試。
> 注入會變的狀態時，注入 **getter** 而非值。

---

## 三、行為保持重構的紀律

這次重構的目標是「**行為完全不變**」。紀律：

1. **逐字搬移**，不順手「優化」。搬移時唯一允許的改動是把
   `getActiveBank()` → `ctx.getActiveBank()` 這類依賴改寫。
   任何「看到順便改」都會讓「行為是否改變」變得無法論證。
2. **搬完用 grep 確認舊位置沒有殘留呼叫**：確認 `index.html` 不再有
   `generateQuestions(` / `currentMistakeKeys(` 等本地定義或呼叫，
   全部變成 `QuizMod.*`。殘留 = 還有一份舊的在跑。
3. **diff 要可解釋**：index.html 應該是「淨刪 ~190 行 + 幾處改成
   `QuizMod.*` + 一個 import + 一個 configure」。如果 diff 出現
   無法解釋的變動，就是重構摻了雜質。

> **關鍵學習**：「行為保持重構」的可信度來自**克制**。
> 搬移與修改分兩次做、絕不混在一起；用 grep 驗證無殘留；
> 用「diff 是否每一行都可解釋」當交付門檻。

---

## 四、重構要靠「行為測試」兜底，不是靠人眼

沒有瀏覽器自動化，怎麼確信出題行為沒變？寫
`tools/test_quiz_engine.mjs`：用一個假 bank + stub `ctx`（`configure` 注入），
斷言**結構性不變量**：

- 每題 `type ∈ {vocab,listen,grammar}`、`options.length === 4`、
  `answer` 是 0–3 的有效索引、`options[answer]` 確實是正解、
  `itemKey` 符合規則。
- `mixed` 回傳 n 題；`review` 只出錯題；`due` 只出到期題；
  加權開啟時仍產生合法題。

注意這些是**不變量**而非「寫死預期輸出」——出題有隨機性，
測「結構恆真」才穩定、才不會變成脆弱測試。

> **關鍵學習**：重構的安全網是**行為測試**。對有隨機性的程式，
> 斷言**不變量**（永遠成立的結構性質）而不是固定輸出，
> 測試才不會今天綠明天紅。能用 DI 把模組從 DOM 剝離、純函式化，
> 正是為了讓這種測試成為可能——**可測性是好架構的副產品，也是目的。**

---

## 五、回顧：這次重構順帶複用了哪些前面的接縫

- 文章 2 的「**選擇/建構分離**」(`pickTarget` / `build*`)：搬進 quiz.js 後，
  `review`、`due` 都靠 `buildQuestionsFromKeys` 共用，沒有重複出題碼。
- 文章 2 的 **identity bug 修法**（index 與 pool 共用同一 bank 物件）：
  搬移時原樣保留，沒有因為換了檔案位置而回退。

好接縫會在多次後續工作裡持續還你利息；重構時要**保護**這些既有正確性，
不要因為「換個地方寫」就不小心改掉。

---

## 六、一頁帶走的重點

1. 抽模組時機＝穩定 + 夠複雜值得隔離 + 邊界清楚，三者同時成立。
2. 模組依賴「不可 import 的內聯程式」時，用 `configure(deps)` 反轉依賴；
   會變的狀態注入 getter，不注入值；configure 要在使用前完成。
3. 行為保持重構靠克制：搬移與修改分離、grep 驗無殘留、diff 每行可解釋。
4. 重構安全網是行為測試；對隨機程式斷言**不變量**而非固定輸出。
5. 可測性是好架構的副產品也是目的；保護既有接縫與既有 bug 修法不回退。
