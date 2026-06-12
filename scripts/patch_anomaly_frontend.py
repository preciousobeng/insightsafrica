"""
patch_anomaly_frontend.py

Applies the anomaly layer additions to non-Ghana FloodWatch pages.
Each page gets:
  - Anomaly CSS (.al-row, .al-swatch, .al-label)
  - Anomaly stats rows in Active Layer sidebar section
  - Rainfall legend section ID + anomaly legend section
  - View Mode toggle before Boundaries section
  - ANOMALY_COLORS / ANOMALY_LABELS / state vars
  - Anomaly-aware buildTooltipContent
  - Anomaly management functions
  - displayLayer modification to reload anomaly

Cape Verde is skipped (structurally different page, handled separately).
"""

import re
from pathlib import Path

BASE = Path(__file__).parent.parent / "frontend"

COUNTRIES = [
    ("nigeria",     "/api/nigeria/flood/anomaly/"),
    ("ivorycoast",  "/api/ivorycoast/flood/anomaly/"),
    ("senegal",     "/api/senegal/flood/anomaly/"),
    ("southafrica", "/api/southafrica/flood/anomaly/"),
]

# ── Patch 1: anomaly CSS ──────────────────────────────────────────────────────
CSS_ANCHOR = "[data-theme=\"light\"] .dl-btn:hover { background: #dcfce7; border-color: #6ee7b7; }"
CSS_INSERT = """[data-theme="light"] .dl-btn:hover { background: #dcfce7; border-color: #6ee7b7; }

    /* ── Anomaly layer ── */
    .al-row { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem; }
    .al-swatch { width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0; }
    .al-label  { font-size: 0.73rem; color: #94a3b8; }
    [data-theme="light"] .al-label { color: #475569; }"""

# ── Patch 2: wrap rainfall stats, add anomaly stats rows ─────────────────────
STATS_OLD = """        <div class="stat-row">
          <span class="stat-label">Min rainfall</span>
          <span class="stat-value" id="rain-min">—</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Max rainfall</span>
          <span class="stat-value" id="rain-max">—</span>
        </div>
        <div class="stat-row">
          <span class="stat-label">Mean rainfall</span>
          <span class="stat-value" id="rain-mean">—</span>
        </div>
      </div>"""

STATS_NEW = """        <div id="rainfall-stats-rows">
          <div class="stat-row">
            <span class="stat-label">Min rainfall</span>
            <span class="stat-value" id="rain-min">—</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Max rainfall</span>
            <span class="stat-value" id="rain-max">—</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Mean rainfall</span>
            <span class="stat-value" id="rain-mean">—</span>
          </div>
        </div>
        <div id="anomaly-stats-rows" style="display:none;">
          <div class="stat-row">
            <span class="stat-label">Reference</span>
            <span class="stat-value" id="anomaly-ref" style="font-size:0.78rem;">1991–2020 LTM</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Below normal</span>
            <span class="stat-value" id="anomaly-drought-pct">—</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Above normal</span>
            <span class="stat-value" id="anomaly-wet-pct">—</span>
          </div>
        </div>
      </div>"""

# ── Patch 3: add id to rainfall legend section, inject anomaly legend ─────────
LEGEND_OLD = """      <div class="sidebar-section">
        <div class="section-label">Rainfall Scale (mm)</div>
        <div class="legend-bar"></div>
        <div class="legend-labels">
          <span>0</span>
          <span id="legend-mid">—</span>
          <span id="legend-max">—</span>
        </div>
      </div>"""

LEGEND_NEW = """      <div class="sidebar-section" id="rainfall-legend-section">
        <div class="section-label">Rainfall Scale (mm)</div>
        <div class="legend-bar"></div>
        <div class="legend-labels">
          <span>0</span>
          <span id="legend-mid">—</span>
          <span id="legend-max">—</span>
        </div>
      </div>

      <div class="sidebar-section" id="anomaly-legend-section" style="display:none;">
        <div class="section-label">Anomaly vs LTM (1991–2020)</div>
        <div>
          <div class="al-row"><span class="al-swatch" style="background:#b91c1c"></span><span class="al-label">Severe drought (&lt;&minus;50%)</span></div>
          <div class="al-row"><span class="al-swatch" style="background:#ef4444"></span><span class="al-label">Moderate drought (&minus;50 to &minus;25%)</span></div>
          <div class="al-row"><span class="al-swatch" style="background:#f97316"></span><span class="al-label">Mild drought (&minus;25 to &minus;10%)</span></div>
          <div class="al-row"><span class="al-swatch" style="background:#64748b"></span><span class="al-label">Near normal (&plusmn;10%)</span></div>
          <div class="al-row"><span class="al-swatch" style="background:#38bdf8"></span><span class="al-label">Above normal (+10 to +25%)</span></div>
          <div class="al-row"><span class="al-swatch" style="background:#1d4ed8"></span><span class="al-label">Well above normal (&gt;+25%)</span></div>
        </div>
      </div>"""

