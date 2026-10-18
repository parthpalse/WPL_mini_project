/**
 * BankEase Dashboard — Chart.js initializations and AI explanation fetch.
 * Depends on: formatters.js (loaded before this file)
 */

document.addEventListener('DOMContentLoaded', function () {
    applyIndianCurrencyFormatting();
    const raw = document.getElementById('engine-data');
    if (!raw) return;
    const data = JSON.parse(raw.textContent);

    initWaterfall(data);
    initAllocation(data);
    initProjection(data.monthly_surplus, 'future');
    fetchAIExplanation(data);
});

// ─── Waterfall Chart ─────────────────────────────────────────────────────────
function initWaterfall(data) {
    const ctx = document.getElementById('waterfallChart');
    if (!ctx) return;

    const gross    = data.gross_monthly_income || data.net_monthly_income || 0;
    const net      = data.net_monthly_income || 0;
    const tax      = data.tax_monthly || Math.max(0, gross - net);
    const expenses = data.total_monthly_expenses || 0;
    const debt     = data.monthly_debt_payments || 0;
    const ef       = data.emergency_fund_monthly || 0;
    const buffer   = data.safety_buffer_monthly || 0;
    const investable = data.monthly_surplus || 0;

    let cursor = (gross > net && tax > 0) ? gross : net;
    const startVal = cursor;
    const startLabel = (gross > net && tax > 0) ? 'Gross Income' : 'Net In-Hand';
    const makeDown = v => { const s = cursor; cursor -= v; return [Math.max(0, cursor), s]; };

    const bars = [
        { label: startLabel, value: [0, startVal], color: '#0e9f6e' },
    ];
    if (gross > net && tax > 0) {
        bars.push({ label: 'Tax Outgo', value: makeDown(tax), color: '#e02424' });
    }
    if (expenses > 0) {
        bars.push({ label: 'Living Expenses', value: makeDown(expenses), color: '#e74c3c' });
    }
    if (debt > 0) {
        bars.push({ label: 'Debt Payments', value: makeDown(debt), color: '#dc2626' });
    }
    if (ef > 0) {
        bars.push({ label: 'Emergency Fund', value: makeDown(ef), color: '#f59e0b' });
    }
    if (buffer > 0) {
        bars.push({ label: 'Safety Buffer', value: makeDown(buffer), color: '#8b5cf6' });
    }
    bars.push({ label: 'Investable', value: [0, Math.max(0, investable)], color: '#1a56db' });

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: bars.map(b => b.label),
            datasets: [{
                data: bars.map(b => b.value),
                backgroundColor: bars.map(b => b.color + 'cc'),
                borderColor: bars.map(b => b.color),
                borderWidth: 1,
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const [lo, hi] = ctx.raw;
                            return ' ' + formatIN(hi - lo);
                        }
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: true,
                    ticks: { callback: v => formatINShort(v) },
                    grid: { color: '#f3f4f6' }
                }
            }
        }
    });
}

// ─── Allocation Donut Chart ───────────────────────────────────────────────────
function initAllocation(data) {
    const ctx = document.getElementById('allocationChart');
    if (!ctx || !data.allocations) return;

    const strat = data.allocations.balanced || data.allocations.safe || data.allocations.growth || {};
    const labels = [], amounts = [], colors = [];
    const palette = ['#1a56db','#0e9f6e','#f59e0b','#8b5cf6','#e02424','#06b6d4','#ec4899'];
    let ci = 0;
    for (const [product, detail] of Object.entries(strat)) {
        const amt = detail.amount || 0;
        if (amt > 0) {
            labels.push(product.replace(/_/g,' ').replace(/\b\w/g, l => l.toUpperCase()));
            amounts.push(amt);
            colors.push(palette[ci++ % palette.length]);
        }
    }
    if (!amounts.length) return;

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{ data: amounts, backgroundColor: colors, borderWidth: 2, borderColor: '#fff', hoverOffset: 6 }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { position: 'bottom', labels: { font: { size: 11 }, boxWidth: 12 } },
                tooltip: {
                    callbacks: {
                        label: ctx => ' ' + ctx.label + ': ' + formatIN(ctx.raw)
                    }
                }
            }
        }
    });
}

