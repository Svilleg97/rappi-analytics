/**
 * charts.js
 * ---------
 * Responsabilidad única: renderizar gráficos con Plotly.
 * Recibe datos ya procesados — no hace fetch ni lógica de negocio.
 *
 * Colores Rappi usados consistentemente en todos los gráficos.
 */

const RAPPI_COLORS = {
  primary:   '#FF441F',
  secondary: '#FF6B35',
  light:     '#FFB347',
  success:   '#10B981',
  danger:    '#EF4444',
  warning:   '#F59E0B',
  blue:      '#3B82F6',
  purple:    '#8B5CF6',
  gray:      '#9CA3AF',
};

const RAPPI_PALETTE = [
  '#FF441F', '#FF6B35', '#10B981', '#3B82F6',
  '#8B5CF6', '#F59E0B', '#EF4444', '#06B6D4', '#84CC16'
];

// Config base para todos los gráficos — sin toolbar excepto descarga
const BASE_CONFIG = {
  responsive:    true,
  displaylogo:   false,
  modeBarButtonsToRemove: [
    'zoom2d','pan2d','select2d','lasso2d','zoomIn2d','zoomOut2d',
    'autoScale2d','hoverClosestCartesian','hoverCompareCartesian',
    'toggleSpikelines'
  ]
};