# ── Patch 4: view mode toggle before Boundaries section ──────────────────────
BOUNDARIES_OLD = """      <div class="sidebar-section">
        <div class="section-label">Boundaries</div>"""

BOUNDARIES_NEW = """      <div class="sidebar-section">
        <div class="section-label">View Mode</div>
        <div style="display:flex; gap:0.4rem;">
          <button class="layer-btn active" id="btn-mode-rainfall" onclick="setViewMode('rainfall')" style="flex:1;text-align:center;">Rainfall</button>
          <button class="layer-btn" id="btn-mode-anomaly" onclick="setViewMode('anomaly')" style="flex:1;text-align:center;">Anomaly vs LTM</button>
        </div>
      </div>

      <div class="sidebar-section">
        <div class="section-label">Boundaries</div>"""

# ── Patch 5: JS constants after BOUNDARY_STYLES ──────────────────────────────
BOUNDARY_STYLES_END = """    };

    async function loadBoundary(level) {"""

JS_CONSTS = """    };

    const ANOMALY_COLORS = {
      severe_drought:    '#b91c1c',
      moderate_drought:  '#ef4444',
      mild_drought:      '#f97316',
      near_normal:       '#64748b',
      above_normal:      '#38bdf8',
      well_above_normal: '#1d4ed8',
      no_baseline:       '#1e293b',
    };

    const ANOMALY_LABELS = {
      severe_drought:    'Severe drought',
      moderate_drought:  'Moderate drought',
      mild_drought:      'Mild drought',
      near_normal:       'Near normal',
      above_normal:      'Above normal',
      well_above_normal: 'Well above normal',
    };

    let viewMode = 'rainfall';
    let currentAnomalyData = null;
    const anomalyCache = {};

    async function loadBoundary(level) {"""

# ── Patch 6: replace buildTooltipContent ─────────────────────────────────────
# We replace from `function buildTooltipContent` up to and including its closing `}`
# The closing `}` is identified by the line that follows it (refreshTooltips)
BUILD_TOOLTIP_PATTERN = re.compile(
    r"    function buildTooltipContent\(feature, level, periodLabel\) \{.*?\n    \}(?=\n\n    function refreshTooltips)",
    re.DOTALL
)

def build_tooltip_func(anomaly_api_path: str) -> str:
    return '''    function buildTooltipContent(feature, level, periodLabel) {
      const p = feature.properties;
      const key = (level === 'districts' && p.region)
        ? p.name + '|' + p.region
        : p.name;

      // ── Anomaly mode ──
      if (viewMode === 'anomaly' && currentAnomalyData) {
        const entry = (currentAnomalyData.anomaly[level] || {})[key];
        const catColor = ANOMALY_COLORS[(entry && entry.category) || 'no_baseline'];
        const catLabel = ANOMALY_LABELS[(entry && entry.category)] || 'No data';

        if (level !== 'districts') {
          if (!entry) return p.name + ' Region\\n\\nNo anomaly data';
          const sign = entry.anomaly_pct >= 0 ? '+' : '';
          return p.name + ' Region\\n\\n' + periodLabel +
            '\\nActual: ' + entry.actual + ' mm' +
            '\\nLTM:    ' + entry.ltm    + ' mm' +
            '\\nAnomaly: ' + sign + entry.anomaly_pct + '%' +
            '\\n' + catLabel;
        }
        const sign = entry && entry.anomaly_pct >= 0 ? '+' : '';
        return (
          '<div class="tt-wrap">' +
          '<div class="tt-name">' + p.name + '</div>' +
          '<div class="tt-region">' + p.region + ' Region</div>' +
          '<hr class="tt-divider">' +
          (entry
            ? '<div class="tt-period">' + periodLabel + ' vs 1991–2020 LTM</div>' +
              '<div class="tt-stat">Actual:&nbsp; ' + entry.actual + ' mm</div>' +
              '<div class="tt-stat">LTM:&nbsp;&nbsp;&nbsp;&nbsp; ' + entry.ltm + ' mm</div>' +
              '<div class="tt-stat">Anomaly: <strong style="color:' + catColor + '">' + sign + entry.anomaly_pct + '%</strong></div>' +
              (entry.z_score !== null ? '<div class="tt-stat" style="color:#64748b">z = ' + entry.z_score + '</div>' : '') +
              '<div class="infra-badge" style="margin-top:0.3rem;background:' + catColor + '22;color:' + catColor + ';border:1px solid ' + catColor + '44">' + catLabel + '</div>'
            : '<div class="tt-stat" style="color:#64748b">No anomaly data</div>') +
          '</div>'
        );
      }

      // ── Rainfall mode ──
      const stats = activeLayerStats[level] || {};
      const areaStats = stats[key];

      if (level !== 'districts') {
        const header = p.name + ' Region';
        if (!areaStats || areaStats.mean === null) return header + '\\n\\nNo data';
        return (
          header +
          '\\n\\n' + periodLabel +
          '\\nMean: ' + areaStats.mean + ' mm' +
          '\\nMax:  ' + areaStats.max  + ' mm' +
          '\\nMin:  ' + areaStats.min  + ' mm'
        );
      }

      const statsHtml = (!areaStats || areaStats.mean === null)
        ? '<div class="tt-stat" style="color:#64748b">No rainfall data</div>'
        : '<div class="tt-period">' + periodLabel + '</div>' +
          '<div class="tt-stat">Mean: ' + areaStats.mean + ' mm</div>' +
          '<div class="tt-stat">Max:&nbsp; ' + areaStats.max  + ' mm</div>' +
          '<div class="tt-stat">Min:&nbsp; ' + areaStats.min  + ' mm</div>';

      const infra = infraData[key];
      let infraHtml = '';
      if (infra) {
        const ratingClass = infra.drainage_rating.toLowerCase().replace(/ /g, '-');
        const badgeClass = ratingClass === 'none' ? 'none-known' : ratingClass;
        infraHtml =
          '<hr class="tt-divider">' +
          '<span class="infra-badge ' + badgeClass + '">' + infra.drainage_rating + ' Drainage</span>' +
          (infra.ift_pct != null
            ? '<div class="infra-ift">Fails ~+' + infra.ift_pct + '% above LTM</div>'
            : '<div class="infra-ift">IFT: pending data</div>');
      }

      return (
        '<div class="tt-wrap">' +
        '<div class="tt-name">' + p.name + '</div>' +
        '<div class="tt-region">' + p.region + ' Region</div>' +
        '<hr class="tt-divider">' +
        statsHtml +
        infraHtml +
        '</div>'
      );
    }'''

