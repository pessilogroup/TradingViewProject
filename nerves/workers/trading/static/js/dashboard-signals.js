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
  activeSymbol: 'BTCUSDT',
};

/* ── SSE connection ───────────────────────────────────────────────── */
let _signalSSE = null;

function startSignalsSSE() {
  if (_signalSSE) return;   // already connected
  _signalSSE = new EventSource('/api/events');

  _signalSSE.addEventListener('connected', () => {
    console.log('[SSE] connected to /api/events');
  });

  _signalSSE.addEventListener('new_signal', (e) => {
    try {
      const d = JSON.parse(e.data);
      const emoji = d.signal_type === 'entry' ? '🟢' : d.signal_type === 'exit' ? '🔴' : '🔵';
      toast(`${emoji} New ${d.signal_type?.toUpperCase()} — ${d.symbol} @$${d.price ?? '?'}`, 'info');
    } catch {}
    // Reload the feed (debounced slightly to batch rapid webhooks)
    clearTimeout(SIG.debounceTimer);
    SIG.debounceTimer = setTimeout(() => {
      SIG.page = 0;
      loadSignals();
    }, 600);
  });

  _signalSSE.addEventListener('scan_complete', () => {
    // Update Scanner tab if it's active, otherwise cache is updated silently
    if (typeof loadLastScan === 'function') loadLastScan();
  });

  _signalSSE.onerror = () => {
    // Browser auto-reconnects — just log
    console.warn('[SSE] connection lost, browser will retry...');
  };
}

function stopSignalsSSE() {
  if (_signalSSE) {
    _signalSSE.close();
    _signalSSE = null;
  }
}

