# 西班牙語學習工具 — 產品規劃 / Product Plan

**作者**：Alex (PM)　**版本**：1.0　**日期**：2026-05-19
**對象**：單人開發者兼學習者（owner）
**範圍**：解決 3 個 owner 提出的問題 — (1) 學習效率/進度可見性、(2) UI/UX 體驗、(3) 前後端現代化
**狀態**：規劃中（本文件為決策依據，非實作）

---

## 0. TL;DR（先讀這段）

- **問題 1（學習效率）是真正的痛點，也是最高槓桿。** 目前 app 量測的是「測驗場次」而非「學習」——它知道你做了幾次測驗、總正確率，但**完全不知道某個題庫裡哪些字你已經會、哪些還沒會、哪些該複習了**。每次測驗都從整個 pool 隨機抽題（`makeVocabQ` → `shuffle(pool)[0]`，`index.html:1647`），答對的字和沒看過的字被抽中的機率一模一樣。這是學習效率最大的洩漏點。
- **問題 2（UX）的根因不是視覺，是資訊架構與回饋迴路。** 視覺已經是乾淨的極簡系統（`index.html:12-53` 的 CSS 變數設計系統做得相當完整）。「體驗很差」來自：主選單沒有「我該學什麼／學到哪」的訊號、錯題答完即焚（`currentQuiz.wrong` 只活在記憶體，`showResult` 後就消失）、進度頁不存在（統計只有 3 個全域數字）、grammar 在自製題庫永遠是空的卻沒講清楚。
- **問題 3（架構現代化）：建議「不要做大遷移」。** 目前 vanilla 單檔 + FastAPI 的架構，對「單人、本機、離線、無帳號、markdown 資料夾」這組硬限制其實是**接近最優解**。遷移到 React/Next 會引入 build step、破壞「打開就能改一個檔」的可維護性，而換不到對等價值。真正值得的現代化是**前端內部結構重構**（拆模組、加狀態層），不是換框架。

**最重要的第一步**：先做「每題項目的精熟度追蹤資料模型」（item-level mastery）。問題 1、問題 2 的進度可見性、未來的 SRS，全部都依賴這一層。沒有它，其他功能都只是貼皮。

---

## 1. 現況評估 (Current-state assessment)

### 1.1 問題一：學習效率 — 進度看不出來、學習沒有針對性

**程式碼實證：**

- **進度資料模型只到「題庫」層級，沒有「題項」層級。**
  `recordQuizResult()`（`index.html:1079-1094`）只累加 `answered / correct / sessions`，和一個 `history[]`（每筆是 `{date, mode, score, total}`）。`progress.banks[key]` 的結構裡**沒有任何「哪個單字答對/答錯幾次」的記錄**。
- **出題完全隨機、無記憶。** `makeVocabQ(pool)`（`:1647`）= `shuffle(pool)[0]`；`generateQuestions()`（`:1723`）就是 for 迴圈呼叫它 n 次。已精熟的 `hola` 和從沒見過的 `treinta` 被考到的機率相同 → 大量練習時間花在已會的字上。
- **「進度」在 UI 上只有 3 個全域數字。** `renderStats()`（`:1140`）只渲染 `完成的測驗 / 總答題數 / 正確率` 三張卡，而且是**跨所有題庫聚合**的。owner 的原話「看不出該題庫的學習進度」——程式碼證實：主選單和題庫管理頁都**沒有任何 per-bank 的精熟/進度顯示**。`_summary.md`（`:933`）雖有 per-bank 表格，但那是寫進檔案、UI 不呈現的。
- **錯題無複習迴路。** `currentQuiz.wrong`（`:1810`）是記憶體陣列，`showResult()`（`:1851`）渲染完就沒了。沒有「錯題本」、沒有「只練錯過的題」、沒有「隔天再考一次」。README 寫的「錯題自動彙整複習」實際上只是單次測驗結束畫面列出來而已。
- **沒有「到期該複習」概念。** 沒有時間衰減、沒有 spaced repetition。`lastPracticed` 只記題庫層級最後一次練習時間，不是題項層級。
- **vocab/grammar 沒有穩定 ID。** `data/levels/L1.json` 的 vocab 是 `{es,zh,ipa,cat}`，**沒有 id 欄位**（listening/grammar 有 `lx_/gx_` id，見 `merge_seed.py:85,106`）。這會直接影響 SRS 設計——必須用 `es` 字串或 `bankKey + es` 當穩定鍵。這是個關鍵的資料模型約束，下面架構建議會處理。

