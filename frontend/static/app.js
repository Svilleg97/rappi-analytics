/**
 * app.js
 * ------
 * Lógica principal del frontend. Organizado en secciones:
 *   1. Estado global
 *   2. Auth
 *   3. Navegación
 *   4. Dashboard
 *   5. Chat
 *   6. Reportes
 *   7. Historial
 *   8. Diccionario
 *   9. Utilidades
 */

// -- 1. Estado global ----------------------------------------------------------
const STATE = {
  currentPage:    'dashboard',
  sessionId:      null,
  pollInterval:   null,
  pendingJobs:    {},
  username:       null,
  activeWeek:     'L0W_ROLL',
  activeReportJob: null,   // job_id del reporte en generación
};

const WEEK_OPTIONS = [
  { value: 'L0W_ROLL', label: 'Semana actual (L0W)' },
  { value: 'L1W_ROLL', label: 'Hace 1 semana (L1W)' },
  { value: 'L2W_ROLL', label: 'Hace 2 semanas (L2W)' },
  { value: 'L3W_ROLL', label: 'Hace 3 semanas (L3W)' },
  { value: 'L4W_ROLL', label: 'Hace 4 semanas (L4W)' },
  { value: 'L5W_ROLL', label: 'Hace 5 semanas (L5W)' },
  { value: 'L6W_ROLL', label: 'Hace 6 semanas (L6W)' },
  { value: 'L7W_ROLL', label: 'Hace 7 semanas (L7W)' },
  { value: 'L8W_ROLL', label: 'Hace 8 semanas (L8W)' },
];

// Configurar marked globalmente — tablas con clases de Rappi
marked.use({
  renderer: {
    table(header, body) {
      return '<div class="msg-table-wrap"><table class="msg-table"><thead>' +
             header + '</thead><tbody>' + body + '</tbody></table></div>';
    },
    tablecell(content, flags) {
      const tag = flags.header ? 'th' : 'td';
      return '<' + tag + '>' + content + '</' + tag + '>';
    }
  }
});

// -- 2. Auth -------------------------------------------------------------------
async function doLogin() {
  const btn  = document.getElementById('login-btn');
  const user = document.getElementById('login-user').value.trim();
  const pass = document.getElementById('login-pass').value.trim();
  const err  = document.getElementById('login-error');

  if (!user || !pass) return;

  btn.disabled    = true;
  btn.textContent = 'Ingresando...';
  err.style.display = 'none';

  try {
    const res = await fetch('/api/auth/login', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ username: user, password: pass }),
      credentials: 'include'
    });
    const data = await res.json();

    if (data.success) {
      STATE.username = data.username;
      showApp(data.username);
    } else {
      err.style.display = 'block';
    }
  } catch (e) {
    err.textContent   = 'Error de conexión. Verifica que el servidor esté corriendo.';
    err.style.display = 'block';
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Ingresar a la plataforma →';
  }
}

async function doLogout() {
  await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
  document.getElementById('app').classList.add('hidden');
  document.getElementById('login-screen').classList.remove('hidden');
  STATE.sessionId = null;
}

function showApp(username) {
  document.getElementById('login-screen').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');

  // Actualizar UI con nombre de usuario
  const initials = username.substring(0, 2).toUpperCase();
  document.getElementById('user-avatar').textContent = initials;
  document.getElementById('user-name').textContent   = username;

  // Cargar página inicial
  loadDashboard();
  loadDictionary();
}

// Verificar sesión activa al cargar (por si refresca la página)
async function checkSession() {
  try {
    const res  = await fetch('/api/auth/me', { credentials: 'include' });
    const data = await res.json();
    if (data.authenticated) {
      STATE.username = data.username;
      showApp(data.username);
    }
  } catch (e) { /* no hay sesión activa */ }
}

// -- 3. Navegación -------------------------------------------------------------
function navigate(page, navEl) {
  // Ocultar página actual
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  // Mostrar nueva página
  document.getElementById(`page-${page}`).classList.add('active');
  if (navEl) navEl.classList.add('active');

  STATE.currentPage = page;

  // Cargar datos de la página si es necesario
  if (page === 'history')    loadHistory();
  if (page === 'reports') {
    loadReports();
    // Si hay un job de reporte en progreso, retomar el polling
    if (STATE.activeReportJob) resumeReportPolling(STATE.activeReportJob);
  }
  if (page === 'chat')       initChat();
}

function switchTab(btn, targetId) {
  btn.closest('.tabs').querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('hist-chats').style.display   = 'none';
  document.getElementById('hist-reports').style.display = 'none';
  document.getElementById(targetId).style.display       = 'flex';
}

// -- 4. Dashboard --------------------------------------------------------------
function injectWeekSelector() {
  if (document.getElementById('week-selector')) return;
  const header = document.querySelector('#page-dashboard .page-header');
  if (!header) return;
  const wrap = document.createElement('div');
  wrap.style.cssText = 'display:flex;align-items:center;gap:10px;margin-top:10px;flex-wrap:wrap';
  const opts = WEEK_OPTIONS.map(o =>
    '<option value="' + o.value + '">' + o.label + '</option>'
  ).join('');
  wrap.innerHTML =
    '<label style="font-size:12px;font-weight:600;color:var(--text2)">Semana:</label>' +
    '<select id="week-selector" onchange="onWeekChange(this.value)" style="' +
    'border:1.5px solid var(--border);border-radius:var(--radius-sm);' +
    'padding:6px 10px;font-size:12px;color:var(--text);background:var(--white);' +
    'outline:none;cursor:pointer;font-family:inherit">' + opts + '</select>' +
    '<button onclick="reloadDataFile()" id="reload-btn" style="' +
    'background:none;border:1.5px solid var(--border);border-radius:var(--radius-sm);' +
    'padding:5px 10px;font-size:11px;color:var(--text2);cursor:pointer">🔄 Recargar datos</button>';
  header.appendChild(wrap);
}

function onWeekChange(week) {
  STATE.activeWeek = week;
  loadDashboard();
}

async function reloadDataFile() {
  const btn = document.getElementById('reload-btn');
  if (btn) { btn.textContent = '⏳ Recargando...'; btn.disabled = true; }
  try {
    await apiFetch('/api/data/reload', { method: 'POST' });
    showToast('✅ Datos recargados correctamente', 'success');
    loadDashboard();
  } catch(e) {
    showToast('Error al recargar datos', 'error');
  } finally {
    if (btn) { btn.textContent = '🔄 Recargar datos'; btn.disabled = false; }
  }
}

