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

// ═══ VISION CAPTURE — CAPTURE STUDIO ═══
let _captureRunning = false;

function _setStep(id, state) {
  const el = document.getElementById(id);
  if (!el) return;
  el.className = `cap-step ${state}`;
}

async function runStealthCapture() {
  if (_captureRunning) return;
  _captureRunning = true;

  const sym = document.getElementById('captureSymbol')?.value || 'BTCUSDT';
  const btn = document.getElementById('captureBtn');
  const btnText = document.getElementById('captureBtnText');
  const btnIcon = document.getElementById('captureBtnIcon');
  const progress = document.getElementById('captureProgress');

  // Reset UI
  if (btn) btn.disabled = true;
  if (btnIcon) btnIcon.textContent = '⏳';
  if (btnText) btnText.textContent = 'Đang capture...';
  if (progress) progress.style.display = 'flex';
  ['step-mcp','step-shot','step-crop','step-ai','step-save'].forEach(s => _setStep(s, ''));

  // Step 1: MCP check (simulated — the endpoint does the actual check)
  _setStep('step-mcp', 'active');
  await new Promise(r => setTimeout(r, 300));
  _setStep('step-mcp', 'done');

  // Step 2: Screenshot
  _setStep('step-shot', 'active');

  let result;
  try {
    result = await apiFetch(`/api/vision/capture?symbol=${encodeURIComponent(sym)}`, {
      method: 'POST'
    });
  } catch (e) {
    result = null;
  }

  if (!result || result.status !== 'ok') {
    const err = result?.detail || 'Capture failed — check CDP connection';
    ['step-shot','step-crop','step-ai','step-save'].forEach(s => _setStep(s, ''));
    showToast(`❌ ${err}`, 'error');
    _resetCaptureBtn();
    _captureRunning = false;
    return;
  }

  // Animate remaining steps (server already completed them)
  for (const [step, delay] of [['step-shot',150],['step-crop',200],['step-ai',300],['step-save',150]]) {
    _setStep(step, 'done');
    await new Promise(r => setTimeout(r, delay));
  }

  showToast(`✅ Capture OK — ${sym} | Verdict: ${result.verdict || '—'} | Conf: ${result.confidence}/10`, 'success');

  // Update preview panel
  _updateCapturePreview(result);

  // Reload history + stats
  await Promise.all([loadVisionHistory(), loadCaptureStats(), loadOverviewVision()]);

  _resetCaptureBtn();
  _captureRunning = false;
}

function _resetCaptureBtn() {
  const btn = document.getElementById('captureBtn');
  const btnText = document.getElementById('captureBtnText');
  const btnIcon = document.getElementById('captureBtnIcon');
  if (btn) btn.disabled = false;
  if (btnIcon) btnIcon.textContent = '📸';
  if (btnText) btnText.textContent = 'Capture + Analyze';
}

function _updateCapturePreview(result) {
  const verdictColor = (result.verdict || '').includes('STRONG') ? 'var(--buy)'
    : (result.verdict || '').includes('AVOID') ? 'var(--sell)' : 'var(--warn)';
  const conf = result.confidence || 0;
  const circumference = 113; // 2πr where r=18
  const dashVal = Math.round((conf / 10) * circumference);

  // ── Chart image ──
  const chartImg = document.getElementById('csChartImg');
  const placeholder = document.getElementById('csChartPlaceholder');
  const overlay = document.getElementById('csChartOverlay');
  if (chartImg && result.screenshot_url) {
    chartImg.src = `${result.screenshot_url}?t=${Date.now()}`;
    chartImg.style.display = 'block';
    if (placeholder) placeholder.style.display = 'none';
    if (overlay) {
      overlay.style.display = 'block';
      const sym = document.getElementById('csOverlaySym');
      const time = document.getElementById('csOverlayTime');
      if (sym) sym.textContent = result.symbol || '—';
      if (time) time.textContent = new Date().toLocaleTimeString('vi-VN', {hour:'2-digit',minute:'2-digit'});
    }
  }

  // ── Verdict card ──
  const card = document.getElementById('csVerdictCard');
  if (card) {
    card.style.display = 'block';
    const s = document.getElementById('csVerdictSym'); if (s) s.textContent = result.symbol || '—';
    const v = document.getElementById('csVerdictVal');
    if (v) { v.textContent = result.verdict || '—'; v.style.color = verdictColor; }
    const num = document.getElementById('csConfNum');
    if (num) { num.textContent = `${conf}/10`; }
    const circle = document.getElementById('csConfCircle');
    if (circle) circle.setAttribute('stroke-dasharray', `${dashVal} ${circumference}`);
    const confColor = conf >= 7 ? 'var(--buy)' : conf >= 5 ? 'var(--accent2)' : 'var(--sell)';
    if (circle) circle.style.stroke = confColor;
    if (num) num.style.color = confColor;

    // Patterns
    const pats = document.getElementById('csPatterns');
    if (pats) pats.innerHTML = (result.patterns || [])
      .map(p => `<span class="pine-chip" style="font-size:0.7rem;padding:2px 8px">${p}</span>`).join('');

    // Analysis text
    const txt = document.getElementById('csAnalysisText');
    if (txt) txt.textContent = result.ai_analysis || '—';
  }
}