**結論**：app 目前是「測驗器」，不是「學習系統」。它能出題、能算分，但不追蹤「掌握度」、不引導「下一步學什麼」。這是 owner 感覺學習效率低的根本原因。

### 1.2 問題二：UI/UX — 「體驗很差」

先講清楚：**視覺層不是問題**。CSS 設計系統（`:8-396`）相當成熟——中性色票、hairline、克制陰影、`prefers-reduced-motion`、focus ring、480px RWD 都有。要遵守的極簡美學已經落實。問題在**資訊架構、回饋迴路、流程清晰度**：

- **主選單沒有「狀態」訊號。** 進入 app（`#menu`，`:402`）看到的是 3 個聚合數字 + 7 個模式按鈕。完全看不出：目前用哪個題庫、這個題庫學了多少、上次學到哪、今天該做什麼。owner 開 app 第一眼是「迷路」狀態。
- **「目前題庫」藏得太深，切換成本高。** 要換練哪一級（L1→L2…）必須：主選單 → 題庫管理（`:433`）→ 找到該 bank → 點「設為使用中」→ 返回。這是一個每天都會做的動作，卻要 4 步。主選單只在 settings 頁用一行小字顯示 active bank（`:480`）。
- **錯題答完即焚。** 上面講過——對學習者，這是體驗最差的一點：做錯了，看一眼解釋，永遠不會再見到它，除非整個題庫重抽剛好又抽到。
- **grammar 模式在自製題庫永遠 disabled，但訊號弱。** `getActiveBank()` 對 custom bank 永遠回傳 `grammar: []`（`:1440`），於是 grammar 按鈕被加 `is-disabled`（`updateMenuForActiveBank`，`:1466`），但使用者不會知道「為什麼這顆灰掉」除非 hover 看 title。自製題庫根本沒有 grammar 資料模型（`parseBankMd` 只解析 vocab/listening，`:765`）。
- **結果頁的鼓勵語有輕微「遊戲化」傾向。** `🏆 ¡Perfecto!`、`🎉`、emoji 評語（`:1840-1844`）與「極簡專注、非 Duolingo」的定位有點衝突。不是大問題，但和美學定位不一致。
- **進度/歷史完全沒有視覺化。** `formatBankProgressMd` 把每場測驗寫成表格進 `<key>.md`（`:962`），但 UI 從不讀回來呈現。學習者要看自己的趨勢，得自己去開 markdown 檔。
- **「重新整理」是手動的、心智負擔高。** 外部編輯 bank md 後要記得回來按「🔄 重新整理」（`refreshBanks`，`:1276`）。這是 FS Access API 的固有限制，但 UX 上沒有引導。
- **無鍵盤作答。** 測驗時要用滑鼠點選項（`renderQ` 綁 `b.onclick`，`:1792`）。對每天練習的 power user，1-4 數字鍵作答是高頻剛需。browse 模式已有鍵盤（`:1576`），測驗模式卻沒有，不一致。

### 1.3 問題三：架構 — 是否該現代化

**目前架構（實證）：**

- 後端 `backend/main.py`：FastAPI，啟動時 `LEVELS = [load_json(...) for ...]`（`:48`）一次性載入 7 級到記憶體；提供 `/api/banks`、`/api/health`、3 個 AI 匯入端點。**改 `data/levels/*.json` 必須重啟後端**（README 也明說）。
- 前端 `frontend/index.html`：**單一 2020 行檔案**，HTML + CSS + 一個 ~1400 行的 `App` IIFE。無 build、無 npm、無框架。靠 system font、無 CDN，可離線。
- 資料/進度：FS Access API 寫使用者選的資料夾（`banks/*.md`、`progress/*.md`），localStorage 備援，雲端硬碟同步。