async function loadDashboard() {
  injectWeekSelector();
  const sel = document.getElementById('week-selector');
  if (sel) sel.value = STATE.activeWeek;

  try {
    const weekParam = STATE.activeWeek.replace('_ROLL','');
    const res  = await apiFetch('/api/insights/dashboard?week=' + weekParam);
    const data = await res.json();

    renderKPIs(data.kpis || {});
    renderAlerts(
      data.alert_counts  || { deterioros: 0, mejoras: 0, deterioro_sostenido: 0 },
      data.top_anomalies || [],
      data.top_growing   || []
    );
    renderDashboardCharts(data);
    loadLeadByCountry();

    const sub = document.getElementById('dashboard-sub');
    const weekLabel = WEEK_OPTIONS.find(o => o.value === STATE.activeWeek);
    if (sub) sub.textContent = (weekLabel ? weekLabel.label : 'Semana actual') + ' · 9 países · datos en tiempo real';
  } catch (e) {
    console.error('Error cargando dashboard:', e);
  }
}

async function loadLeadByCountry() {
  try {
    // Construir promedio por país usando benchmarking de cada país
    const countries = ["AR","BR","CL","CO","CR","EC","MX","PE","UY"];
    const countryNames = {
      AR:"Argentina",BR:"Brasil",CL:"Chile",CO:"Colombia",
      CR:"Costa Rica",EC:"Ecuador",MX:"México",PE:"Perú",UY:"Uruguay"
    };
    const results = [];
    for (const c of countries) {
      try {
        const r   = await apiFetch(`/api/insights/benchmarking?metric=Lead%20Penetration&country=${c}`);
        const data = await r.json();
        const rows = data.benchmarking || [];
        // Solo valores entre 0 y 1 (filtrar outliers)
        const valid = rows.filter(r => r.L0W_ROLL >= 0 && r.L0W_ROLL <= 1);
        if (valid.length > 0) {
          const avg = valid.reduce((s, r) => s + r.L0W_ROLL, 0) / valid.length;
          results.push({ COUNTRY: c, country_name: countryNames[c], avg_value: avg });
        }
      } catch(e) {}
    }
    if (results.length > 0) {
      results.sort((a,b) => b.avg_value - a.avg_value);
      renderLeadByCountry(results);
    }
  } catch(e) {
    console.warn('Error cargando Lead por país:', e);
  }
}

function renderKPIs(kpis) {
  const grid = document.getElementById('kpi-grid');
  if (!grid || !kpis) return;

  const labels = {
    'Perfect Orders':                  'Perfect Orders',
    'Lead Penetration':                'Lead Penetration',
    'Gross Profit UE':                 'Gross Profit UE',
    'Pro Adoption (Last Week Status)': 'Pro Adoption',
  };

  grid.innerHTML = Object.entries(kpis).map(([metric, d]) => `
    <div class="kpi-card">
      <div class="kpi-label">${labels[metric] || metric}</div>
      <div class="kpi-value">${d.value_fmt}</div>
      <div class="kpi-delta ${d.trend}">
        ${d.trend === 'up' ? '↑' : d.trend === 'down' ? '↓' : '→'}
        ${d.delta_fmt} vs semana anterior
      </div>
    </div>
  `).join('');
}

function renderAlerts(counts, anomalies, growing) {
  const grid = document.getElementById('alert-grid');
  if (!grid) return;

  grid.innerHTML = `
    <div class="alert-item danger">
      <div class="alert-title">🚨 ${counts.deterioros || 0} zonas con deterioro >10%</div>
      <div class="alert-sub">${anomalies.slice(0,2).map(a => `${a.ZONE} (${a.COUNTRY})`).join(', ') || 'Sin datos'}</div>
    </div>
    <div class="alert-item warning">
      <div class="alert-title">⚠️ ${counts.deterioro_sostenido || 0} zonas en deterioro sostenido</div>
      <div class="alert-sub">3+ semanas seguidas · requieren atención estratégica</div>
    </div>
    <div class="alert-item success">
      <div class="alert-title">📈 ${growing.length || 0} zonas con alto crecimiento en órdenes</div>
      <div class="alert-sub">${growing.slice(0,2).map(z => `${z.ZONE} ${z.growth_fmt}`).join(', ') || 'Sin datos'}</div>
    </div>
  `;
}

// -- 5. Chat -------------------------------------------------------------------
function initChat() {
  const msgs = document.getElementById('chat-messages');
  if (!msgs) return;
  // Solo mostrar bienvenida si no hay mensajes
  if (msgs.children.length === 0) {
    addBotMessage(
      `Hola 👋 Soy **RappiInsights**, tu asistente de análisis operacional.\n\n` +
      `Puedo ayudarte a analizar métricas de las **1,242 zonas en 9 países**. ` +
      `Pregúntame sobre tendencias, anomalías, comparaciones o cualquier análisis que necesites.\n\n` +
      `¿Por dónde empezamos?`
    );
  }
}

function newConversation() {
  // Guardar resumen de la conversación actual antes de limpiar
  if (STATE.sessionId) {
    fetch(`/api/chat/history/${STATE.sessionId}/summarize`, {
      method: 'POST', credentials: 'include'
    }).catch(() => {});
  }
  STATE.sessionId = null;
  document.getElementById('chat-messages').innerHTML = '';
  initChat();
}

function handleChatKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendChatMessage();
  }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function fillChat(text) {
  const input = document.getElementById('chat-input');
  input.value = text;
  autoResize(input);
  input.focus();
  // Navegar al chat
  navigate('chat', document.querySelector('.nav-item:nth-child(2)'));
}