// Legacy compat — keep for Overview quick action button
async function triggerVisionCapture() {
  switchTab('analysis');
  setTimeout(runStealthCapture, 200);
}


// ── Load Capture Stats ──
async function loadCaptureStats() {
  const data = await apiFetch('/api/vision/stats');
  if (!data) return;
  const el = id => document.getElementById(id);
  if (el('cstat-total'))   el('cstat-total').textContent   = data.total_captures ?? '—';
  if (el('cstat-stealth')) el('cstat-stealth').textContent = data.stealth_count ?? '—';
  if (el('cstat-conf'))    el('cstat-conf').textContent    = data.avg_confidence ? `${data.avg_confidence}/10` : '—';
  if (el('cstat-last'))    el('cstat-last').textContent    = data.last_capture ? (data.last_capture || '').slice(11, 16) : '—';
}

// ── Img Zoom ──
function openImgZoom(src) {
  const modal = document.getElementById('imgZoomModal');
  const img   = document.getElementById('imgZoomEl');
  if (!modal || !img) return;
  img.src = src;
  modal.style.display = 'flex';
}
function closeImgZoom() {
  const modal = document.getElementById('imgZoomModal');
  if (modal) modal.style.display = 'none';
}


// ═══ ANALYSIS TAB — USE /api/vision/history + /api/briefs ═══
async function loadBriefs() {
  const el = document.getElementById('briefContent');
  if (!el) return;
  el.innerHTML = '<div class="loading"><div class="spinner"></div></div>';
  await Promise.all([loadVisionHistory(), loadLatestBriefText()]);
}

