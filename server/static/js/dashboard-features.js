// ═══ INDICATORS TAB — USE /api/scan/trigger ═══
let indVersion = 'v1';
function setIndVersion(v) {
  indVersion = v;
  const p1 = document.getElementById('pill-v1');
  const p2 = document.getElementById('pill-v2');
  if (p1) p1.className = `vpill ${v === 'v1' ? 'active' : ''}`;
  if (p2) p2.className = `vpill ${v === 'v2' ? 'active' : ''}`;
  const g1 = document.getElementById('pine-v1-group');
  const g2 = document.getElementById('pine-v2-group');
  if (g1) g1.style.display = v === 'v1' ? 'block' : 'none';
  if (g2) g2.style.display = v === 'v2' ? 'block' : 'none';
}

let lastScanResults = [];

async function loadIndicators() {
  const sym = document.getElementById('indSymbolSelect')?.value || '';
  if (!sym || lastScanResults.length === 0) { renderEmptyIndicators(); return; }
  const r = lastScanResults.find(x => x.symbol === sym);
  if (!r) { renderEmptyIndicators(); return; }
  renderScore(r.trend_template_score || 0);
  renderMAs(r);
  renderVCP(r);
  renderRS(r);
  renderConditions(r);
}

function renderEmptyIndicators() {
  const el = id => document.getElementById(id);
  if (el('scoreNum')) el('scoreNum').textContent = '—';
  if (el('scoreLabel')) { el('scoreLabel').textContent = 'Run scan first'; el('scoreLabel').className = 'score-label'; }
  if (el('ringFill')) el('ringFill').setAttribute('stroke-dasharray', '0 314');
  if (el('maList')) el('maList').innerHTML = '<p class="muted-label">Run Scan → then view indicators</p>';
  if (el('vcpContent')) el('vcpContent').innerHTML = '<p class="muted-label">No VCP data</p>';
  if (el('rsContent')) el('rsContent').innerHTML = '<p class="muted-label">No RS data</p>';
  if (el('condGrid')) el('condGrid').innerHTML = '<p class="muted-label">No data available</p>';
}

function renderScore(score) {
  const el = document.getElementById('scoreNum');
  const label = document.getElementById('scoreLabel');
  const ring = document.getElementById('ringFill');
  if (!el) return;
  el.textContent = score;
  const pct = (score / 8) * 314;
  if (ring) ring.setAttribute('stroke-dasharray', `${pct} 314`);
  if (label) {
    if (score >= 7) { label.textContent = 'STRONG TREND'; label.className = 'score-label pass'; if (ring) ring.style.stroke = 'var(--buy)'; }
    else if (score >= 5) { label.textContent = 'MODERATE'; label.className = 'score-label warn'; if (ring) ring.style.stroke = 'var(--warn)'; }
    else { label.textContent = 'WEAK'; label.className = 'score-label fail'; if (ring) ring.style.stroke = 'var(--sell)'; }
  }
}

function renderMAs(r) {
  const el = document.getElementById('maList');
  if (!el) return;
  const chgColor = (r.change_pct || 0) >= 0 ? 'var(--buy)' : 'var(--sell)';
  el.innerHTML = `
    <div class="ma-row"><span class="ma-name">Price</span><span class="ma-val" style="font-family:var(--mono)">${r.price || '—'}</span></div>
    <div class="ma-row"><span class="ma-name">Change</span><span class="ma-val" style="color:${chgColor}">${(r.change_pct || 0).toFixed(2)}%</span></div>
    <div class="ma-row"><span class="ma-name">Stage</span><span class="ma-val">${r.trend_template_stage || '—'}</span></div>
    <div class="ma-row"><span class="ma-name">Score</span><span class="ma-val">${r.trend_template_score}/8</span></div>
    <div class="ma-row"><span class="ma-name">Vol Ratio</span><span class="ma-val">${r.volume_ratio || '—'}x</span></div>
  `;
}

