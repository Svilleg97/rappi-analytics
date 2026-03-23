"""
api/reports.py
--------------
Rutas para generación y descarga de reportes ejecutivos.

Flujo:
  POST /api/reports/generate → crea job de reporte en background
  GET  /api/reports/job/{id} → polling hasta que el reporte esté listo
  GET  /api/reports/list     → lista todos los reportes
  GET  /api/reports/{id}/download/html → descarga HTML
  GET  /api/reports/{id}/download/csv  → descarga CSV
"""

import asyncio
from fastapi import APIRouter, Cookie, Query
from fastapi.responses import JSONResponse, FileResponse, Response
from models.schemas import ReportRequest, ReportJobResponse
from core.job_manager import job_manager
from core.persistence import (
    list_reports, load_report,
    get_report_html_path, get_report_csv
)
from core.data_engine import (
    anomaly_detection, consistent_decline_zones,
    fastest_growing_zones, average_by_country,
    correlation_analysis, get_kpis_summary,
    df_to_records
)

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _require_auth(session: str) -> bool:
    return session is not None and session.startswith("user_")


def _build_data_summary(report_type: str, country: str = None) -> str:
    """
    Construye el resumen de datos que se le pasa al LLM para generar el reporte.
    Llama a data_engine para obtener datos reales — nunca inventa nada.
    """
    lines = [f"TIPO DE REPORTE: {report_type}"]
    if country:
        lines.append(f"FILTRO DE PAÍS: {country}")

    # KPIs globales
    try:
        kpis = get_kpis_summary()
        lines.append("\n=== KPIs GLOBALES (semana actual vs anterior) ===")
        for metric, data in kpis.items():
            lines.append(
                f"- {metric}: {data['value_fmt']} "
                f"({data['delta_fmt']} WoW)"
            )
    except Exception:
        pass

    # Anomalías
    try:
        anomalies = anomaly_detection(threshold_pct=0.10)
        deterioros = anomalies[anomalies["tipo"] == "deterioro"].head(10)
        mejoras    = anomalies[anomalies["tipo"] == "mejora"].head(5)
        lines.append(f"\n=== ANOMALÍAS DETECTADAS (>10% cambio WoW) ===")
        lines.append(f"Total deterioros: {len(anomalies[anomalies['tipo']=='deterioro'])}")
        lines.append(f"Total mejoras: {len(anomalies[anomalies['tipo']=='mejora'])}")
        if not deterioros.empty:
            lines.append("TOP DETERIOROS:")
            for _, r in deterioros.iterrows():
                lines.append(
                    f"  - {r['ZONE']} ({r['COUNTRY']}): "
                    f"{r['METRIC']} {r['change_fmt']}"
                )
        if not mejoras.empty:
            lines.append("TOP MEJORAS:")
            for _, r in mejoras.iterrows():
                lines.append(
                    f"  - {r['ZONE']} ({r['COUNTRY']}): "
                    f"{r['METRIC']} {r['change_fmt']}"
                )
    except Exception:
        pass

    # Deterioro consistente
    try:
        declines = consistent_decline_zones(weeks=3)
        if not declines.empty:
            lines.append(f"\n=== DETERIORO CONSISTENTE (3+ semanas) ===")
            lines.append(f"Total zonas: {len(declines)}")
            for _, r in declines.head(8).iterrows():
                lines.append(
                    f"  - {r['ZONE']} ({r['COUNTRY']}): "
                    f"{r['METRIC']} {r['cambio_pct']}% en {r['semanas_caida']} semanas"
                )
    except Exception:
        pass

    # Crecimiento en órdenes
    try:
        growing = fastest_growing_zones(n=5, weeks_back=5)
        if not growing.empty:
            lines.append("\n=== ZONAS CON MAYOR CRECIMIENTO EN ÓRDENES ===")
            for _, r in growing.iterrows():
                lines.append(
                    f"  - {r['ZONE']} ({r['COUNTRY']}): "
                    f"{r['growth_fmt']} en 5 semanas"
                )
    except Exception:
        pass

    # Correlaciones clave — múltiples pares
    try:
        corr_pairs = [
            ("Restaurants Markdowns / GMV", "Perfect Orders"),
            ("Lead Penetration", "Gross Profit UE"),
            ("Pro Adoption (Last Week Status)", "Gross Profit UE"),
            ("Turbo Adoption", "Gross Profit UE"),
        ]
        lines.append("\n=== CORRELACIONES DETECTADAS ===")
        for m1, m2 in corr_pairs:
            try:
                corr = correlation_analysis(m1, m2)
                if corr.get("correlation") is not None:
                    lines.append(
                        f"  - {m1} vs {m2}: "
                        f"r={corr['correlation']} — {corr['interpretation']}"
                    )
            except Exception:
                pass
    except Exception:
        pass

    # Promedio por país para TODAS las métricas clave
    try:
        lines.append("\n=== PROMEDIOS POR PAÍS (semana actual) ===")
        key_metrics = [
            "Perfect Orders", "Lead Penetration",
            "Pro Adoption (Last Week Status)", "Turbo Adoption",
            "Non-Pro PTC > OP", "MLTV Top Verticals Adoption"
        ]
        for metric in key_metrics:
            try:
                df = average_by_country(metric)
                if not df.empty:
                    # Filtrar outliers para métricas de porcentaje
                    valid = df[df['avg_value'] <= 1.0] if metric != "Gross Profit UE" else df
                    if not valid.empty:
                        top = valid.head(3)
                        bottom = valid.tail(3)
                        lines.append(f"\n{metric}:")
                        lines.append(f"  Mejores: " + ", ".join(
                            f"{r['COUNTRY']} ({r['value_fmt']})"
                            for _, r in top.iterrows()
                        ))
                        lines.append(f"  Peores: " + ", ".join(
                            f"{r['COUNTRY']} ({r['value_fmt']})"
                            for _, r in bottom.iterrows()
                        ))
            except Exception:
                pass
    except Exception:
        pass

    # Análisis de funnel de conversión
    try:
        lines.append("\n=== ANÁLISIS DE FUNNEL DE CONVERSIÓN ===")
        funnel_metrics = [
            "Non-Pro PTC > OP",
            "Restaurants SS > ATC CVR",
            "Restaurants SST > SS CVR",
            "Retail SST > SS CVR",
        ]
        for metric in funnel_metrics:
            try:
                df = average_by_country(metric)
                if not df.empty:
                    valid = df[df['avg_value'] <= 1.0]
                    if not valid.empty:
                        global_avg = valid['avg_value'].mean()
                        lines.append(f"  {metric}: promedio global {global_avg:.1%}")
            except Exception:
                pass
    except Exception:
        pass

    return "\n".join(lines)