# ── Patch 7: displayLayer — add anomaly reload at end ────────────────────────
DISPLAYLAYER_OLD = """      // Sync layer list highlight
      document.querySelectorAll('.layer-btn[data-index]').forEach(btn => {
        const idx = parseInt(btn.dataset.index, 10);
        btn.classList.toggle('active', layers[idx] === layer);
      });
    }"""

DISPLAYLAYER_NEW = """      // Sync layer list highlight
      document.querySelectorAll('.layer-btn[data-index]').forEach(btn => {
        const idx = parseInt(btn.dataset.index, 10);
        btn.classList.toggle('active', layers[idx] === layer);
      });

      // In anomaly mode, reload anomaly for the newly selected month
      if (viewMode === 'anomaly') {
        if (currentOverlay) currentOverlay.setOpacity(0);
        loadAndApplyAnomaly(layer.year, layer.month);
      }
    }"""

# ── Patch 8: anomaly functions before loadLayers ─────────────────────────────
LOADLAYERS_OLD = "    async function loadLayers() {"


def anomaly_functions(anomaly_api_path: str) -> str:
    return f"""    // ── Anomaly layer functions ────────────────────────────────────────────

    function setViewMode(mode) {{
      viewMode = mode;
      document.getElementById('btn-mode-rainfall').classList.toggle('active', mode === 'rainfall');
      document.getElementById('btn-mode-anomaly').classList.toggle('active', mode === 'anomaly');
      document.getElementById('rainfall-legend-section').style.display  = mode === 'rainfall' ? '' : 'none';
      document.getElementById('anomaly-legend-section').style.display   = mode === 'anomaly'  ? '' : 'none';
      document.getElementById('rainfall-stats-rows').style.display      = mode === 'rainfall' ? '' : 'none';
      document.getElementById('anomaly-stats-rows').style.display       = mode === 'anomaly'  ? '' : 'none';

      const activeLayer = layers.length
        ? (playerLayers.length ? playerLayers[playerIndex] : layers[layers.length - 1])
        : null;

      if (mode === 'anomaly') {{
        if (currentOverlay) currentOverlay.setOpacity(0);
        if (activeLayer) loadAndApplyAnomaly(activeLayer.year, activeLayer.month);
      }} else {{
        if (currentOverlay) currentOverlay.setOpacity(0.8);
        clearAnomalyStyle('regions');
        clearAnomalyStyle('districts');
        currentAnomalyData = null;
        const label = document.getElementById('layer-label').textContent;
        refreshTooltips('regions', label);
        refreshTooltips('districts', label);
      }}
    }}

    async function loadAndApplyAnomaly(year, month) {{
      const cacheKey = year + '-' + String(month).padStart(2, '0');
      if (!anomalyCache[cacheKey]) {{
        try {{
          const res = await fetch('{anomaly_api_path}' + year + '/' + month);
          if (!res.ok) throw new Error(res.status);
          anomalyCache[cacheKey] = await res.json();
        }} catch (e) {{
          console.warn('No anomaly data for', cacheKey, e);
          return;
        }}
      }}
      currentAnomalyData = anomalyCache[cacheKey];

      if (!boundaryLayers['districts']) {{
        await showBoundary('districts', document.getElementById('layer-label').textContent);
      }}

      applyAnomalyStyle('regions');
      applyAnomalyStyle('districts');

      const label = document.getElementById('layer-label').textContent;
      refreshTooltips('regions', label);
      refreshTooltips('districts', label);
      updateAnomalySummary();
    }}

    function applyAnomalyStyle(level) {{
      if (!boundaryLayers[level] || !currentAnomalyData) return;
      const anomalyLevel = currentAnomalyData.anomaly[level] || {{}};
      boundaryLayers[level].eachLayer(featureLayer => {{
        const p   = featureLayer.feature.properties;
        const key = (level === 'districts' && p.region) ? p.name + '|' + p.region : p.name;
        const entry = anomalyLevel[key];
        const cat   = (entry && entry.category) || 'no_baseline';
        featureLayer.setStyle({{
          fillColor:   ANOMALY_COLORS[cat],
          fillOpacity: 0.72,
          color:       level === 'regions' ? '#ffffff' : '#94a3b8',
          weight:      level === 'regions' ? 1.8 : 0.6,
          opacity:     0.8,
        }});
      }});
    }}

    function clearAnomalyStyle(level) {{
      if (!boundaryLayers[level]) return;
      boundaryLayers[level].setStyle(BOUNDARY_STYLES[level]);
    }}

    function updateAnomalySummary() {{
      if (!currentAnomalyData) return;
      const districtData = currentAnomalyData.anomaly.districts || {{}};
      const counts = {{}};
      Object.values(districtData).forEach(v => {{
        counts[v.category] = (counts[v.category] || 0) + 1;
      }});
      const total = Object.values(counts).reduce((a, b) => a + b, 0);
      if (!total) return;
      const droughtN = (counts.severe_drought || 0) + (counts.moderate_drought || 0) + (counts.mild_drought || 0);
      const wetN     = (counts.above_normal || 0) + (counts.well_above_normal || 0);
      document.getElementById('anomaly-drought-pct').textContent =
        Math.round(droughtN / total * 100) + '% of districts';
      document.getElementById('anomaly-wet-pct').textContent =
        Math.round(wetN / total * 100) + '% of districts';
    }}

    async function loadLayers() {{"""


