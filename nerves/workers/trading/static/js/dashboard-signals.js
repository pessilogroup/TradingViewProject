/**
 * dashboard-signals.js — Indicator Signal Feed Module
 * Sovereign Trading Node v7.6 — TradingView Pine Script Integration
 */

/* ── State ───────────────────────────────────────────────────────── */
const SIG = {
  page:      0,
  pageSize:  20,
  total:     0,
  typeFilter: '',
  debounceTimer: null,
  chart:     null,
};

/* ── Bootstrap: called by switchTab('signals') ───────────────────── */
async function initSignalsTab() {
  await Promise.all([loadSignalStats(), loadSignals()]);
}

/* ── Debounce helper ─────────────────────────────────────────────── */
function debounceLoadSignals() {
  clearTimeout(SIG.debounceTimer);
  SIG.debounceTimer = setTimeout(() => {
    SIG.page = 0;
    loadSignals();
  }, 350);
}

/* ── Type filter pill ───────────────────────────────────────────── */
function setSigType(type, btn) {
  SIG.typeFilter = type;
  SIG.page = 0;
  document.querySelectorAll('.sig-pill').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  loadSignals();
}

/* ── Load KPI stats ──────────────────────────────────────────────── */
async function loadSignalStats() {
  try {
    const res = await apiFetch('/api/indicator-signals/stats');
    if (!res) return;

    const entry   = res.by_type?.entry  || { count: 0 };
    const exit_   = res.by_type?.exit   || { count: 0 };
    const info    = res.by_type?.info   || { count: 0 };

    setText('sigKpiTotal',  res.total    ?? '—');
    setText('sigKpiEntry',  entry.count  ?? '—');
    setText('sigKpiExit',   exit_.count  ?? '—');
    setText('sigKpiInfo',   info.count   ?? '—');
    setText('sigKpiUrgent', res.high_priority_24h ?? '—');
    setText('sigKpiConf',   res.avg_confidence != null ? res.avg_confidence + '%' : '—');

    // Badge on tab nav
    const badge = document.getElementById('signalBadge');
    if (badge) badge.textContent = res.total || 0;

    // Donut chart
    renderSignalTypeChart(res.by_type || {});

    // Top indicators list
    renderTopIndicators(res.top_indicators || []);

    // Top symbols grid
    renderTopSymbols(res.top_symbols || []);

  } catch (e) {
    console.error('[Signals] Stats error:', e);
  }
}