// ─── Projection Chart ─────────────────────────────────────────────────────────
function initProjection(monthly, mode) {
    const ctx = document.getElementById('projectionChart');
    if (!ctx) return;

    const years = [1, 2, 3, 5, 7, 10];
    const INFLATION = 0.06;

    function sipFV(monthly, rateAnnual, years) {
        const r = rateAnnual / 12;
        const n = years * 12;
        if (r === 0) return monthly * n;
        return monthly * ((Math.pow(1 + r, n) - 1) / r) * (1 + r);
    }

    const rates = { conservative: 0.06, base: 0.10, optimistic: 0.14 };
    const datasets = Object.entries(rates).map(([label, rate], i) => {
        const borderColors = ['#8b5cf6','#1a56db','#0e9f6e'];
        const vals = years.map(y => {
            let fv = sipFV(Math.max(0, monthly), rate, y);
            if (mode === 'today') fv = fv / Math.pow(1 + INFLATION, y);
            return Math.round(fv / 1000) * 1000;
        });
        return {
            label: label.charAt(0).toUpperCase() + label.slice(1) + ' (' + (rate*100).toFixed(0) + '% p.a.)',
            data: vals,
            borderColor: borderColors[i],
            backgroundColor: borderColors[i] + '15',
            fill: i === 1,
            tension: 0.35,
            borderWidth: i === 1 ? 2.5 : 1.5,
            borderDash: i === 0 ? [5,3] : i === 2 ? [3,2] : [],
            pointRadius: 4,
        };
    });

    window.projChart = new Chart(ctx, {
        type: 'line',
        data: { labels: years.map(y => 'Year ' + y), datasets },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'top', labels: { font: { size: 11 }, boxWidth: 14 } },
                tooltip: {
                    callbacks: {
                        label: ctx => ' ' + ctx.dataset.label.split('(')[0].trim() + ': ' + formatIN(ctx.raw)
                    }
                }
            },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: true,
                    ticks: { callback: v => formatINShort(v) },
                    grid: { color: '#f3f4f6' }
                }
            }
        }
    });
}

// ─── AI Explanation Fetch ─────────────────────────────────────────────────────
function fetchAIExplanation(engineData) {
    const panel = document.getElementById('ai-panel');
    const content = document.getElementById('ai-content');
    const sourceLabel = document.getElementById('ai-source-label');
    if (!panel) return;

    fetch('/dashboard/explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify(engineData)
    })
    .then(r => r.json())
    .then(resp => {
        const ex = resp.explanation || resp;
        const source = ex.source === 'ai' ? '🤖 AI-generated explanation' : '📋 Standard explanation';
        sourceLabel.innerHTML = `<span class="badge ${ex.source === 'ai' ? 'badge-blue' : 'badge-yellow'}">${source}</span>`;
        if (ex.note) sourceLabel.innerHTML += ` <span style="font-size:0.75rem; color:var(--text-muted);">(${ex.note})</span>`;

        const actions = (ex.three_key_actions || []).map(a => `<li>${a}</li>`).join('');
        content.innerHTML = `
            <h4>${ex.headline || ''}</h4>
            <p>${ex.what_this_means || ''}</p>
            ${actions ? `<strong style="font-size:0.85rem;">Key Actions:</strong><ul style="margin:6px 0 10px; padding-left:18px; font-size:0.9rem;">${actions}</ul>` : ''}
            ${ex.watch_outs ? `<div class="watch-out">⚠️ ${ex.watch_outs}</div>` : ''}
        `;
    })
    .catch(() => {
        sourceLabel.innerHTML = '<span class="badge badge-yellow">📋 Standard explanation</span>';
        content.innerHTML = '<p style="color:var(--text-muted);">AI explanation unavailable. Ensure Ollama is running (<code>ollama serve</code>).</p>';
    });
}

function getCsrfToken() {
    // Try to get CSRF token from meta tag or hidden field
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) return meta.getAttribute('content');
    const field = document.querySelector('input[name="csrf_token"]');
    if (field) return field.value;
    return '';
}

// ─── Explain Single Number / Calculation Step ───────────────────────────────
function explainTraceStep(label, result, formula, note) {
    const modal = document.getElementById('explainModal');
    const loading = document.getElementById('explainModalLoading');
    const content = document.getElementById('explainModalContent');
    if (!modal) return;

    modal.classList.add('active');
    loading.style.display = 'block';
    content.style.display = 'none';

    document.getElementById('explainStepLabel').textContent = label;
    document.getElementById('explainStepResult').textContent = result;
    document.getElementById('explainStepFormula').textContent = formula ? `Formula: ${formula}` : '';
    document.getElementById('explainStepText').textContent = note || '';

    fetch('/dashboard/explain_step', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ label, formatted_result: result, formula, note })
    })
    .then(r => r.json())
    .then(resp => {
        loading.style.display = 'none';
        content.style.display = 'block';
        document.getElementById('explainStepText').textContent = resp.explanation || note || `${label} calculated as ${result}.`;
        const badgeEl = document.getElementById('explainStepBadge');
        if (resp.source === 'ai') {
            badgeEl.innerHTML = '<span class="badge badge-blue">🤖 Verified AI Explanation</span>';
        } else {
            badgeEl.innerHTML = '<span class="badge badge-yellow">📋 Deterministic Engine Rule</span>';
        }
    })
    .catch(() => {
        loading.style.display = 'none';
        content.style.display = 'block';
        document.getElementById('explainStepText').textContent = note || `${label}: ${result}. Calculated with formula '${formula}'.`;
        document.getElementById('explainStepBadge').innerHTML = '<span class="badge badge-yellow">📋 Engine Trace</span>';
    });
}