/* ── Bootstrap: called by switchTab('signals') ───────────────────── */
async function initSignalsTab() {
  await Promise.all([loadSignals(), loadWatchlist()]);
  startSignalsSSE();
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
async function loadSignalStats(symbol) {
  try {
    const indName = (document.getElementById('sigNameFilter')?.value || '').trim();
    let url = '/api/indicator-signals/stats';
    const queryParams = new URLSearchParams();
    if (symbol) queryParams.set('symbol', symbol);
    if (indName) queryParams.set('indicator_name', indName);
    const queryString = queryParams.toString();
    if (queryString) {
      url += '?' + queryString;
    }

    const res = await apiFetch(url);
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

    // Populate Indicator select dropdown in chart section from res.top_indicators
    const indSelect = document.getElementById('sigChartIndicatorSelect');
    if (indSelect) {
      const currentVal = indSelect.value || indName;
      let html = '<option value="">All Indicators</option>';
      let found = false;
      if (res.top_indicators && res.top_indicators.length) {
        res.top_indicators.forEach(ind => {
          if (ind.name === currentVal) found = true;
          html += `<option value="${ind.name}">${ind.name}</option>`;
        });
      }
      if (currentVal && !found) {
        html += `<option value="${currentVal}">${currentVal}</option>`;
      }
      indSelect.innerHTML = html;
      indSelect.value = currentVal;
    }

    // Donut chart
    renderSignalTypeChart(res.by_type || {});

    // Direction Mix stats (Long/Short entry/exit)
    renderDirectionMix(res.direction_mix || {}, res.market_regime || 'CHOP');

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

  const symSelect = document.getElementById('sigChartSymbolSelect');
  if (symSelect) {
    symSelect.value = symbol.toUpperCase();
  }
  const indSelect = document.getElementById('sigChartIndicatorSelect');
  if (indSelect) {
    indSelect.value = indName;
  }

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

    // Resolve active symbol: input value -> first signal's symbol -> default 'BTCUSDT'
    let activeSymbol = symbol.trim();
    if (!activeSymbol && res.signals && res.signals.length > 0) {
      activeSymbol = res.signals[0].symbol;
    }
    SIG.activeSymbol = (activeSymbol || 'BTCUSDT').toUpperCase();

    // Load stats and chart for active symbol
    loadSignalStats(SIG.activeSymbol);

  } catch (e) {
    console.error('[Signals] Feed error:', e);
    if (feedList) feedList.innerHTML = `<div class="empty-state"><div class="icon">⚠️</div><h3>Error loading signals</h3></div>`;
  }
}

/* ── Render single signal card HTML ──────────────────────────────── */
function renderSignalCardHtml(s) {
  const typeClass  = { entry: 'sig-card-entry', exit: 'sig-card-exit', info: 'sig-card-info' }[s.signal_type] || '';
  const typeEmoji  = { entry: '🟢', exit: '🔴', info: '🔵' }[s.signal_type] || '⚪';
  const urgent     = s.confidence_score > 80;
  const confColor  = s.confidence_score > 80 ? '#ef4444' : s.confidence_score > 60 ? '#f59e0b' : '#6b7280';
  const confWidth  = Math.min(s.confidence_score, 100);

  const price      = s.price != null ? `$${Number(s.price).toLocaleString()}` : '—';
  const conditions = (s.conditions_met || []).map(c => `<span class="sig-cond-tag">${escHtml(c)}</span>`).join('');
  const atr        = s.metadata?.atr_value ? `<span class="sig-meta-tag">ATR ${s.metadata.atr_value}</span>` : '';
  const ts         = formatShortTime(s.created_at);

  let tradeBtnHtml = '';
  let recExitHtml = '';
  if (s.signal_type === 'entry' && urgent) {
    const dir = (s.metadata?.direction || 'long').toLowerCase();
    const atrVal = parseFloat(s.metadata?.atr_value || 0);
    const pr = parseFloat(s.price || 0);
    let slVal = 0, tpVal = 0;
    
    if (dir === 'long') {
      if (atrVal && pr) {
        slVal = Math.round(pr - atrVal * 2);
        tpVal = Math.round(pr + atrVal * 3);
      }
      tradeBtnHtml = `
        <button class="sig-trade-btn btn-buy" 
                onclick="executeRealtimeSignalTrade('${s.symbol}', 'buy', ${pr}, '${s.exchange}', '${s.interval}', '${escHtml(s.indicator_name)}', '${atrVal}')">
          ⚡ Buy
        </button>
      `;
    } else {
      if (atrVal && pr) {
        slVal = Math.round(pr + atrVal * 2);
        tpVal = Math.round(pr - atrVal * 3);
      }
      tradeBtnHtml = `
        <button class="sig-trade-btn btn-sell" 
                onclick="executeRealtimeSignalTrade('${s.symbol}', 'sell', ${pr}, '${s.exchange}', '${s.interval}', '${escHtml(s.indicator_name)}', '${atrVal}')">
          ⚡ Sell
        </button>
      `;
    }

    if (slVal && tpVal) {
      recExitHtml = `
        <div class="sig-rec-exit">
          <span>🎯 Rec. Exit:</span>
          <span class="sl">SL $${slVal.toLocaleString()}</span>
          <span class="tp">TP $${tpVal.toLocaleString()}</span>
        </div>
      `;
    }
  }

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
        ${tradeBtnHtml}
      </div>
      ${recExitHtml}
      <div class="sig-conf-row">
        <div class="sig-conf-bar-wrap">
          <div class="sig-conf-bar" style="width:${confWidth}%;background:${confColor}"></div>
        </div>
        <span class="sig-conf-num" style="color:${confColor}">${s.confidence_score}%</span>
      </div>
      ${conditions ? `<div class="sig-conditions">${conditions}</div>` : ''}
    </div>
  </div>`;
}

/* ── Render historical signal card HTML (Collapsed Layout) ───────── */
function renderHistoricalSignalCardHtml(s) {
  const typeClass  = { entry: 'sig-card-entry', exit: 'sig-card-exit', info: 'sig-card-info' }[s.signal_type] || '';
  const typeEmoji  = { entry: '🟢', exit: '🔴', info: '🔵' }[s.signal_type] || '⚪';
  const urgent     = s.confidence_score > 80;
  const confColor  = s.confidence_score > 80 ? '#ef4444' : s.confidence_score > 60 ? '#f59e0b' : '#6b7280';
  const confWidth  = Math.min(s.confidence_score, 100);

  const price      = s.price != null ? `$${Number(s.price).toLocaleString()}` : '—';
  const conditions = (s.conditions_met || []).map(c => `<span class="sig-cond-tag">${escHtml(c)}</span>`).join('');
  const atr        = s.metadata?.atr_value ? `<span class="sig-meta-tag">ATR ${s.metadata.atr_value}</span>` : '';
  const ts         = formatShortTime(s.created_at);

  let recExitHtml = '';
  if (s.signal_type === 'entry') {
    const dir = (s.metadata?.direction || 'long').toLowerCase();
    const atrVal = parseFloat(s.metadata?.atr_value || 0);
    const pr = parseFloat(s.price || 0);
    let slVal = 0, tpVal = 0;
    
    if (dir === 'long' && atrVal && pr) {
      slVal = Math.round(pr - atrVal * 2);
      tpVal = Math.round(pr + atrVal * 3);
    } else if (dir === 'short' && atrVal && pr) {
      slVal = Math.round(pr + atrVal * 2);
      tpVal = Math.round(pr - atrVal * 3);
    }

    if (slVal && tpVal) {
      recExitHtml = `
        <div class="sig-rec-exit" style="margin-top: 10px; margin-bottom: 0;">
          <span>🎯 Rec. Exit:</span>
          <span class="sl">SL $${slVal.toLocaleString()}</span>
          <span class="tp">TP $${tpVal.toLocaleString()}</span>
        </div>
      `;
    }
  }

  const cardId = `sig-hist-${s.id}`;
  const exchangeLabel = s.exchange ? s.exchange.toUpperCase() : 'UNKNOWN';

  return `
  <div class="sig-hist-card ${typeClass}" id="${cardId}" onclick="toggleHistoricalCard('${cardId}', event)">
    <div class="sig-hist-header">
      <div class="sig-hist-badge-wrap">
        <span class="sig-type-label">${s.signal_type.toUpperCase()}</span>
        <span class="sig-hist-symbol">${escHtml(s.symbol)}</span>
        <span class="sig-hist-exchange badge-${(s.exchange || 'binance').toLowerCase()}">${escHtml(exchangeLabel)}</span>
      </div>
      <div class="sig-hist-price-wrap">
        <span class="sig-hist-price">${price}</span>
        <span class="sig-hist-time">${ts}</span>
        <span class="sig-hist-arrow">▼</span>
      </div>
    </div>
    <div class="sig-hist-body" style="display: none;">
      <div class="sig-hist-details-grid">
        <div class="sig-hist-indicator">${escHtml(s.indicator_name)} <span class="sig-hist-interval">${escHtml(s.interval)}</span></div>
        <div class="sig-conf-row" style="margin-top: 8px;">
          <div class="sig-conf-bar-wrap">
            <div class="sig-conf-bar" style="width:${confWidth}%;background:${confColor}"></div>
          </div>
          <span class="sig-conf-num" style="color:${confColor}">${s.confidence_score}%</span>
        </div>
        ${conditions ? `<div class="sig-conditions" style="margin-top: 8px; margin-bottom: 4px;">${conditions}</div>` : ''}
        ${atr ? `<div style="margin-top: 6px;"><span class="sig-meta-tag">ATR ${s.metadata.atr_value}</span></div>` : ''}
        ${recExitHtml}
      </div>
    </div>
  </div>`;
}

/* ── Render grouped symbol card HTML ─────────────────────────────── */
function renderSignalGroupCardHtml(symbol, exchangeMap) {
  const exchanges = Object.keys(exchangeMap);
  const groupSignals = Object.values(exchangeMap);
  
  // Custom tabs
  const tabsHtml = exchanges.map((ex, idx) => {
    const s = exchangeMap[ex];
    const typeEmoji = { entry: '🟢', exit: '🔴', info: '🔵' }[s.signal_type] || '⚪';
    return `
      <button class="sig-ex-tab ${idx === 0 ? 'active' : ''} type-${s.signal_type}" 
              onclick="switchExTab('${symbol}', '${ex}', event)">
        ${typeEmoji} ${ex.toUpperCase()}
      </button>
    `;
  }).join('');

  // Content blocks
  const contentsHtml = exchanges.map((ex, idx) => {
    const s = exchangeMap[ex];
    const typeClass  = { entry: 'sig-card-entry', exit: 'sig-card-exit', info: 'sig-card-info' }[s.signal_type] || '';
    const urgent     = s.confidence_score > 80;
    const confColor  = s.confidence_score > 80 ? '#ef4444' : s.confidence_score > 60 ? '#f59e0b' : '#6b7280';
    const confWidth  = Math.min(s.confidence_score, 100);

    const price      = s.price != null ? `$${Number(s.price).toLocaleString()}` : '—';
    const conditions = (s.conditions_met || []).map(c => `<span class="sig-cond-tag">${escHtml(c)}</span>`).join('');
    const atr        = s.metadata?.atr_value ? `<span class="sig-meta-tag">ATR ${s.metadata.atr_value}</span>` : '';
    const ts         = formatShortTime(s.created_at);

    let tradeBtnHtml = '';
    let recExitHtml = '';
    if (s.signal_type === 'entry' && urgent) {
      const dir = (s.metadata?.direction || 'long').toLowerCase();
      const atrVal = parseFloat(s.metadata?.atr_value || 0);
      const pr = parseFloat(s.price || 0);
      let slVal = 0, tpVal = 0;
      
      if (dir === 'long') {
        if (atrVal && pr) {
          slVal = Math.round(pr - atrVal * 2);
          tpVal = Math.round(pr + atrVal * 3);
        }
        tradeBtnHtml = `
          <button class="sig-trade-btn btn-buy" 
                  onclick="executeRealtimeSignalTrade('${symbol}', 'buy', ${pr}, '${ex}', '${s.interval}', '${escHtml(s.indicator_name)}', '${atrVal}')">
            ⚡ Buy
          </button>
        `;
      } else {
        if (atrVal && pr) {
          slVal = Math.round(pr + atrVal * 2);
          tpVal = Math.round(pr - atrVal * 3);
        }
        tradeBtnHtml = `
          <button class="sig-trade-btn btn-sell" 
                  onclick="executeRealtimeSignalTrade('${symbol}', 'sell', ${pr}, '${ex}', '${s.interval}', '${escHtml(s.indicator_name)}', '${atrVal}')">
            ⚡ Sell
          </button>
        `;
      }

      if (slVal && tpVal) {
        recExitHtml = `
          <div class="sig-rec-exit">
            <span>🎯 Rec. Exit:</span>
            <span class="sl">SL $${slVal.toLocaleString()}</span>
            <span class="tp">TP $${tpVal.toLocaleString()}</span>
          </div>
        `;
      }
    }

    return `
      <div class="sig-ex-content ${ex} ${typeClass} ${idx === 0 ? 'active' : ''}" 
           style="${idx === 0 ? 'display: block;' : 'display: none;'}">
        <div class="sig-card-header">
          <div class="sig-card-left">
            <span class="sig-type-label">${s.signal_type.toUpperCase()}</span>
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
            ${tradeBtnHtml}
          </div>
          ${recExitHtml}
          <div class="sig-conf-row">
            <div class="sig-conf-bar-wrap">
              <div class="sig-conf-bar" style="width:${confWidth}%;background:${confColor}"></div>
            </div>
            <span class="sig-conf-num" style="color:${confColor}">${s.confidence_score}%</span>
          </div>
          ${conditions ? `<div class="sig-conditions">${conditions}</div>` : ''}
        </div>
      </div>
    `;
  }).join('');

  // Initial border class based on the first signal
  const firstSig = groupSignals[0];
  const borderClass = { entry: 'border-entry', exit: 'border-exit', info: 'border-info' }[firstSig.signal_type] || '';

  return `
    <div class="sig-group-card ${borderClass}" id="sig-group-${symbol}">
      <div class="sig-group-header">
        <span class="sig-symbol">${escHtml(symbol)}</span>
        <div class="sig-exchange-tabs">
          ${tabsHtml}
        </div>
      </div>
      <div class="sig-group-content">
        ${contentsHtml}
      </div>
    </div>
  `;
}

/* ── Global tab switcher ─────────────────────────────────────────── */
window.switchExTab = function(symbol, exchange, event) {
  if (event) event.stopPropagation();
  
  const card = document.getElementById(`sig-group-${symbol}`);
  if (!card) return;
  
  // Toggle tab buttons
  card.querySelectorAll('.sig-ex-tab').forEach(btn => {
    btn.classList.toggle('active', btn.textContent.toLowerCase().includes(exchange.toLowerCase()));
  });
  
  // Toggle content blocks and update parent border
  card.querySelectorAll('.sig-ex-content').forEach(block => {
    if (block.classList.contains(exchange)) {
      block.style.display = 'block';
      block.classList.add('active');
      
      card.classList.remove('border-entry', 'border-exit', 'border-info');
      if (block.classList.contains('sig-card-entry')) card.classList.add('border-entry');
      else if (block.classList.contains('sig-card-exit')) card.classList.add('border-exit');
      else if (block.classList.contains('sig-card-info')) card.classList.add('border-info');
    } else {
      block.style.display = 'none';
      block.classList.remove('active');
    }
  });
};

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

  // Inject dynamic styles if not already present
  if (!document.getElementById('sigFeedStyles')) {
    const style = document.createElement('style');
    style.id = 'sigFeedStyles';
    style.textContent = `
      .sig-section {
        margin-bottom: 24px;
      }
      .sig-section-header {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 12px;
        padding-bottom: 6px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.12);
      }
      .sig-section-title {
        font-size: 0.85rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin: 0;
      }
      .sig-title-realtime {
        color: #22c55e;
      }
      .sig-title-history {
        color: #94a3b8;
      }
      .sig-section-badge {
        font-size: 0.7rem;
        font-weight: 700;
        padding: 1px 6px;
        border-radius: 8px;
        font-family: 'JetBrains Mono', monospace;
      }
      .sig-badge-realtime {
        background: rgba(34, 197, 94, 0.15);
        color: #22c55e;
        border: 1px solid rgba(34, 197, 94, 0.3);
      }
      .sig-badge-history {
        background: rgba(148, 163, 184, 0.15);
        color: #94a3b8;
        border: 1px solid rgba(148, 163, 184, 0.3);
      }
      .sig-pulse-dot {
        width: 8px;
        height: 8px;
        background-color: #22c55e;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
        animation: sigPulse 1.8s infinite;
      }
      @keyframes sigPulse {
        0% {
          transform: scale(0.95);
          box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.7);
        }
        70% {
          transform: scale(1);
          box-shadow: 0 0 0 6px rgba(34, 197, 94, 0);
        }
        100% {
          transform: scale(0.95);
          box-shadow: 0 0 0 0 rgba(34, 197, 94, 0);
        }
      }
      .sig-realtime-empty {
        padding: 16px;
        border-radius: 10px;
        border: 1px dashed rgba(148, 163, 184, 0.1);
        background: rgba(30, 41, 59, 0.2);
        color: #64748b;
        font-size: 0.8rem;
        text-align: center;
        margin-bottom: 12px;
      }
      .sig-cards-container {
        display: flex;
        flex-direction: column;
        gap: 10px;
      }
      
      /* Grouped symbols styles */
      .sig-group-card {
        border-radius: 12px;
        border: 1px solid rgba(148,163,184,.12);
        background: rgba(15,23,42,.65);
        padding: 14px 16px;
        transition: all .2s;
        animation: slideInCard .25s ease;
      }
      .sig-group-card.border-entry {
        border-left: 3px solid #22c55e;
      }
      .sig-group-card.border-exit {
        border-left: 3px solid #ef4444;
      }
      .sig-group-card.border-info {
        border-left: 3px solid #3b82f6;
      }
      .sig-group-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 12px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.08);
        padding-bottom: 8px;
      }
      .sig-exchange-tabs {
        display: flex;
        gap: 6px;
      }
      .sig-ex-tab {
        font-size: 0.68rem;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 8px;
        cursor: pointer;
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(148, 163, 184, 0.15);
        color: #94a3b8;
        transition: all 0.15s ease;
      }
      .sig-ex-tab:hover {
        background: rgba(30, 41, 59, 0.8);
        border-color: rgba(148, 163, 184, 0.3);
        color: #e2e8f0;
      }
      .sig-ex-tab.active {
        color: #ffffff;
      }
      .sig-ex-tab.active.type-entry {
        background: rgba(34, 197, 94, 0.2);
        border-color: #22c55e;
      }
      .sig-ex-tab.active.type-exit {
        background: rgba(239, 68, 68, 0.2);
        border-color: #ef4444;
      }
      .sig-ex-tab.active.type-info {
        background: rgba(59, 130, 246, 0.2);
        border-color: #3b82f6;
      }
      .sig-type-label {
        font-size: 0.68rem;
        font-weight: 700;
        color: #64748b;
        background: rgba(30, 41, 59, 0.6);
        padding: 2px 6px;
        border-radius: 6px;
      }
      .sig-ex-content {
        transition: opacity 0.2s ease;
      }
      .sig-group-card .sig-ex-content {
        border-left: none !important;
      }
      
      /* Direction Mix styles */
      .sig-direction-mix {
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid rgba(148, 163, 184, 0.1);
      }
      .sig-dir-single-col {
        background: rgba(30, 41, 59, 0.35);
        border: 1px solid rgba(148, 163, 184, 0.08);
        border-radius: 12px;
        padding: 14px;
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .sig-dir-col-header {
        display: flex;
        align-items: center;
        gap: 8px;
        font-weight: 700;
        font-size: 0.85rem;
        color: #e2e8f0;
      }
      .sig-dir-col-header .emoji {
        font-size: 1.0rem;
      }
      .sig-dir-col-header .title {
        flex: 1;
      }
      .sig-dir-trend-badge {
        font-size: 0.65rem;
        font-weight: 700;
        padding: 2px 8px;
        border-radius: 8px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .sig-dir-trend-badge.active {
        background: rgba(34, 197, 94, 0.12);
        color: #22c55e;
        border: 1px solid rgba(34, 197, 94, 0.25);
      }
      .sig-dir-trend-badge.active-bear {
        background: rgba(239, 68, 68, 0.12);
        color: #ef4444;
        border: 1px solid rgba(239, 68, 68, 0.25);
      }
      .sig-dir-trend-badge.sideway {
        background: rgba(245, 158, 11, 0.12);
        color: #f59e0b;
        border: 1px solid rgba(245, 158, 11, 0.25);
      }
      .sig-dir-trend-badge.inactive {
        background: rgba(148, 163, 184, 0.08);
        color: #64748b;
        border: 1px solid rgba(148, 163, 184, 0.15);
      }
      .sig-dir-stat {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px dashed rgba(148, 163, 184, 0.05);
        padding-bottom: 6px;
      }
      .sig-dir-stat:last-child {
        border-bottom: none;
        padding-bottom: 0;
      }
      .sig-dir-stat .label {
        font-size: 0.72rem;
        color: #64748b;
      }
      .sig-dir-stat .value {
        font-size: 0.8rem;
        font-weight: 700;
        color: #cbd5e1;
        font-family: 'JetBrains Mono', monospace;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .trend-icon {
        font-weight: bold;
        font-size: 0.75rem;
      }
      .trend-icon.icon-active {
        color: #22c55e;
      }
      .trend-icon.icon-active-bear {
        color: #ef4444;
      }
      .trend-icon.icon-sideway {
        color: #f59e0b;
      }
      .trend-icon.icon-inactive {
        color: #64748b;
      }
      .sig-dir-stat-empty {
        font-size: 0.72rem;
        color: #475569;
        font-style: italic;
      }
      .sig-trade-btn {
        padding: 4px 14px;
        font-size: 0.78rem;
        font-weight: 700;
        border-radius: 8px;
        border: none;
        cursor: pointer;
        transition: all 0.15s ease;
        text-transform: uppercase;
        margin-left: auto;
        display: flex;
        align-items: center;
        gap: 4px;
        box-shadow: 0 0 10px rgba(0, 0, 0, 0.2);
      }
      .sig-trade-btn.btn-buy {
        background: #22c55e;
        color: #ffffff;
      }
      .sig-trade-btn.btn-buy:hover {
        background: #16a34a;
        box-shadow: 0 0 12px rgba(34, 197, 94, 0.4);
      }
      .sig-trade-btn.btn-sell {
        background: #ef4444;
        color: #ffffff;
      }
      .sig-trade-btn.btn-sell:hover {
        background: #dc2626;
        box-shadow: 0 0 12px rgba(239, 68, 68, 0.4);
      }
      .sig-rec-exit {
        display: flex;
        gap: 12px;
        font-size: 0.72rem;
        color: #94a3b8;
        background: rgba(30, 41, 59, 0.4);
        padding: 6px 10px;
        border-radius: 6px;
        border: 1px dashed rgba(148, 163, 184, 0.15);
        margin-top: 6px;
        margin-bottom: 8px;
        align-items: center;
      }
      .sig-rec-exit .sl {
        color: #ef4444;
        font-weight: 700;
      }
      .sig-rec-exit .tp {
        color: #22c55e;
        font-weight: 700;
      }
      
      /* Collapsed Historical Cards */
      .sig-hist-card {
        border-radius: 10px;
        border: 1px solid rgba(148, 163, 184, 0.08);
        background: rgba(15, 23, 42, 0.45);
        padding: 10px 14px;
        cursor: pointer;
        transition: all 0.2s ease;
        overflow: hidden;
        margin-bottom: 8px;
      }
      .sig-hist-card:hover {
        background: rgba(30, 41, 59, 0.55);
        border-color: rgba(148, 163, 184, 0.18);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
      }
      .sig-hist-card.expanded {
        background: rgba(30, 41, 59, 0.4);
        border-color: rgba(148, 163, 184, 0.15);
      }
      .sig-hist-card.sig-card-entry {
        border-left: 3px solid rgba(34, 197, 94, 0.45);
      }
      .sig-hist-card.sig-card-entry.expanded {
        border-left: 3px solid #22c55e;
      }
      .sig-hist-card.sig-card-exit {
        border-left: 3px solid rgba(239, 68, 68, 0.45);
      }
      .sig-hist-card.sig-card-exit.expanded {
        border-left: 3px solid #ef4444;
      }
      .sig-hist-card.sig-card-info {
        border-left: 3px solid rgba(59, 130, 246, 0.45);
      }
      .sig-hist-card.sig-card-info.expanded {
        border-left: 3px solid #3b82f6;
      }
      .sig-hist-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        width: 100%;
      }
      .sig-hist-badge-wrap {
        display: flex;
        align-items: center;
        gap: 12px;
      }
      .sig-hist-symbol {
        font-weight: 700;
        font-size: 0.85rem;
        color: #e2e8f0;
      }
      .sig-hist-exchange {
        font-size: 0.65rem;
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 6px;
        text-transform: uppercase;
      }
      .sig-hist-exchange.badge-binance {
        background: rgba(243, 186, 11, 0.12);
        color: #f3ba0b;
        border: 1px solid rgba(243, 186, 11, 0.2);
      }
      .sig-hist-exchange.badge-bybit {
        background: rgba(255, 168, 0, 0.12);
        color: #ffa800;
        border: 1px solid rgba(255, 168, 0, 0.2);
      }
      .sig-hist-exchange.badge-weex {
        background: rgba(34, 197, 94, 0.12);
        color: #22c55e;
        border: 1px solid rgba(34, 197, 94, 0.2);
      }
      .sig-hist-price-wrap {
        display: flex;
        align-items: center;
        gap: 16px;
      }
      .sig-hist-price {
        font-weight: 700;
        font-size: 0.82rem;
        color: #cbd5e1;
        font-family: 'JetBrains Mono', monospace;
      }
      .sig-hist-time {
        font-size: 0.72rem;
        color: #64748b;
      }
      .sig-hist-arrow {
        font-size: 0.65rem;
        color: #64748b;
        transition: transform 0.2s ease;
        display: inline-block;
      }
      .sig-hist-body {
        padding-top: 10px;
        margin-top: 8px;
        border-top: 1px dashed rgba(148, 163, 184, 0.08);
      }
      .sig-hist-indicator {
        font-size: 0.76rem;
        font-weight: 600;
        color: #94a3b8;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .sig-hist-interval {
        font-size: 0.68rem;
        color: #64748b;
        background: rgba(30, 41, 59, 0.6);
        padding: 1px 5px;
        border-radius: 4px;
      }
    `;
    document.head.appendChild(style);
  }

  const now = new Date();
  const realtime = [];
  const history = [];

  signals.forEach(s => {
    let diffMins = 999;
    try {
      const tsStr = s.created_at;
      const d = new Date(tsStr.endsWith('Z') ? tsStr : tsStr + 'Z');
      diffMins = (now - d) / 60000;
    } catch (e) {
      console.error(e);
    }

    if (diffMins <= 5) {
      realtime.push(s);
    } else {
      history.push(s);
    }
  });

  let html = '';

  // Render Real-time Section (Grouped by Symbol)
  html += `
    <div class="sig-section">
      <div class="sig-section-header">
        <span class="sig-pulse-dot"></span>
        <h3 class="sig-section-title sig-title-realtime">⚡ Real-time Signals (≤ 5m)</h3>
        <span class="sig-section-badge sig-badge-realtime">${realtime.length}</span>
      </div>
  `;

  if (realtime.length > 0) {
    // Group realtime signals by symbol and exchange (keep newest signal for each exchange)
    const realtimeGroups = {};
    realtime.forEach(s => {
      const sym = s.symbol.toUpperCase();
      const ex = s.exchange.toLowerCase();
      if (!realtimeGroups[sym]) {
        realtimeGroups[sym] = {};
      }
      if (!realtimeGroups[sym][ex]) {
        realtimeGroups[sym][ex] = s;
      }
    });

    html += `
      <div class="sig-cards-container">
        ${Object.keys(realtimeGroups).map(sym => renderSignalGroupCardHtml(sym, realtimeGroups[sym])).join('')}
      </div>
    `;
  } else {
    html += `
      <div class="sig-realtime-empty">
        No active signals in the last 5 minutes. Monitoring live feed...
      </div>
    `;
  }
  html += `</div>`; // Close sig-section

  // Render History Section
  if (history.length > 0) {
    html += `
      <div class="sig-section">
        <div class="sig-section-header">
          <h3 class="sig-section-title sig-title-history">⏳ Historical Signals (> 5m ago)</h3>
          <span class="sig-section-badge sig-badge-history">${history.length}</span>
        </div>
        <div class="sig-cards-container">
          ${history.map(s => renderHistoricalSignalCardHtml(s)).join('')}
        </div>
      </div>
    `;
  }

  el.innerHTML = html;
}

/* ── Render donut chart ──────────────────────────────────────────── */
/* ── Render Candlestick Chart ────────────────────────────────────── */
async function loadCandleChart(symbol) {
  const canvas = document.getElementById('sigTypeChart');
  if (!canvas) return;

  if (SIG.chart) {
    SIG.chart.destroy();
    SIG.chart = null;
  }

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const wrap = canvas.parentElement;
  const width = wrap ? wrap.clientWidth : 320;
  const height = 180;
  canvas.width = width;
  canvas.height = height;
  canvas.style.width = width + 'px';
  canvas.style.height = height + 'px';

  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = '#64748b';
  ctx.font = '11px Inter, sans-serif';
  ctx.fillText('Loading candles...', 20, height / 2);

  let cleanSym = (symbol || 'BTCUSDT').trim().toUpperCase();
  if (cleanSym.includes(':')) {
    cleanSym = cleanSym.split(':')[1];
  }

  const tfSelect = document.getElementById('sigChartTimeframeSelect');
  const tf = tfSelect ? tfSelect.value : '4h';

  try {
    const res = await fetch(`https://api.binance.com/api/v3/klines?symbol=${cleanSym}&interval=${tf}&limit=24`);
    if (!res.ok) throw new Error('Binance fetch failed');
    const candles = await res.json();

    if (!candles || !candles.length) {
      throw new Error('No candles data');
    }

    drawCandlestickChart(canvas, candles);
    setText('sigChartLabel', `${cleanSym} (${tf.toUpperCase()})`);
  } catch (e) {
    console.error('[Signals] Candle load error:', e);
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = '#ef4444';
    ctx.font = '11px Inter, sans-serif';
    ctx.fillText(`Failed to load candles for ${cleanSym}`, 20, height / 2);
    setText('sigChartLabel', 'Error loading candles');
  }
}

