/**
 * Automated Data Quality Auditor - Enterprise Frontend Engine
 * Pure ES6, strictly typed, theme-aware, zero-emoji.
 */

// Application State
const State = {
  currentReport: null,
  currentFile: null,
  currentSampleName: null,
  currentTheme: localStorage.getItem('dqa_theme') || 'light',
  activeTab: 'overview'
};

// DOM Elements
const Elements = {
  themeLightBtn: document.getElementById('theme-light-btn'),
  themeDarkBtn: document.getElementById('theme-dark-btn'),
  themeSystemBtn: document.getElementById('theme-system-btn'),
  configIqr: document.getElementById('config-iqr'),
  configZscore: document.getElementById('config-zscore'),
  dropZone: document.getElementById('drop-zone'),
  fileInput: document.getElementById('file-input'),
  sampleBtnEcommerce: document.getElementById('sample-btn-ecommerce'),
  sampleBtnSensors: document.getElementById('sample-btn-sensors'),
  loaderOverlay: document.getElementById('loader-overlay'),
  loaderMessage: document.getElementById('loader-message'),
  dashboardSection: document.getElementById('dashboard-section'),
  exportJsonBtn: document.getElementById('export-json-btn'),
  exportHtmlBtn: document.getElementById('export-html-btn'),
  exportPdfBtn: document.getElementById('export-pdf-btn'),
  copyPolarsBtn: document.getElementById('copy-polars-btn'),
  copySqlBtn: document.getElementById('copy-sql-btn')
};

// Theme Management
function applyTheme(theme) {
  State.currentTheme = theme;
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('dqa_theme', theme);

  [Elements.themeLightBtn, Elements.themeDarkBtn, Elements.themeSystemBtn].forEach(btn => {
    if (btn) btn.classList.remove('active');
  });

  if (theme === 'light' && Elements.themeLightBtn) Elements.themeLightBtn.classList.add('active');
  if (theme === 'dark' && Elements.themeDarkBtn) Elements.themeDarkBtn.classList.add('active');
  if (theme === 'system' && Elements.themeSystemBtn) Elements.themeSystemBtn.classList.add('active');

  if (State.currentReport) {
    renderCharts(State.currentReport);
  }
}

function initTheme() {
  applyTheme(State.currentTheme);
  Elements.themeLightBtn.addEventListener('click', () => applyTheme('light'));
  Elements.themeDarkBtn.addEventListener('click', () => applyTheme('dark'));
  Elements.themeSystemBtn.addEventListener('click', () => applyTheme('system'));

  // Re-run profiling if configuration changes and report is active
  [Elements.configIqr, Elements.configZscore].forEach(elem => {
    elem.addEventListener('change', () => {
      if (State.currentFile) {
        handleFileUpload(State.currentFile);
      } else if (State.currentSampleName) {
        loadSampleDataset(State.currentSampleName);
      }
    });
  });
}

function showLoader(message = 'Analyzing dataset...') {
  if (Elements.loaderMessage) Elements.loaderMessage.textContent = message;
  if (Elements.loaderOverlay) Elements.loaderOverlay.style.display = 'flex';
}

function hideLoader() {
  if (Elements.loaderOverlay) Elements.loaderOverlay.style.display = 'none';
}

// Ingestion Handlers
function setupIngestion() {
  const dropZone = Elements.dropZone;
  const fileInput = Elements.fileInput;

  dropZone.addEventListener('click', () => fileInput.click());

  ['dragenter', 'dragover'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.add('drag-over');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropZone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropZone.classList.remove('drag-over');
    });
  });

  dropZone.addEventListener('drop', (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (fileInput.files.length > 0) {
      handleFileUpload(fileInput.files[0]);
    }
  });

  if (Elements.sampleBtnEcommerce) {
    Elements.sampleBtnEcommerce.addEventListener('click', () => loadSampleDataset('messy_ecommerce'));
  }
  if (Elements.sampleBtnSensors) {
    Elements.sampleBtnSensors.addEventListener('click', () => loadSampleDataset('messy_sensors'));
  }
}

async function handleFileUpload(file) {
  State.currentFile = file;
  State.currentSampleName = null;
  showLoader(`Ingesting and profiling ${file.name}...`);
  const formData = new FormData();
  formData.append('file', file);
  formData.append('iqr_multiplier', Elements.configIqr.value);
  formData.append('zscore_threshold', Elements.configZscore.value);

  try {
    const res = await fetch('/api/audit', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Audit execution failed.');
    }

    const report = await res.json();
    State.currentReport = report;
    renderAuditReport(report);
  } catch (error) {
    alert(`Audit Error: ${error.message}`);
  } finally {
    hideLoader();
  }
}

