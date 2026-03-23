"""
persistence.py
--------------
Responsabilidad única: leer y escribir datos en disco.

Maneja tres tipos de datos:
  - Conversaciones (data/history/{session_id}.json)
  - Reportes      (data/reports/{report_id}.json + .html)
  - Jobs          (data/history/jobs/{job_id}.json)

Por qué archivos JSON y no base de datos:
  Para este proyecto no necesitamos queries complejos ni relaciones.
  JSON en disco es simple, portátil, y funciona en Render sin configuración.
  Si el proyecto escala, este es el único archivo que cambiaría para
  usar PostgreSQL o Redis — el resto del código no se toca.
"""

import json
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Rutas base ────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent.parent
HISTORY_DIR   = BASE_DIR / "data" / "history"
REPORTS_DIR   = BASE_DIR / "data" / "reports"
JOBS_DIR      = HISTORY_DIR / "jobs"


def _ensure_dirs():
    """Crea los directorios si no existen. Llamado automáticamente."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


_ensure_dirs()


# ── Conversaciones ────────────────────────────────────────────────────────────

def save_conversation(session_id: str, history: list, title: str = None) -> bool:
    """
    Guarda el historial de una conversación.
    Si no tiene título, usa el primer mensaje del usuario como título.
    """
    try:
        path = HISTORY_DIR / f"{session_id}.json"

        # Si ya existe, preservar metadata como fecha de creación y título previo
        existing = _safe_read_json(path)
        created_at = existing.get("created_at") if existing else datetime.now(timezone.utc).isoformat()
        existing_title = existing.get("title") if existing else None

        # Generar título automático del primer mensaje del usuario
        if not title and not existing_title:
            user_messages = [m for m in history if m.get("role") == "user"]
            if user_messages:
                first_msg = str(user_messages[0].get("content", ""))
                title = first_msg[:60] + ("..." if len(first_msg) > 60 else "")
            else:
                title = "Conversación sin título"
        else:
            title = title or existing_title or "Conversación sin título"

        data = {
            "session_id": session_id,
            "title":      title,
            "created_at": created_at,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "messages":   history,
            "msg_count":  len([m for m in history if m.get("role") == "user"])
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        return True
    except Exception as e:
        logger.error(f"Error guardando conversación {session_id}: {e}")
        return False


def load_conversation(session_id: str) -> Optional[dict]:
    """Carga una conversación por su session_id."""
    path = HISTORY_DIR / f"{session_id}.json"
    return _safe_read_json(path)


def list_conversations(limit: int = 20) -> list[dict]:
    """
    Lista las conversaciones más recientes.
    Retorna solo metadata (sin los mensajes completos) para que la lista cargue rápido.
    """
    try:
        files = sorted(HISTORY_DIR.glob("*.json"),
                       key=lambda f: f.stat().st_mtime, reverse=True)
        result = []
        for f in files[:limit]:
            data = _safe_read_json(f)
            if data and "session_id" in data:
                result.append({
                    "session_id": data["session_id"],
                    "title":      data.get("title", "Sin título"),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "msg_count":  data.get("msg_count", 0)
                })
        return result
    except Exception as e:
        logger.error(f"Error listando conversaciones: {e}")
        return []


def delete_conversation(session_id: str) -> bool:
    """Elimina una conversación del historial."""
    try:
        path = HISTORY_DIR / f"{session_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False
    except Exception as e:
        logger.error(f"Error eliminando conversación {session_id}: {e}")
        return False


def new_session_id() -> str:
    """Genera un nuevo ID de sesión único."""
    return str(uuid.uuid4())


# ── Reportes ──────────────────────────────────────────────────────────────────

def save_report(
    markdown_content: str,
    title: str = None,
    report_type: str = "weekly"
) -> str:
    """
    Guarda un reporte en JSON y genera el HTML para descarga.
    Retorna el report_id.
    """
    report_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    if not title:
        title = f"Reporte Ejecutivo — {now.strftime('%d/%m/%Y %H:%M')}"

    # Extraer resumen ejecutivo (primeros 500 chars del markdown)
    summary = markdown_content[:500].strip()

    # Contar insights detectados de forma básica
    anomalies_count = markdown_content.count("## 2.") + markdown_content.lower().count("anomal")
    trends_count    = markdown_content.lower().count("tendencia")
    opport_count    = markdown_content.lower().count("oportunidad")

    data = {
        "report_id":   report_id,
        "title":       title,
        "type":        report_type,
        "created_at":  now.isoformat(),
        "summary":     summary,
        "markdown":    markdown_content,
        "stats": {
            "anomalies":     min(anomalies_count, 10),
            "trends":        min(trends_count, 10),
            "opportunities": min(opport_count, 10)
        }
    }

    # Guardar JSON
    json_path = REPORTS_DIR / f"{report_id}.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))

    # Generar y guardar HTML descargable
    html_content = _markdown_to_html(markdown_content, title)
    html_path = REPORTS_DIR / f"{report_id}.html"
    html_path.write_text(html_content, encoding="utf-8")

    logger.info(f"Reporte guardado: {report_id}")
    return report_id


def load_report(report_id: str) -> Optional[dict]:
    """Carga un reporte completo por su ID."""
    path = REPORTS_DIR / f"{report_id}.json"
    return _safe_read_json(path)


def get_report_html_path(report_id: str) -> Optional[Path]:
    """Retorna la ruta del HTML de un reporte si existe."""
    path = REPORTS_DIR / f"{report_id}.html"
    return path if path.exists() else None


def get_report_csv(report_id: str) -> Optional[str]:
    """
    Genera un CSV estructurado con todos los hallazgos del reporte.
    Formato útil para trabajo en Excel: sección, tipo, hallazgo, acción, zona/país.
    """
    import re
    report = load_report(report_id)
    if not report:
        return None

    markdown = report.get("markdown", "")
    rows = [["seccion", "tipo", "hallazgo", "zona_pais", "metrica", "valor", "accion"]]

    current_section = ""
    current_subsection = ""

    for line in markdown.split("\n"):
        line = line.strip()
        if not line:
            continue

        # Sección principal (##)
        if line.startswith("## "):
            current_section = line.replace("#", "").strip()
            current_subsection = ""
            continue

        # Subsección (###)
        if line.startswith("### "):
            current_subsection = line.replace("#", "").strip()
            continue

        # Filas de tabla markdown
        if line.startswith("|") and not re.match(r"^[\|\-\s:]+$", line):
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 2 and cells[0] not in ["Métrica", "Zona", "País"]:
                rows.append([
                    current_section, "tabla",
                    cells[0],
                    cells[1] if len(cells) > 1 else "",
                    cells[2] if len(cells) > 2 else "",
                    cells[3] if len(cells) > 3 else "",
                    cells[4] if len(cells) > 4 else "",
                ])
            continue

        # Bullets (- texto)
        if line.startswith("- ") or line.startswith("* "):
            text = line[2:].strip()
            # Extraer zona/país si hay patrón "ZONA (PAÍS):" o "ZONA:"
            zona = ""
            accion = ""
            if "Acción:" in text or "Accion:" in text:
                parts = re.split(r"[Aa]cci[oó]n:", text, 1)
                hallazgo = parts[0].strip().rstrip(".")
                accion = parts[1].strip() if len(parts) > 1 else ""
            else:
                hallazgo = text
            # Detectar zona entre ** **
            zona_match = re.search(r"\*\*([^*]+)\*\*", hallazgo)
            if zona_match:
                zona = zona_match.group(1)
            rows.append([
                current_section,
                current_subsection or "hallazgo",
                hallazgo[:150],
                zona[:50],
                "", "", accion[:150]
            ])
            continue

        # Texto bold como hallazgo clave
        if line.startswith("**") and "**" in line[2:]:
            bold_match = re.match(r"\*\*(.+?)\*\*[:\s]*(.*)", line)
            if bold_match:
                titulo = bold_match.group(1).strip()
                detalle = bold_match.group(2).strip()
                rows.append([
                    current_section,
                    current_subsection or "insight",
                    f"{titulo}: {detalle}"[:150],
                    "", "", "", ""
                ])

    # Convertir a CSV
    import io, csv
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerows(rows)
    return output.getvalue()


def list_reports(limit: int = 20, include_archived: bool = False) -> list[dict]:
    """
    Lista los reportes más recientes con su metadata.
    include_archived=False  → lista principal (excluye archivados)
    include_archived=True   → historial (incluye todos)
    """
    try:
        files = sorted(REPORTS_DIR.glob("*.json"),
                       key=lambda f: f.stat().st_mtime, reverse=True)
        result = []
        for f in files[:limit * 2]:  # fetch extra to account for filtered ones
            data = _safe_read_json(f)
            if data and "report_id" in data:
                is_archived = data.get("archived", False)
                # Skip archived in main list; skip non-archived in history view
                if not include_archived and is_archived:
                    continue
                result.append({
                    "report_id":  data["report_id"],
                    "title":      data.get("title", "Sin título"),
                    "created_at": data.get("created_at", ""),
                    "type":       data.get("type", "weekly"),
                    "stats":      data.get("stats", {}),
                    "archived":   is_archived
                })
            if len(result) >= limit:
                break
        return result
    except Exception as e:
        logger.error(f"Error listando reportes: {e}")
        return []


# ── Jobs ──────────────────────────────────────────────────────────────────────

def save_job(job_id: str, job_data: dict) -> bool:
    """Persiste el estado de un job en disco."""
    try:
        path = JOBS_DIR / f"{job_id}.json"
        path.write_text(json.dumps(job_data, ensure_ascii=False,
                                   indent=2, default=str))
        return True
    except Exception as e:
        logger.error(f"Error guardando job {job_id}: {e}")
        return False


def load_job(job_id: str) -> Optional[dict]:
    """Carga el estado de un job desde disco."""
    path = JOBS_DIR / f"{job_id}.json"
    return _safe_read_json(path)


# ── Helpers internos ──────────────────────────────────────────────────────────

def _safe_read_json(path: Path) -> Optional[dict]:
    """Lee un JSON de forma segura, retorna None si falla."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Error leyendo {path}: {e}")
    return None