async function sendChatMessage() {
  const input  = document.getElementById('chat-input');
  const sendBtn = document.getElementById('chat-send-btn');
  const message = input.value.trim();
  if (!message) return;

  // Agregar mensaje del usuario
  addUserMessage(message);
  input.value = '';
  input.style.height = 'auto';
  sendBtn.disabled = true;

  // Mostrar typing indicator
  const typingId = addTypingIndicator();

  try {
    // Enviar mensaje -- retorna job_id inmediatamente
    const res = await apiFetch('/api/chat/message', {
      method: 'POST',
      body:   JSON.stringify({ message, session_id: STATE.sessionId })
    });
    const { job_id, session_id } = await res.json();
    STATE.sessionId = session_id;

    // Polling hasta que el job termine
    const result = await pollJob(`/api/chat/job/${job_id}`);

    removeTypingIndicator(typingId);

    if (result.error) {
      addBotMessage(`❌ Error: ${result.error}`);
    } else {
      // Extraer texto limpio — puede venir como string, array de bloques, u objeto
      let responseText = result.text;
      if (Array.isArray(responseText)) {
        responseText = responseText
          .filter(b => b && b.type === 'text')
          .map(b => b.text || '')
          .join('\n');
      } else if (responseText && typeof responseText === 'object') {
        responseText = responseText.text || '';
      }
      addBotMessage(responseText || '', result.tool_calls || []);
    }

  } catch (e) {
    removeTypingIndicator(typingId);
    addBotMessage('❌ Error de conexión. Por favor intenta de nuevo.');
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

// Polling genérico -- funciona para chat y reportes
async function pollJob(endpoint, intervalMs = 2000, maxWaitMs = 120000) {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();

    const interval = setInterval(async () => {
      try {
        const res  = await apiFetch(endpoint);
        const data = await res.json();

        if (data.status === 'done') {
          clearInterval(interval);
          resolve(data.result);
        } else if (data.status === 'error') {
          clearInterval(interval);
          resolve({ error: data.error || 'Error desconocido' });
        } else if (Date.now() - startTime > maxWaitMs) {
          clearInterval(interval);
          resolve({ error: 'Tiempo de espera agotado. El análisis tardó demasiado.' });
        }
        // Si está pending o processing, continúa el polling
      } catch (e) {
        clearInterval(interval);
        reject(e);
      }
    }, intervalMs);
  });
}

function addUserMessage(text) {
  const msgs = document.getElementById('chat-messages');
  const div  = document.createElement('div');
  div.className = 'msg user';
  div.innerHTML = `
    <div class="msg-bubble">${escapeHtml(text)}</div>
    <div class="msg-meta">${formatTime(new Date())}</div>
  `;
  msgs.appendChild(div);
  scrollChat();
}

function addBotMessage(text, toolCalls = []) {
  // Asegurar que text sea siempre string limpio
  if (text === null || text === undefined) text = '';
  if (typeof text === 'object' && text !== null) {
    // Si es objeto con propiedad text, extraerla
    text = text.text || text.content || '';
  }
  text = String(text);
  // Limpiar artefactos de serialización JS
  if (text === 'undefined' || text === 'null' || text === '[object Object]') text = '';
  // Si el texto empieza con [object, es un error de serialización
  if (text.startsWith('[object')) text = '';
  const msgs  = document.getElementById('chat-messages');
  const msgId = 'msg-' + Date.now();
  const div   = document.createElement('div');
  div.className = 'msg bot';
  div.id = msgId;

  // Renderizar markdown
  const rendered = marked.parse(text || '');

  div.innerHTML = `
    <div class="msg-bubble">${rendered}</div>
    <div class="msg-meta">${formatTime(new Date())}</div>
  `;
  msgs.appendChild(div);

  // Renderizar tablas para tool calls tipo table
  if (toolCalls && toolCalls.length > 0) {
    toolCalls.forEach((tc) => {
      if (tc.chart_type === 'table' && tc.result && tc.result.data && tc.result.data.length > 0) {
        const data = tc.result.data;
        const cols = Object.keys(data[0]).filter(k =>
          !['change_pct','zone_type_avg','vs_avg_pct','country_name'].includes(k)
        );
        // Format column headers
        const headerMap = {
          COUNTRY:'País', CITY:'Ciudad', ZONE:'Zona', ZONE_TYPE:'Tipo',
          ZONE_PRIORITIZATION:'Prioridad', METRIC:'Métrica',
          L1W_ROLL:'L1W', L0W_ROLL:'L0W', change_fmt:'Cambio',
          tipo:'Tipo', valor_inicio:'Inicio', valor_actual:'Actual',
          cambio_pct:'Cambio%', semanas_caida:'Semanas',
          vs_avg_fmt:'vs Promedio', value_fmt:'Valor'
        };
        let tableHtml = '<div class="msg-table-wrap"><table class="msg-table"><thead><tr>';
        cols.forEach(c => {
          tableHtml += '<th>' + (headerMap[c] || c) + '</th>';
        });
        tableHtml += '</tr></thead><tbody>';
        data.slice(0,15).forEach(row => {
          tableHtml += '<tr>';
          cols.forEach(c => {
            let val = row[c];
            if (val === null || val === undefined) val = '-';
            if (typeof val === 'number' && c.includes('ROLL')) {
              val = (val * 100).toFixed(1) + '%';
            }
            tableHtml += '<td>' + String(val).substring(0, 40) + '</td>';
          });
          tableHtml += '</tr>';
        });
        if (data.length > 15) {
          tableHtml += '<tr><td colspan="' + cols.length + '" style="text-align:center;color:var(--text3);font-style:italic">... y ' + (data.length - 15) + ' más</td></tr>';
        }
        tableHtml += '</tbody></table></div>';
        div.querySelector('.msg-bubble').insertAdjacentHTML('beforeend', tableHtml);
      }
    });
  }

  // Renderizar gráficos para cada tool call que lo soporte
  if (toolCalls && toolCalls.length > 0) {
    toolCalls.forEach((tc, i) => {
      const chartType = tc.chart_type;
      if (!chartType || chartType === 'table') return;

      // Solo renderizar si hay datos suficientes
      if (!tc.result || !tc.result.data || tc.result.data.length < 2) return;

      const chartId  = `chart-${msgId}-${i}`;
      const title    = tc.result.summary || tc.tool;
      const chartDiv = document.createElement('div');
      chartDiv.className = 'msg-chart';
      chartDiv.innerHTML = `
        <div class="msg-chart-title">${escapeHtml(title)}</div>
        <div id="${chartId}"></div>
      `;
      div.querySelector('.msg-bubble').appendChild(chartDiv);

      // Renderizar después de que el DOM esté listo
      requestAnimationFrame(() => {
        renderChartFromToolCall(chartId, tc);
      });
    });
  }

  scrollChat();
}

function addTypingIndicator() {
  const msgs  = document.getElementById('chat-messages');
  const id    = 'typing-' + Date.now();
  const div   = document.createElement('div');
  div.className = 'msg bot';
  div.id = id;
  div.innerHTML = `
    <div class="typing-indicator">
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
      <div class="typing-dot"></div>
    </div>
  `;
  msgs.appendChild(div);
  scrollChat();
  return id;
}

function removeTypingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function scrollChat() {
  const msgs = document.getElementById('chat-messages');
  if (msgs) msgs.scrollTop = msgs.scrollHeight;
}