/* ── Load signal feed ────────────────────────────────────────────── */
async function loadSignals() {
  const symbol    = (document.getElementById('sigSymbolFilter')?.value || '').trim();
  const indName   = (document.getElementById('sigNameFilter')?.value   || '').trim();
  const offset    = SIG.page * SIG.pageSize;

  const params = new URLSearchParams({ limit: SIG.pageSize, offset });
  if (symbol)         params.set('symbol',         symbol.toUpperCase());
  if (SIG.typeFilter) params.set('signal_type',    SIG.typeFilter);
  if (indName)        params.set('indicator_name', indName);

  const feedList = document.getElementById('sigFeedList');
  if (feedList) feedList.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  try {
    const res = await apiFetch(`/api/indicator-signals?${params}`);
    if (!res) return;

    SIG.total = res.total;
    setText('sigFeedCount', `${res.total.toLocaleString()} signal${res.total !== 1 ? 's' : ''}`);
    renderSignalFeed(res.signals || []);
    renderSigPagination();

    // Show ATR risk panel if first entry signal has metadata
    const firstEntry = (res.signals || []).find(s => s.signal_type === 'entry');
    if (firstEntry) renderRiskPanel(firstEntry);

  } catch (e) {
    console.error('[Signals] Feed error:', e);
    if (feedList) feedList.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><h3>Error loading signals</h3></div>`;
  }
}

/* ── Render signal feed cards ────────────────────────────────────── */
function renderSignalFeed(signals) {
  const el = document.getElementById('sigFeedList');
  if (!el) return;

  if (!signals.length) {
    el.innerHTML = `
      <div class="empty-state">
        <div class="icon">📡</div>
        <h3>No signals found</h3>
        <p>Send a TradingView alert to <code>/webhook</code> with <code>"source":"indicator"</code></p>
      </div>`;
    return;
  }

  el.innerHTML = signals.map(s => {
    const typeClass  = { entry: 'sig-card-entry', exit: 'sig-card-exit', info: 'sig-card-info' }[s.signal_type] || '';
    const typeEmoji  = { entry: '🟢', exit: '🔴', info: '🔵' }[s.signal_type] || '⚪';
    const urgent     = s.confidence_score > 80;
    const confColor  = s.confidence_score > 80 ? '#ef4444' : s.confidence_score > 60 ? '#f59e0b' : '#6b7280';
    const confWidth  = Math.min(s.confidence_score, 100);

    const price      = s.price != null ? `$${Number(s.price).toLocaleString()}` : '—';
    const conditions = (s.conditions_met || []).map(c => `<span class="sig-cond-tag">${escHtml(c)}</span>`).join('');
    const atr        = s.metadata?.atr_value ? `<span class="sig-meta-tag">ATR ${s.metadata.atr_value}</span>` : '';
    const ts         = formatShortTime(s.created_at);

    return `
    <div class="sig-card ${typeClass}${urgent ? ' sig-card-urgent' : ''}">
      <div class="sig-card-header">
        <div class="sig-card-left">
          <span class="sig-type-badge">${typeEmoji} ${s.signal_type.toUpperCase()}</span>
          <span class="sig-symbol">${escHtml(s.symbol)}</span>
          <span class="sig-exchange">${escHtml(s.exchange)}</span>
          ${urgent ? '<span class="sig-urgent-tag">🔴 KHẨN CẤP</span>' : ''}
        </div>
        <div class="sig-card-right">
          <span class="sig-time">${ts}</span>
          <span class="sig-interval">${escHtml(s.interval)}</span>
        </div>
      </div>
      <div class="sig-card-body">
        <div class="sig-indicator-name">${escHtml(s.indicator_name)}</div>
        <div class="sig-price-row">
          <span class="sig-price">${price}</span>
          ${atr}
        </div>
        <div class="sig-conf-row">
          <div class="sig-conf-bar-wrap">
            <div class="sig-conf-bar" style="width:${confWidth}%;background:${confColor}"></div>
          </div>
          <span class="sig-conf-num" style="color:${confColor}">${s.confidence_score}%</span>
        </div>
        ${conditions ? `<div class="sig-conditions">${conditions}</div>` : ''}
      </div>
    </div>`;
  }).join('');
}

/* ── Render donut chart ──────────────────────────────────────────── */
function renderSignalTypeChart(byType) {
  const ctx = document.getElementById('sigTypeChart');
  if (!ctx) return;

  const labels = Object.keys(byType);
  const data   = labels.map(k => byType[k].count);
  const colors = { entry: '#22c55e', exit: '#ef4444', info: '#3b82f6' };
  const bgColors = labels.map(l => colors[l] || '#6b7280');

  if (SIG.chart) SIG.chart.destroy();

  SIG.chart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data, backgroundColor: bgColors, borderWidth: 0, hoverOffset: 6 }],
    },
    options: {
      responsive: true,
      cutout: '65%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { color: '#cbd5e1', font: { size: 11, family: 'Inter' }, padding: 12 },
        },
        tooltip: {
          callbacks: {
            label: ctx => ` ${ctx.parsed} signal${ctx.parsed !== 1 ? 's' : ''}`,
          },
        },
      },
    },
  });

  const total = data.reduce((a, b) => a + b, 0);
  setText('sigChartLabel', `${total} total`);
}

/* ── Render top indicators ───────────────────────────────────────── */
function renderTopIndicators(list) {
  const el = document.getElementById('sigTopIndicators');
  if (!el) return;
  if (!list.length) { el.innerHTML = '<div class="empty-state p-16"><p>No data yet</p></div>'; return; }

  const max = list[0]?.count || 1;
  el.innerHTML = list.map((item, i) => `
    <div class="sig-top-item">
      <div class="sig-top-rank">${i + 1}</div>
      <div class="sig-top-body">
        <div class="sig-top-name">${escHtml(item.name)}</div>
        <div class="sig-top-bar-wrap">
          <div class="sig-top-bar" style="width:${Math.round(item.count / max * 100)}%"></div>
        </div>
      </div>
      <div class="sig-top-count">${item.count}</div>
    </div>`).join('');
}

/* ── Render top symbols grid ─────────────────────────────────────── */
function renderTopSymbols(list) {
  const el = document.getElementById('sigTopSymbols');
  if (!el) return;
  if (!list.length) { el.innerHTML = '<div class="empty-state p-16"><p>No data yet</p></div>'; return; }

  el.innerHTML = list.map(s => `
    <div class="sig-sym-chip" onclick="filterBySymbol('${s.symbol}')">
      <span class="sig-sym-name">${escHtml(s.symbol)}</span>
      <span class="sig-sym-count">${s.count}</span>
    </div>`).join('');
}

/* ── Render ATR risk panel ───────────────────────────────────────── */
function renderRiskPanel(signal) {
  const panel = document.getElementById('sigRiskPanel');
  const grid  = document.getElementById('sigRiskGrid');
  if (!panel || !grid) return;

  const atr = parseFloat(signal.metadata?.atr_value || 0);
  const price = signal.price;

  if (!price || !atr) { panel.style.display = 'none'; return; }

  const sl = (price - atr * 2).toFixed(2);
  const tp = (price + atr * 3).toFixed(2);
  const rr = '1:1.5';

  grid.innerHTML = `
    <div class="sig-risk-item"><span class="sig-risk-label">Entry</span><span class="sig-risk-val">$${Number(price).toLocaleString()}</span></div>
    <div class="sig-risk-item"><span class="sig-risk-label">ATR</span><span class="sig-risk-val">${atr.toFixed(2)}</span></div>
    <div class="sig-risk-item sl"><span class="sig-risk-label">Stop Loss</span><span class="sig-risk-val">$${sl}</span></div>
    <div class="sig-risk-item tp"><span class="sig-risk-label">Take Profit</span><span class="sig-risk-val">$${tp}</span></div>
    <div class="sig-risk-item"><span class="sig-risk-label">Symbol</span><span class="sig-risk-val">${escHtml(signal.symbol)}</span></div>
    <div class="sig-risk-item"><span class="sig-risk-label">Indicator</span><span class="sig-risk-val">${escHtml(signal.indicator_name)}</span></div>`;

  panel.style.display = '';
}

/* ── Pagination ──────────────────────────────────────────────────── */
function renderSigPagination() {
  const el = document.getElementById('sigPagination');
  if (!el) return;

  const totalPages = Math.ceil(SIG.total / SIG.pageSize);
  if (totalPages <= 1) { el.innerHTML = ''; return; }

  let html = '';
  if (SIG.page > 0)
    html += `<button class="page-btn" onclick="sigGoPage(${SIG.page - 1})">‹ Prev</button>`;
  html += `<span class="page-info">${SIG.page + 1} / ${totalPages}</span>`;
  if (SIG.page < totalPages - 1)
    html += `<button class="page-btn" onclick="sigGoPage(${SIG.page + 1})">Next ›</button>`;

  el.innerHTML = html;
}

function sigGoPage(p) {
  SIG.page = p;
  loadSignals();
  document.getElementById('sigFeedList')?.scrollIntoView({ behavior: 'smooth' });
}

/* ── Click-to-filter from symbol chip ───────────────────────────── */
function filterBySymbol(symbol) {
  const inp = document.getElementById('sigSymbolFilter');
  if (inp) { inp.value = symbol; debounceLoadSignals(); }
}

/* ── Helpers ─────────────────────────────────────────────────────── */
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

function escHtml(s) {
  return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function formatShortTime(ts) {
  if (!ts) return '—';
  try {
    const d = new Date(ts.endsWith('Z') ? ts : ts + 'Z');
    const now = new Date();
    const diff = Math.round((now - d) / 60000);
    if (diff < 1)   return 'just now';
    if (diff < 60)  return `${diff}m ago`;
    if (diff < 1440) return `${Math.round(diff/60)}h ago`;
    return d.toLocaleDateString();
  } catch { return ts; }
}

/* apiFetch: use existing global or fallback */
// apiFetch is defined globally in dashboard-core.js. We don't overwrite it to avoid token key mismatches or missing POST options.

/* ── Hook into switchTab ─────────────────────────────────────────── */
(function patchSwitchTab() {
  const _orig = window.switchTab;
  window.switchTab = function(tab) {
    _orig && _orig(tab);
    if (tab === 'signals') initSignalsTab();
  };
})();