**真實的痛點是什麼？**

不是「沒用 React 所以落後」。真實痛點是：
1. **單檔 2020 行**：state、出題邏輯、FS I/O、render、MD codec 全擠在一個 IIFE。要加 SRS 這種跨切面功能，會很難不踩到別的地方。**這是可維護性問題，不是技術棧問題。**
2. **改題庫要重啟後端**：對「自己也在加題」的 owner 是摩擦，但這是 in-memory cache 的選擇，不是架構限制。
3. **沒有任何測試**：要重構 SRS / 進度模型卻無回歸網，風險高。

**反面證據——為什麼「不該」大遷移：**

- 硬限制要求「離線 + markdown 資料夾 + 無帳號 + 無 build step（system font / no CDN）」。Next.js/Vite + React 會引入 node_modules、build pipeline，與「打開 index.html 就能改」的本質衝突。
- app 是**單人本機跑**。React 的價值（團隊協作、複雜 state、元件複用、生態系）在這個情境幾乎用不到。
- vanilla 已經用到了該用的瀏覽器原生能力（IndexedDB、FS Access、Web Speech、`<dialog>` 可用），沒有撞到 vanilla 的天花板。

> PM 判斷：**這是一個「重構而非重寫、現代化內部結構而非更換框架」的情境。信心 ~80%。** 會改變這個判斷的訊號：owner 想長期投入大量新功能（多人、雲端帳號、行動 app）→ 那時才值得換棧。

---

## 2. 功能規劃 (Feature plan) — 問題 1 & 2

> 複雜度：S ≈ 半天–1 天、M ≈ 2–4 天、L ≈ 1 週+（以單人開發者節奏估）
> 優先序：P0 = 先做、解決根本痛點；P1 = 高價值、依賴 P0；P2 = 加分項

### 基石功能（所有進度/SRS 功能的前置）

#### F0. 題項精熟度資料模型 (Item-level mastery model) — **P0 · M**
- **解決的問題**：問題 1 的根本——目前只有題庫層級統計，沒有「每個字/句/文法題」的掌握度。
- **使用者價值**：這是讓「進度看得見」「針對性練習」「SRS」全部成為可能的地基。本身不直接有 UI，但沒有它後面都做不了。
- **設計要點**：
  - **穩定鍵（owner 已拍板：補 id）**：替內建 vocab 補上穩定 `id`，沿用既有慣例 → `vx_<LID>_NNN`（對比 listening `lx_*` / grammar `gx_*`，見 `merge_seed.py:85,106`）。`itemKey(card)` 一律回傳該 `id`。自製題庫 vocab 無 id 時退回 `bankKey + '|v|' + es`。
  - **F0a 資料遷移子任務（因「補 id」決定而新增）**：(i) 寫一次性 script 替 `data/levels/L1–L7.json` 約 1050 個 vocab 依序補 `vx_<LID>_NNN`（穩定、不重排既有順序）；(ii) 改 `tools/merge_seed.py` 讓未來合併的 vocab 自動配 `vx_*` id（比照現有 lx/gx 邏輯，含去重）；(iii) 前端 `parseBankMd` 等讀取點改以 id 為主鍵。完成後須更新記憶 `quizbank-data-facts`（schema 由「vocab 無 id」改為「vocab 含 vx_ id」）。
  - 每題項記錄：`{seen, correct, wrong, lastSeen, streak, ease, due}`（SRS 欄位先放但可後啟用）。
  - 存放：擴充 `progress/<bankKey>.md` 增加一個 `# 題項精熟` 表格區塊（沿用既有 markdown codec 風格，`formatBankProgressMd` `:962` 旁邊加），**不破壞既有 frontmatter/歷史格式**，向下相容（舊檔讀不到該區塊就視為空）。
  - localStorage 備援同步寫。
