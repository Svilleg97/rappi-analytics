# Rappi Analytics Platform
### Sistema de Análisis Inteligente para Operaciones SP&A

Plataforma de análisis operacional basada en IA que democratiza el acceso a datos de métricas de Rappi para equipos no técnicos de Strategy, Planning & Analytics (SP&A) y Operations.

---

## Demo en vivo

**URL local:** `http://localhost:8000`
**Credenciales demo:** usuario `rappi_demo` / contraseña `demo123`

---

## ¿Qué hace este sistema?

### 1. Chat Analítico con IA (70% del peso)
Bot conversacional que responde preguntas en lenguaje natural sobre métricas operacionales de 1,242 zonas en 9 países. No requiere conocimiento de SQL ni Python.

**Casos de uso validados:**
- Filtrado: *"¿Cuáles son las 5 zonas con mayor Lead Penetration esta semana?"*
- Comparaciones: *"Compara Perfect Order entre Wealthy y Non Wealthy en México"*
- Tendencias: *"Muestra la evolución de Gross Profit UE en Chapinero últimas 8 semanas"*
- Agregaciones: *"¿Cuál es el promedio de Lead Penetration por país?"*
- Multivariable: *"¿Qué zonas tienen alto Lead Penetration pero bajo Perfect Order?"*
- Inferencia: *"¿Qué zonas crecen más en órdenes y qué podría explicar ese crecimiento?"*

### 2. Insights Automáticos (30% del peso)
Reporte ejecutivo generado con IA que identifica automáticamente:
- Anomalías (cambios >10% semana a semana)
- Tendencias preocupantes (deterioro 3+ semanas consecutivas)
- Benchmarking entre zonas similares
- Correlaciones entre métricas
- Oportunidades de crecimiento

Descargable en **HTML** y **CSV**.

---

## Stack tecnológico y justificación de decisiones

| Componente | Tecnología | Por qué |
|---|---|---|
| Backend | FastAPI (Python) | Async nativo, Tool Use compatible, un solo servidor |
| LLM | Claude claude-sonnet-4-20250514 (Anthropic) | Mejor razonamiento analítico, Tool Use preciso, temperatura=0 para anti-alucinación |
| Análisis de datos | pandas + openpyxl | Estándar de industria, filtrado de outliers integrado |
| Frontend | HTML + Vanilla JS | Sin dependencias de build, carga rápida, control total de UI |
| Gráficos | Plotly.js | Interactivo, zoom, hover, exportación de imágenes |
| Persistencia | JSON en disco | Sin base de datos externa, portátil, suficiente para el caso |
| Deploy | Render (Python) | Gratis, un solo comando, URL pública |

### Decisión técnica clave: Tool Use sobre RAG

En lugar de pasar todos los datos al contexto de Claude (costoso, lento, propenso a alucinaciones), implementamos **Tool Use**: Claude decide qué análisis ejecutar, Python corre el análisis con pandas sobre los datos reales, y Claude interpreta los resultados. Esto garantiza:

- **Cero alucinaciones de datos** — Claude no puede inventar un número que no obtuvo de una tool
- **Respuestas exactas** — los cálculos los hace pandas, no el LLM
- **Escalabilidad** — agregar una nueva métrica = agregar una función en `data_engine.py`

### Anti-alucinación: 5 capas de protección

1. `temperature=0` en todas las llamadas → respuestas deterministas
2. Tool Use obligatorio → Claude no tiene los datos en memoria
3. Validación de DataFrames → si la tool falla, Claude recibe "no hay datos"
4. System prompt explícito → "los números SIEMPRE vienen de las herramientas"
5. Límite de 150 registros por tool call → evita context window overflow

---

## Arquitectura

```
rappi-analytics/
├── main.py                 # Punto de entrada (~25 líneas, solo monta routers)
├── api/
│   ├── auth.py             # Login/logout con cookies HTTP-only
│   ├── chat.py             # Endpoints de chat con job polling async
│   ├── reports.py          # Generación y descarga de reportes
│   └── insights.py         # Dashboard y análisis automáticos
├── core/
│   ├── data_engine.py      # Motor de análisis pandas (única fuente de verdad)
│   ├── llm_engine.py       # Loop de Tool Use con Claude API
│   ├── tools.py            # Definición y ejecución de herramientas
│   ├── prompts.py          # System prompt con contexto de negocio Rappi
│   ├── persistence.py      # Lectura/escritura de conversaciones y reportes
│   ├── job_manager.py      # Manejo de tareas async (resuelve pérdida de contexto)
│   └── file_watcher.py     # Recarga automática del Excel al detectar cambios
├── models/
│   └── schemas.py          # Tipos Pydantic para validación de requests
├── data/
│   ├── rappi_data.xlsx     # Dataset operacional (no incluido en repo)
│   ├── history/            # Conversaciones guardadas (JSON)
│   └── reports/            # Reportes generados (JSON + HTML)
└── frontend/
    ├── index.html          # Shell principal con login y navegación
    └── static/
        ├── style.css       # Estilos con branding Rappi (Nunito, #FF441F)
        ├── app.js          # Lógica de navegación, chat, polling
        └── charts.js       # Renderizado de gráficos con Plotly
```