// -- 6. Reportes ---------------------------------------------------------------
const COUNTRIES_LIST = [
  {code:'AR',name:'Argentina'},{code:'BR',name:'Brasil'},{code:'CL',name:'Chile'},
  {code:'CO',name:'Colombia'},{code:'CR',name:'Costa Rica'},{code:'EC',name:'Ecuador'},
  {code:'MX',name:'México'},{code:'PE',name:'Perú'},{code:'UY',name:'Uruguay'}
];
const METRICS_LIST = [
  'Perfect Orders','Lead Penetration','Gross Profit UE',
  'Pro Adoption (Last Week Status)','Turbo Adoption','Non-Pro PTC > OP',
  'Restaurants Markdowns / GMV','MLTV Top Verticals Adoption',
  '% PRO Users Who Breakeven'
];

async function resumeReportPolling(job_id) {
  // Retoma el polling de un reporte que estaba generándose
  const container = document.getElementById('reports-list');
  if (!container || document.getElementById('generating-card')) return;

  const generatingCard = document.createElement('div');
  generatingCard.className = 'report-generating';
  generatingCard.id = 'generating-card';
  generatingCard.innerHTML =
    '<div class="spinner spinner-lg"></div>' +
    '<div class="report-generating-text">Reporte en generación — recuperando estado...</div>' +
    '<div class="report-generating-sub">El reporte seguirá procesándose automáticamente</div>';
  container.prepend(generatingCard);

  try {
    const result = await pollJob('/api/reports/job/' + job_id, 3000, 120000);
    STATE.activeReportJob = null;
    document.getElementById('generating-card')?.remove();
    if (result && result.report_id) {
      showToast('✅ Reporte listo', 'success');
      loadReports();
      setTimeout(() => previewReport(result.report_id), 500);
    } else {
      loadReports();
    }
  } catch(e) {
    STATE.activeReportJob = null;
    document.getElementById('generating-card')?.remove();
    loadReports();
  }
}

async function loadReports() {
  const container = document.getElementById('reports-list');
  if (!container) return;
  container.innerHTML = '<div class="empty-state"><div class="spinner spinner-lg"></div></div>';
  try {
    const res = await apiFetch('/api/reports/list');
    const { reports } = await res.json();
    if (!reports || reports.length === 0) {
      container.innerHTML =
        '<div class="empty-state">' +
        '<div class="empty-state-icon">📄</div>' +
        '<div class="empty-state-text">No hay reportes generados aún</div>' +
        '<div class="empty-state-sub">Haz clic en "+ Generar nuevo reporte" para crear el primero</div>' +
        '</div>';
      return;
    }
    container.innerHTML = reports.map(r => renderReportCard(r)).join('');
  } catch (e) {
    container.innerHTML = '<div class="empty-state"><div class="empty-state-text">Error cargando reportes</div></div>';
  }
}

function renderReportCard(r, showDelete = false) {
  const stats = r.stats || {};
  const date  = r.created_at ? new Date(r.created_at).toLocaleString('es-CO') : '';
  const deleteBtn = showDelete
    ? '<button class="btn btn-sm" onclick="deleteReportPermanent(\'' + r.report_id + '\')" style="color:var(--danger);border:1.5px solid var(--danger);background:white;border-radius:var(--radius-sm);padding:5px 10px;font-size:11px;font-weight:700">🗑 Eliminar</button>'
    : '<button class="btn btn-sm btn-ghost" onclick="archiveReport(\'' + r.report_id + '\')" title="Mover al historial">📥 Archivar</button>';
  return '<div class="report-card" id="rcard-' + r.report_id + '">' +
    '<div class="report-card-header">' +
      '<div style="flex:1;min-width:0">' +
        '<div class="report-card-title">' + escapeHtml(r.title) + '</div>' +
        '<div class="report-tags">' +
          (stats.anomalies    ? '<span class="badge yellow">⚠️ ' + stats.anomalies + ' anomalías</span>' : '') +
          (stats.trends       ? '<span class="badge red">📉 ' + stats.trends + ' tendencias</span>' : '') +
          (stats.opportunities ? '<span class="badge green">💡 ' + stats.opportunities + ' oportunidades</span>' : '') +
        '</div>' +
        '<div class="report-card-date">' + date + '</div>' +
      '</div>' +
      '<div class="report-actions" style="flex-shrink:0">' +
        '<button class="btn btn-sm btn-ghost" onclick="previewReport(\'' + r.report_id + '\')">👁 Ver</button>' +
        '<button class="btn btn-sm btn-outline" onclick="downloadReport(\'' + r.report_id + '\',\'html\')">↓ HTML</button>' +
        '<button class="btn btn-sm btn-ghost" onclick="downloadReport(\'' + r.report_id + '\',\'csv\')">↓ CSV</button>' +
        deleteBtn +
      '</div>' +
    '</div>' +
  '</div>';
}

async function archiveReport(reportId) {
  // "Eliminar" de la sección de Reportes = mover al historial (solo ocultar de la lista activa)
  // El reporte sigue existiendo y aparece en Historial
  const card = document.getElementById('rcard-' + reportId);
  if (card) {
    card.style.opacity = '0.5';
    card.style.pointerEvents = 'none';
  }
  try {
    await apiFetch('/api/reports/' + reportId + '/archive', { method: 'POST' });
    showToast('Reporte movido al historial', 'info');
    setTimeout(() => loadReports(), 600);
  } catch(e) {
    if (card) { card.style.opacity = '1'; card.style.pointerEvents = ''; }
    showToast('Error al archivar', 'error');
  }
}

async function deleteReportPermanent(reportId) {
  const confirmed = await showConfirmModal(
    'Eliminar reporte',
    '¿Estás segura de que quieres eliminar este reporte? Esta acción no se puede deshacer.',
    'Sí, eliminar',
    'danger'
  );
  if (!confirmed) return;
  try {
    await apiFetch('/api/reports/' + reportId, { method: 'DELETE' });
    showToast('Reporte eliminado', 'info');
    loadReportHistory();
  } catch(e) {
    showToast('Error al eliminar', 'error');
  }
}

function onReportTypeChange(type) {
  const allCheckboxes = document.querySelectorAll('#rpt-country-wrap input[type=checkbox]');
  if (type === 'weekly') {
    // Semanal global — marcar todos los países
    allCheckboxes.forEach(cb => { cb.checked = true; });
  } else if (type === 'anomalies' || type === 'opportunities') {
    // Mantener selección actual
  } else if (type === 'country') {
    // Por país — desmarcar todos para que el usuario elija uno
    allCheckboxes.forEach(cb => { cb.checked = false; });
  }
}

