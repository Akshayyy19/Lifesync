/**
 * LifeSync — weather-charts.js
 *
 * Single data-driven chart engine for the weather page. Renders every tab
 * (Overview, Precipitation, Wind, Humidity, Pressure, UV, Visibility) through
 * one line-chart function, and Air Quality through one bar-chart function,
 * instead of eight near-identical renderers. Adds a hover crosshair + tooltip
 * so you can scrub the chart for an exact reading at any hour.
 */
(function () {
  'use strict';

  const VB = { width: 1000, height: 300, padLeft: 42, padRight: 16, padTop: 18, padBottom: 30 };

  const LINE_TABS = {
    overview: {
      unit: '\u00b0',
      series: [
        { key: 'temp', label: 'Temperature', color: 'var(--chart-1)', isTemp: true },
        { key: 'feels_like', label: 'Feels like', color: 'var(--chart-2)', isTemp: true },
      ],
      fill: true,
    },
    precipitation: {
      unit: 'mm',
      series: [
        { key: 'precip_mm', label: 'Precipitation', color: 'var(--chart-1)', decimals: 1 },
      ],
      fill: true,
      secondaryKey: 'precip_prob',
      secondaryLabel: 'Chance of rain',
      secondaryUnit: '%',
    },
    wind: {
      unit: 'km/h',
      series: [
        { key: 'wind_speed', label: 'Wind speed', color: 'var(--chart-1)' },
        { key: 'wind_gust', label: 'Gusts', color: 'var(--chart-2)' },
      ],
      dirKey: 'wind_dir',
    },
    humidity: {
      unit: '%',
      series: [{ key: 'humidity', label: 'Humidity', color: 'var(--chart-1)' }],
      fill: true,
    },
    pressure: {
      unit: 'hPa',
      series: [{ key: 'pressure', label: 'Pressure', color: 'var(--chart-1)' }],
    },
    uv: {
      unit: '',
      series: [{ key: 'uv', label: 'UV Index', color: 'var(--chart-1)', decimals: 1 }],
      fill: true,
    },
    visibility: {
      unit: 'km',
      series: [{ key: 'visibility_km', label: 'Visibility', color: 'var(--chart-1)', decimals: 1 }],
      fill: true,
    },
  };

  const POLLUTANTS = {
    aqi: { label: 'AQI', unit: '' },
    pm2_5: { label: 'PM 2.5', unit: '\u00b5g/m\u00b3' },
    pm10: { label: 'PM 10', unit: '\u00b5g/m\u00b3' },
    o3: { label: 'O\u2083', unit: '\u00b5g/m\u00b3' },
    no2: { label: 'NO\u2082', unit: '\u00b5g/m\u00b3' },
    so2: { label: 'SO\u2082', unit: '\u00b5g/m\u00b3' },
    co: { label: 'CO', unit: '\u00b5g/m\u00b3' },
  };

  const WIND_COMPASS = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];

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
    } catch (e) {
      return fallback;
    }
  }
  function fmt(value, decimals) {
    if (value === null || value === undefined || Number.isNaN(value)) return '\u2013';
    return decimals ? value.toFixed(decimals) : String(Math.round(value));
  }
  function svgEl(tag, attrs) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    Object.keys(attrs || {}).forEach((k) => el.setAttribute(k, attrs[k]));
    return el;
  }

  // Builds a smooth-ish path through points using quadratic curves toward
  // each point rather than straight segments — same idea for line or area.
  function buildSmoothPath(pts) {
    if (pts.length === 0) return '';
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

  function makeScales(n, min, max) {
    const left = VB.padLeft, right = VB.width - VB.padRight;
    const top = VB.padTop, bottom = VB.height - VB.padBottom;
    const span = (max - min) || 1;
    const stepX = n > 1 ? (right - left) / (n - 1) : 0;
    return {
      x: (i) => left + i * stepX,
      y: (v) => bottom - ((v - min) / span) * (bottom - top),
      stepX,
      left, right, top, bottom,
    };
  }

  function gridAndAxisSvg(yTicks, xLabels, xIndices, scales) {
    let s = '';
    yTicks.forEach((tv) => {
      const y = scales.y(tv);
      s += `<line class="chart-grid-line" x1="${scales.left}" y1="${y}" x2="${scales.right}" y2="${y}" />`;
      s += `<text class="chart-axis-label" x="${scales.left - 8}" y="${y + 4}" text-anchor="end">${tv}</text>`;
    });
    xIndices.forEach((i, idx) => {
      if (idx % Math.ceil(xIndices.length / 12 || 1) !== 0) return;
      s += `<text class="chart-axis-label" x="${scales.x(i)}" y="${VB.height - 8}" text-anchor="middle">${xLabels[i] || ''}</text>`;
    });
    return s;
  }

  /**
   * Renders a line chart (1-2 series) for any of the LINE_TABS configs and
   * wires up crosshair-on-hover. Returns nothing; mutates the svg in place.
   */
  function renderLineChart(svg, tooltipEl, data, cfg, unitSystem, isToday) {
    if (!data || data.length === 0) {
      renderEmptyState(svg, 'No data available for this view yet.');
      return;
    }

    const seriesValues = cfg.series.map((s) =>
      data.map((d) => (s.isTemp && unitSystem === 'F' ? toF(d[s.key]) : d[s.key]))
    );
    const allVals = seriesValues.flat().filter((v) => v !== null && v !== undefined && !Number.isNaN(v));
    let min = Math.min(...allVals);
    let max = Math.max(...allVals);
    if (min === max) { min -= 1; max += 1; }
    const padSpan = (max - min) * 0.12;
    min -= padSpan; max += padSpan;

    const scales = makeScales(data.length, min, max);
    const yTicks = [min, (min + max) / 2, max].map((v) => Math.round(v));
    const xLabels = data.map((d) => d.time);
    const xIndices = data.map((_, i) => i);

    let html = gridAndAxisSvg(yTicks, xLabels, xIndices, scales);

    const perSeriesPoints = seriesValues.map((vals) =>
      vals.map((v, i) => ({ x: scales.x(i), y: scales.y(v), raw: v }))
    );

    if (cfg.fill) {
      const pts = perSeriesPoints[0];
      const path = buildSmoothPath(pts);
      const areaPath = `${path} L ${scales.x(data.length - 1)} ${scales.bottom} L ${scales.x(0)} ${scales.bottom} Z`;
      html += `<defs><linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="${cfg.series[0].color}" stop-opacity="0.28" />
        <stop offset="100%" stop-color="${cfg.series[0].color}" stop-opacity="0" />
      </linearGradient></defs>`;
      html += `<path d="${areaPath}" fill="url(#areaFill)" stroke="none" />`;
    }

    perSeriesPoints.forEach((pts, si) => {
      html += `<path d="${buildSmoothPath(pts)}" fill="none" stroke="${cfg.series[si].color}" stroke-width="2.5" stroke-linecap="round" />`;
    });

    html += `<line class="chart-crosshair-line" x1="0" y1="${scales.top}" x2="0" y2="${scales.bottom}" />`;
    perSeriesPoints.forEach((_, si) => {
      html += `<circle class="chart-hover-dot" r="5" fill="${cfg.series[si].color}" stroke="var(--surface-solid)" stroke-width="2" />`;
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
        const raw = seriesValues[si][idx];
        const dot = hoverDots[si];
        dot.setAttribute('cx', scales.x(idx));
        dot.setAttribute('cy', scales.y(raw));
        dot.style.opacity = 1;
        const unitLabel = s.isTemp ? (unitSystem === 'F' ? '\u00b0F' : '\u00b0C') : cfg.unit;
        rows.push({ color: s.color, label: s.label, text: `${fmt(raw, s.decimals)}${unitLabel}` });
      });
      if (cfg.secondaryKey) {
        rows.push({ color: 'var(--ink-soft)', label: cfg.secondaryLabel, text: `${fmt(data[idx][cfg.secondaryKey])}${cfg.secondaryUnit}` });
      }
      if (cfg.dirKey) {
        rows.push({ color: 'var(--ink-soft)', label: 'Direction', text: windDirLabel(data[idx][cfg.dirKey]) });
      }
      showTooltip(tooltipEl, data[idx].time, rows);
    }, () => {
      crosshair.style.opacity = 0;
      hoverDots.forEach((d) => { d.style.opacity = 0; });
      hideTooltip(tooltipEl);
    });

    // Default-highlight the current hour, but only when this timeline is
    // actually today's — highlighting "now" on a past/future date is meaningless.
    if (isToday) {
      const nowHour = new Date().getHours();
      const nowIdx = data.findIndex((d) => d.hour === nowHour);
      if (nowIdx >= 0) hover.trigger(nowIdx);
    }
  }

  function renderBarChart(svg, tooltipEl, data, pollutantKey) {
    if (!data || data.length === 0) {
      renderEmptyState(svg, 'Air quality data isn\u2019t available for this date/location right now.');
      return;
    }
    const vals = data.map((d) => d[pollutantKey]);
    let max = Math.max(...vals, 1);
    const scales = makeScales(data.length, 0, max * 1.15);
    const yTicks = [0, Math.round(max * 0.5), Math.round(max * 1.15)];
    const xLabels = data.map((d) => d.time);
    const xIndices = data.map((_, i) => i);

    let html = gridAndAxisSvg(yTicks, xLabels, xIndices, scales);
    const barWidth = Math.max(4, scales.stepX * 0.5);
    const bars = [];
    data.forEach((d, i) => {
      const x = scales.x(i) - barWidth / 2;
      const y = scales.y(d[pollutantKey]);
      const color = pollutantKey === 'aqi' ? d.color : 'var(--chart-1)';
      html += `<rect class="chart-bar" data-idx="${i}" x="${x}" y="${y}" width="${barWidth}" height="${scales.bottom - y}" rx="3" fill="${color}" opacity="0.85" />`;
      bars.push({ x: scales.x(i) });
    });
    html += `<line class="chart-crosshair-line" x1="0" y1="${scales.top}" x2="0" y2="${scales.bottom}" />`;
    svg.innerHTML = html;

    const crosshair = svg.querySelector('.chart-crosshair-line');
    const barEls = svg.querySelectorAll('.chart-bar');

    attachHover(svg, tooltipEl, data.length, scales, (idx) => {
      crosshair.setAttribute('x1', scales.x(idx));
      crosshair.setAttribute('x2', scales.x(idx));
      crosshair.style.opacity = 1;
      barEls.forEach((b, i) => { b.style.opacity = i === idx ? 1 : 0.55; });
      const d = data[idx];
      const cfg = POLLUTANTS[pollutantKey];
      const rows = [{ color: d.color || 'var(--chart-1)', label: pollutantKey === 'aqi' ? d.status : cfg.label, text: `${fmt(d[pollutantKey])}${cfg.unit}` }];
      showTooltip(tooltipEl, d.time, rows);
    }, () => {
      crosshair.style.opacity = 0;
      barEls.forEach((b) => { b.style.opacity = 0.85; });
      hideTooltip(tooltipEl);
    });
  }

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
    const empty = wrapper && wrapper.querySelector('.chart-empty-state');
    if (empty) empty.style.display = 'none';
  }

  function attachHover(svg, tooltipEl, n, scales, onMove, onLeave) {
    const nearestIndex = (clientX) => {
      const rect = svg.getBoundingClientRect();
      const vbX = ((clientX - rect.left) / rect.width) * VB.width;
      const idx = Math.round((vbX - scales.left) / (scales.stepX || 1));
      return Math.max(0, Math.min(n - 1, idx));
    };
    svg.onpointermove = (e) => onMove(nearestIndex(e.clientX));
    svg.onpointerleave = onLeave;
    return { trigger: onMove };
  }

  function showTooltip(tooltipEl, timeLabel, rows) {
    if (!tooltipEl) return;
    tooltipEl.innerHTML = `<div class="tt-time">${timeLabel}</div>` + rows.map((r) =>
      `<div class="tt-row"><span class="legend-swatch" style="background:${r.color}"></span>${r.label}: <strong>${r.text}</strong></div>`
    ).join('');
    tooltipEl.classList.add('visible');
  }
  function hideTooltip(tooltipEl) {
    if (tooltipEl) tooltipEl.classList.remove('visible');
  }

  // ---------------------------------------------------------------------
  // App wiring
  // ---------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', function () {
    const root = document.querySelector('[data-weather-app]');
    if (!root) return;

    const timeline = readJSON('timeline-data', []);
    const aqiTimeline = readJSON('aqi-data', []);

    const svg = root.querySelector('.weather-svg-chart');
    const tooltipEl = root.querySelector('.chart-tooltip');
    const legendEl = root.querySelector('.chart-legend');
    const pollutantBar = root.querySelector('.pollutant-chips');

    let state = {
      tab: root.dataset.initialTab || 'overview',
      unit: root.dataset.initialUnit || 'C',
      pollutant: 'aqi',
    };

    function renderLegend(cfg) {
      if (!legendEl) return;
      if (cfg) {
        legendEl.innerHTML = cfg.series.map((s) =>
          `<span class="legend-item"><span class="legend-swatch" style="background:${s.color}"></span>${s.label}</span>`
        ).join('');
        legendEl.style.display = 'flex';
      } else {
        legendEl.style.display = 'none';
      }
    }

    function renderActiveChart(targetSvg, targetTooltip) {
      const useSvg = targetSvg || svg;
      const useTooltip = targetTooltip || tooltipEl;
      if (!useSvg) return;
      clearEmptyState(useSvg);
      if (state.tab === 'air_quality') {
        if (!targetSvg) { renderLegend(null); if (pollutantBar) pollutantBar.style.display = 'flex'; }
        renderBarChart(useSvg, useTooltip, aqiTimeline, state.pollutant);
      } else {
        if (!targetSvg) { if (pollutantBar) pollutantBar.style.display = 'none'; }
        const cfg = LINE_TABS[state.tab] || LINE_TABS.overview;
        if (!targetSvg) renderLegend(cfg.series.length > 1 ? cfg : null);
        renderLineChart(useSvg, useTooltip, timeline, cfg, state.unit, root.dataset.isToday === 'true');
      }
    }

    // Tabs
    root.querySelectorAll('.weather-tabs a').forEach((link) => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        state.tab = link.dataset.tab;
        root.querySelectorAll('.weather-tabs a').forEach((l) => l.classList.toggle('active', l === link));
        renderActiveChart();
        const url = new URL(window.location.href);
        url.searchParams.set('tab', state.tab);
        window.history.replaceState({}, '', url);
      });
    });

    // Pollutant chips
    if (pollutantBar) {
      pollutantBar.querySelectorAll('.pollutant-chip').forEach((chip) => {
        chip.addEventListener('click', () => {
          state.pollutant = chip.dataset.pollutant;
          pollutantBar.querySelectorAll('.pollutant-chip').forEach((c) => c.classList.toggle('active', c === chip));
          renderActiveChart();
        });
      });
    }

    // Unit toggle — flips already-loaded values in place, no reload.
    root.querySelectorAll('.unit-toggle button').forEach((btn) => {
      btn.addEventListener('click', () => {
        state.unit = btn.dataset.unit;
        root.querySelectorAll('.unit-toggle button').forEach((b) => b.classList.toggle('active', b === btn));
        root.querySelectorAll('[data-c]').forEach((el) => {
          const c = parseFloat(el.dataset.c);
          el.textContent = state.unit === 'F' ? `${toF(c)}\u00b0` : `${Math.round(c)}\u00b0`;
        });
        const url = new URL(window.location.href);
        url.searchParams.set('unit', state.unit);
        window.history.replaceState({}, '', url);
        if (state.tab !== 'air_quality') renderActiveChart();
      });
    });

    // Expand modal — reuses the exact same render functions at a larger size.
    const expandBtn = root.querySelector('.chart-expand-btn');
    const modalBackdrop = document.querySelector('.chart-modal-backdrop');
    const modalSvg = document.querySelector('.weather-svg-chart-expanded');
    const modalTooltip = document.querySelector('.chart-modal .chart-tooltip');
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
