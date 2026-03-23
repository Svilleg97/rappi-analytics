"""
api/insights.py
---------------
Rutas para el dashboard principal y análisis de insights automáticos.
Todos los datos vienen de data_engine — no hay lógica de negocio aquí.
"""

from fastapi import APIRouter, Cookie, Query
from fastapi.responses import JSONResponse
from core.data_engine import (
    get_kpis_summary, get_weekly_trend_all_metrics,
    anomaly_detection, consistent_decline_zones,
    fastest_growing_zones, top_zones_by_metric,
    average_by_country, benchmarking,
    correlation_analysis, df_to_records,
    get_available_metrics, get_available_countries
)

router = APIRouter(prefix="/api/insights", tags=["insights"])


def _require_auth(session: str) -> bool:
    return session is not None and session.startswith("user_")


@router.get("/dashboard")
async def get_dashboard(
    week: str = Query(default="L0W"),
    session: str = Cookie(default=None)
):
    """
    Datos completos para el dashboard principal.
    Acepta parámetro week: L0W (default) hasta L8W.
    """
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})

    # Normalizar semana — acepta L0W o L0W_ROLL
    week_col = week if week.endswith("_ROLL") else week + "_ROLL"
    # Validar que sea una semana válida
    valid_weeks = ["L8W_ROLL","L7W_ROLL","L6W_ROLL","L5W_ROLL",
                   "L4W_ROLL","L3W_ROLL","L2W_ROLL","L1W_ROLL","L0W_ROLL"]
    if week_col not in valid_weeks:
        week_col = "L0W_ROLL"

    try:
        kpis = get_kpis_summary(week_col=week_col)

        # Top 3 anomalías para la sección de alertas
        anomalies_df = anomaly_detection(threshold_pct=0.10)
        top_anomalies = df_to_records(
            anomalies_df[anomalies_df["tipo"] == "deterioro"].head(3)
        ) if not anomalies_df.empty else []

        # Top 3 zonas creciendo en órdenes
        growing_df = fastest_growing_zones(n=3, weeks_back=5)
        top_growing = df_to_records(growing_df)

        # Tendencias semanales para los 2 KPIs principales del gráfico
        trends = {
            "perfect_orders":   get_weekly_trend_all_metrics("Perfect Orders"),
            "lead_penetration": get_weekly_trend_all_metrics("Lead Penetration"),
        }

        # Conteo de alertas
        all_anomalies    = anomaly_detection(threshold_pct=0.10)
        decline_zones    = consistent_decline_zones(weeks=3)

        deterioros_count = int(len(all_anomalies[all_anomalies["tipo"] == "deterioro"])) if not all_anomalies.empty else 0
        mejoras_count    = int(len(all_anomalies[all_anomalies["tipo"] == "mejora"]))    if not all_anomalies.empty else 0
        decline_count    = int(len(decline_zones)) if not decline_zones.empty else 0

        alert_counts = {
            "deterioros":          deterioros_count,
            "mejoras":             mejoras_count,
            "deterioro_sostenido": decline_count
        }

        return {
            "kpis":         kpis,
            "top_anomalies": top_anomalies,
            "top_growing":  top_growing,
            "trends":       trends,
            "alert_counts": alert_counts
        }

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Error cargando dashboard: {str(e)}"}
        )


@router.get("/anomalies")
async def get_anomalies(
    threshold: float = Query(default=0.10, ge=0.01, le=0.50),
    session: str = Cookie(default=None)
):
    """Anomalías con threshold configurable."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})
    df = anomaly_detection(threshold_pct=threshold)
    return {
        "anomalies":  df_to_records(df),
        "total":      len(df),
        "deterioros": len(df[df["tipo"] == "deterioro"]),
        "mejoras":    len(df[df["tipo"] == "mejora"])
    }


@router.get("/trends")
async def get_declining_trends(
    weeks: int = Query(default=3, ge=2, le=7),
    session: str = Cookie(default=None)
):
    """Zonas con deterioro consistente N semanas seguidas."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})
    df = consistent_decline_zones(weeks=weeks)
    return {"trends": df_to_records(df), "total": len(df)}


@router.get("/growing")
async def get_growing_zones(
    n: int = Query(default=10, ge=1, le=50),
    weeks: int = Query(default=5, ge=2, le=8),
    session: str = Cookie(default=None)
):
    """Zonas con mayor crecimiento en órdenes."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})
    df = fastest_growing_zones(n=n, weeks_back=weeks)
    return {"zones": df_to_records(df)}


@router.get("/benchmarking")
async def get_benchmarking(
    metric: str = Query(...),
    country: str = Query(...),
    session: str = Cookie(default=None)
):
    """Benchmarking de zonas de un país para una métrica."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})
    df = benchmarking(metric=metric, country=country.upper())
    if df.empty:
        return JSONResponse(
            status_code=404,
            content={"detail": f"No hay datos para {country} - {metric}"}
        )
    return {"benchmarking": df_to_records(df)}


@router.get("/correlation")
async def get_correlation(
    metric1: str = Query(...),
    metric2: str = Query(...),
    session: str = Cookie(default=None)
):
    """Correlación de Pearson entre dos métricas."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})
    result = correlation_analysis(metric1=metric1, metric2=metric2)
    return result


@router.get("/metrics")
async def get_metrics_list(session: str = Cookie(default=None)):
    """Lista de métricas disponibles para el diccionario."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})
    return {"metrics": get_available_metrics()}


@router.get("/countries")
async def get_countries_list(session: str = Cookie(default=None)):
    """Lista de países disponibles."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})
    from core.data_engine import COUNTRY_NAMES
    countries = get_available_countries()
    return {
        "countries": [
            {"code": c, "name": COUNTRY_NAMES.get(c, c)}
            for c in countries
        ]
    }