async function loadLatestBriefText() {
  const el = document.getElementById('briefContent');
  if (!el) return;
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

async function loadVisionHistory() {
  const container = document.getElementById('visionHistory');
  if (!container) return;
  container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

  const filterVal = document.getElementById('captureFilter')?.value || 'all';
  const data = await apiFetch('/api/vision/history?limit=20');
  if (!data || !data.items || data.items.length === 0) {
    container.innerHTML = '<div class="empty-state" style="padding:30px 16px"><div class="icon">👁</div><h3>Chưa có phân tích</h3><p>Nhấn Capture + Analyze</p></div>';
    return;
  }

  let items = data.items;
  if (filterVal === 'stealth') items = items.filter(v => v.source === 'stealth');
  else if (filterVal === 'brief') items = items.filter(v => v.source !== 'stealth');

  if (items.length === 0) {
    container.innerHTML = `<div class="empty-state" style="padding:30px 16px"><div class="icon">🔍</div><h3>Không có kết quả</h3><p>Filter: ${filterVal}</p></div>`;
    return;
  }

  // Auto-load latest into canvas if canvas is empty
  if (document.getElementById('csChartImg')?.style.display === 'none' && items[0]) {
    _loadInCanvas(items[0]);
  }

  container.innerHTML = items.map((v, idx) => {
    const srcBadge = v.source === 'stealth'
      ? '<span class="notif-tag tag-webhook" style="font-size:0.62rem;padding:1px 5px">S</span>'
      : '<span class="notif-tag tag-brief" style="font-size:0.62rem;padding:1px 5px">B</span>';
    const conf = v.confidence || 0;
    const confColor = conf >= 7 ? 'var(--buy)' : conf >= 5 ? 'var(--accent2)' : 'var(--sell)';
    const verdictColor = (v.verdict || '').includes('STRONG') ? 'var(--buy)'
      : (v.verdict || '').includes('AVOID') ? 'var(--sell)' : 'var(--warn)';
    const thumbUrl = v.has_screenshot ? `${v.screenshot_url}?t=${Date.now()}` : null;

    return `<div class="cs-hist-card" onclick="_loadInCanvas(${JSON.stringify(v).replace(/"/g, '&quot;')})">
      <div class="cs-hist-thumb">
        ${thumbUrl
          ? `<img src="${thumbUrl}" alt="${v.symbol}" onerror="this.parentElement.innerHTML='📷'">`
          : '📷'}
      </div>
      <div class="cs-hist-body">
        <div style="display:flex;align-items:center;gap:6px">
          <span class="cs-hist-sym">${v.symbol || '—'}</span>
          ${srcBadge}
        </div>
        <div class="cs-hist-meta">
          <span class="cs-hist-verdict" style="color:${verdictColor}">${(v.verdict||'—').substring(0,28)}</span>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <span class="cs-hist-conf" style="color:${confColor}">👁 ${conf}/10</span>
          <span class="cs-hist-time">${(v.created_at||'').slice(5,16)}</span>
        </div>
      </div>
    </div>`;
  }).join('');
}

function _loadInCanvas(v) {
  if (!v) return;
  const conf = v.confidence || 0;
  const circumference = 113;
  const dashVal = Math.round((conf / 10) * circumference);
  const verdictColor = (v.verdict || '').includes('STRONG') ? 'var(--buy)'
    : (v.verdict || '').includes('AVOID') ? 'var(--sell)' : 'var(--warn)';
  const confColor = conf >= 7 ? 'var(--buy)' : conf >= 5 ? 'var(--accent2)' : 'var(--sell)';

  // Chart image
  const chartImg = document.getElementById('csChartImg');
  const placeholder = document.getElementById('csChartPlaceholder');
  const overlay = document.getElementById('csChartOverlay');
  if (chartImg && v.has_screenshot && v.screenshot_url) {
    chartImg.src = `${v.screenshot_url}?t=${Date.now()}`;
    chartImg.style.display = 'block';
    if (placeholder) placeholder.style.display = 'none';
    if (overlay) {
      overlay.style.display = 'block';
      const sym = document.getElementById('csOverlaySym');
      const time = document.getElementById('csOverlayTime');
      if (sym) sym.textContent = v.symbol || '—';
      if (time) time.textContent = (v.created_at || '').slice(5, 16);
    }
  }
  // Verdict card
  const card = document.getElementById('csVerdictCard');
  if (card) {
    card.style.display = 'block';
    const s = document.getElementById('csVerdictSym'); if (s) s.textContent = v.symbol || '—';
    const vv = document.getElementById('csVerdictVal');
    if (vv) { vv.textContent = v.verdict || '—'; vv.style.color = verdictColor; }
    const num = document.getElementById('csConfNum'); if (num) { num.textContent = `${conf}/10`; num.style.color = confColor; }
    const circle = document.getElementById('csConfCircle');
    if (circle) { circle.setAttribute('stroke-dasharray', `${dashVal} ${circumference}`); circle.style.stroke = confColor; }
    const pats = document.getElementById('csPatterns');
    if (pats) pats.innerHTML = (v.patterns || [])
      .map(p => `<span class="pine-chip" style="font-size:0.7rem;padding:2px 8px">${p}</span>`).join('');
    const txt = document.getElementById('csAnalysisText');
    if (txt) txt.textContent = v.ai_analysis || '—';
  }
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
  setTimeout(loadOverviewWidgets, 1000);
  setTimeout(loadCaptureStats, 3000);
});


// ═══ OVERVIEW WIDGETS ═══

async function loadOverviewWidgets() {
  await Promise.all([
    loadOverviewSignals(),
    loadOverviewVision(),
    loadOverviewHealth(),
    startTickerPolling(),
  ]);
}

// ── LIVE TICKER ──
const _tickerSyms = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'];
const _tickerPrev = {};
let _tickerInterval = null;

async function fetchTickerPrices() {
  try {
    const syms = _tickerSyms.map(s => `"${s}"`).join(',');
    const res = await fetch(`https://api.binance.com/api/v3/ticker/24hr?symbols=[${syms}]`);
    if (!res.ok) return;
    const data = await res.json();
    data.forEach(d => {
      const sym = d.symbol;
      const price = parseFloat(d.lastPrice);
      const chgPct = parseFloat(d.priceChangePercent);
      const prev = _tickerPrev[sym];

      const priceEl = document.getElementById(`tp-${sym}`);
      const chgEl   = document.getElementById(`tc-${sym}`);
      const card    = document.getElementById(`ticker-${sym}`);
      if (!priceEl || !card) return;

      // Flash animation on price change
      if (prev !== undefined) {
        card.classList.remove('flash-up', 'flash-down');
        void card.offsetWidth; // reflow
        if (price > prev) card.classList.add('flash-up');
        else if (price < prev) card.classList.add('flash-down');
        setTimeout(() => card.classList.remove('flash-up', 'flash-down'), 600);
      }
      _tickerPrev[sym] = price;

      const fmt = price > 1000 ? price.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})
                               : price.toFixed(4);
      priceEl.textContent = '$' + fmt;

      const sign = chgPct >= 0 ? '+' : '';
      chgEl.textContent = `${sign}${chgPct.toFixed(2)}%`;
      chgEl.className = `ticker-chg ${chgPct >= 0 ? 'up' : 'down'}`;
    });

    // Also update header live price with BTC
    const btc = data.find(d => d.symbol === 'BTCUSDT');
    if (btc) {
      const lp = document.getElementById('livePrice');
      const lc = document.getElementById('liveChange');
      if (lp) lp.textContent = '$' + parseFloat(btc.lastPrice).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
      if (lc) {
        const chg = parseFloat(btc.priceChangePercent);
        lc.textContent = `${chg >= 0 ? '+' : ''}${chg.toFixed(2)}%`;
        lc.style.color = chg >= 0 ? 'var(--buy)' : 'var(--sell)';
      }
    }
  } catch (e) {
    // Binance unreachable — fallback silently
  }
}

