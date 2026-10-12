/**
 * LifeSync — weather-charts.js  (Enhanced v2)
 *
 * Rendering engine for the Weather page charts:
 *  - Line charts (Overview, Precipitation, Wind, Humidity, Pressure, UV, Visibility)
 *  - Bar chart (Air Quality)
 *
 * New in v2:
 *  • 5 evenly-spaced Y-axis ticks with minor grid lines
 *  • Denser X-axis time labels (every 2 h)
 *  • Day/Night background bands (uses sunrise/sunset from <body> data attrs)
 *  • Per-tab risk-zone bands (UV danger levels, humidity comfort, wind thresholds, etc.)
 *  • Min/Max flag annotations on the line
 *  • Pulsing "current hour" now-line (today only)
 *  • Summary stat strip (avg · min · max · extra) above the SVG
 *  • Enriched hover tooltip: trend arrow (↑/→/↓), "Highest of the day" context
 *  • Sparklines injected into each .hero-stat[data-sparkline-key] card
 *  • Wind compass rose (Wind tab)
 *  • AQI threshold lines with labels (Air Quality tab)
 */
(function () {
  'use strict';

  // -------------------------------------------------------------------------
  // Layout constants (SVG coordinate space)
  // -------------------------------------------------------------------------
  const VB = { width: 1000, height: 300, padLeft: 48, padRight: 56, padTop: 22, padBottom: 34 };

  // -------------------------------------------------------------------------
  // Tab configurations
  // -------------------------------------------------------------------------
  const LINE_TABS = {
    overview: {
      unit: '\u00b0',
      series: [
        { key: 'temp',       label: 'Temperature', color: 'var(--chart-1)', isTemp: true },
        { key: 'feels_like', label: 'Feels like',  color: 'var(--chart-2)', isTemp: true },
      ],
      fill: true,
      summaryExtra: (data) => {
        const diurnal = Math.max(...data.map(d => d.temp)) - Math.min(...data.map(d => d.temp));
        return `Diurnal range: ${Math.round(diurnal)}\u00b0`;
      },
    },
    precipitation: {
      unit: 'mm',
      series: [{ key: 'precip_mm', label: 'Precipitation', color: 'var(--chart-1)', decimals: 1 }],
      fill: true,
      secondaryKey: 'precip_prob',
      secondaryLabel: 'Chance of rain',
      secondaryUnit: '%',
      summaryExtra: (data) => {
        const total = data.reduce((s, d) => s + (d.precip_mm || 0), 0);
        const peakHour = data.reduce((best, d) => (d.precip_mm || 0) > (best.precip_mm || 0) ? d : best, data[0]);
        return `Total: ${total.toFixed(1)} mm • Peak at ${peakHour.time}`;
      },
    },
    wind: {
      unit: 'km/h',
      series: [
        { key: 'wind_speed', label: 'Wind speed', color: 'var(--chart-1)' },
        { key: 'wind_gust',  label: 'Gusts',      color: 'var(--chart-2)' },
      ],
      dirKey: 'wind_dir',
      summaryExtra: (data) => {
        const dirs = data.map(d => d.wind_dir).filter(v => v !== null && v !== undefined);
        if (!dirs.length) return '';
        const avg = dirs.reduce((s, v) => s + v, 0) / dirs.length;
        return `Dom. dir: ${windDirLabel(avg)}`;
      },
    },
    humidity: {
      unit: '%',
      series: [{ key: 'humidity', label: 'Humidity', color: 'var(--chart-1)' }],
      fill: true,
    },
    pressure: {
      unit: 'hPa',
      series: [{ key: 'pressure', label: 'Pressure', color: 'var(--chart-1)' }],
      summaryExtra: (data) => {
        const vals = data.map(d => d.pressure).filter(v => v);
        if (!vals.length) return '';
        const trend = vals[vals.length - 1] - vals[0];
        return trend > 1 ? '\u2191 Rising' : trend < -1 ? '\u2193 Falling' : '\u2192 Steady';
      },
    },
    uv: {
      unit: '',
      series: [{ key: 'uv', label: 'UV Index', color: 'var(--chart-1)', decimals: 1 }],
      fill: true,
      summaryExtra: (data) => {
        const peak = Math.max(...data.map(d => d.uv || 0));
        const cat = peak >= 11 ? 'Extreme' : peak >= 8 ? 'Very High' : peak >= 6 ? 'High' : peak >= 3 ? 'Moderate' : 'Low';
        return `Peak category: ${cat}`;
      },
    },
    visibility: {
      unit: 'km',
      series: [{ key: 'visibility_km', label: 'Visibility', color: 'var(--chart-1)', decimals: 1 }],
      fill: true,
    },
  };

  // Zone bands per tab: [minValue, maxValue, cssColor, alpha, label]
  // null means "extend to chart min" / "extend to chart max"
  const ZONE_BANDS = {
    uv: [
      [0,  3,  '#22c55e', 0.10, 'Low'],
      [3,  6,  '#eab308', 0.12, 'Moderate'],
      [6,  8,  '#f97316', 0.14, 'High'],
      [8,  11, '#ef4444', 0.16, 'V.High'],
      [11, null, '#a855f7', 0.18, 'Extreme'],
    ],
    humidity: [
      [0,  30, '#f97316', 0.10, 'Dry'],
      [30, 70, '#22c55e', 0.08, 'Comfort'],
      [70, 100,'#3b82f6', 0.12, 'Humid'],
    ],
    wind: [
      [50, 75,  '#f97316', 0.10, 'Strong'],
      [75, null,'#ef4444', 0.14, 'Storm'],
    ],
    pressure: [
      [null, 980,  '#3b82f6', 0.12, 'Low'],
      [1025, null, '#ef4444', 0.12, 'High'],
    ],
    precipitation: [
      [2, null, '#3b82f6', 0.12, 'Heavy'],
    ],
  };

  const AQI_THRESHOLDS = [
    { value: 50,  color: '#22c55e', label: 'Good' },
    { value: 100, color: '#eab308', label: 'Moderate' },
    { value: 150, color: '#f97316', label: 'Unhealthy*' },
    { value: 200, color: '#ef4444', label: 'Unhealthy' },
    { value: 300, color: '#a855f7', label: 'V.Unhealthy' },
  ];

  const POLLUTANTS = {
    aqi:  { label: 'AQI',  unit: '' },
    pm2_5:{ label: 'PM 2.5', unit: '\u00b5g/m\u00b3' },
    pm10: { label: 'PM 10',  unit: '\u00b5g/m\u00b3' },
    o3:   { label: 'O\u2083', unit: '\u00b5g/m\u00b3' },
    no2:  { label: 'NO\u2082',unit: '\u00b5g/m\u00b3' },
    so2:  { label: 'SO\u2082',unit: '\u00b5g/m\u00b3' },
    co:   { label: 'CO',    unit: '\u00b5g/m\u00b3' },
  };

  const WIND_COMPASS = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];

  // -------------------------------------------------------------------------
  // Utility helpers
  // -------------------------------------------------------------------------
  function toF(c) { return Math.round((c * 9) / 5 + 32); }
  function windDirLabel(deg) {
    if (deg === null || deg === undefined) return '';
    return WIND_COMPASS[Math.round(deg / 22.5) % 16];
  }
  function readJSON(id, fallback) {
    const el = document.getElementById(id);
    if (!el) return fallback;
    try {
      const parsed = JSON.parse(el.textContent);
      return Array.isArray(parsed) ? parsed : fallback;
    } catch (e) { return fallback; }
  }
  function fmt(value, decimals) {
    if (value === null || value === undefined || Number.isNaN(value)) return '\u2013';
    return decimals != null ? value.toFixed(decimals) : String(Math.round(value));
  }
  function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

  // Parse a time string like "06:00" into fractional hours
  function timeToHours(str) {
    if (!str) return null;
    const [h, m] = str.split(':').map(Number);
    return h + (m || 0) / 60;
  }

  // -------------------------------------------------------------------------
  // Path helpers
  // -------------------------------------------------------------------------
  function buildSmoothPath(pts) {
    if (!pts.length) return '';
    if (pts.length === 1) return `M ${pts[0].x} ${pts[0].y}`;
    if (pts.length === 2) return `M ${pts[0].x} ${pts[0].y} L ${pts[1].x} ${pts[1].y}`;
    let d = `M ${pts[0].x} ${pts[0].y}`;
    for (let i = 1; i < pts.length - 1; i++) {
      const midX = (pts[i].x + pts[i + 1].x) / 2;
      const midY = (pts[i].y + pts[i + 1].y) / 2;
      d += ` Q ${pts[i].x} ${pts[i].y} ${midX} ${midY}`;
    }
    const p2 = pts[pts.length - 2];
    const p1 = pts[pts.length - 1];
    d += ` Q ${p2.x} ${p2.y} ${p1.x} ${p1.y}`;
    return d;
  }

  // -------------------------------------------------------------------------
  // Scale factory
  // -------------------------------------------------------------------------
  function makeScales(n, min, max) {
    const left   = VB.padLeft;
    const right  = VB.width - VB.padRight;
    const top    = VB.padTop;
    const bottom = VB.height - VB.padBottom;
    const span   = (max - min) || 1;
    const stepX  = n > 1 ? (right - left) / (n - 1) : 0;
    return {
      x:      (i) => left + i * stepX,
      y:      (v) => bottom - ((v - min) / span) * (bottom - top),
      stepX, left, right, top, bottom, min, max, span,
    };
  }

  // -------------------------------------------------------------------------
  // Y-ticks: 5 evenly spaced, rounded to clean numbers
  // -------------------------------------------------------------------------
  function buildYTicks(min, max, count = 5) {
    const span = max - min;
    const raw  = span / (count - 1);
    // Pick a nice step
    const mag  = Math.pow(10, Math.floor(Math.log10(raw)));
    const nice = [1, 2, 2.5, 5, 10].map(f => f * mag).find(f => f >= raw) || raw;
    const lo   = Math.floor(min / nice) * nice;
    const ticks = [];
    for (let t = lo; t <= max + nice * 0.01; t += nice) {
      if (t >= min - nice * 0.01) ticks.push(parseFloat(t.toFixed(6)));
    }
    // Trim to count if over
    while (ticks.length > count + 1) ticks.splice(Math.floor(ticks.length / 2), 1);
    return ticks;
  }

  // -------------------------------------------------------------------------
  // Grid + axis (5 Y-ticks, every-2h X labels)
  // -------------------------------------------------------------------------
  function gridAndAxisSvg(yTicks, data, scales) {
    let s = '';
    // Y ticks + horizontal grid
    yTicks.forEach((tv, ti) => {
      const y = scales.y(tv);
      if (y < scales.top - 2 || y > scales.bottom + 2) return;
      const isMid = ti > 0 && ti < yTicks.length - 1;
      s += `<line class="chart-grid-line" x1="${scales.left}" y1="${y}" x2="${scales.right}" y2="${y}" opacity="${isMid ? 0.5 : 0.8}"/>`;
      s += `<text class="chart-axis-label" x="${scales.left - 7}" y="${y + 4}" text-anchor="end">${Math.round(tv)}</text>`;
    });
    // X labels every 2 hours (or every 3 if dense)
    const step = data.length > 16 ? 3 : 2;
    data.forEach((d, i) => {
      const h = d.hour !== undefined ? d.hour : i;
      if (h % step !== 0) return;
      const x = scales.x(i);
      // Tick mark
      s += `<line stroke="var(--line)" stroke-width="1" x1="${x}" y1="${scales.bottom}" x2="${x}" y2="${scales.bottom + 5}"/>`;
      s += `<text class="chart-axis-label" x="${x}" y="${VB.height - 6}" text-anchor="middle">${d.time || ''}</text>`;
    });
    return s;
  }

  // -------------------------------------------------------------------------
  // Day / Night background bands
  // -------------------------------------------------------------------------
  function renderDayNightBands(data, scales) {
    const body = document.body;
    const srStr = body.dataset.sunrise;
    const ssStr = body.dataset.sunset;
    const sunrise = timeToHours(srStr);
    const sunset  = timeToHours(ssStr);
    if (sunrise === null || sunset === null) return '';

    let s = '';
    data.forEach((d, i) => {
      const h = d.hour !== undefined ? d.hour : i;
      const isNight = h < sunrise || h >= sunset;
      if (!isNight) return;
      const x = scales.x(i) - scales.stepX / 2;
      const w = scales.stepX;
      s += `<rect x="${x}" y="${scales.top}" width="${w}" height="${scales.bottom - scales.top}" fill="rgba(15,23,42,0.08)" />`;
    });
    // Label bands
    if (sunrise < data.length) {
      const ri = data.findIndex(d => (d.hour !== undefined ? d.hour : 0) >= Math.ceil(sunrise));
      if (ri >= 0) {
        s += `<text class="chart-axis-label" x="${scales.x(ri) + 4}" y="${scales.top + 12}" fill="var(--accent)" opacity="0.6" font-size="9">\u2600\uFE0F ${srStr}</text>`;
      }
    }
    if (sunset < data.length) {
      const si = data.findIndex(d => (d.hour !== undefined ? d.hour : 0) >= Math.floor(sunset));
      if (si >= 0) {
        s += `<text class="chart-axis-label" x="${scales.x(si) + 4}" y="${scales.top + 12}" fill="var(--ink-soft)" opacity="0.6" font-size="9">\uD83C\uDF19 ${ssStr}</text>`;
      }
    }
    return s;
  }

  // -------------------------------------------------------------------------
  // Zone bands (risk/comfort regions)
  // -------------------------------------------------------------------------
  function renderZoneBands(tabKey, scales) {
    const bands = ZONE_BANDS[tabKey];
    if (!bands) return '';
    let s = '';
    bands.forEach(([lo, hi, color, alpha, label]) => {
      const yTop    = scales.y(hi !== null ? Math.min(hi, scales.max) : scales.max);
      const yBottom = scales.y(lo !== null ? Math.max(lo, scales.min) : scales.min);
      if (yTop >= yBottom) return;        // band is out of chart range
      if (yTop > scales.bottom) return;
      if (yBottom < scales.top) return;
      const clampedTop    = Math.max(yTop, scales.top);
      const clampedBottom = Math.min(yBottom, scales.bottom);
      s += `<rect x="${scales.left}" y="${clampedTop}" width="${scales.right - scales.left}" height="${clampedBottom - clampedTop}" fill="${color}" opacity="${alpha}" />`;
      // Dashed boundary line at top of zone
      s += `<line stroke="${color}" stroke-width="1" stroke-dasharray="4 3" opacity="0.5" x1="${scales.left}" y1="${clampedTop}" x2="${scales.right}" y2="${clampedTop}" />`;
      // Zone label on the right
      const labelY = clamp((clampedTop + clampedBottom) / 2 + 4, scales.top + 8, scales.bottom - 2);
      s += `<text class="chart-zone-label" x="${scales.right + 4}" y="${labelY}" fill="${color}">${label}</text>`;
    });
    return s;
  }

  // -------------------------------------------------------------------------
  // Min / Max flag annotations
  // -------------------------------------------------------------------------
  function renderMinMaxFlags(pts, vals, color, unit, decimals) {
    if (!pts.length) return '';
    const maxIdx = vals.indexOf(Math.max(...vals));
    const minIdx = vals.indexOf(Math.min(...vals));
    let s = '';

    function flag(pt, val, isMax) {
      const label = `${isMax ? '\u25b2' : '\u25bc'} ${fmt(val, decimals)}${unit}`;
      const tx = clamp(pt.x, VB.padLeft + 10, VB.width - VB.padRight - 40);
      const ty = isMax ? pt.y - 10 : pt.y + 18;
      const clampedTy = clamp(ty, VB.padTop + 4, VB.height - VB.padBottom - 4);
      // Pill background
      const approxW = label.length * 6 + 10;
      s += `<rect x="${tx - 2}" y="${clampedTy - 11}" width="${approxW}" height="14" rx="3" fill="${color}" opacity="0.15"/>`;
      s += `<text class="chart-minmax-flag" x="${tx}" y="${clampedTy}" fill="${color}">${label}</text>`;
      // Dot
      s += `<circle cx="${pt.x}" cy="${pt.y}" r="4" fill="${color}" stroke="var(--surface-solid)" stroke-width="2"/>`;
    }

    flag(pts[maxIdx], vals[maxIdx], true);
    if (minIdx !== maxIdx) flag(pts[minIdx], vals[minIdx], false);
    return s;
  }

  // -------------------------------------------------------------------------
  // "Now" pulsing line
  // -------------------------------------------------------------------------
  function renderNowLine(nowIdx, scales, data) {
    if (nowIdx < 0) return '';
    const x = scales.x(nowIdx);
    const nowEntry = data && data[nowIdx];
    const timeText = nowEntry ? `NOW • ${nowEntry.time}` : 'NOW';
    const pillW = Math.max(40, timeText.length * 5.6 + 12);
    return `<line class="chart-now-line" x1="${x}" y1="${scales.top}" x2="${x}" y2="${scales.bottom}" stroke="var(--accent)" stroke-width="2"/>
            <rect x="${x - pillW / 2}" y="${scales.top - 16}" width="${pillW}" height="14" rx="4" fill="var(--accent)" opacity="0.22"/>
            <text class="chart-axis-label" x="${x}" y="${scales.top - 6}" text-anchor="middle" fill="var(--accent)" font-weight="700" font-size="8.5">${timeText}</text>`;
  }

  // -------------------------------------------------------------------------
  // Area fill with gradient
  // -------------------------------------------------------------------------
  function renderAreaFill(pts, scales, color, gradId) {
    const path = buildSmoothPath(pts);
    const areaPath = `${path} L ${pts[pts.length - 1].x} ${scales.bottom} L ${pts[0].x} ${scales.bottom} Z`;
    return `<defs><linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${color}" stop-opacity="0.32"/>
      <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
    </linearGradient></defs>
    <path d="${areaPath}" fill="url(#${gradId})" stroke="none"/>`;
  }

  // -------------------------------------------------------------------------
  // Summary stat row
  // -------------------------------------------------------------------------
  function buildSummaryRow(summaryEl, data, cfg, unitSystem) {
    if (!summaryEl || !data.length) return;
    const s = cfg.series[0];
    const vals = data.map(d => s.isTemp && unitSystem === 'F' ? toF(d[s.key]) : d[s.key])
                     .filter(v => v !== null && v !== undefined && !Number.isNaN(v));
    if (!vals.length) { summaryEl.innerHTML = ''; return; }
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    const unit = s.isTemp ? (unitSystem === 'F' ? '\u00b0F' : '\u00b0C') : cfg.unit;
    const dec  = s.decimals != null ? s.decimals : 0;

    const stats = [
      { icon: '\u2205', label: 'Avg', value: `${fmt(avg, dec)}${unit}` },
      { icon: '\u25bc', label: 'Min', value: `${fmt(min, dec)}${unit}` },
      { icon: '\u25b2', label: 'Max', value: `${fmt(max, dec)}${unit}` },
    ];
    if (cfg.summaryExtra) {
      const extra = cfg.summaryExtra(data);
      if (extra) stats.push({ icon: '\u2139\uFE0F', label: '', value: extra });
    }

    summaryEl.innerHTML = stats.map(st =>
      `<span class="chart-summary-stat">
        <span class="cs-icon">${st.icon}</span>
        ${st.label ? `<span class="cs-label">${st.label}</span>` : ''}
        <span class="cs-value">${st.value}</span>
      </span>`
    ).join('');
  }

  function buildSummaryRowAqi(summaryEl, data, pollutantKey) {
    if (!summaryEl || !data.length) return;
    const vals = data.map(d => d[pollutantKey]).filter(v => v !== null && v !== undefined);
    if (!vals.length) { summaryEl.innerHTML = ''; return; }
    const avg  = vals.reduce((a, b) => a + b, 0) / vals.length;
    const max  = Math.max(...vals);
    const cfg  = POLLUTANTS[pollutantKey];
    summaryEl.innerHTML = [
      `<span class="chart-summary-stat"><span class="cs-icon">\u2205</span><span class="cs-label">Avg</span><span class="cs-value">${fmt(avg)} ${cfg.unit}</span></span>`,
      `<span class="chart-summary-stat"><span class="cs-icon">\u25b2</span><span class="cs-label">Peak</span><span class="cs-value">${fmt(max)} ${cfg.unit}</span></span>`,
    ].join('');
  }

  // -------------------------------------------------------------------------
  // Enriched tooltip (trend arrow + context)
  // -------------------------------------------------------------------------
  function buildTrendBadge(curr, prev) {
    if (prev === null || prev === undefined) return '';
    const delta = curr - prev;
    const pct   = Math.abs(delta / (prev || 1));
    if (pct < 0.01 || Math.abs(delta) < 0.5) return '<span class="tt-trend flat">\u2192</span>';
    return delta > 0
      ? '<span class="tt-trend up">\u2191</span>'
      : '<span class="tt-trend down">\u2193</span>';
  }

  function buildContextNote(val, vals) {
    const max = Math.max(...vals);
    const min = Math.min(...vals);
    if (val === max) return 'Highest of the day';
    if (val === min) return 'Lowest of the day';
    const pct = (val - min) / (max - min);
    if (pct >= 0.8) return 'Near daily high';
    if (pct <= 0.2) return 'Near daily low';
    return null;
  }

  function showTooltip(tooltipEl, timeLabel, rows, contextNote, isCurrentHour) {
    if (!tooltipEl) return;
    let html = `<div class="tt-time"><i class="bi bi-clock me-1 text-warning"></i>${timeLabel}`;
    if (isCurrentHour) {
      html += ` <span class="badge bg-warning text-dark ms-auto" style="font-size:0.65rem; padding: 0.15rem 0.4rem; font-weight:700;">CURRENT HOUR</span>`;
    }
    html += `</div>`;
    html += rows.map(r =>
      `<div class="tt-row"><span class="legend-swatch" style="background:${r.color}"></span>${r.label}: <strong>${r.text}</strong>${r.badge || ''}</div>`
    ).join('');
    if (contextNote) html += `<div class="tt-context">${contextNote}</div>`;
    tooltipEl.innerHTML = html;
    tooltipEl.classList.add('visible');
  }
  function hideTooltip(tooltipEl) {
    if (tooltipEl) tooltipEl.classList.remove('visible');
  }

  // -------------------------------------------------------------------------
  // Sparklines
  // -------------------------------------------------------------------------
  function renderSparklines(data) {
    document.querySelectorAll('[data-sparkline-key]').forEach(card => {
      const key   = card.dataset.sparklineKey;
      const vals  = data.map(d => d[key]).filter(v => v !== null && v !== undefined && !Number.isNaN(v));
      if (vals.length < 2) return;
      const existing = card.querySelector('.chart-sparkline-wrap');
      if (existing) existing.remove();

      const W = 200, H = 28, pad = 2;
      const min = Math.min(...vals);
      const max = Math.max(...vals);
      const span = (max - min) || 1;
      const sx   = (i) => pad + (i / (vals.length - 1)) * (W - pad * 2);
      const sy   = (v) => H - pad - ((v - min) / span) * (H - pad * 2);

      const pts = vals.map((v, i) => ({ x: sx(i), y: sy(v) }));
      const linePath = buildSmoothPath(pts);
      const areaPath = `${linePath} L ${sx(vals.length - 1)} ${H} L ${sx(0)} ${H} Z`;

      const color = key === 'uv' ? 'var(--accent)' : key === 'precip_mm' ? '#3b82f6' : 'var(--chart-1)';
      const gradId = `spark-${key}`;

      const wrap = document.createElement('div');
      wrap.className = 'chart-sparkline-wrap';
      wrap.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        <defs><linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${color}" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
        </linearGradient></defs>
        <path d="${areaPath}" fill="url(#${gradId})" stroke="none"/>
        <path d="${linePath}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round"/>
      </svg>`;
      card.appendChild(wrap);
    });
  }

  // -------------------------------------------------------------------------
  // Wind compass rose
  // -------------------------------------------------------------------------
  function renderWindRose(wrapper, data) {
    if (!wrapper) return;
    const dirs = data.map(d => d.wind_dir).filter(v => v !== null && v !== undefined);
    if (!dirs.length) { wrapper.style.display = 'none'; return; }
    const avg = dirs.reduce((a, b) => a + b, 0) / dirs.length;
    const rad = (avg - 90) * Math.PI / 180;
    const cx = 32, cy = 32, r = 24, ar = 16;
    const ax = cx + Math.cos(rad) * ar;
    const ay = cy + Math.sin(rad) * ar;

    wrapper.style.display = 'block';
    wrapper.innerHTML = `<svg viewBox="0 0 64 64">
      <!-- Circle -->
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="var(--surface)" stroke="var(--line)" stroke-width="1.5"/>
      <!-- Cardinal labels -->
      <text x="32" y="8"  text-anchor="middle" font-size="8" fill="var(--ink-soft)" font-weight="700">N</text>
      <text x="32" y="60" text-anchor="middle" font-size="8" fill="var(--ink-soft)" font-weight="700">S</text>
      <text x="4"  y="35" text-anchor="middle" font-size="8" fill="var(--ink-soft)" font-weight="700">W</text>
      <text x="60" y="35" text-anchor="middle" font-size="8" fill="var(--ink-soft)" font-weight="700">E</text>
      <!-- Arrow -->
      <line x1="${cx}" y1="${cy}" x2="${ax}" y2="${ay}" stroke="var(--accent)" stroke-width="2.5" stroke-linecap="round"/>
      <circle cx="${ax}" cy="${ay}" r="3" fill="var(--accent)"/>
      <!-- Center dot -->
      <circle cx="${cx}" cy="${cy}" r="2.5" fill="var(--ink-soft)"/>
    </svg>`;
  }

  // -------------------------------------------------------------------------
  // AQI threshold lines
  // -------------------------------------------------------------------------
  function renderAqiThresholdLines(scales) {
    let s = '';
    AQI_THRESHOLDS.forEach(({ value, color, label }) => {
      if (value < scales.min || value > scales.max) return;
      const y = scales.y(value);
      s += `<line class="chart-aqi-threshold" x1="${scales.left}" y1="${y}" x2="${scales.right}" y2="${y}" stroke="${color}"/>`;
      s += `<text class="chart-zone-label" x="${scales.right + 4}" y="${y + 4}" fill="${color}">${label}</text>`;
    });
    return s;
  }

  // -------------------------------------------------------------------------
  // Hover attachment helper
  // -------------------------------------------------------------------------
  function attachHover(svg, tooltipEl, n, scales, onMove, onLeave) {
    const nearestIndex = (clientX) => {
      const rect = svg.getBoundingClientRect();
      const vbX  = ((clientX - rect.left) / rect.width) * VB.width;
      const idx  = Math.round((vbX - scales.left) / (scales.stepX || 1));
      return Math.max(0, Math.min(n - 1, idx));
    };
    svg.onpointermove = (e) => onMove(nearestIndex(e.clientX));
    svg.onpointerleave = onLeave;
    return { trigger: onMove };
  }

  // -------------------------------------------------------------------------
  // Empty state
  // -------------------------------------------------------------------------
  function renderEmptyState(svg, message) {
    svg.innerHTML = '';
    const wrapper = svg.closest('.svg-chart-wrapper');
    if (!wrapper) return;
    let empty = wrapper.querySelector('.chart-empty-state');
    if (!empty) {
      empty = document.createElement('div');
      empty.className = 'chart-empty-state';
      wrapper.appendChild(empty);
    }
    empty.innerHTML = `<i class="bi bi-cloud-slash"></i>${message}`;
    empty.style.display = 'block';
    svg.style.display = 'none';
  }
  function clearEmptyState(svg) {
    svg.style.display = 'block';
    const wrapper = svg.closest('.svg-chart-wrapper');
    const empty   = wrapper && wrapper.querySelector('.chart-empty-state');
    if (empty) empty.style.display = 'none';
  }

  // -------------------------------------------------------------------------
  // Main line chart renderer
  // -------------------------------------------------------------------------
  function renderLineChart(svg, tooltipEl, data, cfg, unitSystem, isToday) {
    if (!data || !data.length) {
      renderEmptyState(svg, 'No data available for this view yet.');
      return;
    }

    const seriesValues = cfg.series.map(s =>
      data.map(d => s.isTemp && unitSystem === 'F' ? toF(d[s.key]) : d[s.key])
    );
    const allVals = seriesValues.flat().filter(v => v !== null && v !== undefined && !Number.isNaN(v));
    let min = Math.min(...allVals);
    let max = Math.max(...allVals);
    if (min === max) { min -= 1; max += 1; }
    const padSpan = (max - min) * 0.15;
    min -= padSpan; max += padSpan;

    const scales  = makeScales(data.length, min, max);
    const yTicks  = buildYTicks(min, max, 5);

    const perSeriesPoints = seriesValues.map(vals =>
      vals.map((v, i) => ({ x: scales.x(i), y: scales.y(v != null ? v : min), raw: v }))
    );

    let html = '';

    // --- 1. Day/night bands (behind everything)
    html += renderDayNightBands(data, scales);

    // --- 2. Zone bands
    html += renderZoneBands(Object.keys(LINE_TABS).find(k => LINE_TABS[k] === cfg) || '', scales);

    // --- 3. Grid + axis
    html += gridAndAxisSvg(yTicks, data, scales);

    // --- 4. Area fill
    if (cfg.fill) {
      html += renderAreaFill(perSeriesPoints[0], scales, cfg.series[0].color, 'areaFill0');
    }

    // --- 5. Lines
    perSeriesPoints.forEach((pts, si) => {
      html += `<path d="${buildSmoothPath(pts)}" fill="none" stroke="${cfg.series[si].color}" stroke-width="2.5" stroke-linecap="round"/>`;
    });

    // --- 6. Min/Max flags (primary series only)
    const primary = seriesValues[0];
    const validPrimary = primary.filter(v => v !== null && v !== undefined && !Number.isNaN(v));
    if (validPrimary.length) {
      const unit = cfg.series[0].isTemp ? (unitSystem === 'F' ? '\u00b0F' : '\u00b0C') : cfg.unit;
      html += renderMinMaxFlags(perSeriesPoints[0], primary, cfg.series[0].color, unit, cfg.series[0].decimals);
    }

    // --- 7. Now line
    const nowIdx = isToday ? data.findIndex(d => d.is_current_hour || d.hour === new Date().getHours()) : -1;
    html += renderNowLine(nowIdx, scales, data);

    // --- 8. Crosshair + hover dots (invisible initially)
    html += `<line class="chart-crosshair-line" x1="0" y1="${scales.top}" x2="0" y2="${scales.bottom}"/>`;
    perSeriesPoints.forEach((_, si) => {
      html += `<circle class="chart-hover-dot" r="5" fill="${cfg.series[si].color}" stroke="var(--surface-solid)" stroke-width="2"/>`;
    });

    svg.innerHTML = html;

    const hoverDots = svg.querySelectorAll('.chart-hover-dot');
    const crosshair = svg.querySelector('.chart-crosshair-line');

    const hover = attachHover(svg, tooltipEl, data.length, scales, (idx) => {
      crosshair.setAttribute('x1', scales.x(idx));
      crosshair.setAttribute('x2', scales.x(idx));
      crosshair.style.opacity = 1;

      const rows = [];
      cfg.series.forEach((s, si) => {
        const raw  = seriesValues[si][idx];
        const prev = idx > 0 ? seriesValues[si][idx - 1] : null;
        const dot  = hoverDots[si];
        dot.setAttribute('cx', scales.x(idx));
        dot.setAttribute('cy', scales.y(raw != null ? raw : min));
        dot.style.opacity = 1;
        const unitLabel = s.isTemp ? (unitSystem === 'F' ? '\u00b0F' : '\u00b0C') : cfg.unit;
        rows.push({
          color: s.color,
          label: s.label,
          text:  `${fmt(raw, s.decimals)}${unitLabel}`,
          badge: si === 0 ? buildTrendBadge(raw, prev) : '',
        });
      });
      if (cfg.secondaryKey) {
        rows.push({ color: 'var(--ink-soft)', label: cfg.secondaryLabel, text: `${fmt(data[idx][cfg.secondaryKey])}${cfg.secondaryUnit}`, badge: '' });
      }
      if (cfg.dirKey) {
        rows.push({ color: 'var(--ink-soft)', label: 'Direction', text: windDirLabel(data[idx][cfg.dirKey]), badge: '' });
      }

      const contextNote = buildContextNote(seriesValues[0][idx], seriesValues[0].filter(v => v != null));
      const isCurrentHour = isToday && (idx === nowIdx);
      showTooltip(tooltipEl, data[idx].time, rows, contextNote, isCurrentHour);
    }, () => {
      crosshair.style.opacity = 0;
      hoverDots.forEach(d => { d.style.opacity = 0; });
      hideTooltip(tooltipEl);
    });

    if (isToday && nowIdx >= 0) hover.trigger(nowIdx);
  }

  // -------------------------------------------------------------------------
  // Bar chart (Air Quality)
  // -------------------------------------------------------------------------
  function renderBarChart(svg, tooltipEl, data, pollutantKey) {
    if (!data || !data.length) {
      renderEmptyState(svg, 'Air quality data isn\u2019t available for this date/location right now.');
      return;
    }
    const vals = data.map(d => d[pollutantKey]).filter(v => v !== null && v !== undefined);
    const max  = Math.max(...vals, 1);
    const scales = makeScales(data.length, 0, max * 1.18);
    const yTicks  = buildYTicks(0, max * 1.18, 5);

    let html = gridAndAxisSvg(yTicks, data, scales);

    // AQI threshold lines
    if (pollutantKey === 'aqi') {
      html += renderAqiThresholdLines(scales);
    }

    const barWidth = Math.max(6, scales.stepX * 0.55);
    data.forEach((d, i) => {
      const x     = scales.x(i) - barWidth / 2;
      const y     = scales.y(d[pollutantKey] || 0);
      const color = pollutantKey === 'aqi' ? d.color : 'var(--chart-1)';
      const gradId = `bar-grad-${i}`;
      html += `<defs><linearGradient id="${gradId}" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${color}" stop-opacity="0.95"/>
        <stop offset="100%" stop-color="${color}" stop-opacity="0.55"/>
      </linearGradient></defs>`;
      html += `<rect class="chart-bar" data-idx="${i}" x="${x}" y="${y}" width="${barWidth}" height="${scales.bottom - y}" rx="4" fill="url(#${gradId})" opacity="0.85"/>`;
    });

    html += `<line class="chart-crosshair-line" x1="0" y1="${scales.top}" x2="0" y2="${scales.bottom}"/>`;
    svg.innerHTML = html;

    const crosshair = svg.querySelector('.chart-crosshair-line');
    const barEls    = svg.querySelectorAll('.chart-bar');

    attachHover(svg, tooltipEl, data.length, scales, (idx) => {
      crosshair.setAttribute('x1', scales.x(idx));
      crosshair.setAttribute('x2', scales.x(idx));
      crosshair.style.opacity = 1;
      barEls.forEach((b, i) => { b.style.opacity = i === idx ? 1 : 0.45; });

      const d   = data[idx];
      const cfg = POLLUTANTS[pollutantKey];
      const prev = idx > 0 ? data[idx - 1][pollutantKey] : null;
      const rows = [{
        color: d.color || 'var(--chart-1)',
        label: pollutantKey === 'aqi' ? (d.status || 'AQI') : cfg.label,
        text:  `${fmt(d[pollutantKey])}${cfg.unit}`,
        badge: buildTrendBadge(d[pollutantKey], prev),
      }];
      const contextNote = buildContextNote(d[pollutantKey], data.map(x => x[pollutantKey]).filter(v => v != null));
      const isCurrentHour = Boolean(d && (d.is_current_hour || d.hour === new Date().getHours()));
      showTooltip(tooltipEl, d.time, rows, contextNote, isCurrentHour);
    }, () => {
      crosshair.style.opacity = 0;
      barEls.forEach(b => { b.style.opacity = 0.85; });
      hideTooltip(tooltipEl);
    });
  }

  // -------------------------------------------------------------------------
  // App wiring
  // -------------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    const root = document.querySelector('[data-weather-app]');
    if (!root) return;

    const timeline    = readJSON('timeline-data', []);
    const aqiTimeline = readJSON('aqi-data', []);

    const svg          = root.querySelector('.weather-svg-chart');
    const tooltipEl    = root.querySelector('.chart-tooltip');
    const legendEl     = root.querySelector('.chart-legend');
    const pollutantBar = root.querySelector('.pollutant-chips');
    const summaryRow   = root.querySelector('.chart-summary-row');
    const svgWrapper   = root.querySelector('.svg-chart-wrapper');

    // Wind rose container (created once, reused)
    let windRoseWrap = svgWrapper && svgWrapper.querySelector('.chart-wind-rose-wrap');
    if (svgWrapper && !windRoseWrap) {
      windRoseWrap = document.createElement('div');
      windRoseWrap.className = 'chart-wind-rose-wrap';
      svgWrapper.appendChild(windRoseWrap);
    }

    let state = {
      tab:       root.dataset.initialTab  || 'overview',
      unit:      root.dataset.initialUnit || 'C',
      pollutant: 'aqi',
    };

    function renderLegend(cfg) {
      if (!legendEl) return;
      if (cfg) {
        legendEl.innerHTML = cfg.series.map(s =>
          `<span class="legend-item"><span class="legend-swatch" style="background:${s.color}"></span>${s.label}</span>`
        ).join('');
        legendEl.style.display = 'flex';
      } else {
        legendEl.style.display = 'none';
      }
    }

    function renderActiveChart(targetSvg, targetTooltip) {
      const useSvg     = targetSvg     || svg;
      const useTooltip = targetTooltip || tooltipEl;
      if (!useSvg) return;
      clearEmptyState(useSvg);

      if (state.tab === 'air_quality') {
        if (!targetSvg) {
          renderLegend(null);
          if (pollutantBar) pollutantBar.style.display = 'flex';
          if (windRoseWrap) windRoseWrap.style.display = 'none';
          buildSummaryRowAqi(summaryRow, aqiTimeline, state.pollutant);
        }
        renderBarChart(useSvg, useTooltip, aqiTimeline, state.pollutant);
      } else {
        if (!targetSvg) {
          if (pollutantBar) pollutantBar.style.display = 'none';
        }
        const cfg = LINE_TABS[state.tab] || LINE_TABS.overview;
        if (!targetSvg) {
          renderLegend(cfg.series.length > 1 ? cfg : null);
          buildSummaryRow(summaryRow, timeline, cfg, state.unit);
          // Wind rose
          if (windRoseWrap) {
            if (state.tab === 'wind') {
              renderWindRose(windRoseWrap, timeline);
            } else {
              windRoseWrap.style.display = 'none';
            }
          }
        }
        renderLineChart(useSvg, useTooltip, timeline, cfg, state.unit, root.dataset.isToday === 'true');
      }
    }

    // Inject sparklines into detail cards
    if (timeline.length) renderSparklines(timeline);

    // Tabs
    root.querySelectorAll('.weather-tabs a').forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        state.tab = link.dataset.tab;
        root.querySelectorAll('.weather-tabs a').forEach(l => l.classList.toggle('active', l === link));
        renderActiveChart();
        const url = new URL(window.location.href);
        url.searchParams.set('tab', state.tab);
        window.history.replaceState({}, '', url);
      });
    });

    // Pollutant chips
    if (pollutantBar) {
      pollutantBar.querySelectorAll('.pollutant-chip').forEach(chip => {
        chip.addEventListener('click', () => {
          state.pollutant = chip.dataset.pollutant;
          pollutantBar.querySelectorAll('.pollutant-chip').forEach(c => c.classList.toggle('active', c === chip));
          buildSummaryRowAqi(summaryRow, aqiTimeline, state.pollutant);
          renderActiveChart();
        });
      });
    }

    // Unit toggle
    root.querySelectorAll('.unit-toggle button').forEach(btn => {
      btn.addEventListener('click', () => {
        state.unit = btn.dataset.unit;
        root.querySelectorAll('.unit-toggle button').forEach(b => b.classList.toggle('active', b === btn));
        root.querySelectorAll('[data-c]').forEach(el => {
          const c = parseFloat(el.dataset.c);
          el.textContent = state.unit === 'F' ? `${toF(c)}\u00b0` : `${Math.round(c)}\u00b0`;
        });
        const url = new URL(window.location.href);
        url.searchParams.set('unit', state.unit);
        window.history.replaceState({}, '', url);
        if (state.tab !== 'air_quality') renderActiveChart();
      });
    });

    // Expand modal
    const expandBtn       = root.querySelector('.chart-expand-btn');
    const modalBackdrop   = document.querySelector('.chart-modal-backdrop');
    const modalSvg        = document.querySelector('.weather-svg-chart-expanded');
    const modalTooltip    = document.querySelector('.chart-modal .chart-tooltip');
    if (expandBtn && modalBackdrop) {
      expandBtn.addEventListener('click', () => {
        modalBackdrop.classList.add('open');
        if (modalSvg) renderActiveChart(modalSvg, modalTooltip);
      });
      modalBackdrop.addEventListener('click', (e) => {
        if (e.target === modalBackdrop || e.target.closest('.chart-modal-close')) {
          modalBackdrop.classList.remove('open');
        }
      });
    }

    renderActiveChart();
  });
})();