function closeExplainModal() {
    const modal = document.getElementById('explainModal');
    if (modal) modal.classList.remove('active');
}

// ─── Save Scenario Modal ───────────────────────────────────────────────────
function openSaveScenarioModal() {
    const modal = document.getElementById('saveScenarioModal');
    const status = document.getElementById('saveScenarioStatus');
    if (!modal) return;
    if (status) status.textContent = '';
    modal.classList.add('active');
}

function closeSaveScenarioModal() {
    const modal = document.getElementById('saveScenarioModal');
    if (modal) modal.classList.remove('active');
}

function confirmSaveScenario() {
    const input = document.getElementById('scenarioNameInput');
    const status = document.getElementById('saveScenarioStatus');
    const name = input ? input.value.trim() : '';
    if (!name) return;

    fetch('/dashboard/save_scenario', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ name })
    })
    .then(r => r.json())
    .then(resp => {
        if (resp.success) {
            status.innerHTML = `<span style="color:var(--success);">✅ Saved as "${resp.name}" (${resp.count} saved plans)</span>`;
            setTimeout(() => {
                closeSaveScenarioModal();
            }, 1200);
        } else {
            status.innerHTML = `<span style="color:var(--danger);">${resp.error || 'Failed to save.'}</span>`;
        }
    })
    .catch(() => {
        status.innerHTML = `<span style="color:var(--danger);">Network error while saving scenario.</span>`;
    });
}

// ─── Compare Scenarios Modal ───────────────────────────────────────────────
function openCompareModal() {
    const modal = document.getElementById('compareModal');
    if (!modal) return;
    modal.classList.add('active');

    // Populate scenario dropdown
    const select = document.getElementById('compareSelect');
    fetch('/dashboard/list_scenarios')
        .then(r => r.json())
        .then(resp => {
            select.innerHTML = '<option value="">Optimized Expenses (-20%)</option>';
            (resp.scenarios || []).forEach(name => {
                const opt = document.createElement('option');
                opt.value = name;
                opt.textContent = name;
                select.appendChild(opt);
            });
            runComparison(select.value);
        })
        .catch(() => {
            runComparison('');
        });
}

function closeCompareModal() {
    const modal = document.getElementById('compareModal');
    if (modal) modal.classList.remove('active');
}

function runComparison(targetName) {
    const loading = document.getElementById('compareLoading');
    const content = document.getElementById('compareContent');
    const tbody = document.getElementById('compareTableBody');
    const headerB = document.getElementById('compHeaderB');

    loading.style.display = 'block';
    content.style.display = 'none';

    fetch('/dashboard/compare_api', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ target_scenario_name: targetName })
    })
    .then(r => r.json())
    .then(resp => {
        loading.style.display = 'none';
        content.style.display = 'block';
        headerB.textContent = resp.name_b || 'Comparison Plan';

        tbody.innerHTML = '';
        (resp.items || []).forEach(item => {
            const tr = document.createElement('tr');
            let deltaHtml = '';
            if (item.delta > 0) {
                deltaHtml = `<span class="delta-tag delta-pos">+${formatIN(item.delta)}</span>`;
            } else if (item.delta < 0) {
                deltaHtml = `<span class="delta-tag delta-neg">-${formatIN(Math.abs(item.delta))}</span>`;
            } else {
                deltaHtml = `<span class="delta-tag delta-zero">—</span>`;
            }

            tr.innerHTML = `
                <td><strong>${item.label}</strong></td>
                <td>${formatIN(item.val_a)}</td>
                <td style="font-weight:600;">${formatIN(item.val_b)}</td>
                <td>${deltaHtml}</td>
            `;
            tbody.appendChild(tr);
        });
    })
    .catch(() => {
        loading.innerHTML = '<p style="color:var(--danger);">Failed to calculate scenario comparison.</p>';
    });
}

// Set print date
document.addEventListener('DOMContentLoaded', function () {
    const printDate = document.getElementById('print-date');
    if (printDate) {
        const now = new Date();
        printDate.textContent = now.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
    }
});

