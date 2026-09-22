import json
from jinja2 import Template
from weasyprint import HTML
from backend.models import AuditReport

HTML_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Data Quality Audit Dossier - {{ report.summary.filename }}</title>
<style>
  @page {
    size: A4;
    margin: 18mm 14mm 18mm 14mm;
    @bottom-right {
      content: "Page " counter(page) " of " counter(pages);
      font-size: 8pt;
      color: #64748b;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    color: #0f172a;
    background-color: #ffffff;
    line-height: 1.4;
    margin: 0;
    padding: 0;
    font-size: 10pt;
  }
  .header-bar {
    border-bottom: 2px solid #0f172a;
    padding-bottom: 10px;
    margin-bottom: 20px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }
  .title-group h1 {
    font-size: 18pt;
    font-weight: 700;
    letter-spacing: -0.02em;
    margin: 0 0 4px 0;
    color: #0f172a;
    text-transform: uppercase;
  }
  .title-group .meta {
    font-size: 8.5pt;
    color: #475569;
    font-family: monospace;
  }
  .score-badge {
    font-size: 22pt;
    font-weight: 800;
    padding: 3px 14px;
    border-radius: 4px;
    background: #0f172a;
    color: #ffffff;
    display: inline-block;
  }
  .score-sub {
    font-size: 8pt;
    font-weight: 600;
    text-transform: uppercase;
    color: #64748b;
    margin-top: 3px;
    text-align: right;
  }
  .grid-2 {
    display: table;
    width: 100%;
    margin-bottom: 20px;
  }
  .col-half {
    display: table-cell;
    width: 50%;
    vertical-align: top;
  }
  .col-half:first-child {
    padding-right: 12px;
  }
  .col-half:last-child {
    padding-left: 12px;
  }
  .section-title {
    font-size: 10.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #334155;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 4px;
    margin-bottom: 10px;
  }
  table.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 8.5pt;
    margin-bottom: 14px;
  }
  table.data-table th, table.data-table td {
    padding: 5px 7px;
    text-align: left;
    border-bottom: 1px solid #e2e8f0;
  }
  table.data-table th {
    background-color: #f8fafc;
    color: #475569;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 7.5pt;
  }
  .mono {
    font-family: monospace;
  }
  .badge {
    display: inline-block;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 7.5pt;
    font-weight: 600;
    text-transform: uppercase;
  }
  .badge-danger { background-color: #fee2e2; color: #991b1b; }
  .badge-warning { background-color: #fef3c7; color: #92400e; }
  .badge-success { background-color: #dcfce7; color: #166534; }
  .badge-neutral { background-color: #f1f5f9; color: #475569; }
  ul.clean-list {
    margin: 0;
    padding-left: 16px;
    font-size: 9pt;
  }
  ul.clean-list li {
    margin-bottom: 4px;
  }
  .code-block {
    background: #0f172a;
    color: #f8fafc;
    font-family: monospace;
    font-size: 8pt;
    padding: 10px;
    border-radius: 4px;
    white-space: pre-wrap;
    margin-top: 6px;
  }
  .page-break {
    page-break-before: always;
  }
</style>
</head>
<body>

<div class="header-bar">
  <div class="title-group">
    <h1>Enterprise Data Quality Audit</h1>
    <div class="meta">Target: {{ report.summary.filename }} | Generated: {{ report.timestamp }}</div>
  </div>
  <div>
    <div class="score-badge">{{ report.health_score.overall_score }}</div>
    <div class="score-sub">Grade {{ report.health_score.grade }} / 100</div>
  </div>
</div>

<div class="grid-2">
  <div class="col-half">
    <div class="section-title">Dataset Characteristics</div>
    <table class="data-table">
      <tr><th>Dimensions</th><td class="mono">{{ report.summary.row_count }} rows × {{ report.summary.column_count }} cols</td></tr>
      <tr><th>File Format</th><td>{{ report.summary.file_format }}</td></tr>
      <tr><th>File Size</th><td class="mono">{{ (report.summary.file_size_bytes / 1024)|round(1) }} KB</td></tr>
      <tr><th>Overall Missing</th><td class="mono">{{ report.summary.total_missing_cells }} ({{ report.summary.overall_missing_percentage }}%)</td></tr>
      <tr><th>Duplicate Rows</th><td class="mono">{{ report.summary.duplicate_rows_count }} ({{ report.summary.duplicate_rows_percentage }}%)</td></tr>
      <tr>
        <th>Candidate Keys</th>
        <td>
          {% if report.summary.candidate_primary_keys %}
            <span class="mono">{{ report.summary.candidate_primary_keys|join(', ') }}</span>
          {% else %}
            <span class="badge badge-warning">None Found</span>
          {% endif %}
        </td>
      </tr>
    </table>
  </div>
  
  <div class="col-half">
    <div class="section-title">Quality Pillar Scores</div>
    <table class="data-table">
      <tr><th>Completeness (35 pts max)</th><td class="mono">{{ report.health_score.completeness_score }} pts</td></tr>
      <tr><th>Uniqueness (25 pts max)</th><td class="mono">{{ report.health_score.uniqueness_score }} pts</td></tr>
      <tr><th>Validity & Outliers (25 pts max)</th><td class="mono">{{ report.health_score.validity_score }} pts</td></tr>
      <tr><th>Consistency (15 pts max)</th><td class="mono">{{ report.health_score.consistency_score }} pts</td></tr>
    </table>

    <div class="section-title" style="margin-top: 10px;">Missingness Mechanism Analysis</div>
    <div style="font-size: 8.5pt; color: #1e293b; margin-bottom: 6px;">
      <strong>Pattern:</strong> {{ report.missing_analysis.mechanism_hypothesis }}
    </div>
    <div style="font-size: 8pt; color: #475569;">
      {{ report.missing_analysis.description }}
    </div>
  </div>
</div>

<div class="section-title">Column Profile & Quality Matrix</div>
<table class="data-table">
  <thead>
    <tr>
      <th>Column</th>
      <th>Inferred Type</th>
      <th>Missing (%)</th>
      <th>Unique (%)</th>
      <th>Outliers (IQR)</th>
      <th>Robust Z (|Z*|&ge;3.5)</th>
      <th>Flags</th>
    </tr>
  </thead>
  <tbody>
    {% for col in report.columns %}
    <tr>
      <td class="mono"><strong>{{ col.name }}</strong></td>
      <td>{{ col.inferred_type }}</td>
      <td class="mono">
        {% if col.missing_percentage > 20 %}
          <span class="badge badge-danger">{{ col.missing_percentage }}%</span>
        {% elif col.missing_percentage > 0 %}
          <span class="badge badge-warning">{{ col.missing_percentage }}%</span>
        {% else %}
          <span class="badge badge-success">0%</span>
        {% endif %}
      </td>
      <td class="mono">
        {% if col.is_candidate_key %}
          <span class="badge badge-success">Primary Key</span>
        {% else %}
          {{ col.unique_percentage }}%
        {% endif %}
      </td>
      <td class="mono">
        {% if col.outliers and col.outliers.iqr_outlier_count > 0 %}
          <span class="badge badge-warning">{{ col.outliers.iqr_outlier_count }} ({{ col.outliers.iqr_outlier_percentage }}%)</span>
        {% elif col.outliers %}
          0
        {% else %}
          -
        {% endif %}
      </td>
      <td class="mono">
        {% if col.outliers and col.outliers.robust_zscore_outlier_count > 0 %}
          <span class="badge badge-warning">{{ col.outliers.robust_zscore_outlier_count }}</span>
        {% elif col.outliers %}
          0
        {% else %}
          -
        {% endif %}
      </td>
      <td>
        {% if col.issues %}
          {% for issue in col.issues %}
            <div style="font-size: 7.5pt; color: #b91c1c;">• {{ issue }}</div>
          {% endfor %}
        {% else %}
          <span style="font-size: 7.5pt; color: #15803d;">Healthy</span>
        {% endif %}
      </td>
    </tr>
    {% endfor %}
  </tbody>
</table>

<div class="page-break"></div>

<div class="section-title">Numerical Distributions, Skewness & Kurtosis</div>
<table class="data-table">
  <thead>
    <tr>
      <th>Column</th>
      <th>Mean</th>
      <th>Std Dev</th>
      <th>Median</th>
      <th>Skewness</th>
      <th>Kurtosis</th>
      <th>Distribution Shape</th>
    </tr>
  </thead>
  <tbody>
    {% for col in report.columns %}
      {% if col.numeric_stats %}
      <tr>
        <td class="mono"><strong>{{ col.name }}</strong></td>
        <td class="mono">{{ col.numeric_stats.mean }}</td>
        <td class="mono">{{ col.numeric_stats.std }}</td>
        <td class="mono">{{ col.numeric_stats.median }}</td>
        <td class="mono">{{ col.numeric_stats.skewness if col.numeric_stats.skewness is not none else '-' }}</td>
        <td class="mono">{{ col.numeric_stats.kurtosis if col.numeric_stats.kurtosis is not none else '-' }}</td>
        <td>{{ col.numeric_stats.distribution_shape }}</td>
      </tr>
      {% endif %}
    {% endfor %}
  </tbody>
</table>

<div class="section-title" style="margin-top: 16px;">Automated Remediation Plan</div>
<ul class="clean-list" style="margin-bottom: 12px;">
  {% for act in report.remediation.summary_actions %}
  <li>{{ act }}</li>
  {% endfor %}
</ul>

<div class="section-title">Executable Remediation Script (Polars)</div>
<div class="code-block">{{ report.remediation.polars_code }}</div>

</body>
</html>
"""

def generate_json_report(report: AuditReport) -> str:
    return report.model_dump_json(indent=2)

def generate_html_report(report: AuditReport) -> str:
    template = Template(HTML_REPORT_TEMPLATE)
    return template.render(report=report)

def generate_pdf_report(report: AuditReport) -> bytes:
    html_content = generate_html_report(report)
    return HTML(string=html_content).write_pdf()
