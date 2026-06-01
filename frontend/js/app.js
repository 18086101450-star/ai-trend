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
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.getElementById(`view-${btn.dataset.view}`).classList.add('active');
  });
});

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

// ── Load Stats ──

async function loadStats() {
  const data = await api('/stats');
  if (!data) return;
  state.stats = data;
  document.getElementById('statKeywords').textContent = data.total_keywords;
  document.getElementById('statPredictions').textContent = data.total_predictions;
  document.getElementById('statTrending').textContent = data.trending_keywords;
  document.getElementById('statEmerging').textContent = data.emerging_keywords;
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

// ── Load All Keywords (with pagination) ──

async function loadAllKeywords(page = 0) {
  const search = document.getElementById('keywordSearch')?.value || '';
  const cat = document.getElementById('keywordCategoryFilter')?.value || '';
  const sort = document.getElementById('keywordSort')?.value || 'trend_score';
  const limit = 24;
  const offset = page * limit;

  let url = `/keywords?sort=${sort}&limit=${limit}&offset=${offset}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;
  if (cat) url += `&category=${encodeURIComponent(cat)}`;

  const data = await api(url);
  if (!data) return;

  state.keywords = { page, total: data.total, items: data.keywords };
  renderKeywordGrid('allKeywords', data.keywords);
  renderPagination('keywordPagination', page, Math.ceil(data.total / limit), loadAllKeywords);
}

// ── Render Keyword Card ──

function renderKeywordCard(kw) {
  const score = kw.trend_score || 0;
  const trendClass = score > 0.5 ? 'high' : score > 0.3 ? 'medium' : 'low';
  const isUp = score > 0.3;

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

function renderPagination(containerId, currentPage, totalPages, loadFn) {
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
  window.paginateTo = (page) => loadFn(page);
}

// ── Modal ──

function openKeywordModal(kw) {
  const modal = document.getElementById('keywordModal');
  document.getElementById('modalKeyword').textContent = kw.keyword;
  document.getElementById('modalCategory').textContent = kw.category;
  document.getElementById('modalTrend').textContent = `Trend Score: ${(kw.trend_score || 0).toFixed(3)}`;
  document.getElementById('modalFrequency').textContent = `Frequency: ${kw.frequency}`;
  document.getElementById('modalSource').textContent = `Source: ${kw.source}`;
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

  modal.classList.add('active');
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
      // poll for completion
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
    const data = await api(`/scans?limit=1`);
    if (data && data.scans && data.scans[0]) {
      const scan = data.scans[0];
      if (scan.status === 'completed') {
        resetScanBtn();
        await refreshAll();
        return;
      }
      if (scan.status === 'failed') {
        resetScanBtn();
        alert(`Scan failed: ${scan.error || 'Unknown error'}`);
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
  btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Scan Now';
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
  // keyword search with debounce
  let searchTimeout;
  document.getElementById('keywordSearch')?.addEventListener('input', () => {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => loadAllKeywords(0), 300);
  });

  document.getElementById('keywordCategoryFilter')?.addEventListener('change', () => {
    loadAllKeywords(0);
  });
  document.getElementById('keywordSort')?.addEventListener('change', () => {
    loadAllKeywords(0);
  });
  document.getElementById('predCategoryFilter')?.addEventListener('change', () => {
    loadAllPredictions();
  });

  // initial load
  refreshAll();
});

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