function startTickerPolling() {
  fetchTickerPrices();
  if (_tickerInterval) clearInterval(_tickerInterval);
  _tickerInterval = setInterval(fetchTickerPrices, 15000);
}

// ── RECENT SIGNALS (Overview) ──
async function loadOverviewSignals() {
  const el = document.getElementById('overviewSignals');
  if (!el) return;
  const data = await apiFetch('/trades?limit=8');
  if (!data || !data.trades || data.trades.length === 0) {
    el.innerHTML = '<p class="muted-label" style="padding:12px">Chưa có tín hiệu nào</p>';
    return;
  }
  el.innerHTML = data.trades.map(t => {
    const side = (t.side || 'INFO').toUpperCase();
    const dotClass = side === 'BUY' ? 'buy' : side === 'SELL' ? 'sell' : 'info';
    const sym = t.symbol || '—';
    const msg = t.signal_action === 'alert'
      ? `Webhook alert @ ${t.executed_price || '—'}`
      : `${side} @ ${t.executed_price || '—'} | ${(t.status || '').toUpperCase()}`;
    const ts = (t.created_at || '').slice(11, 16);
    return `<div class="signal-row">
      <span class="signal-dot ${dotClass}"></span>
      <span class="signal-sym">${sym}</span>
      <span class="signal-msg">${msg}</span>
      <span class="signal-ts">${ts}</span>
    </div>`;
  }).join('');
}

// ── LAST VISION (Overview) ──
async function loadOverviewVision() {
  const el = document.getElementById('overviewVision');
  if (!el) return;
  const data = await apiFetch('/api/vision/history?limit=1');
  if (!data || !data.items || data.items.length === 0) {
    el.innerHTML = `<div class="empty-state" style="padding:24px">
      <div class="icon">👁</div><h3>No analysis yet</h3><p>Capture a chart to start</p>
    </div>`;
    return;
  }
  const v = data.items[0];
  const verdictClass = (v.verdict || '').includes('STRONG') ? 'verdict-buy'
    : (v.verdict || '').includes('AVOID') ? 'verdict-sell' : 'verdict-hold';
  const conf = v.confidence || 0;
  const confColor = conf >= 7 ? 'var(--buy)' : conf >= 5 ? 'var(--warn)' : 'var(--sell)';

  el.innerHTML = `<div class="vision-mini">
    ${v.has_screenshot
      ? `<img class="vision-mini-img" src="${v.screenshot_url}?t=${Date.now()}" alt="Chart"
             onerror="this.style.display='none'">`
      : ''}
    <div class="vision-mini-meta">
      <span class="vision-mini-sym">${v.symbol || '—'}</span>
      <span class="vision-mini-conf" style="color:${confColor}">Confidence: ${conf}/10</span>
      <span class="vision-mini-verdict ${verdictClass}">${v.verdict || '—'}</span>
      <span style="font-size:0.72rem;color:var(--text-muted)">${(v.created_at || '').slice(0,16)}</span>
    </div>
  </div>`;
}

// ── SYSTEM HEALTH (Overview) ──
async function loadOverviewHealth() {
  const setDot = (id, state) => {
    const el = document.getElementById(id);
    if (el) el.className = `health-dot ${state}`;
  };
  // Server always OK if we got here
  setDot('hd-server', 'ok');

  try {
    const status = await apiFetch('/api/system/status');
    if (status) {
      // Actual schema: mcp.connected, telegram_bot.enabled, rag.enabled
      setDot('hd-mcp',      status.mcp?.connected  ? 'ok' : 'err');
      setDot('hd-telegram', status.telegram_bot?.enabled ? 'ok' : 'warn');
      setDot('hd-binance',  status.rag?.enabled ? 'ok' : 'warn');  // use RAG as 4th indicator
    }
  } catch(e) {
    setDot('hd-mcp', 'err');
    setDot('hd-telegram', 'err');
    setDot('hd-binance', 'err');
  }
}


// ── EQUITY RANGE ──
function setEquityRange(range, btn) {
  document.querySelectorAll('.eq-range-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  // TODO: filter equityChart data by range when trade history supports date filter
  // For now just show toast
  showToast(`Equity range: ${range}`, 'info');
}