function generateReport() {
  // Mostrar modal de configuración
  const modal = document.createElement('div');
  modal.id = 'report-modal';
  modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:9000;display:flex;align-items:center;justify-content:center;padding:20px';

  const weekOpts = WEEK_OPTIONS.map(o =>
    '<option value="' + o.value.replace('_ROLL','') + '">' + o.label + '</option>'
  ).join('');
  const countryOpts = COUNTRIES_LIST.map(c =>
    '<label style="display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;cursor:pointer">' +
    '<input type="checkbox" value="' + c.code + '" style="accent-color:var(--rappi)"> ' + c.name + '</label>'
  ).join('');
  const metricOpts = METRICS_LIST.map(m =>
    '<label style="display:flex;align-items:center;gap:6px;font-size:12px;font-weight:600;cursor:pointer">' +
    '<input type="checkbox" value="' + m + '" checked style="accent-color:var(--rappi)"> ' + m + '</label>'
  ).join('');

  modal.innerHTML =
    '<div style="background:white;border-radius:16px;width:100%;max-width:560px;max-height:88vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.2)">' +
      '<div style="background:var(--rappi);padding:20px 24px;border-radius:16px 16px 0 0;display:flex;justify-content:space-between;align-items:center">' +
        '<div style="color:white;font-size:16px;font-weight:800">Configurar Reporte Ejecutivo</div>' +
        '<button onclick="document.getElementById(\'report-modal\').remove()" style="background:rgba(255,255,255,0.2);border:none;color:white;width:28px;height:28px;border-radius:50%;font-size:16px;cursor:pointer">x</button>' +
      '</div>' +
      '<div style="padding:24px;display:flex;flex-direction:column;gap:20px">' +

        '<div>' +
          '<div style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;color:var(--text2);margin-bottom:8px">Tipo de reporte</div>' +
          '<select id="rpt-type" onchange="onReportTypeChange(this.value)" style="width:100%;border:2px solid var(--border);border-radius:8px;padding:9px 12px;font-size:13px;font-family:inherit;font-weight:600;outline:none">' +
            '<option value="weekly">Semanal global (todos los países)</option>' +
            '<option value="country">Por país específico</option>' +
            '<option value="anomalies">Solo anomalías y alertas</option>' +
            '<option value="opportunities">Solo oportunidades de crecimiento</option>' +
          '</select>' +
        '</div>' +

        '<div>' +
          '<div style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;color:var(--text2);margin-bottom:8px">Intervalo de análisis</div>' +
          '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">' +
            '<div>' +
              '<label style="font-size:11px;font-weight:700;color:var(--text3);display:block;margin-bottom:4px">Desde</label>' +
              '<select id="rpt-from" style="width:100%;border:2px solid var(--border);border-radius:8px;padding:8px 10px;font-size:12px;font-family:inherit;font-weight:600;outline:none">' +
              weekOpts.replace('value="L0W"', 'value="L8W"').replace('value="L8W"','value="L8W" selected') +
              '</select>' +
            '</div>' +
            '<div>' +
              '<label style="font-size:11px;font-weight:700;color:var(--text3);display:block;margin-bottom:4px">Hasta</label>' +
              '<select id="rpt-to" style="width:100%;border:2px solid var(--border);border-radius:8px;padding:8px 10px;font-size:12px;font-family:inherit;font-weight:600;outline:none">' +
              weekOpts +
              '</select>' +
            '</div>' +
          '</div>' +
        '</div>' +

        '<div id="rpt-country-wrap">' +
          '<div style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;color:var(--text2);margin-bottom:8px">Países a incluir</div>' +
          '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;background:var(--bg);border-radius:8px;padding:12px">' +
          countryOpts +
          '</div>' +
        '</div>' +

        '<div>' +
          '<div style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;color:var(--text2);margin-bottom:8px">Métricas a analizar</div>' +
          '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;background:var(--bg);border-radius:8px;padding:12px">' +
          metricOpts +
          '</div>' +
        '</div>' +

        '<div>' +
          '<div style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.6px;color:var(--text2);margin-bottom:8px">Título del reporte (opcional)</div>' +
          '<input id="rpt-title" type="text" placeholder="Ej: Reporte Q1 2026 -- Colombia" style="width:100%;border:2px solid var(--border);border-radius:8px;padding:9px 12px;font-size:13px;font-family:inherit;font-weight:500;outline:none">' +
        '</div>' +

        '<button onclick="submitReportConfig()" style="width:100%;background:var(--rappi);color:white;border:none;border-radius:8px;padding:13px;font-size:14px;font-weight:800;cursor:pointer">Generar reporte →</button>' +
      '</div>' +
    '</div>';

  document.body.appendChild(modal);
  modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
}