// Layout base compartido
function baseLayout(overrides = {}) {
  return {
    font:        { family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", size: 11 },
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor:  'rgba(0,0,0,0)',
    margin:      { t: 10, r: 16, b: 40, l: 48 },
    autosize:    true,
    showlegend:  false,
    xaxis: {
      gridcolor:    '#F3F4F6',
      linecolor:    '#E5E7EB',
      tickfont:     { size: 10, color: '#9CA3AF' },
      fixedrange:   true,
    },
    yaxis: {
      gridcolor:    '#F3F4F6',
      linecolor:    '#E5E7EB',
      tickfont:     { size: 10, color: '#9CA3AF' },
      fixedrange:   true,
      rangemode:    'tozero',
    },
    ...overrides
  };
}


// ── Gráfico de línea — tendencias temporales ──────────────────────────────────
function renderLineChart(containerId, data, options = {}) {
  /**
   * data: { labels: [...], series: [{ name, values, color? }] }
   *   o   { labels: [...], values: [...] }  (serie única)
   */
  const el = document.getElementById(containerId);
  if (!el) return;

  // Normalizar a formato multi-serie
  const series = data.series || [{ name: options.yLabel || 'Valor', values: data.values }];

  const traces = series.map((s, i) => ({
    x:          data.labels,
    y:          s.values,
    type:       'scatter',
    mode:       'lines+markers',
    name:       s.name || '',
    line: {
      color:  s.color || RAPPI_PALETTE[i % RAPPI_PALETTE.length],
      width:  2.5,
      shape:  'spline',
    },
    marker: {
      color:  s.color || RAPPI_PALETTE[i % RAPPI_PALETTE.length],
      size:   5,
    },
    hovertemplate: `<b>${s.name || ''}</b><br>%{x}: %{y:.1%}<extra></extra>`,
  }));

  // Si hay múltiples series, mostrar leyenda
  const layout = baseLayout({
    showlegend: series.length > 1,
    legend:     { orientation: 'h', y: -0.2, x: 0.5, xanchor: 'center', font: { size: 10 } },
    yaxis: {
      ...baseLayout().yaxis,
      tickformat: options.isPercent === false ? '.2f' : '.0%',
      tickprefix: options.isPercent === false ? '$' : '',
    },
    height: options.height || 180,
  });


  // Ajuste de rango: si valores estan muy juntos (e.g. 87% y 90%), ampliar eje Y
  if (options.isPercent !== false) {
    const allVals = series.flatMap(s => s.values).filter(v => v != null && v > 0 && v <= 1);
    if (allVals.length > 0) {
      const minVal = Math.min(...allVals);
      const maxVal = Math.max(...allVals);
      if ((maxVal - minVal) < 0.15) {
        const pad = Math.max(0.04, (maxVal - minVal) * 1.5);
        layout.yaxis.range = [Math.max(0, minVal - pad), Math.min(1.02, maxVal + pad)];
      }
    }
  }
  Plotly.newPlot(el, traces, layout, BASE_CONFIG);
}


// ── Gráfico de barras — comparaciones ────────────────────────────────────────
function renderBarChart(containerId, data, options = {}) {
  /**
   * data: { labels: [...], values: [...], colors?: [...] }
   */
  const el = document.getElementById(containerId);
  if (!el) return;

  const colors = data.colors || data.labels.map((_, i) =>
    i === 0 ? RAPPI_COLORS.primary : RAPPI_PALETTE[i % RAPPI_PALETTE.length]
  );

  const traces = [{
    x:              options.horizontal ? data.values : data.labels,
    y:              options.horizontal ? data.labels  : data.values,
    type:           'bar',
    orientation:    options.horizontal ? 'h' : 'v',
    marker: {
      color:        colors,
      line:         { width: 0 },
    },
    hovertemplate:  options.isPercent !== false
      ? '%{x}: %{y:.1%}<extra></extra>'
      : '%{x}: %{y:.2f}<extra></extra>',
  }];

  const layout = baseLayout({
    height: options.height || 180,
    yaxis: {
      ...baseLayout().yaxis,
      tickformat: options.isPercent !== false ? '.0%' : '.2f',
    },
  });

  if (options.horizontal) {
    layout.xaxis = { ...layout.xaxis, tickformat: options.isPercent !== false ? '.0%' : '.2f' };
    layout.yaxis = { ...layout.yaxis, tickformat: '', automargin: true };
    layout.margin = { t: 10, r: 20, b: 30, l: 120 };
  }

  Plotly.newPlot(el, traces, layout, BASE_CONFIG);
}


// ── Gráfico de barras agrupadas — Wealthy vs Non Wealthy ─────────────────────
function renderGroupedBarChart(containerId, data, options = {}) {
  /**
   * data: { labels, groups: [{ name, values, color? }] }
   */
  const el = document.getElementById(containerId);
  if (!el) return;

  const traces = data.groups.map((g, i) => ({
    x:            data.labels,
    y:            g.values,
    name:         g.name,
    type:         'bar',
    marker: {
      color: g.color || RAPPI_PALETTE[i],
    },
    hovertemplate: `<b>${g.name}</b><br>%{x}: %{y:.1%}<extra></extra>`,
  }));

  const layout = baseLayout({
    barmode:    'group',
    showlegend: true,
    legend:     { orientation: 'h', y: -0.25, x: 0.5, xanchor: 'center', font: { size: 10 } },
    height:     options.height || 200,
    yaxis: {
      ...baseLayout().yaxis,
      tickformat: '.0%',
    },
  });

  Plotly.newPlot(el, traces, layout, BASE_CONFIG);
}


// ── Scatter plot — correlaciones ─────────────────────────────────────────────
function renderScatterChart(containerId, data, options = {}) {
  /**
   * data: { x: [...], y: [...], labels?: [...] }
   */
  const el = document.getElementById(containerId);
  if (!el) return;

  const traces = [{
    x:    data.x,
    y:    data.y,
    text: data.labels || [],
    type: 'scatter',
    mode: 'markers',
    marker: {
      color:   RAPPI_COLORS.primary,
      size:    7,
      opacity: 0.7,
    },
    hovertemplate: data.labels
      ? '<b>%{text}</b><br>X: %{x:.2f}<br>Y: %{y:.2f}<extra></extra>'
      : 'X: %{x:.2f}<br>Y: %{y:.2f}<extra></extra>',
  }];

  const layout = baseLayout({
    height: options.height || 220,
    xaxis: {
      ...baseLayout().xaxis,
      title: { text: options.xLabel || '', font: { size: 10 } },
      tickformat: '.1%',
    },
    yaxis: {
      ...baseLayout().yaxis,
      title: { text: options.yLabel || '', font: { size: 10 } },
      tickformat: '.1%',
    },
  });

  Plotly.newPlot(el, traces, layout, BASE_CONFIG);
}


// ── Render automático según tipo ──────────────────────────────────────────────
function renderChartFromToolCall(containerId, toolCall) {
  /**
   * Decide qué gráfico renderizar basándose en el chart_type
   * sugerido por la tool y los datos retornados.
   */
  const { chart_type, result } = toolCall;
  if (!result || !result.success || !result.data || result.data.length === 0) return false;

  const data = result.data;
  const chartType = chart_type || 'table';

  try {
    if (chartType === 'line') {
      // Tendencia temporal — busca columnas week/value
      const hasWeek  = data[0] && 'week'  in data[0];
      const hasValue = data[0] && 'value' in data[0];

      if (hasWeek && hasValue) {
        // Detectar si es métrica monetaria (Gross Profit UE)
        const metricName = data[0].metric || '';
        const isMonetary = metricName.includes('Gross Profit') || metricName.includes('GP');

        const grouped = {};
        data.forEach(r => {
          const serie = r.zone || r.ZONE_TYPE || 'Valor';
          if (!grouped[serie]) grouped[serie] = { labels: [], values: [] };
          grouped[serie].labels.push(r.week);
          grouped[serie].values.push(r.value);
        });
        const series = Object.entries(grouped).map(([name, d], i) => ({
          name, values: d.values, color: RAPPI_PALETTE[i]
        }));
        renderLineChart(containerId, {
          labels: Object.values(grouped)[0].labels,
          series
        }, { isPercent: !isMonetary, height: 180 });
        return true;
      }

      // Compare zone types — columnas L8W..L0W
      if (data[0] && 'ZONE_TYPE' in data[0]) {
        const labels = Object.keys(data[0]).filter(k => k !== 'ZONE_TYPE');
        const series = data.map((row, i) => ({
          name:   row.ZONE_TYPE,
          values: labels.map(l => row[l]),
          color:  i === 0 ? RAPPI_COLORS.primary : RAPPI_COLORS.blue
        }));
        renderLineChart(containerId, { labels, series });
        return true;
      }
    }

    if (chartType === 'bar') {
      // Órdenes trend
      if (data[0] && 'orders' in data[0] && 'week' in data[0]) {
        renderBarChart(containerId, {
          labels: data.map(r => r.week),
          values: data.map(r => r.orders),
        }, { isPercent: false });
        return true;
      }

      // Average by country
      if (data[0] && 'COUNTRY' in data[0] && 'avg_value' in data[0]) {
        // Filtrar outliers: métricas de % deben estar entre 0 y 1
        const filtered = data.filter(r => r.avg_value >= 0 && r.avg_value <= 1);
        const display = filtered.length >= 2 ? filtered : data;
        renderBarChart(containerId, {
          labels: display.map(r => r.country_name || r.COUNTRY),
          values: display.map(r => Math.min(r.avg_value, 1)),
          colors: display.map((_, i) => RAPPI_PALETTE[i % RAPPI_PALETTE.length])
        }, { isPercent: true, horizontal: display.length > 5, height: 220 });
        return true;
      }

      // Top zones / benchmarking — usa L0W_ROLL o value_fmt
      if (data[0] && 'ZONE' in data[0]) {
        const valueKey = 'L0W_ROLL' in data[0] ? 'L0W_ROLL'
                       : 'growth_pct' in data[0] ? 'growth_pct' : null;
        if (valueKey) {
          const isGrowth = valueKey === 'growth_pct';
          // Filtrar outliers para métricas de porcentaje
          let display = data;
          if (!isGrowth) {
            const clean = data.filter(r => r[valueKey] >= 0 && r[valueKey] <= 1);
            display = clean.length >= 2 ? clean : data;
          }
          renderBarChart(containerId, {
            labels: display.map(r => (r.ZONE + ' (' + r.COUNTRY + ')').substring(0, 30)),
            values: display.map(r => isGrowth ? r[valueKey] : Math.min(r[valueKey], 1)),
            colors: display.map((_, i) => RAPPI_PALETTE[i % RAPPI_PALETTE.length])
          }, { isPercent: !isGrowth, horizontal: true, height: Math.max(180, display.length * 32) });
          return true;
        }
      }

      // Fastest growing zones
      if (data[0] && 'growth_pct' in data[0]) {
        renderBarChart(containerId, {
          labels: data.map(r => (r.ZONE + ' (' + r.COUNTRY + ')').substring(0, 30)),
          values: data.map(r => r.growth_pct),
        }, { isPercent: false, horizontal: true, height: Math.max(180, data.length * 32) });
        return true;
      }
    }

    if (chartType === 'scatter' && data[0]) {
      const keys = Object.keys(data[0]).filter(k =>
        !['COUNTRY','CITY','ZONE','ZONE_TYPE'].includes(k) && typeof data[0][k] === 'number'
      );
      if (keys.length >= 2) {
        renderScatterChart(containerId, {
          x:      data.map(r => r[keys[0]]),
          y:      data.map(r => r[keys[1]]),
          labels: data.map(r => r.ZONE || r.COUNTRY || '')
        }, { xLabel: keys[0], yLabel: keys[1], height: 220 });
        return true;
      }
    }

  } catch (e) {
    console.warn('Error renderizando gráfico:', e);
  }

  return false;
}


// ── Gráficos del dashboard ────────────────────────────────────────────────────
function renderDashboardCharts(dashboardData) {
  const { trends, kpis } = dashboardData;

  // Gráfico 1: Tendencia Perfect Orders
  if (trends && trends.perfect_orders) {
    const po = trends.perfect_orders;
    renderLineChart('chart-perfect-orders', {
      labels: po.labels,
      series: [{ name: 'Perfect Orders', values: po.values, color: RAPPI_COLORS.primary }]
    }, { height: 160 });
  }

  // Gráfico 2: Lead Penetration por país (barras)
  // Se carga por separado desde la API en app.js
}

function renderLeadByCountry(countryData) {
  if (!countryData || !countryData.length) return;
  renderBarChart('chart-lead-country', {
    labels: countryData.map(r => r.country_name || r.COUNTRY),
    values: countryData.map(r => r.avg_value),
    colors: countryData.map((_, i) => RAPPI_PALETTE[i % RAPPI_PALETTE.length])
  }, { isPercent: true, height: 160 });
  // Forzar resize después de render para que Plotly calcule bien el ancho
  setTimeout(() => {
    const el = document.getElementById('chart-lead-country');
    if (el && el._fullLayout) Plotly.relayout(el, { autosize: true });
    window.dispatchEvent(new Event('resize'));
  }, 100);
}