- **依賴**：無。**這是 Phase 1 第一件事。**
- **複雜度修正**：因納入 F0a 資料遷移（動 7 個 JSON + `merge_seed.py` + 前端 keying），由原估 **M 上修為 M–L**。
- **風險**：補 id 後 vocab 改西語拼寫不再斷歷史（這正是選此方案的目的）；風險轉移到「一次性遷移 script 必須穩定且不打亂既有順序」——須以 round-trip 測試把關（接 §3.1 的最小回歸測試）。

---

### 問題 1：學習效率功能

#### F1. 每題庫精熟度總覽 (Per-bank mastery overview) — **P0 · M**
- **解決**：「看不出該題庫的學習進度」——直接命中 owner 原話。
- **價值**：打開 app / 題庫管理頁，每個題庫顯示 `精熟 / 學習中 / 未開始` 三段條 + 百分比（例：`L1 ‧ 精熟 38% ‧ 學習中 22% ‧ 未開始 40%`）。學習者第一眼就知道每級學到哪。
- **精熟定義（owner 已拍板）**：某題項 `correct streak ≥ N` 且最後一次答對 → 精熟；`seen 但未達精熟` → 學習中；`seen=0` → 未開始。**`N` 預設 3，且為「設定」頁可調參數**（非僅程式常數）→ F1 範圍含設定頁一個門檻欄位（S 級小增量，UI 沿用既有 settings 樣式）。
- **依賴**：F0。
- **複雜度**：M（資料彙整 + 主選單/題庫卡 UI + 設定頁門檻欄位）。

#### F2. 弱項優先出題 (Weak-item weighted selection) — **P0 · M**
- **解決**：練習時間花在已會的字上（`makeVocabQ` 純隨機）。
- **價值**：出題時加權——未學過 > 答錯過 > 久未複習 >> 已精熟。學習者每一題的邊際學習效益大幅提升。這是「真的加速學習」最直接的功能。
- **設計**：在 `generateQuestions()`（`:1723`）抽題前，依 F0 的精熟資料對 pool 做加權抽樣；保留一個「純隨機」開關（settings 頁），預設加權。精熟項仍有低機率被抽中（防遺忘）。
- **依賴**：F0。建議與 F1 同階段做（共用精熟資料）。
- **複雜度**：M。

#### F3. 錯題本 + 錯題複習模式 (Mistake log & review loop) — **P0 · M**
- **解決**：錯題答完即焚（`currentQuiz.wrong` 只在記憶體）。
- **價值**：
  - 錯題持久化進 F0 模型（答錯 → wrong+1、進入「待複習」）。
  - 主選單新增「複習錯題」入口：只從「答錯過且未重新精熟」的題項出題。
  - 結果頁的錯題清單加「立即複習這些」按鈕。
- **依賴**：F0。
- **複雜度**：M（資料已在 F0，主要是出題模式 + 入口 UI）。

#### F4. 間隔複習排程 (Lightweight SRS) — **P1 · L**
- **解決**：沒有「到期該複習」概念，靠感覺練。
- **價值**：每題項有 `due` 日期，用簡化 SM-2（或更簡單的 Leitner 盒：答對升盒、答錯回盒一，盒對應 1/3/7/16/35 天間隔）。主選單顯示「今天 N 題到期複習」，一鍵開始。這是長期記憶留存的關鍵。
- **設計取捨**：**建議用 Leitner 盒而非完整 SM-2**——更好解釋、無浮點 ease 調參、對單人學習者足夠。寫入 F0 模型的 `box` + `due` 欄位。
- **依賴**：F0、F2（共用加權出題基礎設施）。
- **複雜度**：L（排程邏輯 + 到期計算 + 入口 + 跨日測試）。
- **取捨說明**：P1 而非 P0，因為 F1/F2/F3 已能帶來大部分學習效率提升；SRS 是錦上添花的留存層，且引入「時間」維度測試成本高，先讓基礎穩。

