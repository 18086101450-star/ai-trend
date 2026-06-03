const API_BASE = '/api';

let state = {
  keywords: { page: 0, total: 0, items: [] },
  trending: [],
  emerging: [],
  predictions: [],
  allPredictions: [],
  categories: [],
  stats: null,
  scanInProgress: false,
  categoryChart: null,
  timelineChart: null,
  modalChart: null,
};

// ── API Helpers ──

async function api(url, method = 'GET', body = null) {
  try {
    const opts = { method };
    if (body) {
      opts.headers = { 'Content-Type': 'application/json' };
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(`${API_BASE}${url}`, opts);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    console.error(`API error: ${url}`, e);
    return null;
  }
}

// ── View Navigation ──

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const prev = document.querySelector('.view.active');
    const next = document.getElementById(`view-${btn.dataset.view}`);
    if (prev) {
      prev.classList.remove('active');
      requestAnimationFrame(() => {
        next.classList.add('no-anim');
        next.classList.add('active');
        requestAnimationFrame(() => next.classList.remove('no-anim'));
      });
    } else {
      next.classList.add('active');
    }
    // lazy load charts on dashboard
    if (btn.dataset.view === 'dashboard') {
      loadCategoryChart();
      loadTimelineChart();
    }
  });
});

// ── Scan Status ──

function formatDuration(startISO, endISO) {
  if (!startISO || !endISO) return '';
  const s = new Date(startISO);
  const e = new Date(endISO);
  const min = Math.round((e - s) / 60000);
  if (min < 1) return '<1m';
  if (min < 60) return `${min}m`;
  return `${Math.floor(min / 60)}h ${min % 60}m`;
}

function updateScanStatus(stats) {
  const el = document.getElementById('scanStatus');
  if (!el) return;
  const scan = stats?.last_scan;
  if (!scan) {
    el.innerHTML = '<span class="dot none"></span> No scans yet';
    return;
  }
  const ok = scan.status === 'completed';
  const time = scan.completed_at || scan.started_at;
  const label = time ? new Date(time).toLocaleDateString() : '';
  const duration = scan.completed_at && scan.started_at ? formatDuration(scan.started_at, scan.completed_at) : '';
  el.innerHTML = `<span class="dot ${ok ? 'ok' : 'fail'}"></span> ${label}${duration ? ` / ${duration}` : ''}`;
  el.title = scan.status === 'completed' ? `Last scan: ${time} (took ${duration})` : `Scan status: ${scan.status}`;
}

// ── Load Categories ──

async function loadCategories() {
  const data = await api('/categories');
  if (!data) return;
  state.categories = data.categories;
  const selects = document.querySelectorAll('select[id$="CategoryFilter"]');
  selects.forEach(sel => {
    const currentVal = sel.value;
    sel.innerHTML = '<option value="">All Categories</option>';
    data.categories.forEach(c => {
      const opt = document.createElement('option');
      opt.value = c.name;
      opt.textContent = `${c.name} (${c.count})`;
      sel.appendChild(opt);
    });
    sel.value = currentVal;
  });
}

// ── Load Sources for filter ──

async function loadSourceFilter() {
  const data = state.stats;
  if (!data?.sources_available) return;
  const sel = document.getElementById('keywordSourceFilter');
  if (!sel) return;
  sel.innerHTML = '<option value="">All Sources</option>';
  data.sources_available.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s;
    opt.textContent = s.charAt(0).toUpperCase() + s.slice(1);
    sel.appendChild(opt);
  });
}

// ── Load Stats ──