def _markdown_to_html(markdown: str, title: str) -> str:
    """
    Convierte markdown a HTML con estilos de Rappi para descarga.
    Maneja: headings, bold, italic, listas, tablas markdown.
    """
    import re

    html_content = markdown

    # Headings
    html_content = re.sub(r'^# (.+)$',   r'<h1>\1</h1>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^## (.+)$',  r'<h2>\1</h2>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_content, flags=re.MULTILINE)

    # Bold e italic
    html_content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_content)
    html_content = re.sub(r'\*(.+?)\*',        r'<em>\1</em>',         html_content)

    # Convertir tablas markdown a HTML
    def convert_table(match):
        lines = [l.strip() for l in match.group().strip().split('\n') if l.strip()]
        if len(lines) < 2:
            return match.group()
        header_cells = [c.strip() for c in lines[0].split('|') if c.strip()]
        # Saltar la línea de separadores (|---|---|)
        data_lines = [l for l in lines[1:] if not re.match(r'^[\|\-\s:]+$', l)]
        thead = '<tr>' + ''.join(f'<th>{c}</th>' for c in header_cells) + '</tr>'
        tbody = ''
        for dl in data_lines:
            cells = [c.strip() for c in dl.split('|') if c.strip()]
            tbody += '<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>'
        return (f'<div class="table-wrap">'
                f'<table class="report-table"><thead>{thead}</thead>'
                f'<tbody>{tbody}</tbody></table></div>')

    # Detectar bloques de tabla markdown (líneas que empiezan con |)
    html_content = re.sub(
        r'((?:^\|.+\|\s*\n)+)',
        convert_table,
        html_content,
        flags=re.MULTILINE
    )

    # Bullets
    html_content = re.sub(r'^[-\*] (.+)$', r'<li>\1</li>', html_content, flags=re.MULTILINE)
    html_content = re.sub(r'(<li>.*?</li>\n?)+',
                          lambda m: f'<ul>{m.group()}</ul>', html_content, flags=re.DOTALL)

    # Párrafos: líneas que no son tags HTML
    lines = html_content.split('\n')
    result_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('<'):
            result_lines.append(f'<p>{stripped}</p>')
        else:
            result_lines.append(line)
    html_content = '\n'.join(result_lines)

    now_str = datetime.now().strftime('%d/%m/%Y %H:%M')

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    *{{ box-sizing:border-box;margin:0;padding:0 }}
    body{{
      font-family:'Nunito',-apple-system,BlinkMacSystemFont,sans-serif;
      font-size:14px;line-height:1.7;color:#1A1A2E;background:#F8F7F5;
    }}
    .header{{
      background:#FF441F;color:white;
      padding:24px 48px;display:flex;
      align-items:center;justify-content:space-between;
    }}
    .header-left{{display:flex;align-items:center;gap:16px}}
    .logo-box{{
      width:44px;height:44px;background:rgba(255,255,255,0.2);
      border-radius:10px;display:flex;align-items:center;
      justify-content:center;font-size:26px;font-weight:900;color:white;
    }}
    .table-wrap{{overflow-x:auto;margin:16px 0;border-radius:10px;border:1px solid #EBEBEB}}
    .report-table{{width:100%;border-collapse:collapse;font-size:13px}}
    .report-table th{{
      background:#FFF2EF;color:#CC2F0F;padding:10px 14px;
      text-align:left;font-weight:800;font-size:11px;
      text-transform:uppercase;letter-spacing:.4px;
      border-bottom:2px solid #FFD0C4;white-space:nowrap;
    }}
    .report-table td{{
      padding:9px 14px;border-bottom:1px solid #F5F5F5;
      color:#374151;font-weight:500;
    }}
    .report-table tr:nth-child(even) td{{background:#FAFAFA}}
    .report-table tr:hover td{{background:#FFF2EF}}
    .report-table td:first-child{{font-weight:700;color:#1A1A2E}}
    .header-title{{font-size:20px;font-weight:800;letter-spacing:-0.3px}}
    .header-sub{{font-size:12px;opacity:0.85;margin-top:2px;font-weight:500}}
    .header-badge{{
      background:rgba(255,255,255,0.2);padding:7px 16px;
      border-radius:20px;font-size:11px;font-weight:800;
      border:1px solid rgba(255,255,255,0.3);
    }}
    .container{{max-width:860px;margin:36px auto;padding:0 28px 60px}}
    h1{{font-size:22px;color:#FF441F;margin:32px 0 10px;font-weight:800}}
    h2{{
      font-size:16px;font-weight:800;color:#1A1A2E;
      margin:28px 0 10px;padding-bottom:8px;
      border-bottom:2px solid #FF441F;
    }}
    h3{{font-size:14px;font-weight:700;color:#374151;margin:16px 0 6px}}
    p{{margin-bottom:10px;color:#4B5563;font-weight:500}}
    ul{{margin:8px 0 12px 20px}}
    li{{margin-bottom:5px;color:#4B5563;font-weight:500}}
    strong{{color:#1A1A2E;font-weight:800}}
    .section-card{{
      background:white;border-radius:14px;
      border:1px solid #EBEBEB;padding:24px 28px;
      margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,0.06);
    }}
    .kpi-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}}
    .kpi-box{{
      background:#FFF2EF;border-radius:10px;padding:14px;
      border-left:3px solid #FF441F;
    }}
    .kpi-label{{font-size:10px;font-weight:700;color:#9CA3AF;text-transform:uppercase;letter-spacing:.5px}}
    .kpi-value{{font-size:20px;font-weight:800;color:#1A1A2E;margin-top:4px}}
    .footer{{
      text-align:center;padding:24px;font-size:11px;color:#9CA3AF;
      border-top:1px solid #EBEBEB;margin-top:40px;font-weight:600;
    }}
    @media print{{
      body{{background:white}}
      .header{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
    }}
  </style>
</head>
<body>
  <div class="header">
    <div class="header-left">
      <div class="logo-box" style="font-size:24px;font-weight:900;color:white;letter-spacing:-1px">R</div>
      <div>
        <div class="header-title">Rappi Analytics</div>
        <div class="header-sub">{title}</div>
        <div class="header-sub">Generado: {now_str}</div>
      </div>
    </div>
    <div class="header-badge">Reporte Ejecutivo SP&amp;A</div>
  </div>
  <div class="container">
    <div class="section-card">
      {html_content}
    </div>
  </div>
  <div class="footer">
    Rappi SP&amp;A Intelligence Platform &nbsp;·&nbsp; Confidencial &nbsp;·&nbsp; {now_str}
  </div>
</body>
</html>"""