async function submitReportConfig() {
  const type    = document.getElementById('rpt-type').value;
  const fromW   = document.getElementById('rpt-from').value;
  const toW     = document.getElementById('rpt-to').value;
  const title   = document.getElementById('rpt-title').value.trim();
  const countries = [...document.querySelectorAll('#rpt-country-wrap input:checked')].map(i => i.value);
  const metrics   = [...document.querySelectorAll('#report-modal input[type=checkbox]:checked')].filter(i => !COUNTRIES_LIST.find(c => c.code === i.value)).map(i => i.value);

  document.getElementById('report-modal')?.remove();

  const container = document.getElementById('reports-list');
  const generatingCard = document.createElement('div');
  generatingCard.className = 'report-generating';
  generatingCard.id = 'generating-card';
  generatingCard.innerHTML =
    '<div class="spinner spinner-lg"></div>' +
    '<div class="report-generating-text">Generando reporte ejecutivo con IA...</div>' +
    '<div class="report-generating-sub">Analizando ' + (metrics.length || 'todas las') + ' métricas · ' + (countries.length || '9') + ' países · semanas ' + fromW + ' a ' + toW + '</div>';
  container.prepend(generatingCard);
  showToast('Generando reporte... esto puede tomar 30-60 segundos', 'info');

  try {
    const res = await apiFetch('/api/reports/generate', {
      method: 'POST',
      body: JSON.stringify({
        report_type: type,
        country:     countries.length === 1 ? countries[0] : null,
        countries:   countries,
        metrics:     metrics,
        week_from:   fromW,
        week_to:     toW,
        title:       title || null
      })
    });
    const { job_id } = await res.json();
    STATE.activeReportJob = job_id;
    const result = await pollJob('/api/reports/job/' + job_id, 3000, 180000);
    STATE.activeReportJob = null;
    document.getElementById('generating-card')?.remove();
    if (result && result.error) {
      showToast('Error generando reporte: ' + result.error, 'error');
    } else if (result && result.report_id) {
      showToast('✅ Reporte generado', 'success');
      loadReports();
      setTimeout(() => previewReport(result.report_id), 500);
    }
  } catch (e) {
    STATE.activeReportJob = null;
    document.getElementById('generating-card')?.remove();
    showToast('Error de conexión', 'error');
  }

}
async function previewReport(reportId) {
  try {
    const res    = await apiFetch('/api/reports/' + reportId);
    const report = await res.json();
    if (!report || !report.markdown) return;

    const modal = document.createElement('div');
    modal.id = 'preview-modal';
    modal.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:9000;display:flex;align-items:center;justify-content:center;padding:20px';

    const stats = report.stats || {};
    const date  = report.created_at ? new Date(report.created_at).toLocaleString('es-CO') : '';

    // Convertir markdown a HTML para preview (con soporte de tablas)
    let html = report.markdown;
    // Tablas markdown
    html = html.replace(/((?:^\|.+\|[ ]*\n)+)/gm, function(block) {
      const rows = block.trim().split("\n").filter(l => l.trim());
      if (rows.length < 2) return block;
      const headers = rows[0].split("|").map(c => c.trim()).filter(c => c);
      const body = rows.slice(1).filter(l => !/^[\|\-\s:]+$/.test(l.trim()));
      const thCss = "background:var(--rappi-light);color:var(--rappi-dark);padding:8px 12px;text-align:left;font-weight:800;font-size:11px;text-transform:uppercase;letter-spacing:.4px;border-bottom:2px solid var(--rappi-light2);white-space:nowrap";
      const tdCss = "padding:8px 12px;border-bottom:1px solid var(--border2);font-weight:500;color:var(--text)";
      const thead = "<tr>" + headers.map(h => "<th style=\"" + thCss + "\">" + h + "</th>").join("") + "</tr>";
      const tbody = body.map(r => { const cells = r.split("|").map(c=>c.trim()).filter(c=>c); return "<tr>" + cells.map((c,i) => "<td style=\"" + tdCss + (i===0?";font-weight:700":"") + "\">" + c + "</td>").join("") + "</tr>"; }).join("");
      return "<div style=\"overflow-x:auto;margin:12px 0;border-radius:8px;border:1px solid var(--border)\"><table style=\"width:100%;border-collapse:collapse;font-size:12px\"><thead>" + thead + "</thead><tbody>" + tbody + "</tbody></table></div>";
    });
    html = html
      .replace(/^# (.+)$/gm, '<h1 style="font-size:20px;font-weight:800;color:var(--rappi);margin:20px 0 10px">$1</h1>')
      .replace(/^## (.+)$/gm, '<h2 style="font-size:15px;font-weight:800;color:var(--text);margin:16px 0 8px;padding-bottom:6px;border-bottom:2px solid var(--rappi)">$1</h2>')
      .replace(/^### (.+)$/gm, '<h3 style="font-size:13px;font-weight:700;color:var(--text2);margin:12px 0 6px">$1</h3>')
      .replace(/[*][*](.+?)[*][*]/g, '<strong>$1</strong>')
      .replace(/^[-] (.+)$/gm, '<li style="margin-bottom:4px;font-weight:500;color:var(--text2)">$1</li>')
      .replace(/\n\n/g, '</p><p style="margin-bottom:8px;font-weight:500;color:var(--text2)">')
      .replace(/^([^<].+)$/gm, '<p style="margin-bottom:8px;font-weight:500;color:var(--text2)">$1</p>');
    modal.innerHTML =
      '<div style="background:white;border-radius:16px;width:100%;max-width:780px;max-height:90vh;display:flex;flex-direction:column;box-shadow:0 20px 60px rgba(0,0,0,0.25)">' +
        '<div style="background:var(--rappi);padding:18px 24px;border-radius:16px 16px 0 0;display:flex;justify-content:space-between;align-items:center;flex-shrink:0">' +
          '<div>' +
            '<div style="color:white;font-size:15px;font-weight:800">' + escapeHtml(report.title) + '</div>' +
            '<div style="color:rgba(255,255,255,0.8);font-size:11px;margin-top:2px;font-weight:500">' + date + '</div>' +
          '</div>' +
          '<div style="display:flex;gap:8px;align-items:center">' +
            '<button onclick="downloadReport(\'' + reportId + '\',\'html\')" style="background:white;color:var(--rappi);border:none;padding:7px 14px;border-radius:6px;font-size:12px;font-weight:800;cursor:pointer">↓ HTML</button>' +
            '<button onclick="downloadReport(\'' + reportId + '\',\'csv\')" style="background:rgba(255,255,255,0.2);color:white;border:1px solid rgba(255,255,255,0.4);padding:7px 14px;border-radius:6px;font-size:12px;font-weight:800;cursor:pointer">↓ CSV</button>' +
            '<button onclick="document.getElementById(\'preview-modal\').remove()" style="background:rgba(255,255,255,0.2);border:none;color:white;width:30px;height:30px;border-radius:50%;font-size:18px;cursor:pointer">x</button>' +
          '</div>' +
        '</div>' +
        '<div style="display:flex;gap:10px;padding:14px 24px;background:var(--bg);border-bottom:1px solid var(--border);flex-shrink:0">' +
          (stats.anomalies    ? '<span class="badge yellow">⚠️ ' + stats.anomalies + ' anomalías</span>' : '') +
          (stats.trends       ? '<span class="badge red">📉 ' + stats.trends + ' tendencias</span>' : '') +
          (stats.opportunities ? '<span class="badge green">💡 ' + stats.opportunities + ' oportunidades</span>' : '') +
        '</div>' +
        '<div style="overflow-y:auto;padding:24px 28px;flex:1">' + html + '</div>' +
      '</div>';

    document.body.appendChild(modal);
    modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });
  } catch(e) {
    showToast('Error cargando el reporte', 'error');
  }
}

function downloadReport(reportId, format) {
  window.open('/api/reports/' + reportId + '/download/' + format, '_blank');
}

// -- 7. Historial --------------------------------------------------------------
async function loadHistory() {
  loadChatHistory();
  loadReportHistory();
}

async function loadChatHistory() {
  const container = document.getElementById('hist-chats');
  if (!container) return;

  container.innerHTML = '<div class="empty-state"><div class="spinner"></div></div>';

  try {
    const res  = await apiFetch('/api/chat/history');
    const data = await res.json();
    const convos = data.conversations || [];

    if (convos.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">💬</div>
          <div class="empty-state-text">No hay conversaciones aún</div>
          <div class="empty-state-sub">Ve al Chat Analítico para empezar</div>
        </div>`;
      return;
    }

    container.innerHTML = convos.map(c => `
      <div class="history-item" onclick="resumeConversation('${c.session_id}')">
        <div class="hi-icon chat">💬</div>
        <div class="hi-info">
          <div class="hi-title">${escapeHtml(c.title)}</div>
          <div class="hi-sub">
            <span class="badge orange">${c.msg_count} mensajes</span>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
          <div class="hi-date">${formatRelativeDate(c.updated_at)}</div>
          <button class="hi-delete" onclick="deleteConversation(event,'${c.session_id}')">✕</button>
        </div>
      </div>
    `).join('');
  } catch (e) {
    container.innerHTML = '<div class="empty-state"><div class="empty-state-text">Error cargando historial</div></div>';
  }
}

async function loadReportHistory() {
  const container = document.getElementById('hist-reports');
  if (!container) return;

  try {
    // Historial incluye todos — archivados y activos
    const res     = await apiFetch('/api/reports/list?archived=true');
    const { reports } = await res.json();

    if (!reports || reports.length === 0) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">📄</div>
          <div class="empty-state-text">No hay reportes generados aún</div>
        </div>`;
      return;
    }

    container.innerHTML = reports.map(r => {
      const date = formatRelativeDate(r.created_at);
      const stats = r.stats || {};
      return '<div class="history-item" style="flex-direction:column;align-items:stretch;gap:8px">' +
        '<div style="display:flex;align-items:center;gap:12px">' +
          '<div class="hi-icon report">📄</div>' +
          '<div class="hi-info">' +
            '<div class="hi-title">' + escapeHtml(r.title) + '</div>' +
            '<div class="hi-sub">' +
              '<span class="badge blue">HTML + CSV</span> ' +
              (stats.anomalies ? '<span class="badge yellow">⚠️ ' + stats.anomalies + '</span> ' : '') +
              (stats.opportunities ? '<span class="badge green">💡 ' + stats.opportunities + '</span>' : '') +
            '</div>' +
          '</div>' +
          '<div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;flex-shrink:0">' +
            '<div class="hi-date">' + date + '</div>' +
            '<div style="display:flex;gap:5px">' +
              '<button class="btn btn-sm btn-ghost" onclick="previewReport(\'' + r.report_id + '\')">👁 Ver</button>' +
              '<button class="btn btn-sm btn-outline" onclick="downloadReport(\'' + r.report_id + '\',\'html\')">↓ HTML</button>' +
              '<button class="btn btn-sm btn-ghost" onclick="downloadReport(\'' + r.report_id + '\',\'csv\')">↓ CSV</button>' +
              '<button onclick="deleteReportPermanent(\'' + r.report_id + '\')" style="background:none;border:1.5px solid var(--danger);color:var(--danger);border-radius:var(--radius-sm);padding:5px 10px;font-size:11px;font-weight:700;cursor:pointer">🗑</button>' +
            '</div>' +
          '</div>' +
        '</div>' +
      '</div>';
    }).join('');
  } catch (e) {}
}

async function resumeConversation(sessionId) {
  try {
    const res  = await apiFetch(`/api/chat/history/${sessionId}`);
    const data = await res.json();

    // Limpiar chat y cargar mensajes
    const msgs = document.getElementById('chat-messages');
    msgs.innerHTML = '';
    STATE.sessionId = sessionId;

    // Agregar mensaje de contexto
    addBotMessage(`📂 *Retomando conversación anterior*\n\n${data.summary || 'Contexto cargado. ¿En qué continuamos?'}`);

    // Mostrar últimos 6 mensajes del historial
    const history = data.messages || [];
    const recent  = history.slice(-6);
    recent.forEach(m => {
      if (m.role === 'user')      addUserMessage(m.content);
      else if (m.role === 'assistant') addBotMessage(m.content);
    });

    // Navegar al chat
    navigate('chat', document.querySelectorAll('.nav-item')[1]);
    showToast('Conversación retomada', 'success');
  } catch (e) {
    showToast('Error cargando la conversación', 'error');
  }
}

async function deleteConversation(event, sessionId) {
  event.stopPropagation();
  const confirmed = await showConfirmModal(
    'Eliminar conversación',
    '¿Estás segura de que quieres eliminar esta conversación? Esta acción no se puede deshacer.',
    'Sí, eliminar',
    'danger'
  );
  if (!confirmed) return;

  await apiFetch(`/api/chat/history/${sessionId}`, { method: 'DELETE' });
  loadChatHistory();
  showToast('Conversación eliminada', 'info');
}

// -- 8. Diccionario ------------------------------------------------------------
const METRICS_INFO = [
  {
    name:    'Perfect Orders',
    formula: 'Órdenes sin defectos / Total órdenes',
    desc:    'Calidad operacional end-to-end. Mide qué % de órdenes llega a tiempo, sin errores y sin cancelaciones.',
    dir:     'up',
    dirText: '↑ Subir es bueno'
  },
  {
    name:    'Lead Penetration',
    formula: 'Tiendas habilitadas / (Leads + Habilitadas + Salidas)',
    desc:    'Cobertura de mercado potencial. Qué % de los locales identificados ya están activos en Rappi.',
    dir:     'up',
    dirText: '↑ Subir es bueno'
  },
  {
    name:    'Gross Profit UE',
    formula: 'Margen bruto / Total órdenes',
    desc:    'Ganancia por orden. El indicador de salud financiera más importante a nivel de zona. Valor monetario.',
    dir:     'up',
    dirText: '↑ Subir es bueno'
  },
  {
    name:    'Pro Adoption',
    formula: 'Usuarios Pro / Total usuarios activos',
    desc:    'Penetración de Rappi Prime. Usuarios Pro tienen mayor LTV y más frecuencia de compra.',
    dir:     'up',
    dirText: '↑ Subir es bueno'
  },
  {
    name:    'Turbo Adoption',
    formula: 'Usuarios Turbo / Usuarios con Turbo disponible',
    desc:    'Adopción del delivery express (15-30 min). Vertical de alto margen y diferenciador competitivo.',
    dir:     'up',
    dirText: '↑ Subir es bueno'
  },
  {
    name:    'Non-Pro PTC > OP',
    formula: 'Órdenes completadas / Usuarios No-Pro en checkout',
    desc:    'Conversión final del funnel para no suscritos. Detecta fricciones en el momento de pago.',
    dir:     'up',
    dirText: '↑ Subir es bueno'
  },
  {
    name:    'Restaurants Markdowns / GMV',
    formula: 'Descuentos restaurantes / GMV restaurantes',
    desc:    'Dependencia de promociones. Valor alto indica que la demanda solo funciona con descuentos -- insostenible.',
    dir:     'down',
    dirText: '↓ Bajar es bueno'
  },
  {
    name:    'MLTV Top Verticals Adoption',
    formula: 'Usuarios multi-vertical / Total usuarios',
    desc:    'Qué tan "pegajoso" es Rappi. Usuarios que usan múltiples verticales tienen mayor LTV y menor churn.',
    dir:     'up',
    dirText: '↑ Subir es bueno'
  },
  {
    name:    '% PRO Users Who Breakeven',
    formula: 'Usuarios Pro rentables / Total usuarios Pro',
    desc:    'Qué % de usuarios Pro generan suficiente valor para cubrir el costo de la membresía.',
    dir:     'up',
    dirText: '↑ Subir es bueno'
  },
  {
    name:    'Restaurants SS > ATC CVR',
    formula: 'Sesiones con algo en carrito / Sesiones en restaurante',
    desc:    'Conversión del catálogo: qué % de usuarios que entran a un restaurante agregan algo al carrito.',
    dir:     'up',
    dirText: '↑ Subir es bueno'
  },
  {
    name:    'Restaurants SST > SS CVR',
    formula: 'Seleccionan tienda / Entran a categoría restaurantes',
    desc:    'Conversión del listado: qué % de usuarios que ven restaurantes entran a uno específico.',
    dir:     'up',
    dirText: '↑ Subir es bueno'
  },
  {
    name:    'Retail SST > SS CVR',
    formula: 'Seleccionan tienda / Entran a categoría supermercados',
    desc:    'Igual que el anterior pero para supermercados.',
    dir:     'up',
    dirText: '↑ Subir es bueno'
  },
  {
    name:    '% Restaurants Sessions With Optimal Assortment',
    formula: 'Sesiones con ≥40 restaurantes / Total sesiones',
    desc:    'En qué % de sesiones el usuario tiene suficiente variedad. Menos de 40 restaurantes limita la conversión.',
    dir:     'up',
    dirText: '↑ Subir es bueno'
  },
];

function loadDictionary() {
  const grid = document.getElementById('dict-grid');
  if (!grid) return;

  grid.innerHTML = METRICS_INFO.map(m => `
    <div class="metric-card" onclick="fillChat('Explícame en detalle la métrica ${m.name} y cómo está en las zonas esta semana')">
      <div class="metric-card-name">${m.name}</div>
      <div class="metric-card-formula">${m.formula}</div>
      <div class="metric-card-desc">${m.desc}</div>
      <div class="metric-card-dir ${m.dir}">${m.dirText}</div>
    </div>
  `).join('');
}

// -- 9. Utilidades -------------------------------------------------------------
async function apiFetch(url, options = {}) {
  const defaults = {
    credentials: 'include',
    headers:     { 'Content-Type': 'application/json' },
  };
  return fetch(url, { ...defaults, ...options,
    headers: { ...defaults.headers, ...(options.headers || {}) }
  });
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatTime(date) {
  return date.toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' });
}

function formatRelativeDate(isoStr) {
  if (!isoStr) return '';
  const d    = new Date(isoStr);
  const now  = new Date();
  const diff = Math.floor((now - d) / 1000);
  if (diff < 60)     return 'hace un momento';
  if (diff < 3600)   return `hace ${Math.floor(diff/60)} min`;
  if (diff < 86400)  return `hace ${Math.floor(diff/3600)}h`;
  if (diff < 172800) return 'ayer';
  return d.toLocaleDateString('es-CO');
}

// -- Confirm Modal ----------------------------------------------------------
function showConfirmModal(title, message, confirmLabel, variant) {
  variant = variant || "danger";
  return new Promise(function(resolve) {
    document.getElementById("confirm-modal")?.remove();
    var bg = variant === "danger" ? "var(--danger)" : "var(--rappi)";
    var light = variant === "danger" ? "var(--danger-light)" : "var(--rappi-light)";
    var icon = variant === "danger" ? "🗑" : "⚠️";
    var modal = document.createElement("div");
    modal.id = "confirm-modal";
    modal.style.cssText = "position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.45);display:flex;align-items:center;justify-content:center;padding:20px";
    modal.innerHTML =
      "<div style=\"background:var(--white);border-radius:14px;width:100%;max-width:400px;box-shadow:0 20px 60px rgba(0,0,0,0.2);overflow:hidden\">" +
        "<div style=\"padding:20px 22px 16px;border-bottom:1px solid var(--border)\">" +
          "<div style=\"display:flex;align-items:center;gap:10px\">" +
            "<div style=\"width:32px;height:32px;border-radius:8px;background:" + light + ";display:flex;align-items:center;justify-content:center;font-size:16px\">" + icon + "</div>" +
            "<div style=\"font-size:15px;font-weight:800;color:var(--text)\">" + title + "</div>" +
          "</div>" +
        "</div>" +
        "<div style=\"padding:16px 22px 20px\">" +
          "<p style=\"font-size:13px;color:var(--text2);font-weight:500;line-height:1.6;margin-bottom:18px\">" + message + "</p>" +
          "<div style=\"display:flex;gap:8px;justify-content:flex-end\">" +
            "<button id=\"confirm-cancel\" style=\"background:none;border:1.5px solid var(--border);border-radius:8px;padding:8px 18px;font-size:13px;font-weight:700;color:var(--text2);cursor:pointer;font-family:inherit\">Cancelar</button>" +
            "<button id=\"confirm-ok\" style=\"background:" + bg + ";border:none;border-radius:8px;padding:8px 18px;font-size:13px;font-weight:700;color:#fff;cursor:pointer;font-family:inherit\">" + confirmLabel + "</button>" +
          "</div>" +
        "</div>" +
      "</div>";
    document.body.appendChild(modal);
    function cleanup(result) {
      modal.remove();
      resolve(result);
    }
    modal.querySelector("#confirm-ok").onclick = function() { cleanup(true); };
    modal.querySelector("#confirm-cancel").onclick = function() { cleanup(false); };
    modal.addEventListener("click", function(e) { if (e.target === modal) cleanup(false); });
  });
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast     = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// -- Inicialización -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
  // Enter en login
  document.getElementById('login-pass')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') doLogin();
  });
  // Verificar si ya hay sesión activa
  checkSession();
});