async function loadSampleDataset(sampleName) {
  State.currentSampleName = sampleName;
  State.currentFile = null;
  showLoader(`Loading sample benchmark: ${sampleName}...`);
  try {
    const iqr = Elements.configIqr.value;
    const zscore = Elements.configZscore.value;
    const res = await fetch(`/api/audit/sample/${sampleName}?iqr_multiplier=${iqr}&zscore_threshold=${zscore}`, {
      method: 'POST'
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to load sample dataset.');
    }

    const report = await res.json();
    State.currentReport = report;
    renderAuditReport(report);
  } catch (error) {
    alert(`Sample Loading Error: ${error.message}`);
  } finally {
    hideLoader();
  }
}

// Rendering Dashboard & Panels
function renderAuditReport(report) {
  Elements.dashboardSection.style.display = 'block';

  // Executive KPI Cards
  document.getElementById('kpi-score-val').textContent = report.health_score.overall_score;
  document.getElementById('kpi-score-grade').textContent = `Grade ${report.health_score.grade}`;
  document.getElementById('kpi-dims-val').textContent = `${report.summary.row_count.toLocaleString()} × ${report.summary.column_count}`;
  document.getElementById('kpi-missing-val').textContent = `${report.summary.overall_missing_percentage}%`;
  document.getElementById('kpi-dup-val').textContent = `${report.summary.duplicate_rows_percentage}% (${report.summary.duplicate_rows_count})`;
  
  const keysVal = document.getElementById('kpi-keys-val');
  if (report.summary.candidate_primary_keys && report.summary.candidate_primary_keys.length > 0) {
    keysVal.innerHTML = `<span class="badge badge-good">${report.summary.candidate_primary_keys.join(', ')}</span>`;
  } else {
    keysVal.innerHTML = `<span class="badge badge-warn">None</span>`;
  }

  // Findings & Recommendations
  renderRecommendations(report);

  // Missing Pattern Heuristics
  renderMissingPatternAnalysis(report.missing_analysis);

  // Table Tabs
  renderSchemaTable(report.columns);
  renderMissingTable(report.columns, report.summary.row_count);
  renderAnomalyTable(report.columns);
  renderRemediationTab(report.remediation);
  renderPreviewTable(report.preview_rows, report.columns);

  // Vectorized Charts
  renderCharts(report);

  Elements.dashboardSection.scrollIntoView({ behavior: 'smooth' });
}

function renderRecommendations(report) {
  const container = document.getElementById('recommendations-list');
  if (!container) return;

  const items = report.health_score.recommendations.map(r => `<li>${r}</li>`).join('');
  const findings = report.health_score.summary_findings.map(f => `<div style="margin-bottom: 4px; color: var(--text-muted); font-size: 11px;">• ${f}</div>`).join('');

  container.innerHTML = `
    <div style="margin-bottom: 10px;">${findings}</div>
    <ul style="padding-left: 18px; font-size: 11px; color: var(--text-main);">${items}</ul>
  `;
}

function renderMissingPatternAnalysis(pattern) {
  const title = document.getElementById('missing-pattern-title');
  const desc = document.getElementById('missing-pattern-desc');
  const pairs = document.getElementById('missing-pattern-pairs');

  title.textContent = pattern.mechanism_hypothesis;
  desc.textContent = pattern.description;

  if (pattern.correlated_missing_pairs && pattern.correlated_missing_pairs.length > 0) {
    pairs.innerHTML = `
      <div style="font-weight: 700; text-transform: uppercase; margin-bottom: 4px; color: var(--text-muted);">Correlated Null Pairs:</div>
      ${pattern.correlated_missing_pairs.map(p => `
        <div class="mono" style="margin-bottom: 2px;">
          • ${p.column_a} &harr; ${p.column_b} (correlation r = ${p.correlation})
        </div>
      `).join('')}
    `;
  } else {
    pairs.innerHTML = '';
  }
}

function renderSchemaTable(columns) {
  const tbody = document.getElementById('schema-table-body');
  if (!tbody) return;

  tbody.innerHTML = columns.map(col => {
    const keyBadge = col.is_candidate_key 
      ? '<span class="badge badge-good">Primary Key</span>' 
      : '<span class="badge badge-neutral">No</span>';

    const issuesBadges = col.issues.length > 0 
      ? col.issues.map(i => `<div style="color: var(--badge-danger-text); font-size: 10px;">${i}</div>`).join('') 
      : '<span class="badge badge-good">Healthy</span>';

    return `
      <tr>
        <td class="mono"><strong>${col.name}</strong></td>
        <td class="mono">${col.physical_type}</td>
        <td>${col.inferred_type}</td>
        <td>${keyBadge}</td>
        <td class="mono">${col.unique_percentage}%</td>
        <td class="mono">${col.missing_count} (${col.missing_percentage}%)</td>
        <td>${issuesBadges}</td>
      </tr>
    `;
  }).join('');
}

function renderMissingTable(columns, totalRows) {
  const tbody = document.getElementById('missing-table-body');
  if (!tbody) return;

  tbody.innerHTML = columns.map(col => {
    let statusClass = 'badge-good';
    if (col.missing_percentage > 20) statusClass = 'badge-danger';
    else if (col.missing_percentage > 0) statusClass = 'badge-warn';

    return `
      <tr>
        <td class="mono"><strong>${col.name}</strong></td>
        <td class="mono">${col.missing_count}</td>
        <td class="mono">${(totalRows - col.missing_count)}</td>
        <td><span class="badge ${statusClass}">${col.missing_percentage}%</span></td>
        <td class="mono">${col.inferred_type}</td>
      </tr>
    `;
  }).join('');
}

function renderAnomalyTable(columns) {
  const tbody = document.getElementById('anomaly-table-body');
  if (!tbody) return;

  tbody.innerHTML = columns
    .filter(c => c.numeric_stats !== null)
    .map(col => {
      const stats = col.numeric_stats;
      const outliers = col.outliers || { iqr_outlier_count: 0, robust_zscore_outlier_count: 0 };
      const iqrBounds = (outliers.iqr_lower_bound !== null && outliers.iqr_lower_bound !== undefined)
        ? `[${outliers.iqr_lower_bound}, ${outliers.iqr_upper_bound}]`
        : '-';

      const outlierBadge = outliers.iqr_outlier_count > 0 
        ? `<span class="badge badge-warn">${outliers.iqr_outlier_count} (${outliers.iqr_outlier_percentage}%)</span>` 
        : '<span class="badge badge-good">0</span>';

      return `
        <tr>
          <td class="mono"><strong>${col.name}</strong></td>
          <td class="mono">${stats.mean ?? '-'}</td>
          <td class="mono">${stats.std ?? '-'}</td>
          <td class="mono">${stats.median ?? '-'}</td>
          <td class="mono">${stats.skewness ?? '-'}</td>
          <td class="mono">${stats.kurtosis ?? '-'}</td>
          <td>${stats.distribution_shape}</td>
          <td class="mono">${iqrBounds}</td>
          <td>${outlierBadge}</td>
          <td class="mono">${outliers.robust_zscore_outlier_count}</td>
        </tr>
      `;
    }).join('');
}

function renderRemediationTab(remediation) {
  const actionsList = document.getElementById('remediation-actions-list');
  const polarsCode = document.getElementById('remediation-polars-code');
  const sqlCode = document.getElementById('remediation-sql-code');

  actionsList.innerHTML = remediation.summary_actions.map(act => `<li style="margin-bottom: 4px;">${act}</li>`).join('');
  polarsCode.textContent = remediation.polars_code;
  sqlCode.textContent = remediation.sql_code;
}

function renderPreviewTable(rows, columns) {
  const thead = document.getElementById('preview-table-head');
  const tbody = document.getElementById('preview-table-body');
  if (!thead || !tbody) return;

  thead.innerHTML = `<tr>${columns.map(c => `<th class="mono">${c.name}</th>`).join('')}</tr>`;

  if (!rows || rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="${columns.length}">No preview data available.</td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map(row => {
    return `<tr>${columns.map(c => {
      const val = row[c.name];
      if (val === null || val === undefined) {
        return `<td class="mono" style="color: var(--text-faint); font-style: italic;">null</td>`;
      }
      return `<td class="mono">${val}</td>`;
    }).join('')}</tr>`;
  }).join('');
}

function renderCharts(report) {
  if (typeof Plotly === 'undefined') return;

  const isDark = State.currentTheme === 'dark' || State.currentTheme === 'system';
  const paperBg = isDark ? '#111827' : '#ffffff';
  const plotBg = isDark ? '#111827' : '#ffffff';
  const textColor = isDark ? '#f9fafb' : '#0f172a';
  const gridColor = isDark ? '#1f2937' : '#e2e8f0';

  // 1. Missingness Bar Chart
  const colNames = report.columns.map(c => c.name);
  const missingPcts = report.columns.map(c => c.missing_percentage);

  const missingTrace = {
    x: colNames,
    y: missingPcts,
    type: 'bar',
    marker: {
      color: missingPcts.map(pct => pct > 20 ? '#ef4444' : (pct > 0 ? '#f59e0b' : '#10b981'))
    }
  };

  const missingLayout = {
    paper_bgcolor: paperBg,
    plot_bgcolor: plotBg,
    font: { color: textColor, family: '-apple-system, sans-serif', size: 10 },
    margin: { t: 20, r: 20, l: 40, b: 60 },
    yaxis: { title: 'Missing %', range: [0, 100], gridcolor: gridColor },
    xaxis: { tickangle: -30, gridcolor: gridColor }
  };

  Plotly.newPlot('chart-missingness', [missingTrace], missingLayout, { responsive: true, displayModeBar: false });

  // 2. Outliers Frequency Chart: IQR vs Robust MAD Z-Score
  const numCols = report.columns.filter(c => c.outliers && c.numeric_stats);
  const numNames = numCols.map(c => c.name);
  const iqrCounts = numCols.map(c => c.outliers.iqr_outlier_count);
  const robustCounts = numCols.map(c => c.outliers.robust_zscore_outlier_count);

  const traceIqr = {
    name: 'IQR Outliers',
    x: numNames,
    y: iqrCounts,
    type: 'bar',
    marker: { color: '#6366f1' }
  };

  const traceRobust = {
    name: 'Robust MAD Z (|Z*|>=3.5)',
    x: numNames,
    y: robustCounts,
    type: 'bar',
    marker: { color: '#ec4899' }
  };

  const outlierLayout = {
    barmode: 'group',
    paper_bgcolor: paperBg,
    plot_bgcolor: plotBg,
    font: { color: textColor, family: '-apple-system, sans-serif', size: 10 },
    margin: { t: 20, r: 20, l: 40, b: 60 },
    yaxis: { title: 'Outliers Count', gridcolor: gridColor },
    xaxis: { tickangle: -30, gridcolor: gridColor },
    legend: { orientation: 'h', y: 1.15 }
  };

  Plotly.newPlot('chart-outliers', [traceIqr, traceRobust], outlierLayout, { responsive: true, displayModeBar: false });
}

function setupTabs() {
  const tabs = document.querySelectorAll('.tab-btn');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(p => p.classList.remove('active'));

      tab.classList.add('active');
      const targetId = tab.getAttribute('data-tab');
      const panel = document.getElementById(targetId);
      if (panel) panel.classList.add('active');
    });
  });
}