#### F5. 進度趨勢視覺化 (Progress trend view) — **P1 · M**
- **解決**：`<key>.md` 有 history 但 UI 從不呈現。
- **價值**：一個簡單的進度頁——精熟曲線（隨時間精熟項數）、近 N 場正確率走勢（純 CSS/SVG sparkline，符合極簡，不引圖表庫）、連續學習天數（streak，低調呈現，非遊戲化大徽章）。
- **依賴**：F0、F1。
- **複雜度**：M。

### 問題 2：UI/UX 功能

#### F6. 主選單改為「學習中樞」(Home as a learning hub) — **P0 · M**
- **解決**：主選單沒狀態訊號、迷路感、active bank 藏太深。
- **價值**：重排主選單資訊架構（**不改視覺語言**，仍用既有 stat-card / mode-btn 元件）：
  1. 頂部一行：目前題庫名 + 直接可點的切換（dropdown 或就地切換，免進題庫管理 4 步）。
  2. 該題庫的精熟條（來自 F1）+「今天 N 題到期」（來自 F4，未做前先隱藏）。
  3. 主要行動按鈕順序調整：把「複習錯題 / 繼續學習（弱項）」放最上面，純測驗模式其次。
- **依賴**：F1（精熟條）；切換器本身無依賴可先做。
- **複雜度**：M。

#### F7. 測驗鍵盤作答 + 流程順手化 — **P1 · S**
- **解決**：測驗只能滑鼠點；與 browse 模式不一致。
- **價值**：1–4 鍵選答、Enter / Space 下一題、答錯時自動聚焦解釋。對每天練的人是高頻體感提升。沿用 browse 已有的 keydown 模式（`:1576`），bind/unbind 對齊。
- **依賴**：無。
- **複雜度**：S。

#### F8. 結果頁與美學對齊 + 錯題行動化 — **P2 · S**
- **解決**：emoji 鼓勵語與「非 Duolingo 極簡」定位輕微衝突；結果頁錯題是死的。
- **價值**：把 `🏆🎉💪` 評語改為克制的文字回饋（保留西語短語當學習元素，移除大 emoji）；錯題清單加「複習這些」行動（接 F3）。
- **依賴**：F3（錯題行動）。
- **複雜度**：S。
- **備註**：純美學偏好，列 P2；若 owner 其實喜歡那點 emoji，可只做錯題行動化。**這是一個需要 owner 拍板的開放問題（見 §5）。**

#### F9. 自製題庫的 grammar 缺口——明確化而非假裝有 — **P2 · S**
- **解決**：custom bank grammar 永遠空，使用者不解為何按鈕灰掉。
- **價值**：兩條路（owner 二選一，§5 開放問題）：
  - (a) **誠實告知**：在自製題庫卡與主選單灰按鈕旁，明寫「自製題庫僅含單字／聽力，無文法題」。S，零風險。
  - (b) **擴充 codec 支援 grammar**：`parseBankMd`/`formatBankMd`（`:739-796`）加 `# Grammar` 區塊。M，且要處理 `___` 與 4 選項格式驗證（可借 `merge_seed.py` 的驗證規則）。
- **建議先做 (a)**，(b) 視 owner 是否真的想手寫 grammar 題再說。
- **複雜度**：S（方案 a）/ M（方案 b）。

### 優先序總表

| ID | 功能 | 問題 | 優先 | 複雜度 | 依賴 | 一句話理由 |
|----|------|------|------|--------|------|-----------|
| F0 | 題項精熟資料模型 | 1 | **P0** | M | — | 一切進度/SRS 的地基，先做 |
| F1 | 每題庫精熟總覽 | 1,2 | **P0** | M | F0 | 直接命中 owner 原話「看不出進度」 |
| F2 | 弱項優先出題 | 1 | **P0** | M | F0 | 最直接「真的加速學習」 |
| F3 | 錯題本 + 複習模式 | 1,2 | **P0** | M | F0 | 修掉最痛的「錯題即焚」 |
| F6 | 主選單 = 學習中樞 | 2 | **P0** | M | F1 | 修掉迷路感與切換成本 |
| F7 | 測驗鍵盤作答 | 2 | P1 | S | — | 高頻體感、低成本、可獨立先插隊 |
| F4 | 輕量 SRS（Leitner） | 1 | P1 | L | F0,F2 | 長期留存，但先讓基礎穩 |
| F5 | 進度趨勢視覺化 | 1,2 | P1 | M | F0,F1 | 讓既有 history 資料變可見 |
| F8 | 結果頁美學對齊 | 2 | P2 | S | F3 | 美學一致性，需 owner 拍板 |
| F9 | 自製題庫 grammar 明確化 | 2 | P2 | S/M | — | 消除困惑，先做誠實告知版 |