function drawCandlestickChart(canvas, candles) {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const width = canvas.width;
  const height = canvas.height;

  ctx.clearRect(0, 0, width, height);

  const paddingLeft = 12;
  const paddingRight = 60;
  const paddingTop = 20;
  const paddingBottom = 20;

  const chartWidth = width - paddingLeft - paddingRight;
  const chartHeight = height - paddingTop - paddingBottom;

  let minPrice = Infinity;
  let maxPrice = -Infinity;
  candles.forEach(c => {
    const low = parseFloat(c[3]);
    const high = parseFloat(c[2]);
    if (low < minPrice) minPrice = low;
    if (high > maxPrice) maxPrice = high;
  });

  const priceRange = maxPrice - minPrice;
  minPrice -= priceRange * 0.08;
  maxPrice += priceRange * 0.08;
  const finalRange = maxPrice - minPrice || 1;

  ctx.strokeStyle = 'rgba(148, 163, 184, 0.08)';
  ctx.fillStyle = '#64748b';
  ctx.font = '9px "JetBrains Mono", monospace';
  ctx.lineWidth = 1;

  const gridCount = 3;
  for (let i = 0; i <= gridCount; i++) {
    const y = paddingTop + (chartHeight * i) / gridCount;
    const price = maxPrice - (finalRange * i) / gridCount;

    ctx.beginPath();
    ctx.moveTo(paddingLeft, y);
    ctx.lineTo(width - paddingRight, y);
    ctx.stroke();

    ctx.fillText(`$${Math.round(price).toLocaleString()}`, width - paddingRight + 6, y + 3);
  }

  const candleCount = candles.length;
  const spacing = chartWidth / candleCount;
  const candleWidth = spacing * 0.65;

  candles.forEach((c, index) => {
    const open = parseFloat(c[1]);
    const high = parseFloat(c[2]);
    const low = parseFloat(c[3]);
    const close = parseFloat(c[4]);

    const isBullish = close >= open;
    const color = isBullish ? '#22c55e' : '#ef4444';

    const x = paddingLeft + index * spacing + spacing / 2;

    const getY = (val) => {
      return paddingTop + chartHeight * (1 - (val - minPrice) / finalRange);
    };

    const yOpen = getY(open);
    const yClose = getY(close);
    const yHigh = getY(high);
    const yLow = getY(low);

    ctx.strokeStyle = color;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(x, yHigh);
    ctx.lineTo(x, yLow);
    ctx.stroke();

    ctx.fillStyle = color;
    const bodyHeight = Math.abs(yClose - yOpen) || 1.5;
    const bodyY = Math.min(yOpen, yClose);
    ctx.fillRect(x - candleWidth / 2, bodyY, candleWidth, bodyHeight);
  });
}