function setupExports() {
  Elements.exportJsonBtn.addEventListener('click', () => downloadExport('/api/export/json'));
  Elements.exportHtmlBtn.addEventListener('click', () => downloadExport('/api/export/html'));
  Elements.exportPdfBtn.addEventListener('click', () => downloadExport('/api/export/pdf'));

  Elements.copyPolarsBtn.addEventListener('click', () => {
    const code = document.getElementById('remediation-polars-code').textContent;
    navigator.clipboard.writeText(code).then(() => {
      Elements.copyPolarsBtn.textContent = 'Copied!';
      setTimeout(() => Elements.copyPolarsBtn.textContent = 'Copy Script', 2000);
    });
  });

  Elements.copySqlBtn.addEventListener('click', () => {
    const code = document.getElementById('remediation-sql-code').textContent;
    navigator.clipboard.writeText(code).then(() => {
      Elements.copySqlBtn.textContent = 'Copied!';
      setTimeout(() => Elements.copySqlBtn.textContent = 'Copy SQL', 2000);
    });
  });
}

async function downloadExport(endpoint) {
  if (!State.currentReport) {
    alert('Please ingest a dataset before exporting an audit report.');
    return;
  }
  showLoader('Generating export file...');
  try {
    const res = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(State.currentReport)
    });

    if (!res.ok) throw new Error('Failed to generate export file.');

    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    let filename = 'audit_report';
    const match = disposition.match(/filename="?([^"]+)"?/);
    if (match && match[1]) filename = match[1];

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
  } catch (err) {
    alert(`Export Error: ${err.message}`);
  } finally {
    hideLoader();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  setupIngestion();
  setupTabs();
  setupExports();
});