---

## 3. 架構建議 (Architecture recommendation) — 問題 3

### 3.1 建議：**不做框架遷移；做「同棧內現代化重構」**

**推薦目標形態（維持 vanilla + FastAPI，但結構升級）：**

| 面向 | 現況 | 建議目標 | 為何 |
|------|------|----------|------|
| 前端框架 | vanilla 單檔 | **維持 vanilla**，但拆檔 | React 換不到對等價值，且破壞無 build 限制 |
| 前端結構 | 2020 行單一 `index.html` | 拆成 `index.html` + `app.css` + `js/` 多個 ES module（原生 `<script type="module">`，**仍無 build**） | 解決真痛點（可維護性），不違反硬限制 |
| 狀態管理 | 散落的閉包變數 | 集中一個 `store.js`（單一 state 物件 + 明確 mutation 函式 + 訂閱 render） | SRS/進度是跨切面，需要單一可信來源 |
| 後端 | in-memory，改 JSON 要重啟 | 加一個 `/api/reload`（dev 用）或檔案 mtime 檢查 | 消除 owner 加題的摩擦，極小改動 |
| 後端職責 | 同時服務題庫 + AI 匯入 | **維持不變** | FastAPI 對這個量級剛好，無需動 |
| 測試 | 無 | 加最小回歸測試：出題加權、SRS 排程、MD codec round-trip（Node 內建 `node:test` 跑 ES module，無需 build） | 重構 SRS 前的安全網，這是唯一「非選配」的新增 |
| 資料/進度 | FS Access + MD + localStorage | **完全維持**，僅擴充 MD schema（新增區塊、向下相容） | 硬限制核心，動它風險最高、收益最低 |

**原生 ES module 拆檔範例（無 build、可離線、瀏覽器原生支援）：**

```
frontend/
  index.html        ← 只剩結構 + <link app.css> + <script type="module" src="js/main.js">
  app.css           ← 把現有 <style> 整段搬出（設計系統不動）
  js/
    store.js        ← 單一 state + mutations + 訂閱
    progress.js     ← F0 精熟模型 + MD codec（含既有 progress/bank codec）
    quiz.js         ← 出題（含 F2 加權、F4 SRS 排程）
    fs.js           ← FS Access / IndexedDB / localStorage
    views/          ← menu / quiz / result / bank / browse 各自 render
    main.js         ← init + 路由（沿用現有 show()）
```

> 這是「現代化」真正該花力氣的地方：**模組邊界、單一狀態源、可測試**——而不是 JSX。`<script type="module">` 是所有目標瀏覽器（Chrome/Edge，FS Access 本就只在這些跑）原生支援，**零 build、零 node_modules、可離線、可雙擊開啟**，完全相容硬限制。

### 3.2 取捨分析（對照硬限制）

| 硬限制 | 大遷移 (React/Next) | 建議方案（vanilla 重構） |
|--------|---------------------|--------------------------|
| 離線、無 CDN、system font | ✗ 需 bundle/SSR 思考，易引入網路依賴 | ✓ 原生 module，完全離線 |
| 無 build step | ✗ 一定需要 Vite/Next build | ✓ 完全無 build |
| markdown 資料夾 + 無帳號 | △ 可保留但 FS Access 整合更繞 | ✓ 完全不動既有 codec |
| 單人本機 | ✗ React 的價值用不到 | ✓ 複雜度匹配情境 |
| 可維護性（真痛點） | ✓ 元件化會改善 | ✓ 模組化同樣改善，成本低 10 倍 |
| 風險 | 高（重寫 1400 行邏輯 + FS/語音/離線回歸） | 低（搬移 + 漸進，可分檔逐步） |