function renderVCP(r) {
  const el = document.getElementById('vcpContent');
  if (!el) return;
  el.innerHTML = `
    <div style="text-align:center;margin:10px 0">
      <div style="font-size:2.5rem;margin-bottom:8px">${r.vcp_detected ? '🔺' : '⬜'}</div>
      <div style="font-weight:700;color:${r.vcp_detected ? 'var(--buy)' : 'var(--text-muted)'}">${r.vcp_detected ? 'VCP DETECTED!' : 'No VCP'}</div>
      <div style="font-size:0.78rem;color:var(--text-muted);margin-top:6px">${r.vcp_note || ''}</div>
      <div style="margin-top:8px;font-size:0.8rem">
        <span>Range: ${r.range_ratio || '—'}</span> · <span>Pivot: ${r.pivot_level || '—'}</span>
      </div>
    </div>`;
}

function renderRS(r) {
  const el = document.getElementById('rsContent');
  if (!el) return;
  el.innerHTML = `
    <div style="text-align:center;margin:10px 0">
      <div style="font-size:2rem;margin-bottom:8px">💪</div>
      <div style="font-size:0.85rem;color:var(--text-sub)">Volume Ratio</div>
      <div style="font-size:1.5rem;font-weight:700;font-family:var(--mono);margin-top:4px">${r.volume_ratio || '—'}x</div>
      <div style="font-size:0.78rem;color:var(--text-muted);margin-top:6px">${r.vol_breakout ? '🚀 Volume Breakout!' : 'Normal volume'}</div>
    </div>`;
}

function renderConditions(r) {
  const el = document.getElementById('condGrid');
  if (!el) return;
  const criteria = r.trend_template_criteria || {};
  const labels = ['Giá > SMA 150 & 200', 'SMA 150 > SMA 200', 'SMA 200 dốc lên',
    'SMA 50 > SMA 150 & 200', 'Giá > SMA 50', 'Giá cách đáy 52W > 30%',
    'Giá cách đỉnh 52W < 25%', 'RS > Benchmark'];
  const keys = Object.keys(criteria);
  if (keys.length === 0) {
    el.innerHTML = labels.map((l, i) => `<div class="cond-item"><span class="cond-icon">⬜</span><span>${i + 1}. ${l}</span></div>`).join('');
    return;
  }
  el.innerHTML = keys.map((k, i) => {
    const pass = criteria[k];
    return `<div class="cond-item ${pass ? 'pass' : 'fail'}"><span class="cond-icon">${pass ? '✅' : '❌'}</span><span>${i + 1}. ${labels[i] || k}</span></div>`;
  }).join('');
}

// ═══ NOTIFICATIONS — BUILD FROM SIGNALS + TRADES ═══
let notifications = [];
async function loadNotifications() {
  const data = await apiFetch('/trades?limit=50');
  if (!data || !data.trades) return;
  notifications = data.trades.map(t => ({
    type: t.signal_action === 'alert' ? 'WEBHOOK' : 'TRADE',
    title: `${(t.side || '').toUpperCase()} ${t.symbol || ''}`,
    msg: `Price: ${t.executed_price || '—'} | Qty: ${t.executed_qty || t.requested_qty || '—'} | Status: ${(t.status || '—').toUpperCase()}`,
    time: t.created_at,
    score: t.combined_score
  }));
  renderNotifications(notifications);
  const badge = document.getElementById('notifBadge');
  if (badge) badge.textContent = notifications.length;
}

function filterNotifs() {
  const f = document.getElementById('notifFilter')?.value || 'all';
  if (f === 'all') renderNotifications(notifications);
  else renderNotifications(notifications.filter(n => n.type === f));
}