def patch_page(html: str, anomaly_api_path: str) -> tuple[str, list]:
    applied = []
    skipped = []

    def apply(name, old, new):
        if 'btn-mode-rainfall' in html and name in ('patch4', 'patch8'):
            skipped.append(name + ' (already patched)')
            return html
        if old in html:
            applied.append(name)
            return html.replace(old, new, 1)
        skipped.append(name + ' (anchor not found)')
        return html

    patched = html

    patched = apply('patch1_css',     CSS_ANCHOR,          CSS_INSERT)
    patched = apply('patch2_stats',   STATS_OLD,           STATS_NEW)
    patched = apply('patch3_legend',  LEGEND_OLD,          LEGEND_NEW)
    patched = apply('patch4_viewmode',BOUNDARIES_OLD,      BOUNDARIES_NEW)
    patched = apply('patch5_jsvars',  BOUNDARY_STYLES_END, JS_CONSTS)
    patched = apply('patch7_displaylayer', DISPLAYLAYER_OLD, DISPLAYLAYER_NEW)
    patched = apply('patch8_functions', LOADLAYERS_OLD, anomaly_functions(anomaly_api_path))

    # Patch 6: replace buildTooltipContent via regex
    if 'btn-mode-rainfall' not in html:  # only if not already patched
        new_html, count = BUILD_TOOLTIP_PATTERN.subn(build_tooltip_func(anomaly_api_path), patched)
        if count:
            applied.append('patch6_tooltip')
            patched = new_html
        else:
            skipped.append('patch6_tooltip (regex no match)')

    return patched, applied, skipped


if __name__ == '__main__':
    for country, api_path in COUNTRIES:
        path = BASE / country / "flood" / "index.html"
        if not path.exists():
            print(f"SKIP {country} — file not found")
            continue

        html = path.read_text()
        patched, applied, skipped = patch_page(html, api_path)

        path.write_text(patched)
        print(f"{country}: applied={applied}, skipped={skipped}")

    print("\nDone.")