### 3.3 「做更少」的分階段選項（建議採用的節奏）

不要為了重構而重構。**重構服務於功能，不領先於功能：**

- **Tier 0（必做，搭配 Phase 1）**：抽出 `progress.js` 與 `store.js` 兩個 module——因為 F0 精熟模型本來就要寫新程式碼，順勢從乾淨模組開始，不回頭塞進 2020 行單檔。其餘檔案暫不動。
- **Tier 1（做 F4/F5 時）**：抽出 `quiz.js`，因為 SRS 出題邏輯複雜，值得隔離 + 測試。
- **Tier 2（機會性）**：CSS 外置、views 拆分——純整理，無功能價值，**有空才做，不排期**。
- **永遠不做**：React/Vue/Next 遷移、TypeScript build、後端改寫、改 MD 儲存模型為 DB/帳號。除非硬限制本身改變。

### 3.4 後端微調（低風險高回報，可任何時候做，S）
- 加 `/api/reload`（POST，dev only）重新載入 `LEVELS`，免去改題庫重啟（`main.py:48` 改成可重呼叫的 `load_levels()`）。
- 或更省事：`get_banks()` 比對 `data/levels` 的 mtime，有變就 reload。對單人本機無併發疑慮。

---

## 4. 建議路線圖 (Recommended roadmap)

### Phase 1 — 讓學習「看得見、有方向」（地基 + 最痛點）
**目標**：解決問題 1 的根本 + 問題 2 最痛的兩點。
**內容**：
1. **F0 題項精熟資料模型**（含 **F0a：vocab 補 `vx_*` id 一次性遷移 + `merge_seed.py` 配 id** + `progress.js` / `store.js` 模組化，Tier 0 重構）— 一切的地基。**建議 F0 內部順序：先 F0a 資料遷移 + round-trip 測試 → 再建精熟模型**，避免在不穩的鍵上疊資料。
2. **F1 每題庫精熟總覽** — 直接回答 owner「看不出進度」。
3. **F2 弱項優先出題** — 真正加速學習。
4. **F3 錯題本 + 複習模式** — 修掉「錯題即焚」。
5. **F7 測驗鍵盤作答**（小、可平行插入，體感立即提升）。
6. **後端 `/api/reload` 或 mtime reload**（順手做，消除 owner 加題摩擦）。
**為何先做這些**：F0 是所有東西的前置；F1+F2+F3 合起來把「測驗器」變成「學習系統」，是最高槓桿且彼此共用 F0 資料，一次做完最省。
**先不做**：SRS、趨勢圖、結果頁美學、grammar codec 擴充——避免在地基未驗證前擴張。

### Phase 2 — 留存與洞察（在穩固地基上加值）
**內容**：
1. **F6 主選單 = 學習中樞**（精熟條 + 就地切換題庫；依賴 Phase 1 的 F1）。
2. **F4 輕量 SRS（Leitner 盒）** — 長期記憶留存。
3. **F5 進度趨勢視覺化** — 讓既有 history 資料變可見。
4. **Tier 1 重構**：抽出 `quiz.js`（SRS 邏輯複雜，值得隔離 + 加 `node:test` 回歸）。
**為何排這裡**：這些都依賴 Phase 1 的精熟資料已在真實使用中被驗證過（精熟閾值合不合理、加權體感如何），先收集自己的使用回饋再上 SRS。

### Phase 3 — 打磨與一致性（低風險收尾）
**內容**：
1. **F8 結果頁美學對齊 + 錯題行動化**（需 owner 先拍板 §5）。
2. **F9 自製題庫 grammar 明確化**（先做誠實告知版 a）。
3. **Tier 2 機會性重構**：CSS 外置、views 拆分（純整理，有空才做）。
**為何最後**：純打磨，無學習效率槓桿，且 F8 卡在 owner 決策。