function renderNotifications(list) {
  const el = document.getElementById('notifList');
  if (!el) return;
  if (!list.length) { el.innerHTML = '<div class="empty-state"><div class="icon">🔔</div><h3>Không có thông báo</h3></div>'; return; }
  el.innerHTML = list.map(n => {
    const icons = { WEBHOOK: '📡', TRADE: '💰', VISION: '👁', BRIEF: '🌅' };
    const tags = { WEBHOOK: 'tag-webhook', TRADE: 'tag-trade', VISION: 'tag-vision', BRIEF: 'tag-brief' };
    return `<div class="notif-item">
      <div class="notif-icon">${icons[n.type] || '📋'}</div>
      <div class="notif-body">
        <div class="notif-title">${n.title} <span class="notif-tag ${tags[n.type] || ''}">${n.type}</span></div>
        <div class="notif-msg">${n.msg}</div>
      </div>
      <div class="notif-time">${n.time || '—'}</div>
    </div>`;
  }).join('');
}

function clearNotifs() {
  notifications = [];
  renderNotifications([]);
  const badge = document.getElementById('notifBadge');
  if (badge) badge.textContent = '0';
}

// ═══ VISION CAPTURE — USE /api/mcp/status + /api/vision/analyze ═══
async function triggerVisionCapture() {
  showToast('👁 Checking TradingView CDP...', 'info');
  const status = await apiFetch('/api/system/status');
  if (!status || !status.mcp || !status.mcp.connected) {
    showToast('❌ TradingView CDP chưa kết nối! Chạy launch_tv_msix_cdp.ps1 trước.', 'error');
    return;
  }
  showToast('📸 Đang chụp chart + phân tích AI...', 'info');
  // The actual capture is triggered via webhook with action=alert
  const sym = document.getElementById('analysisSymbol')?.value || 'BTCUSDT';
  const res = await apiFetch('/webhook', {
    method: 'POST',
    body: JSON.stringify({ symbol: sym, action: 'alert', price: '', source: 'dashboard_vision' })
  });
  if (res && res.received) {
    showToast(`✅ Stealth Capture triggered for ${sym}! Check Telegram.`, 'success');
  } else {
    showToast('❌ Vision capture failed', 'error');
  }
}

// ═══ ANALYSIS TAB — USE /api/briefs ═══
async function loadBriefs() {
  const el = document.getElementById('briefContent');
  if (!el) return;
  el.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
  const data = await apiFetch('/api/briefs?limit=1');
  if (!data || !data.briefs || data.briefs.length === 0) {
    el.innerHTML = '<div class="empty-state"><div class="icon">🌅</div><h3>Chưa có brief</h3><p>Click "Morning Brief" để tạo</p></div>';
    return;
  }
  const b = data.briefs[0];
  el.innerHTML = `
    <div style="margin-bottom:12px"><span class="muted-label">Brief #${b.id} — ${b.created_at} — ${b.symbols_scanned} symbols</span></div>
    <div style="white-space:pre-wrap;line-height:1.7;font-size:0.85rem">${b.brief_text || b.ai_analysis || 'No content'}</div>
  `;
}

async function submitRagQuery() {
  const q = document.getElementById('ragQuery')?.value.trim();
  if (!q) { showToast('Nhập câu hỏi!', 'error'); return; }
  const el = document.getElementById('ragResults');
  if (!el) return;
  el.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
  const data = await apiFetch(`/api/rag/query?q=${encodeURIComponent(q)}&n=3`);
  if (!data || !data.chunks || data.chunks.length === 0) {
    el.innerHTML = '<p class="muted-label">Không tìm thấy kết quả hoặc RAG chưa enabled</p>';
    return;
  }
  el.innerHTML = data.chunks.map(c => `
    <div class="rag-chunk">
      <div class="rag-chunk-meta">
        <span class="rag-chunk-topic">${c.topic || c.chapter || '—'}</span>
        <span class="rag-chunk-score">Score: ${((c.relevance || 0) * 100).toFixed(0)}%</span>
      </div>
      <div style="font-size:0.82rem;line-height:1.6">${c.preview || c.content || ''}</div>
    </div>`).join('');
}

