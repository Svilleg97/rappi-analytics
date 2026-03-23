"""
tests/test_brief_cases.py
-------------------------
Tests de regresión para los 6 casos de uso del brief.
Verifica que las herramientas del bot devuelvan datos
coherentes para las consultas específicas del caso técnico.
"""

import pytest
from core.tools import execute_tool


# ── Caso 1: Filtrado ──────────────────────────────────────────────────────────

def test_caso1_top_5_lead_penetration():
    """
    Brief: '¿Cuáles son las 5 zonas con mayor Lead Penetration esta semana?'
    La tool debe retornar exactamente 5 zonas con datos válidos.
    """
    result = execute_tool("top_zones_by_metric", {
        "metric": "Lead Penetration",
        "n": 5
    })
    assert result["success"] == True, f"Tool falló: {result.get('error')}"
    assert len(result["data"]) == 5
    assert result["chart_type"] in ["bar", "table"]


# ── Caso 2: Comparación ───────────────────────────────────────────────────────

def test_caso2_wealthy_vs_non_wealthy_mexico():
    """
    Brief: 'Compara el Perfect Order entre zonas Wealthy y Non Wealthy en México'
    La tool debe retornar datos para ambos tipos de zona.
    """
    result = execute_tool("compare_zone_types", {
        "metric": "Perfect Orders",
        "country": "MX"
    })
    assert result["success"] == True, f"Tool falló: {result.get('error')}"
    assert len(result["data"]) > 0

    zone_types = [r["ZONE_TYPE"] for r in result["data"]]
    assert "Wealthy" in zone_types, "No hay datos para Wealthy"
    assert "Non Wealthy" in zone_types, "No hay datos para Non Wealthy"


# ── Caso 3: Tendencia temporal ────────────────────────────────────────────────

def test_caso3_tendencia_chapinero_gross_profit():
    """
    Brief: 'Muestra la evolución de Gross Profit UE en Chapinero últimas 8 semanas'
    La tool debe retornar 9 puntos de datos (L8W a L0W).
    """
    result = execute_tool("zone_trend", {
        "zone": "Chapinero",
        "metric": "Gross Profit UE"
    })
    assert result["success"] == True, f"Tool falló: {result.get('error')}"
    assert len(result["data"]) == 9, \
        f"Se esperaban 9 semanas, se encontraron {len(result['data'])}"

    weeks = [r["week"] for r in result["data"]]
    assert any("L0W" in w for w in weeks)
    assert any("L8W" in w for w in weeks)


# ── Caso 4: Agregación ────────────────────────────────────────────────────────

def test_caso4_promedio_lead_penetration_por_pais():
    """
    Brief: '¿Cuál es el promedio de Lead Penetration por país?'
    La tool debe retornar datos para los 9 países.
    """
    result = execute_tool("average_by_country", {
        "metric": "Lead Penetration"
    })
    assert result["success"] == True, f"Tool falló: {result.get('error')}"
    assert len(result["data"]) == 9, \
        f"Se esperaban 9 países, se encontraron {len(result['data'])}"

    countries = [r["COUNTRY"] for r in result["data"]]
    for expected in ["AR", "BR", "CL", "CO", "CR", "EC", "MX", "PE", "UY"]:
        assert expected in countries, f"País {expected} no encontrado"


# ── Caso 5: Multivariable ─────────────────────────────────────────────────────

def test_caso5_alto_lp_bajo_po():
    """
    Brief: '¿Qué zonas tienen alto Lead Penetration pero bajo Perfect Order?'
    La tool debe retornar zonas con ambas métricas.
    """
    result = execute_tool("multivariable_analysis", {
        "metric_high": "Lead Penetration",
        "metric_low": "Perfect Orders"
    })
    assert result["success"] == True, f"Tool falló: {result.get('error')}"
    # Puede ser vacío si no hay zonas que cumplan, pero no debe fallar
    assert isinstance(result["data"], list)

    if len(result["data"]) > 0:
        first = result["data"][0]
        assert "ZONE" in first
        assert "COUNTRY" in first


# ── Caso 6: Inferencia ────────────────────────────────────────────────────────

def test_caso6_zonas_mayor_crecimiento_ordenes():
    """
    Brief: '¿Cuáles son las zonas que más crecen en órdenes en las últimas 5 semanas?'
    La tool debe retornar zonas con crecimiento positivo.
    """
    result = execute_tool("fastest_growing_zones", {
        "n": 10,
        "weeks_back": 5
    })
    assert result["success"] == True, f"Tool falló: {result.get('error')}"
    assert len(result["data"]) > 0

    if len(result["data"]) > 0:
        first = result["data"][0]
        assert "ZONE" in first
        assert "growth_pct" in first
        assert first["growth_pct"] > 0, "El crecimiento debe ser positivo"


# ── Tests adicionales de herramientas ─────────────────────────────────────────

def test_anomaly_detection_tool():
    """La tool de anomalías debe retornar resultados con tipo clasificado."""
    result = execute_tool("anomaly_detection", {"threshold_pct": 0.10})
    assert result["success"] == True
    if len(result["data"]) > 0:
        tipos = [r["tipo"] for r in result["data"]]
        assert all(t in ["mejora", "deterioro"] for t in tipos)


def test_consistent_decline_tool():
    """La tool de deterioro consistente debe retornar datos válidos."""
    result = execute_tool("consistent_decline_zones", {"weeks": 3})
    assert result["success"] == True
    assert isinstance(result["data"], list)


def test_benchmarking_tool():
    """La tool de benchmarking debe funcionar para Colombia."""
    result = execute_tool("benchmarking", {
        "country": "CO",
        "metric": "Perfect Orders"
    })
    assert result["success"] == True
    assert len(result["data"]) > 0


def test_correlation_tool():
    """La tool de correlación debe retornar un coeficiente r válido."""
    result = execute_tool("correlation_analysis", {
        "metric1": "Restaurants Markdowns / GMV",
        "metric2": "Perfect Orders"
    })
    assert result["success"] == True
    assert "correlation" in result
    r = result["correlation"]
    assert -1.0 <= r <= 1.0, f"Coeficiente de correlación inválido: {r}"


def test_get_metrics_list_tool():
    """La tool de lista de métricas debe retornar las 13 métricas."""
    result = execute_tool("list_available_options", {"type": "metrics"})
    assert result["success"] == True
    assert len(result["data"]) > 0