### 明確「現在不要做」清單
| 不做 | 原因 | 何時重新評估 |
|------|------|--------------|
| React/Next/Vue 遷移 | 違反無 build/離線硬限制，換不到價值 | owner 要做多人/雲端/行動 app 時 |
| 改 markdown 為 DB/帳號 | 硬限制核心，風險最高收益最低 | 同上 |
| 完整 SM-2 SRS 演算法 | Leitner 對單人足夠且好解釋 | F4 上線後若覺得排程太粗 |
| 自製題庫 grammar 手寫 codec (F9b) | 需求未驗證，先誠實告知 | owner 明確說想手寫文法題 |
| 後端改寫/換框架 | FastAPI 對此量級剛好 | 永遠不需要，除非硬限制變 |
| 圖表/動畫庫 | 違反離線無 CDN + 極簡美學 | 不重新評估 |

---

## 5. 開放問題 (Open questions) — 需 owner 在開工前拍板

1. ~~**【F0 阻斷性】精熟（mastery）的定義門檻？**~~ ✅ **已解決（2026-05-19）**：採「連續答對 **3 次** = 精熟」，且 **3 為設定頁可調參數**。已反映於 F1。

2. ~~**【F0/SRS 設計】vocab 穩定鍵取捨？**~~ ✅ **已解決（2026-05-19）**：owner 選 **補 id**（非 `es` 字串鍵）。內建 vocab 補 `vx_<LID>_NNN`，新增 F0a 資料遷移子任務，F0 複雜度上修 M–L。已反映於 F0。

3. **【F4 範圍】SRS 用 Leitner 盒（建議）還是要完整 SM-2？**
   Leitner 更好解釋、無調參、對單人足夠。確認採 Leitner？間隔預設 1/3/7/16/35 天可接受嗎？

4. **【F8 美學】結果頁的 `🏆🎉💪` emoji 鼓勵語要移除嗎？**
   PM 觀點：與「非 Duolingo 極簡」定位輕微衝突，建議改克制文字。但這是 owner 的個人學習工具——若 owner 喜歡那點正回饋，保留也合理。**這題不拍板不影響 Phase 1/2，但 Phase 3 需要答案。**

5. **【F9 方向】自製題庫要不要支援手寫 grammar 題？**
   影響 F9 是做「誠實告知」(S) 還是「擴充 MD codec」(M)。owner 平常會自己出文法題嗎？若否，永遠只做告知版。

6. **【節奏確認】是否接受「重構只服務於功能、不獨立排期大重寫」的原則？**
   這是整份架構建議的核心立場。若 owner 其實很想要一次性把前端拆乾淨（即使無新功能），那 Tier 2 的排期判斷要調整。

---

## 附錄：關鍵程式碼引用索引

| 主題 | 位置 |
|------|------|
| 進度資料模型（僅題庫層級） | `frontend/index.html:1079-1094` `recordQuizResult()` |
| 隨機出題（無記憶） | `frontend/index.html:1647` `makeVocabQ()`、`:1723` `generateQuestions()` |
| 全域統計 UI（只有 3 數字） | `frontend/index.html:1140` `renderStats()` |
| 錯題只在記憶體 | `frontend/index.html:1810`、`:1851` `showResult()` |
| 進度 MD codec（可擴充處） | `frontend/index.html:933` `formatSummaryMd()`、`:962` `formatBankProgressMd()` |
| custom bank 永遠無 grammar | `frontend/index.html:1440`、`:765` `parseBankMd()` |
| browse 已有鍵盤（測驗沒有） | `frontend/index.html:1576` `bindBrowseKeys()` |
| 設計系統（極簡，已落實，勿動） | `frontend/index.html:12-396` |
| 後端 in-memory 載入（改題庫要重啟） | `backend/main.py:48` |
| vocab 無 id（SRS 鍵設計約束） | `data/levels/L1.json:5-11`；對比 listening/grammar id 見 `tools/merge_seed.py:85,106` |
