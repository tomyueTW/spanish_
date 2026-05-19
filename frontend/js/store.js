// 極簡 reactive store（零依賴、原生 ES module、可離線）。
//
// 設計目標（PRODUCT_PLAN.md §3 Tier 0）：建立「單一狀態來源 + 明確
// mutation + 訂閱」的接縫。本階段先服務 progress 切片，App 其餘狀態
// 仍維持原樣，日後可逐步遷入而不需大重寫。

export function createStore(initialState) {
  let state = initialState;
  const subscribers = new Set();

  function get() {
    return state;
  }

  // mutator：(draft) => newStateOrUndefined。回傳新值則取代，否則沿用
  // （允許就地修改後回傳同一物件；一律通知訂閱者）。
  function update(mutator) {
    const next = mutator(state);
    if (next !== undefined) state = next;
    for (const fn of subscribers) {
      try { fn(state); } catch (e) { console.warn('store subscriber error', e); }
    }
    return state;
  }

  function set(next) {
    return update(() => next);
  }

  function subscribe(fn) {
    subscribers.add(fn);
    return () => subscribers.delete(fn);
  }

  return { get, set, update, subscribe };
}
