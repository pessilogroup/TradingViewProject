/**
 * Minervini SEPA — Performance Dashboard
 * Sprint 6: Vanilla JS + Chart.js
 */

const API_BASE = '';
let equityChart = null;
let currentPage = 0;
const PAGE_SIZE = 20;
let currentSymbol = '';

// ═══ INIT ═════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
    document.getElementById('symbolFilter').addEventListener('change', (e) => {
        currentSymbol = e.target.value;
        currentPage = 0;
        loadDashboard();
    });
});

async function loadDashboard() {
    await Promise.all([
        loadStats(),
        loadEquityCurve(),
        loadTrades(),
    ]);
}

// ═══ KPI STATS ════════════════════════════════════════
async function loadStats() {
    const grid = document.getElementById('kpiGrid');
    try {
        const params = currentSymbol ? `?symbol=${currentSymbol}` : '';
        const res = await fetch(`${API_BASE}/trades/stats${params}`);
        const s = await res.json();

        grid.innerHTML = `
            <div class="kpi-card">
                <div class="kpi-label">Win Rate</div>
                <div class="kpi-value ${s.win_rate >= 50 ? 'positive' : 'negative'}">${s.win_rate}%</div>
                <div class="kpi-sub">${s.winning_trades}W / ${s.losing_trades}L</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Profit Factor</div>
                <div class="kpi-value ${s.profit_factor >= 1.5 ? 'positive' : s.profit_factor >= 1 ? 'neutral' : 'negative'}">${s.profit_factor === Infinity ? '∞' : s.profit_factor}</div>
                <div class="kpi-sub">${s.total_trades} trades</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Total P&L</div>
                <div class="kpi-value ${s.total_pnl >= 0 ? 'positive' : 'negative'}">$${s.total_pnl >= 0 ? '+' : ''}${s.total_pnl.toLocaleString()}</div>
                <div class="kpi-sub">Cumulative</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Max Drawdown</div>
                <div class="kpi-value negative">${s.max_drawdown === 0 ? '$0' : '$' + s.max_drawdown.toLocaleString()}</div>
                <div class="kpi-sub">Peak to trough</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Best Trade</div>
                <div class="kpi-value positive">$${s.best_trade > 0 ? '+' : ''}${s.best_trade.toLocaleString()}</div>
                <div class="kpi-sub">Avg win: $${s.avg_win}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Worst Trade</div>
                <div class="kpi-value negative">$${s.worst_trade.toLocaleString()}</div>
                <div class="kpi-sub">Avg loss: $${s.avg_loss}</div>
            </div>
        `;
    } catch (e) {
        grid.innerHTML = `<div class="empty-state"><div class="icon">📊</div><h3>No Data Yet</h3><p>Start trading to see your performance metrics.</p></div>`;
    }
}

// ═══ EQUITY CURVE ═════════════════════════════════════
async function loadEquityCurve() {
    const container = document.getElementById('equityChart');
    try {
        const params = currentSymbol ? `?symbol=${currentSymbol}` : '';
        const res = await fetch(`${API_BASE}/trades/equity${params}`);
        const data = await res.json();

        if (!data.labels || data.labels.length === 0) {
            container.parentElement.innerHTML = `
                <div class="empty-state">
                    <div class="icon">📈</div>
                    <h3>No Equity Data</h3>
                    <p>Complete trades with P&L to see your equity curve.</p>
                </div>`;
            return;
        }

        const labels = data.labels.map(d => {
            const date = new Date(d);
            return date.toLocaleDateString('vi-VN', { month: 'short', day: 'numeric' });
        });

        if (equityChart) equityChart.destroy();

        const ctx = container.getContext('2d');
        const gradient = ctx.createLinearGradient(0, 0, 0, 320);
        const lastPnl = data.cumulative_pnl[data.cumulative_pnl.length - 1];
        if (lastPnl >= 0) {
            gradient.addColorStop(0, 'rgba(16, 185, 129, 0.25)');
            gradient.addColorStop(1, 'rgba(16, 185, 129, 0)');
        } else {
            gradient.addColorStop(0, 'rgba(239, 68, 68, 0.25)');
            gradient.addColorStop(1, 'rgba(239, 68, 68, 0)');
        }

        equityChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Cumulative P&L ($)',
                    data: data.cumulative_pnl,
                    borderColor: lastPnl >= 0 ? '#10b981' : '#ef4444',
                    backgroundColor: gradient,
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.35,
                    pointRadius: data.labels.length > 50 ? 0 : 3,
                    pointHoverRadius: 6,
                    pointBackgroundColor: lastPnl >= 0 ? '#10b981' : '#ef4444',
                    pointBorderColor: '#0a0e17',
                    pointBorderWidth: 2,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(17, 24, 39, 0.95)',
                        borderColor: 'rgba(255,255,255,0.1)',
                        borderWidth: 1,
                        titleFont: { family: 'Inter', size: 12 },
                        bodyFont: { family: 'Inter', size: 13, weight: '600' },
                        padding: 12,
                        cornerRadius: 10,
                        callbacks: {
                            label: (ctx) => `P&L: $${ctx.raw >= 0 ? '+' : ''}${ctx.raw.toLocaleString()}`
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255,255,255,0.03)', drawBorder: false },
                        ticks: { color: '#64748b', font: { size: 11, family: 'Inter' }, maxTicksLimit: 10 },
                    },
                    y: {
                        grid: { color: 'rgba(255,255,255,0.03)', drawBorder: false },
                        ticks: {
                            color: '#64748b',
                            font: { size: 11, family: 'Inter' },
                            callback: (v) => '$' + v.toLocaleString(),
                        },
                    }
                }
            }
        });
    } catch (e) {
        console.error('Equity curve error:', e);
    }
}

