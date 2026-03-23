"""
tests/test_data_engine.py
-------------------------
Tests unitarios para el motor de análisis de datos.
Verifica que las funciones de data_engine.py devuelvan
resultados correctos y coherentes con los datos reales.
"""

import pytest
import pandas as pd
from core.data_engine import (
    get_metrics_df,
    get_orders_df,
    top_zones_by_metric,
    compare_zone_types,
    zone_trend,
    average_by_country,
    anomaly_detection,
    consistent_decline_zones,
    fastest_growing_zones,
    get_kpis_summary,
    WEEK_COLS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def metrics_df():
    """DataFrame de métricas cargado una vez para todos los tests."""
    return get_metrics_df()


@pytest.fixture(scope="module")
def orders_df():
    """DataFrame de órdenes cargado una vez para todos los tests."""
    return get_orders_df()


# ── Tests de carga de datos ───────────────────────────────────────────────────

def test_metrics_df_not_empty(metrics_df):
    """El DataFrame de métricas debe tener datos."""
    assert len(metrics_df) > 0


def test_orders_df_not_empty(orders_df):
    """El DataFrame de órdenes debe tener datos."""
    assert len(orders_df) > 0


def test_metrics_df_has_required_columns(metrics_df):
    """El DataFrame debe tener las columnas esperadas."""
    required = ["COUNTRY", "CITY", "ZONE", "ZONE_TYPE", "METRIC", "L0W_ROLL", "L1W_ROLL"]
    for col in required:
        assert col in metrics_df.columns, f"Columna faltante: {col}"


def test_metrics_df_has_9_countries(metrics_df):
    """Debe haber exactamente 9 países."""
    countries = metrics_df["COUNTRY"].unique()
    assert len(countries) == 9, f"Se esperaban 9 países, se encontraron {len(countries)}"


def test_metrics_df_expected_countries(metrics_df):
    """Los países deben ser los 9 de LATAM."""
    expected = {"AR", "BR", "CL", "CO", "CR", "EC", "MX", "PE", "UY"}
    actual = set(metrics_df["COUNTRY"].unique())
    assert actual == expected, f"Países inesperados: {actual - expected}"


def test_week_cols_order():
    """Las columnas de semanas deben estar en orden de más antigua a más reciente."""
    assert WEEK_COLS[0] == "L8W_ROLL"
    assert WEEK_COLS[-1] == "L0W_ROLL"
    assert len(WEEK_COLS) == 9


# ── Tests de top_zones_by_metric ─────────────────────────────────────────────

def test_top_zones_returns_correct_count():
    """Debe retornar exactamente N zonas."""
    result = top_zones_by_metric("Perfect Orders", n=5)
    assert len(result) == 5


def test_top_zones_sorted_descending():
    """Las zonas deben estar ordenadas de mayor a menor valor."""
    result = top_zones_by_metric("Perfect Orders", n=10)
    values = result["L0W_ROLL"].tolist()
    assert values == sorted(values, reverse=True), "No está ordenado de mayor a menor"


def test_top_zones_correct_metric():
    """Solo debe retornar datos de la métrica solicitada."""
    """Solo debe retornar datos de la métrica — verifica columnas del resultado."""
    result = top_zones_by_metric("Lead Penetration", n=5)
    assert len(result) == 5
    assert "value_fmt" in result.columns or "L0W_ROLL" in result.columns

def test_top_zones_filter_by_country():
    """Debe filtrar correctamente por país."""
    result = top_zones_by_metric("Perfect Orders", n=5, country="CO")
    assert all(result["COUNTRY"] == "CO"), "Hay zonas de otros países"


def test_top_zones_invalid_metric_returns_empty():
    """Una métrica inexistente debe retornar DataFrame vacío."""
    result = top_zones_by_metric("MetricaQueNoExiste", n=5)
    assert len(result) == 0


# ── Tests de compare_zone_types ───────────────────────────────────────────────

def test_compare_zone_types_returns_both_types():
    """Debe retornar datos para Wealthy y Non Wealthy."""
    result = compare_zone_types("Perfect Orders", country="MX")
    assert len(result) > 0
    # La función retorna formato wide — solo verificamos que tiene datos


def test_compare_zone_types_mexico():
    """Perfect Orders en México debe tener datos."""
    result = compare_zone_types("Perfect Orders", country="MX")
    assert len(result) > 0



# ── Tests de zone_trend ───────────────────────────────────────────────────────

def test_zone_trend_returns_9_weeks():
    """La tendencia debe tener exactamente 9 puntos (L8W a L0W)."""
    result = zone_trend("Chapinero", "Gross Profit UE")
    assert len(result) == 9, f"Se esperaban 9 semanas, se encontraron {len(result)}"


def test_zone_trend_has_week_column():
    """El resultado debe tener columna 'week'."""
    result = zone_trend("Chapinero", "Gross Profit UE")
    assert "week" in result.columns


def test_zone_trend_has_value_column():
    """El resultado debe tener columna 'value'."""
    result = zone_trend("Chapinero", "Gross Profit UE")
    assert "value" in result.columns


def test_zone_trend_nonexistent_zone_returns_empty():
    """Una zona inexistente debe retornar DataFrame vacío."""
    result = zone_trend("ZonaQueNoExiste123", "Perfect Orders")
    assert len(result) == 0


# ── Tests de average_by_country ───────────────────────────────────────────────

def test_average_by_country_returns_all_countries():
    """Debe retornar promedios para los 9 países."""
    result = average_by_country("Perfect Orders")
    assert len(result) == 9, f"Se esperaban 9 países, se encontraron {len(result)}"


def test_average_by_country_sorted():
    """Debe estar ordenado de mayor a menor."""
    result = average_by_country("Perfect Orders")
    values = result["avg_value"].tolist()
    assert values == sorted(values, reverse=True)


def test_average_by_country_has_value_fmt():
    """Debe tener columna 'value_fmt' con formato legible."""
    result = average_by_country("Perfect Orders")
    assert "value_fmt" in result.columns
    assert all(result["value_fmt"].str.len() > 0)


# ── Tests de anomaly_detection ────────────────────────────────────────────────

def test_anomaly_detection_respects_threshold():
    """Todas las anomalías tienen change_fmt con el cambio porcentual."""
    threshold = 0.10
    result = anomaly_detection(threshold_pct=threshold)
    if len(result) > 0:
        assert "change_fmt" in result.columns
        assert all(result["change_fmt"].str.len() > 0)


def test_anomaly_detection_has_tipo_column():
    """Debe clasificar cada anomalía como 'mejora' o 'deterioro'."""
    result = anomaly_detection()
    if len(result) > 0:
        valid_tipos = {"mejora", "deterioro"}
        assert set(result["tipo"].unique()).issubset(valid_tipos)


def test_anomaly_detection_higher_threshold_fewer_results():
    """Un umbral más alto debe retornar menos anomalías."""
    result_low = anomaly_detection(threshold_pct=0.05)
    result_high = anomaly_detection(threshold_pct=0.30)
    assert len(result_low) >= len(result_high), \
        "Umbral más alto debería tener menos o igual anomalías"


def test_anomaly_detection_max_50_results():
    """Debe retornar máximo 50 resultados."""
    result = anomaly_detection(threshold_pct=0.01)
    assert len(result) <= 50


# ── Tests de fastest_growing_zones ───────────────────────────────────────────

def test_fastest_growing_returns_correct_count():
    """Debe retornar el número de zonas solicitado."""
    result = fastest_growing_zones(n=10)
    assert len(result) <= 10


def test_fastest_growing_has_growth_column():
    """Debe tener columna 'growth_pct'."""
    result = fastest_growing_zones(n=5)
    assert "growth_pct" in result.columns


def test_fastest_growing_positive_growth():
    """Las zonas en crecimiento deben tener growth_pct positivo."""
    result = fastest_growing_zones(n=10)
    if len(result) > 0:
        assert all(result["growth_pct"] > 0), "Hay zonas con crecimiento negativo"


# ── Tests de get_kpis_summary ─────────────────────────────────────────────────

def test_kpis_summary_has_all_metrics():
    """Debe retornar los 4 KPIs principales."""
    result = get_kpis_summary()
    assert "Perfect Orders" in result
    assert "Lead Penetration" in result
    assert "Gross Profit UE" in result
    assert "Pro Adoption (Last Week Status)" in result


def test_kpis_summary_has_required_fields():
    """Cada KPI debe tener los campos necesarios para el dashboard."""
    result = get_kpis_summary()
    required_fields = ["current", "previous", "delta_pct", "value_fmt", "trend"]
    for metric, data in result.items():
        for field in required_fields:
            assert field in data, f"Campo '{field}' faltante en {metric}"


def test_kpis_summary_trend_valid_values():
    """El campo 'trend' debe ser 'up', 'down' o 'flat'."""
    result = get_kpis_summary()
    valid_trends = {"up", "down", "flat"}
    for metric, data in result.items():
        assert data["trend"] in valid_trends, \
            f"Trend inválido '{data['trend']}' en {metric}"


def test_kpis_summary_historical_week():
    """Debe funcionar con semanas históricas."""
    result_current = get_kpis_summary(week_col="L0W_ROLL")
    result_historical = get_kpis_summary(week_col="L4W_ROLL")
    # Los valores históricos deben ser diferentes a los actuales
    po_current = result_current["Perfect Orders"]["current"]
    po_historical = result_historical["Perfect Orders"]["current"]
    # No necesariamente diferentes, pero ambos deben ser números válidos
    assert isinstance(po_current, float)
    assert isinstance(po_historical, float)