function renderSignalTypeChart(byType) {
  loadCandleChart(SIG.activeSymbol || 'BTCUSDT');
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

/* ── Load watchlist ──────────────────────────────────────────────── */
async function loadWatchlist() {
  const el = document.getElementById('sigWatchlistList');
  if (!el) return;

  try {
    const res = await apiFetch('/api/watchlist');
    if (!res || !res.symbols) {
      el.innerHTML = '<div class="empty-state p-8" style="grid-column: span 3;"><p>Empty watchlist</p></div>';
      return;
    }
    renderWatchlist(res.symbols);
  } catch (e) {
    console.error('[Signals] Watchlist load error:', e);
    el.innerHTML = '<div class="empty-state p-8" style="grid-column: span 3;"><p>Error loading watchlist</p></div>';
  }
}

/* ── Render watchlist ────────────────────────────────────────────── */
function renderWatchlist(symbols) {
  const el = document.getElementById('sigWatchlistList');
  if (!el) return;

  if (!symbols || !symbols.length) {
    el.innerHTML = '<div class="empty-state p-8" style="grid-column: span 3;"><p>Empty watchlist</p></div>';
  } else {
    el.innerHTML = symbols.map(symbol => `
      <div class="sig-sym-chip" style="position: relative; padding-right: 24px; display: flex; align-items: center; justify-content: center; min-height: 38px;" onclick="filterBySymbol('${symbol}')">
        <span class="sig-sym-name">${escHtml(symbol)}</span>
        <span onclick="removeSigWatchlistSymbol('${symbol}', event)" style="position: absolute; right: 8px; top: 50%; transform: translateY(-50%); font-size: 0.85rem; color: #ef4444; cursor: pointer; font-weight: bold; width: 14px; height: 14px; line-height: 14px; display: inline-block; transition: color 0.15s;" title="Remove from Watchlist" onmouseover="this.style.color='#f87171'" onmouseout="this.style.color='#ef4444'">✕</span>
      </div>
    `).join('');
  }

  // Populate Symbol select dropdown in the chart section
  const symSelect = document.getElementById('sigChartSymbolSelect');
  if (symSelect) {
    const currentVal = symSelect.value || (document.getElementById('sigSymbolFilter')?.value || '').trim().toUpperCase();
    let html = '<option value="">All Symbols</option>';
    if (symbols && symbols.length) {
      symbols.forEach(sym => {
        html += `<option value="${sym}">${sym}</option>`;
      });
    }
    symSelect.innerHTML = html;
    symSelect.value = currentVal;
  }
}

/* ── Add symbol to watchlist ─────────────────────────────────────── */
async function addSigWatchlistSymbol() {
  const inp = document.getElementById('sigNewWatchlistSymbol');
  if (!inp) return;
  const symbol = inp.value.trim().toUpperCase();
  if (!symbol) {
    showToast('Vui lòng nhập symbol', 'error');
    return;
  }

  try {
    const res = await apiFetch('/api/watchlist', {
      method: 'POST',
      body: JSON.stringify({ symbol })
    });
    if (res && (res.added || res.reason === 'already_exists')) {
      inp.value = '';
      showToast(res.added ? `Đã thêm ${symbol} vào watchlist` : `${symbol} đã tồn tại trong watchlist`, 'info');
      await loadWatchlist();
    } else {
      showToast('Không thể thêm symbol', 'error');
    }
  } catch (e) {
    console.error('[Signals] Watchlist add error:', e);
    showToast('Lỗi khi thêm symbol', 'error');
  }
}

/* ── Remove symbol from watchlist ────────────────────────────────── */
async function removeSigWatchlistSymbol(symbol, event) {
  if (event) {
    event.stopPropagation(); // prevent filtering by symbol
    event.preventDefault();
  }

  if (!confirm(`Bạn có chắc chắn muốn xóa ${symbol} khỏi watchlist?`)) {
    return;
  }

  try {
    const res = await apiFetch(`/api/watchlist/${symbol}`, {
      method: 'DELETE'
    });
    if (res && res.removed) {
      showToast(`Đã xóa ${symbol} khỏi watchlist`, 'info');
      await loadWatchlist();
    } else {
      showToast('Không thể xóa symbol', 'error');
    }
  } catch (e) {
    console.error('[Signals] Watchlist delete error:', e);
    showToast('Lỗi khi xóa symbol', 'error');
  }
}

/* ── Sync watchlist from TradingView ─────────────────────────────── */
async function syncSigWatchlist() {
  showToast('Đang đồng bộ từ TradingView...', 'info');
  try {
    const res = await apiFetch('/api/watchlist/sync', {
      method: 'PUT'
    });
    if (res && res.synced) {
      showToast(`Đồng bộ thành công! Đã thêm ${res.added} symbols mới (tổng số: ${res.total})`, 'success');
      await loadWatchlist();
    } else {
      showToast(res ? `Không đồng bộ được: ${res.reason || res.error || 'Unknown error'}` : 'Đồng bộ thất bại', 'error');
    }
  } catch (e) {
    console.error('[Signals] Watchlist sync error:', e);
    showToast('Lỗi khi đồng bộ watchlist', 'error');
  }
}

/* ── Render Direction Mix stats (Long/Short, Prices In/Out) ──────── */
function renderDirectionMix(dirMix, regime) {
  const el = document.getElementById('sigDirectionMix');
  if (!el) return;

  if (!dirMix) {
    el.innerHTML = '<div class="sig-dir-stat-empty">No trend statistics available</div>';
    return;
  }

  const upperRegime = (regime || 'CHOP').toUpperCase();
  
  // Calculate counts to check if there are active signals in the last 5 minutes
  const longEntryCount = dirMix.long?.entry?.count || 0;
  const longExitCount = dirMix.long?.exit?.count || 0;
  const shortEntryCount = dirMix.short?.entry?.count || 0;
  const shortExitCount = dirMix.short?.exit?.count || 0;
  const totalActiveSignals = longEntryCount + longExitCount + shortEntryCount + shortExitCount;

  let useShort = (upperRegime === 'BEAR');

  // Fallback / Auto-detect which direction has active signals if there are any
  const longCnt = longEntryCount + longExitCount;
  const shortCnt = shortEntryCount + shortExitCount;
  if (longCnt > 0 || shortCnt > 0) {
    if (shortCnt > longCnt) {
      useShort = true;
    } else if (longCnt > shortCnt) {
      useShort = false;
    }
  }

  let icon = "—";
  if (totalActiveSignals > 0) {
    if (useShort) {
      icon = "▼";
    } else {
      icon = "▲";
    }
  }

  let title = "Signals";
  if (totalActiveSignals > 0) {
    if (useShort) {
      title = `Short Signals (${icon})`;
    } else {
      title = `Long Signals (${icon})`;
    }
  } else {
    title = `Signals (${icon})`;
  }

  const titleEl = document.getElementById('sigTypeMixTitle');
  if (titleEl) {
    if (totalActiveSignals > 0) {
      if (useShort) {
        titleEl.innerHTML = '📉 Signal Type Mix';
      } else {
        titleEl.innerHTML = '📈 Signal Type Mix';
      }
    } else {
      titleEl.innerHTML = '📊 Signal Type Mix';
    }
  }

  let statusClass = "inactive";
  let statusText = "Waiting";
  let showLong = !useShort;
  let showShort = useShort;

  if (totalActiveSignals > 0) {
    if (useShort) {
      statusClass = "active-bear";
      statusText = "Trend Available";
    } else {
      statusClass = "active";
      statusText = "Trend Available";
    }
  } else {
    if (upperRegime === 'CHOP' || upperRegime === 'SIDEWAY' || upperRegime === 'SIDEWAYS') {
      statusClass = "sideway";
      statusText = "Side Way";
    } else {
      statusClass = "inactive";
      statusText = "Waiting";
    }
  }

  let entryCount = 0;
  let entryPrice = 0;
  let exitCount = 0;
  let exitPrice = 0;

  if (showLong) {
    entryCount = longEntryCount;
    entryPrice = dirMix.long?.entry?.avg_price || 0;
    exitCount = longExitCount;
    exitPrice = dirMix.long?.exit?.avg_price || 0;
  } else if (showShort) {
    entryCount = shortEntryCount;
    entryPrice = dirMix.short?.entry?.avg_price || 0;
    exitCount = shortExitCount;
    exitPrice = dirMix.short?.exit?.avg_price || 0;
  }

  let entryValueHtml = `: ${entryCount} ${entryCount > 0 ? '($' + Number(Math.round(entryPrice)).toLocaleString() + ')' : '(—)'}`;
  if (statusText === 'Side Way') {
    entryValueHtml = `: <span style="color: #64748b; font-style: italic; font-weight: normal;">Not Entry</span>`;
  }

  el.innerHTML = `
    <div class="sig-dir-single-col sig-dir-${showShort ? 'short' : 'long'}">
      <div class="sig-dir-col-header">
        <span class="emoji">${totalActiveSignals > 0 ? (showShort ? '📉' : '📈') : '📊'}</span>
        <span class="title">${title}</span>
        <span class="sig-dir-trend-badge ${statusClass}">${statusText}</span>
      </div>
      <div class="sig-dir-stat">
        <span class="label">Entry / Prices In (<span class="trend-icon icon-${statusClass}">${icon}</span>)</span>
        <span class="value">${entryValueHtml}</span>
      </div>
      <div class="sig-dir-stat">
        <span class="label">Exit / Prices Out (<span class="trend-icon icon-${statusClass}">${icon}</span>)</span>
        <span class="value">: ${exitCount} ${exitCount > 0 ? '($' + Number(Math.round(exitPrice)).toLocaleString() + ')' : '(—)'}</span>
      </div>
    </div>
  `;
}

/* ── Execute real-time signal manual trade order ───────────────── */
async function executeRealtimeSignalTrade(symbol, action, price, exchange, interval, indicatorName, atrValue) {
  const side = action === 'buy' ? 'BUY' : 'SELL';
  
  let sl = '';
  let tp = '';
  if (atrValue && atrValue !== '0') {
    const atr = parseFloat(atrValue);
    const pr = parseFloat(price);
    if (action === 'buy') {
      sl = (pr - atr * 2).toFixed(2);
      tp = (pr + atr * 3).toFixed(2);
    } else {
      sl = (pr + atr * 2).toFixed(2);
      tp = (pr - atr * 3).toFixed(2);
    }
  }

  const confirmMsg = `Bạn có chắc chắn muốn thực hiện lệnh ${side} ${symbol} tại mức giá $${Number(price).toLocaleString()}?\n` +
                     (sl && tp ? `Khuyến nghị:\n- Stop Loss: $${Number(sl).toLocaleString()}\n- Take Profit: $${Number(tp).toLocaleString()}` : '');
  
  if (!confirm(confirmMsg)) return;

  const payload = {
    source: 'dashboard',
    symbol: symbol,
    action: action,
    price: parseFloat(price),
    exchange: exchange || 'binance',
    interval: interval || '1h',
    indicator_name: indicatorName
  };
  if (sl) payload.sl = sl;
  if (tp) payload.tp = tp;

  showToast(`Đang gửi lệnh ${side} ${symbol}...`, 'info');
  try {
    const res = await apiFetch('/webhook', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    if (res && res.received) {
      showToast(`✅ Đã gửi lệnh ${side} ${symbol}! Signal #${res.signal_id}`, 'success');
      setTimeout(() => {
        if (typeof loadTrades === 'function') loadTrades();
        if (typeof loadKPIs === 'function') loadKPIs();
      }, 1500);
    } else {
      showToast('❌ Gửi lệnh thất bại', 'error');
    }
  } catch (e) {
    console.error('[Signals] Trade execution error:', e);
    showToast('Lỗi khi gửi lệnh', 'error');
  }
}

/* ── Toggle historical card expand/collapse ─────────────────────── */
window.toggleHistoricalCard = function(cardId, event) {
  if (event) event.stopPropagation();
  const card = document.getElementById(cardId);
  if (!card) return;
  const body = card.querySelector('.sig-hist-body');
  const arrow = card.querySelector('.sig-hist-arrow');
  if (!body) return;
  
  const isExpanded = body.style.display === 'block';
  if (isExpanded) {
    body.style.display = 'none';
    card.classList.remove('expanded');
    if (arrow) arrow.style.transform = 'rotate(0deg)';
  } else {
    body.style.display = 'block';
    card.classList.add('expanded');
    if (arrow) arrow.style.transform = 'rotate(180deg)';
  }
};

/* ── Chart dropdown controllers ─────────────────────────────────── */
window.onChartSymbolChange = function() {
  const select = document.getElementById('sigChartSymbolSelect');
  if (!select) return;
  const sym = select.value;
  const inp = document.getElementById('sigSymbolFilter');
  if (inp) {
    inp.value = sym;
  }
  SIG.page = 0;
  loadSignals();
};

window.onChartIndicatorChange = function() {
  const select = document.getElementById('sigChartIndicatorSelect');
  if (!select) return;
  const ind = select.value;
  const inp = document.getElementById('sigNameFilter');
  if (inp) {
    inp.value = ind;
  }
  SIG.page = 0;
  loadSignals();
};

window.onChartTimeframeChange = function() {
  loadCandleChart(SIG.activeSymbol || 'BTCUSDT');
};