// ═══ TRADE HISTORY ════════════════════════════════════
async function loadTrades() {
    const tbody = document.getElementById('tradesBody');
    const pagination = document.getElementById('pagination');

    try {
        const params = new URLSearchParams({
            limit: PAGE_SIZE,
            offset: currentPage * PAGE_SIZE,
        });
        if (currentSymbol) params.set('symbol', currentSymbol);

        const res = await fetch(`${API_BASE}/trades?${params}`);
        const data = await res.json();

        if (!data.trades || data.trades.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="empty-state"><div class="icon">📋</div><h3>No Trades</h3><p>Trade history will appear here.</p></td></tr>`;
            pagination.innerHTML = '';
            return;
        }

        tbody.innerHTML = data.trades.map((t, i) => {
            const date = t.created_at ? new Date(t.created_at).toLocaleString('vi-VN', {
                month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
            }) : '-';
            const side = (t.side || '').toLowerCase();
            const pnl = t.pnl !== null && t.pnl !== undefined ? t.pnl : null;
            const pnlClass = pnl !== null ? (pnl >= 0 ? 'pnl-positive' : 'pnl-negative') : '';
            const pnlText = pnl !== null ? `$${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}` : '-';
            const statusClass = (t.status || '').toLowerCase() === 'filled' ? 'filled' : 'failed';

            return `<tr>
                <td>${currentPage * PAGE_SIZE + i + 1}</td>
                <td>${date}</td>
                <td style="color:var(--text-primary);font-weight:500">${t.symbol || '-'}</td>
                <td><span class="side-badge ${side}">${(t.side || '-').toUpperCase()}</span></td>
                <td>${t.executed_qty || t.requested_qty || '-'}</td>
                <td>${t.executed_price ? '$' + Number(t.executed_price).toLocaleString() : '-'}</td>
                <td class="${pnlClass}">${pnlText}</td>
                <td><span class="status-badge ${statusClass}">${t.status || '-'}</span></td>
            </tr>`;
        }).join('');

        // Pagination
        const totalPages = Math.ceil(data.total / PAGE_SIZE);
        if (totalPages > 1) {
            let btns = `<button class="page-btn" onclick="goPage(0)" ${currentPage === 0 ? 'disabled' : ''}>&laquo;</button>`;
            btns += `<button class="page-btn" onclick="goPage(${currentPage - 1})" ${currentPage === 0 ? 'disabled' : ''}>&lsaquo;</button>`;

            const start = Math.max(0, currentPage - 2);
            const end = Math.min(totalPages, start + 5);
            for (let i = start; i < end; i++) {
                btns += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goPage(${i})">${i + 1}</button>`;
            }

            btns += `<button class="page-btn" onclick="goPage(${currentPage + 1})" ${currentPage >= totalPages - 1 ? 'disabled' : ''}>&rsaquo;</button>`;
            btns += `<button class="page-btn" onclick="goPage(${totalPages - 1})" ${currentPage >= totalPages - 1 ? 'disabled' : ''}>&raquo;</button>`;
            pagination.innerHTML = btns;
        } else {
            pagination.innerHTML = '';
        }

        document.getElementById('tradeCount').textContent = `${data.total} trades`;
    } catch (e) {
        console.error('Trades error:', e);
        tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text-muted)">Error loading trades</td></tr>`;
    }
}

function goPage(page) {
    currentPage = Math.max(0, page);
    loadTrades();
}

// Auto-refresh every 30 seconds
setInterval(loadDashboard, 30000);