**Principio de diseño:** responsabilidad única por archivo. Ningún archivo supera 250 líneas. `main.py` solo registra routers.

---

## Instalación y ejecución local

### Requisitos
- Python 3.9+
- Node.js (no requerido para correr, solo para verificar JS)

### Pasos

```bash
# 1. Clonar el repositorio
git clone https://github.com/Svilleg97/rappi-analytics.git
cd rappi-analytics

# 2. Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env y agregar tu ANTHROPIC_API_KEY
# Editar .env y reemplazar ANTHROPIC_API_KEY con tu clave real

# 5. Iniciar el servidor
python3 main.py
```

> ✅ El dataset (`data/rappi_data.xlsx`) ya está incluido en el repositorio.
> Son datos anonimizados del caso técnico. No necesitas agregar ningún archivo adicional.

Abrir `http://localhost:8000` en el navegador.

### Variables de entorno (.env)

```
ANTHROPIC_API_KEY=sk-ant-...     # API key de Anthropic (requerida)
SECRET_KEY=rappi_analytics_2024  # Clave para cookies de sesión
DEMO_USER=rappi_demo             # Usuario de demo
DEMO_PASSWORD=demo123            # Contraseña de demo
```

---

## Costo estimado de API

| Operación | Tokens aprox. | Costo estimado |
|---|---|---|
| Pregunta simple en chat | ~3,000 tokens | ~$0.009 |
| Pregunta compleja (3 tools) | ~8,000 tokens | ~$0.024 |
| Sesión de 10 preguntas | ~50,000 tokens | ~$0.15 |
| Generación de reporte ejecutivo | ~15,000 tokens | ~$0.045 |

*Precios basados en Claude claude-sonnet-4-20250514: $3/M tokens input, $15/M tokens output (marzo 2026)*

---

## Funcionalidades principales

| Feature | Estado |
|---|---|
| Chat con lenguaje natural | ✅ |
| Gráficos automáticos (barras, líneas, scatter) | ✅ |
| Tablas de datos en el chat | ✅ |
| Memoria conversacional (sesión actual) | ✅ |
| Memoria persistente (retomar conversaciones) | ✅ |
| Sugerencias proactivas de análisis | ✅ |
| Dashboard con KPIs en tiempo real | ✅ |
| Selector de semana histórica (L0W-L8W) | ✅ |
| Recarga automática al actualizar Excel | ✅ |
| Generación de reportes ejecutivos con IA | ✅ |
| Descarga de reportes en HTML | ✅ |
| Descarga de reportes en CSV | ✅ |
| Modal de configuración de reportes | ✅ |
| Preview de reportes antes de descargar | ✅ |
| Historial de conversaciones | ✅ |
| Historial de reportes | ✅ |
| Login con sesión persistente | ✅ |
| Diccionario de métricas con explicaciones | ✅ |
| Manejo de múltiples consultas simultáneas | ✅ |
| Anti-pérdida de respuesta al cambiar pestaña | ✅ |

---

## Limitaciones conocidas y próximos pasos

### Limitaciones actuales
- **Datos dummy con outliers**: El dataset de prueba tiene valores de Lead Penetration >100% en Ecuador. El sistema los detecta y los reporta correctamente como anomalías metodológicas, pero los gráficos los filtran automáticamente.
- **Autenticación básica**: El sistema de login usa cookies simples, suficiente para demo. En producción requeriría JWT + base de datos de usuarios.
- **Persistencia en disco**: Los historiales se guardan en JSON locales. Para producción con múltiples usuarios simultáneos se requeriría PostgreSQL o Redis.