// ═══ SCANNER — USE /api/scan/trigger ═══
async function triggerScan() {
  const btn = document.getElementById('scanBtn');
  const status = document.getElementById('scanStatus');
  if (btn) btn.disabled = true;
  if (status) status.textContent = 'Scanning...';
  showToast('🔍 Đang scan watchlist qua MCP/TradingView...', 'info');

  const data = await apiFetch('/api/scan/trigger?timeframe=D', { method: 'POST' });
  if (btn) btn.disabled = false;
  if (!data || !data.results) {
    showToast('❌ Scan thất bại — MCP có thể chưa connected', 'error');
    if (status) status.textContent = 'Scan failed';
    return;
  }

  lastScanResults = data.results;
  if (status) status.textContent = `Scanned ${data.scanned} symbols at ${new Date().toLocaleTimeString('vi-VN')}`;

  // Populate symbol selects
  populateSymbolsFromScan(data.results);

  const tbody = document.getElementById('scanBody');
  if (!tbody) return;
  tbody.innerHTML = data.results.map(r => {
    const chg = r.change_pct || 0;
    const score = r.trend_template_score || 0;
    const err = r.error;
    if (err) return `<tr><td><strong>${r.symbol}</strong></td><td colspan="7" style="color:var(--sell)">${err}</td></tr>`;
    return `<tr>
      <td><strong>${r.symbol}</strong></td>
      <td style="font-family:var(--mono)">${r.price || '—'}</td>
      <td style="color:${chg >= 0 ? 'var(--buy)' : 'var(--sell)'};font-family:var(--mono)">${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%</td>
      <td><div style="display:flex;align-items:center;gap:8px"><span>${score}/8</span>
        <div class="score-bar-wrap"><div class="score-bar" style="width:${(score/8)*100}%"></div></div></div></td>
      <td><span class="badge badge-ok">${r.trend_template_stage || '—'}</span></td>
      <td>${r.vcp_detected ? '<span class="badge badge-buy">🔺 YES</span>' : '<span class="badge badge-fail">No</span>'}</td>
      <td style="font-family:var(--mono)">${r.volume_ratio}x</td>
      <td><button class="qbtn" style="padding:4px 10px;font-size:0.75rem" onclick="quickTradeFromScan('${r.symbol}','${r.price}')">⚡ Trade</button></td>
    </tr>`;
  }).join('');
  showToast(`✅ Scan xong ${data.scanned} symbols!`, 'success');
}

function quickTradeFromScan(symbol, price) {
  document.getElementById('orderSymbol').value = symbol;
  document.getElementById('orderPrice').value = price || '';
  openOrderModal();
}

// ═══ POPULATE SYMBOLS ═══
function populateSymbolsFromScan(results) {
  const symbols = results.map(r => r.symbol).filter(Boolean);
  ['indSymbolSelect', 'analysisSymbol'].forEach(id => {
    const sel = document.getElementById(id);
    if (!sel || symbols.length === 0) return;
    sel.innerHTML = symbols.map(s => `<option value="${s}">${s}</option>`).join('');
  });
}

async function populateSymbols() {
  const data = await apiFetch('/api/watchlist');
  if (!data || !data.symbols || data.symbols.length === 0) return;
  ['indSymbolSelect', 'analysisSymbol'].forEach(id => {
    const sel = document.getElementById(id);
    if (!sel) return;
    sel.innerHTML = data.symbols.map(s => `<option value="${s}">${s}</option>`).join('');
  });
}

async function syncWatchlist() {
  showToast('🔄 Syncing watchlist from TradingView...', 'info');
  const res = await apiFetch('/api/watchlist/sync', { method: 'PUT' });
  if (res) {
    populateSymbols();
    showToast('✅ Watchlist synced!', 'success');
  } else {
    showToast('❌ Sync failed — MCP may be offline', 'error');
  }
}

// Late init
document.addEventListener('DOMContentLoaded', () => {
  setTimeout(populateSymbols, 1500);
  setTimeout(loadNotifications, 2500);
});