function animateCounter(el, target, duration = 800) {
  const start = parseInt(el.textContent.replace(/,/g, '')) || 0;
  const startTime = performance.now();
  const step = (now) => {
    const progress = Math.min((now - startTime) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = Math.round(start + (target - start) * eased).toLocaleString();
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

async function loadStats() {
  const data = await api('/stats');
  if (!data) return;
  state.stats = data;
  animateCounter(document.getElementById('statKeywords'), data.total_keywords);
  animateCounter(document.getElementById('statPredictions'), data.total_predictions);
  animateCounter(document.getElementById('statTrending'), data.trending_keywords);
  animateCounter(document.getElementById('statEmerging'), data.emerging_keywords);
  updateScanStatus(data);
}

// ── Load Trending Keywords ──

async function loadTrending() {
  const data = await api('/keywords?trending=true&sort=trend_score&limit=12');
  if (!data) return;
  state.trending = data.keywords;
  document.getElementById('trendingCount').textContent = data.total;
  renderKeywordGrid('trendingKeywords', data.keywords);
}

async function loadEmerging() {
  const data = await api('/keywords?emerging=true&sort=trend_score&limit=12');
  if (!data) return;
  state.emerging = data.keywords;
  document.getElementById('emergingCount').textContent = data.total;
  renderKeywordGrid('emergingKeywords', data.keywords);
}

// ── Load Predictions ──

async function loadLatestPredictions() {
  const data = await api('/predictions?limit=6');
  if (!data) return;
  state.predictions = data.predictions;
  document.getElementById('predictionCount').textContent = data.total;
  renderPredictions('latestPredictions', data.predictions);
}

async function loadAllPredictions() {
  const cat = document.getElementById('predCategoryFilter')?.value || '';
  const data = await api(`/predictions?limit=50${cat ? `&category=${encodeURIComponent(cat)}` : ''}`);
  if (!data) return;
  state.allPredictions = data.predictions;
  renderPredictions('allPredictions', data.predictions);
}

// ── Load All Keywords (with pagination & source filter) ──

async function loadAllKeywords(page = 0) {
  const search = document.getElementById('keywordSearch')?.value || '';
  const cat = document.getElementById('keywordCategoryFilter')?.value || '';
  const source = document.getElementById('keywordSourceFilter')?.value || '';
  const sort = document.getElementById('keywordSort')?.value || 'trend_score';
  const limit = 24;
  const offset = page * limit;

  let url = `/keywords?sort=${sort}&limit=${limit}&offset=${offset}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  if (cat) url += `&category=${encodeURIComponent(cat)}`;
  if (source) url += `&source=${encodeURIComponent(source)}`;

  const data = await api(url);
  if (!data) return;

  state.keywords = { page, total: data.total, items: data.keywords };
  renderKeywordGrid('allKeywords', data.keywords);
  renderPagination('keywordPagination', page, Math.ceil(data.total / limit));
}

// ── Render Keyword Card ──

function renderKeywordCard(kw) {
  const score = kw.trend_score || 0;
  const trendClass = score > 0.5 ? 'high' : score > 0.3 ? 'medium' : 'low';

  const card = document.createElement('div');
  card.className = 'keyword-card';
  card.innerHTML = `
    <div class="trend-indicator ${trendClass}"></div>
    <div class="keyword-card-header">
      <h4>${escapeHtml(kw.keyword)}</h4>
      <div class="keyword-badges">
        <span class="category-badge">${escapeHtml(kw.category)}</span>
        ${kw.is_emerging ? '<span class="trend-badge emerging">Emerging</span>' : ''}
        ${kw.is_trending && !kw.is_emerging ? '<span class="trend-badge up">Trending</span>' : ''}
      </div>
    </div>
    <p>${escapeHtml(truncate(kw.explanation, 120))}</p>
    <div class="card-footer">
      <span class="score">Trend Score: <strong>${score.toFixed(3)}</strong></span>
      <span class="score">Freq: ${kw.frequency}</span>
    </div>
  `;
  card.addEventListener('click', () => openKeywordModal(kw));
  return card;
}

function renderKeywordGrid(containerId, keywords) {
  const container = document.getElementById(containerId);
  if (!container) return;
  if (!keywords || keywords.length === 0) {
    container.innerHTML = '<div class="loading-spinner" style="--:">No keywords found. Try running a scan.</div>';
    return;
  }
  container.innerHTML = '';
  keywords.forEach(kw => container.appendChild(renderKeywordCard(kw)));
}

// ── Render Prediction Card ──

function renderPredictionCard(pred) {
  const card = document.createElement('div');
  card.className = 'prediction-card';
  const confPct = Math.round((pred.confidence || 0) * 100);
  card.innerHTML = `
    <div class="pred-header">
      <h4>${escapeHtml(pred.title)}</h4>
      <div class="pred-meta">
        <span class="impact-badge ${pred.predicted_impact}">${pred.predicted_impact} impact</span>
        <span class="horizon-badge">${pred.time_horizon}</span>
      </div>
    </div>
    <p>${escapeHtml(pred.description)}</p>
    <div class="pred-confidence">
      <div class="conf-bar"><div class="conf-fill" style="width:${confPct}%"></div></div>
      <span class="conf-label">${confPct}% confidence</span>
    </div>
    ${pred.keywords_involved && pred.keywords_involved.length > 0 ? `
      <div class="pred-keywords">
        ${pred.keywords_involved.map(k => `<span class="pred-keyword-tag">${escapeHtml(k)}</span>`).join('')}
      </div>
    ` : ''}
  `;
  return card;
}

function renderPredictions(containerId, predictions) {
  const container = document.getElementById(containerId);
  if (!container) return;
  if (!predictions || predictions.length === 0) {
    container.innerHTML = '<div class="loading-spinner">No predictions yet. Run a scan first.</div>';
    return;
  }
  container.innerHTML = '';
  predictions.forEach(p => container.appendChild(renderPredictionCard(p)));
}

// ── Pagination ──

function renderPagination(containerId, currentPage, totalPages) {
  const container = document.getElementById(containerId);
  if (!container) return;
  if (totalPages <= 1) { container.innerHTML = ''; return; }

  let html = '';
  html += `<button ${currentPage === 0 ? 'disabled' : ''} onclick="window.paginateTo(${currentPage - 1})">Prev</button>`;

  const start = Math.max(0, currentPage - 2);
  const end = Math.min(totalPages - 1, currentPage + 2);

  if (start > 0) html += `<button onclick="window.paginateTo(0)">1</button>`;
  if (start > 1) html += `<span class="page-info">...</span>`;

  for (let i = start; i <= end; i++) {
    html += `<button class="${i === currentPage ? 'active' : ''}" onclick="window.paginateTo(${i})">${i + 1}</button>`;
  }

  if (end < totalPages - 2) html += `<span class="page-info">...</span>`;
  if (end < totalPages - 1) html += `<button onclick="window.paginateTo(${totalPages - 1})">${totalPages}</button>`;

  html += `<button ${currentPage >= totalPages - 1 ? 'disabled' : ''} onclick="window.paginateTo(${currentPage + 1})">Next</button>`;

  container.innerHTML = html;
  window.paginateTo = (page) => loadAllKeywords(page);
}

// ── Charts ──

const CHART_COLORS = ['#00d4ff','#7c3aed','#22d3a7','#f59e0b','#ec4899','#ef4444','#06b6d4','#a855f7','#34d399','#f97316'];

async function loadCategoryChart() {
  const canvas = document.getElementById('categoryChart');
  if (!canvas || !state.categories?.length) return;

  const labels = state.categories.slice(0, 8).map(c => c.name);
  const data = state.categories.slice(0, 8).map(c => c.count);

  if (state.categoryChart) { state.categoryChart.destroy(); }

  const ctx = canvas.getContext('2d');
  state.categoryChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: CHART_COLORS.slice(0, labels.length),
        borderColor: 'rgba(8,8,24,0.8)',
        borderWidth: 2,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: { color: '#8888aa', font: { size: 11 }, padding: 12, boxWidth: 12 }
        }
      },
      cutout: '60%',
    }
  });
}

async function loadTimelineChart() {
  const canvas = document.getElementById('timelineChart');
  if (!canvas) return;

  const data = await api('/trend-timeline');
  if (!data?.timeline?.length) {
    canvas.parentElement.innerHTML = '<div class="loading-spinner" style="padding:40px">Not enough data yet. Run a few scans to see trends.</div>';
    return;
  }

  if (state.timelineChart) { state.timelineChart.destroy(); }

  const weeks = data.timeline.map(t => t.week.replace('W', '\nW'));
  const counts = data.timeline.map(t => t.total_mentions);
  const scores = data.timeline.map(t => t.avg_score);

  const ctx = canvas.getContext('2d');
  state.timelineChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: weeks,
      datasets: [
        {
          label: 'Mentions',
          data: counts,
          backgroundColor: 'rgba(0,212,255,0.3)',
          borderColor: '#00d4ff',
          borderWidth: 1,
          order: 2,
        },
        {
          label: 'Avg Score',
          data: scores,
          type: 'line',
          borderColor: '#7c3aed',
          backgroundColor: 'rgba(124,58,237,0.1)',
          borderWidth: 2,
          pointRadius: 3,
          pointBackgroundColor: '#7c3aed',
          fill: true,
          tension: 0.3,
          order: 1,
          yAxisID: 'y1',
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#8888aa', font: { size: 11 }, boxWidth: 12, padding: 8 }
        }
      },
      scales: {
        x: {
          ticks: { color: '#555577', font: { size: 9 } },
          grid: { color: 'rgba(255,255,255,0.03)' }
        },
        y: {
          beginAtZero: true,
          ticks: { color: '#555577', font: { size: 10 } },
          grid: { color: 'rgba(255,255,255,0.03)' },
          position: 'left',
        },
        y1: {
          beginAtZero: true,
          max: 1.0,
          ticks: { color: '#555577', font: { size: 10 }, callback: v => v.toFixed(2) },
          grid: { display: false },
          position: 'right',
        }
      }
    }
  });
}

// ── Modal ──

function openKeywordModal(kw) {
  const modal = document.getElementById('keywordModal');
  document.getElementById('modalKeyword').textContent = kw.keyword;
  document.getElementById('modalCategory').textContent = kw.category;
  document.getElementById('modalTrend').textContent = `Trend Score: ${(kw.trend_score || 0).toFixed(3)}`;
  document.getElementById('modalFrequency').textContent = `Frequency: ${kw.frequency}`;
  document.getElementById('modalSource').textContent = `Source: ${kw.source || 'unknown'}`;
  document.getElementById('modalExplanation').textContent = kw.explanation || 'No explanation available.';
  document.getElementById('modalMeaning').textContent = kw.meaning || 'No significance data available.';
  document.getElementById('modalApplication').textContent = kw.application || 'No application data available.';

  const relatedContainer = document.getElementById('modalRelated');
  const relatedSection = document.getElementById('modalRelatedSection');
  if (kw.related_keywords && kw.related_keywords.length > 0) {
    relatedSection.style.display = 'block';
    relatedContainer.innerHTML = kw.related_keywords.map(k =>
      `<span class="related-tag">${escapeHtml(k)}</span>`
    ).join('');
  } else {
    relatedSection.style.display = 'none';
  }

  // load history chart
  loadKeywordHistoryChart(kw.id);

  modal.classList.add('active');
}

async function loadKeywordHistoryChart(keywordId) {
  const canvas = document.getElementById('modalTrendChart');
  const section = document.getElementById('modalHistorySection');
  if (!canvas || !section) return;

  const data = await api(`/keywords/${keywordId}/history`);
  if (!data?.timeline?.length) {
    section.style.display = 'none';
    return;
  }
  section.style.display = 'block';

  if (state.modalChart) { state.modalChart.destroy(); }

  const weeks = data.timeline.map(t => t.week.replace('W', '\nW'));
  const counts = data.timeline.map(t => t.count);

  const ctx = canvas.getContext('2d');
  state.modalChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: weeks,
      datasets: [{
        label: 'Mentions',
        data: counts,
        borderColor: '#00d4ff',
        backgroundColor: 'rgba(0,212,255,0.15)',
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: '#00d4ff',
        fill: true,
        tension: 0.3,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#555577', font: { size: 9 } }, grid: { display: false } },
        y: { beginAtZero: true, ticks: { color: '#555577', font: { size: 9 } }, grid: { color: 'rgba(255,255,255,0.03)' } }
      }
    }
  });
}

document.querySelector('.modal-close').addEventListener('click', () => {
  document.getElementById('keywordModal').classList.remove('active');
});
document.getElementById('keywordModal').addEventListener('click', (e) => {
  if (e.target === e.currentTarget) {
    document.getElementById('keywordModal').classList.remove('active');
  }
});
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') document.getElementById('keywordModal').classList.remove('active');
});

// ── Scan Button ──

document.getElementById('scanBtn').addEventListener('click', async () => {
  const btn = document.getElementById('scanBtn');
  if (state.scanInProgress) return;
  state.scanInProgress = true;
  btn.disabled = true;
  btn.classList.add('scanning');
  btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Scanning...';

  try {
    const result = await api('/scan', 'POST');
    if (result && result.scan_id) {
      pollScanStatus(result.scan_id);
    } else {
      alert('Failed to start scan. The server may already be scanning.');
      resetScanBtn();
    }
  } catch (e) {
    alert('Failed to start scan. Check server connection.');
    resetScanBtn();
  }
});

async function pollScanStatus(scanId) {
  let attempts = 0;
  const maxAttempts = 60;
  const poll = async () => {
    attempts++;
    const data = await api('/scans?limit=1');
    if (data && data.scans && data.scans[0]) {
      const scan = data.scans[0];
      if (scan.status === 'completed') {
        resetScanBtn();
        await refreshAll();
        return;
      }
      if (scan.status === 'failed') {
        resetScanBtn();
        alert('Scan failed: ' + (scan.error || 'Unknown error'));
        return;
      }
    }
    if (attempts < maxAttempts) {
      setTimeout(poll, 3000);
    } else {
      resetScanBtn();
      alert('Scan is taking longer than expected. Check back later.');
    }
  };
  setTimeout(poll, 2000);
}

function resetScanBtn() {
  const btn = document.getElementById('scanBtn');
  state.scanInProgress = false;
  btn.disabled = false;
  btn.classList.remove('scanning');
  btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> <span>Scan Now</span>';
}

// ── Refresh All ──

async function refreshAll() {
  await Promise.all([
    loadStats(),
    loadTrending(),
    loadEmerging(),
    loadLatestPredictions(),
    loadCategories(),
  ]);
  loadSourceFilter();
  loadCategoryChart();
  loadTimelineChart();
  // reload the active view
  const activeView = document.querySelector('.nav-btn.active');
  if (activeView) {
    const view = activeView.dataset.view;
    if (view === 'predictions') await loadAllPredictions();
    if (view === 'keywords') await loadAllKeywords(0);
  }
}

// ── Filter Events ──

document.addEventListener('DOMContentLoaded', () => {
  let searchTimeout;
  document.getElementById('keywordSearch')?.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => loadAllKeywords(0), 300);
  });

  document.getElementById('keywordCategoryFilter')?.addEventListener('change', () => {
    loadAllKeywords(0);
  });
  document.getElementById('keywordSourceFilter')?.addEventListener('change', () => {
    loadAllKeywords(0);
  });
  document.getElementById('keywordSort')?.addEventListener('change', () => {
    loadAllKeywords(0);
  });
  document.getElementById('predCategoryFilter')?.addEventListener('change', () => {
    loadAllPredictions();
  });

  document.getElementById('exportBtn')?.addEventListener('click', exportKeywordsCSV);

  refreshAll();
});

// ── Export CSV ──

async function exportKeywordsCSV() {
  const data = await api('/keywords?sort=trend_score&limit=5000&offset=0');
  if (!data?.keywords?.length) return;

  const rows = [['Keyword','Category','Trend Score','Frequency','Source','Trending','Emerging','First Seen']];
  data.keywords.forEach(k => {
    rows.push([
      k.keyword,
      k.category,
      (k.trend_score || 0).toFixed(4),
      k.frequency,
      k.source || '',
      k.is_trending ? 'Yes' : 'No',
      k.is_emerging ? 'Yes' : 'No',
      k.first_seen ? new Date(k.first_seen).toISOString().split('T')[0] : '',
    ]);
  });

  const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `ai-trends-keywords-${new Date().toISOString().split('T')[0]}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ── Utilities ──

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function truncate(str, len) {
  if (!str || str.length <= len) return str || '';
  return str.substring(0, len) + '...';
}