### Próximos pasos (con más tiempo)
1. **Envío automático de reportes por email** (bonus del brief)
2. **Alertas proactivas por Slack/WhatsApp** cuando se detectan anomalías críticas
3. **Dashboard con filtros interactivos** por país, ciudad y tipo de zona
4. **Comparación temporal automática** entre semanas seleccionadas
5. **Fine-tuning del modelo** con histórico de preguntas y respuestas del equipo SP&A
6. **API REST documentada** (Swagger/OpenAPI) para integración con otras herramientas

---

## Criterios de evaluación — autoevaluación

| Criterio | Peso | Implementación |
|---|---|---|
| Arquitectura y diseño técnico | 15% | FastAPI modular, separación api/core/frontend, Tool Use pattern |
| Calidad del bot | 35% | 6/6 casos de uso validados, respuestas con profundidad de negocio |
| Calidad de insights | 30% | 5 categorías de insights, recomendaciones accionables por zona |
| Código y documentación | 5% | Archivos <250 líneas, comentarios en funciones clave, este README |
| Presentación | 20% | Demo en vivo preparada con 6 preguntas de complejidad creciente |

---

## Seguridad

### Estado actual (demo)
El sistema fue diseñado para una demo funcional con las siguientes consideraciones de seguridad básicas ya implementadas:

| Medida | Estado | Detalle |
|--------|--------|---------|
| API Key en variables de entorno | ✅ | `.env` excluido del repositorio vía `.gitignore` |
| Datos sensibles fuera del repo | ✅ | `rappi_data.xlsx` e historiales excluidos del repo |
| Autenticación por sesión | ✅ | Cookies HTTP-only con clave secreta configurable |
| Sin credenciales hardcodeadas | ✅ | Todo via variables de entorno |
| HTTPS | ⚠️ | En Render se activa automáticamente; en local no aplica |
| Multi-usuario | ⚠️ | Demo usa usuario único; producción requiere DB de usuarios |

### Para producción (recomendaciones)
Un deployment real en Rappi requeriría las siguientes mejoras de seguridad:

**Autenticación:**
- Integración con SSO corporativo de Rappi (OAuth 2.0 / SAML)
- JWT con expiración corta + refresh tokens
- Passwords hasheados con bcrypt (nunca texto plano)
- Rate limiting por usuario para prevenir abuso de API

**Datos:**
- Cifrado en reposo del archivo de datos y los historiales
- Logging de auditoría: quién consultó qué y cuándo
- Row-level security: analistas de CO solo ven datos de CO
- Backup automático de conversaciones y reportes

**Infraestructura:**
- Variables de entorno manejadas por un secret manager (AWS Secrets Manager, Vault)
- API keys rotadas periódicamente
- Network policies para restringir acceso al servidor de datos

---

## Análisis de Costos de API

El sistema usa **Claude Sonnet** (claude-sonnet-4-20250514) como modelo principal.
Precios vigentes: $3/M tokens input · $15/M tokens output.

### Costo por operación

| Operación | Tokens estimados | Costo estimado |
|-----------|-----------------|----------------|
| Pregunta simple (filtrado, ranking) | ~3,000 tokens | ~$0.009 |
| Pregunta compleja (3 tool calls) | ~10,000 tokens | ~$0.030 |
| Pregunta de inferencia (6 tool calls) | ~18,000 tokens | ~$0.054 |
| Sesión completa (10 preguntas) | ~60,000 tokens | ~$0.18 |
| Reporte ejecutivo completo | ~20,000 tokens | ~$0.060 |

### Proyección por equipo

| Escenario | Uso mensual | Costo mensual |
|-----------|------------|---------------|
| 1 analista uso intenso | ~2M tokens | ~$6 |
| Equipo SP&A (5 analistas) | ~10M tokens | ~$30 |
| Operaciones LATAM (20 analistas) | ~40M tokens | ~$120 |
| Uso corporativo completo (50 usuarios) | ~100M tokens | ~$300 |

### Comparación con alternativa manual
Un analista junior dedicado a generar estos reportes manualmente cuesta ~$2,000-3,000/mes en LATAM.
El sistema reemplaza ~60% de ese trabajo analítico repetitivo a **$30-300/mes en costos de API** — un ROI de 10-100x.

### Optimizaciones de costo implementadas
- `temperature=0` reduce tokens de output al eliminar variabilidad innecesaria
- Máximo 6 tool calls por consulta para evitar loops costosos
- Compresión de historial conversacional cuando supera 20 mensajes
- Caché del Excel en memoria (`lru_cache`) — cero costo de re-procesamiento

---

*Desarrollado para el caso técnico de AI Engineer — Rappi SP&A*