@router.post("/generate", response_model=ReportJobResponse)
async def generate_report(
    request: ReportRequest,
    session: str = Cookie(default=None)
):
    """
    Inicia la generación de un reporte ejecutivo en background.
    Retorna job_id inmediatamente para que el frontend haga polling.
    """
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})

    # Construir resumen de datos (síncrono, rápido — solo pandas)
    data_summary = _build_data_summary(
        report_type=request.report_type,
        country=request.country
    )

    job_id = job_manager.create_job(
        job_type="report",
        metadata={
            "type":    request.report_type,
            "country": request.country,
            "title":   request.title
        }
    )

    asyncio.create_task(
        job_manager.run_report_job(
            job_id=job_id,
            data_summary=data_summary,
            title=request.title
        )
    )

    return ReportJobResponse(job_id=job_id)


@router.get("/job/{job_id}")
async def get_report_job_status(
    job_id: str,
    session: str = Cookie(default=None)
):
    """Polling del estado de generación de un reporte."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})

    job = job_manager.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"detail": "Job no encontrado"})

    return {
        "job_id": job_id,
        "status": job["status"],
        "result": job.get("result"),
        "error":  job.get("error")
    }


@router.get("/list")
async def list_all_reports(
    archived: bool = Query(default=False),
    session: str = Cookie(default=None)
):
    """Lista reportes. archived=false (default) = lista principal. archived=true = historial."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})
    return {"reports": list_reports(include_archived=archived)}


@router.get("/{report_id}")
async def get_report(report_id: str, session: str = Cookie(default=None)):
    """Carga un reporte completo por ID."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})

    report = load_report(report_id)
    if not report:
        return JSONResponse(status_code=404, content={"detail": "Reporte no encontrado"})
    return report


@router.post("/{report_id}/archive")
async def archive_report(report_id: str, session: str = Cookie(default=None)):
    """
    Archiva un reporte — lo marca como archivado para que no aparezca
    en la lista principal, pero sigue disponible en el historial.
    """
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})
    from core.persistence import REPORTS_DIR
    import json
    path = REPORTS_DIR / f"{report_id}.json"
    if not path.exists():
        return JSONResponse(status_code=404, content={"detail": "Reporte no encontrado"})
    data = json.loads(path.read_text(encoding="utf-8"))
    data["archived"] = True
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str))
    return {"success": True}


@router.delete("/{report_id}")
async def delete_report(report_id: str, session: str = Cookie(default=None)):
    """Elimina un reporte definitivamente del disco."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})
    from core.persistence import REPORTS_DIR
    json_path = REPORTS_DIR / f"{report_id}.json"
    html_path = REPORTS_DIR / f"{report_id}.html"
    if not json_path.exists():
        return JSONResponse(status_code=404, content={"detail": "Reporte no encontrado"})
    json_path.unlink(missing_ok=True)
    html_path.unlink(missing_ok=True)
    return {"success": True}


@router.get("/{report_id}/download/html")
async def download_html(report_id: str, session: str = Cookie(default=None)):
    """Descarga el reporte como archivo HTML."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})

    html_path = get_report_html_path(report_id)
    if not html_path:
        return JSONResponse(status_code=404, content={"detail": "HTML no encontrado"})

    return FileResponse(
        path=str(html_path),
        media_type="text/html",
        filename=f"rappi_report_{report_id[:8]}.html"
    )


@router.get("/{report_id}/download/csv")
async def download_csv(report_id: str, session: str = Cookie(default=None)):
    """Descarga los datos del reporte como CSV."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})

    csv_content = get_report_csv(report_id)
    if not csv_content:
        return JSONResponse(status_code=404, content={"detail": "Reporte no encontrado"})

    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=rappi_report_{report_id[:8]}.csv"
        }
    )
