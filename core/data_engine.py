"""
data_engine.py
--------------
Responsabilidad única: leer el Excel de Rappi y exponer funciones
de análisis limpias. No sabe nada de HTTP, LLM ni HTML.

Cualquier función que necesite datos del Excel vive aquí.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from functools import lru_cache

# ── Rutas ────────────────────────────────────────────────────────────────────
DATA_PATH = Path(__file__).parent.parent / "data" / "rappi_data.xlsx"

# ── Constantes de columnas ────────────────────────────────────────────────────
WEEK_COLS   = ["L8W_ROLL","L7W_ROLL","L6W_ROLL","L5W_ROLL",
               "L4W_ROLL","L3W_ROLL","L2W_ROLL","L1W_ROLL","L0W_ROLL"]
ORDER_COLS  = ["L8W","L7W","L6W","L5W","L4W","L3W","L2W","L1W","L0W"]
WEEK_LABELS = ["L8W","L7W","L6W","L5W","L4W","L3W","L2W","L1W","L0W (actual)"]

COUNTRY_NAMES = {
    "AR":"Argentina","BR":"Brasil","CL":"Chile","CO":"Colombia",
    "CR":"Costa Rica","EC":"Ecuador","MX":"México","PE":"Perú","UY":"Uruguay"
}

# Dirección positiva: True = subir es bueno, False = bajar es bueno
METRIC_DIRECTION = {
    "Perfect Orders": True,
    "Lead Penetration": True,
    "Gross Profit UE": True,
    "Pro Adoption (Last Week Status)": True,
    "Turbo Adoption": True,
    "Non-Pro PTC > OP": True,
    "MLTV Top Verticals Adoption": True,
    "% PRO Users Who Breakeven": True,
    "% Restaurants Sessions With Optimal Assortment": True,
    "Restaurants SS > ATC CVR": True,
    "Restaurants SST > SS CVR": True,
    "Retail SST > SS CVR": True,
    "Restaurants Markdowns / GMV": False,  # bajar es bueno
}


# ── Carga de datos (cacheada — solo lee el Excel una vez) ─────────────────────
@lru_cache(maxsize=1)
def _load_raw():
    """Carga el Excel completo. Se ejecuta una sola vez gracias a lru_cache."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"No se encontró el archivo de datos en: {DATA_PATH}")
    metrics = pd.read_excel(DATA_PATH, sheet_name="RAW_INPUT_METRICS")
    orders  = pd.read_excel(DATA_PATH, sheet_name="RAW_ORDERS")
    return metrics, orders


def get_metrics_df() -> pd.DataFrame:
    return _load_raw()[0].copy()


def get_orders_df() -> pd.DataFrame:
    return _load_raw()[1].copy()


def reload_data():
    """
    Limpia el caché y fuerza recarga del Excel en el próximo request.
    Se llama automáticamente cuando el archivo cambia en disco.
    """
    _load_raw.cache_clear()
    import logging
    logging.getLogger(__name__).info("Cache limpiado — datos se recargarán en el próximo request")


def get_data_file_mtime() -> float:
    """Retorna la fecha de última modificación del archivo de datos."""
    return DATA_PATH.stat().st_mtime if DATA_PATH.exists() else 0


# ── Helpers de formato ────────────────────────────────────────────────────────
def fmt_pct(val: float) -> str:
    """Formatea 0.734 como '73.4%'"""
    if pd.isna(val):
        return "N/A"
    return f"{val*100:.1f}%"


def fmt_val(val: float, metric: str) -> str:
    """Formatea un valor según el tipo de métrica."""
    if pd.isna(val):
        return "N/A"
    if metric == "Gross Profit UE":
        return f"${val:.2f}"
    return fmt_pct(val)


def df_to_records(df: pd.DataFrame, max_rows: int = 30) -> list[dict]:
    """Convierte un DataFrame a lista de dicts para JSON/frontend."""
    return df.head(max_rows).replace({np.nan: None}).to_dict(orient="records")


# ── Funciones de análisis ─────────────────────────────────────────────────────

def top_zones_by_metric(
    metric: str,
    n: int = 5,
    ascending: bool = False,
    country: str = None,
    zone_type: str = None,
    week: str = "L0W_ROLL"
) -> pd.DataFrame:
    """
    Top N zonas por métrica en una semana dada.
    ascending=True devuelve las peores (bottom N).
    """
    df = get_metrics_df()
    df = df[df["METRIC"] == metric]

    if country:
        df = df[df["COUNTRY"].str.upper() == country.upper()]
    if zone_type:
        df = df[df["ZONE_TYPE"].str.lower() == zone_type.lower()]
    if week not in df.columns:
        week = "L0W_ROLL"

    df = df.dropna(subset=[week])
    result = df.nsmallest(n, week) if ascending else df.nlargest(n, week)

    result = result[["COUNTRY","CITY","ZONE","ZONE_TYPE","ZONE_PRIORITIZATION", week]].copy()
    result["value_fmt"] = result[week].apply(lambda v: fmt_val(v, metric))
    result["country_name"] = result["COUNTRY"].map(COUNTRY_NAMES)
    return result.reset_index(drop=True)


def compare_zone_types(metric: str, country: str = None) -> pd.DataFrame:
    """
    Promedio semanal de Wealthy vs Non Wealthy.
    Retorna un DataFrame con las 9 semanas como columnas.
    """
    df = get_metrics_df()
    df = df[df["METRIC"] == metric]
    if country:
        df = df[df["COUNTRY"].str.upper() == country.upper()]

    result = df.groupby("ZONE_TYPE")[WEEK_COLS].mean()
    result.columns = WEEK_LABELS
    result = result.round(4)
    return result


def zone_trend(zone: str, metric: str, country: str = None) -> pd.DataFrame:
    """
    Serie temporal de 8 semanas para una zona y métrica específica.
    """
    df = get_metrics_df()
    mask = (df["ZONE"] == zone) & (df["METRIC"] == metric)
    if country:
        mask &= df["COUNTRY"].str.upper() == country.upper()

    df = df[mask]
    if df.empty:
        return pd.DataFrame()

    row = df.iloc[0]
    values = [row[c] for c in WEEK_COLS]
    result = pd.DataFrame({
        "week": WEEK_LABELS,
        "value": values,
        "value_fmt": [fmt_val(v, metric) for v in values]
    })
    result["zone"]    = zone
    result["metric"]  = metric
    result["country"] = row["COUNTRY"]
    return result


def average_by_country(metric: str, week: str = "L0W_ROLL") -> pd.DataFrame:
    """Promedio de una métrica por país en la semana indicada."""
    df = get_metrics_df()
    df = df[df["METRIC"] == metric].dropna(subset=[week])

    result = df.groupby("COUNTRY")[week].mean().round(4).reset_index()
    result.columns = ["COUNTRY", "avg_value"]
    result["country_name"] = result["COUNTRY"].map(COUNTRY_NAMES)
    result["value_fmt"] = result["avg_value"].apply(lambda v: fmt_val(v, metric))
    result = result.sort_values("avg_value", ascending=False)
    return result.reset_index(drop=True)


def multivariable_analysis(
    metric_high: str,
    metric_low: str,
    country: str = None
) -> pd.DataFrame:
    """
    Zonas con metric_high por encima de la mediana
    y metric_low por debajo de la mediana.
    Útil para: 'alto Lead Penetration pero bajo Perfect Order'.
    """
    df = get_metrics_df()
    if country:
        df = df[df["COUNTRY"].str.upper() == country.upper()]

    base_cols = ["COUNTRY","CITY","ZONE","ZONE_TYPE","ZONE_PRIORITIZATION"]

    m1 = df[df["METRIC"] == metric_high][base_cols + ["L0W_ROLL"]].copy()
    m1 = m1.rename(columns={"L0W_ROLL": metric_high})

    m2 = df[df["METRIC"] == metric_low][base_cols + ["L0W_ROLL"]].copy()
    m2 = m2.rename(columns={"L0W_ROLL": metric_low})

    merged = m1.merge(m2, on=base_cols)
    if merged.empty:
        return pd.DataFrame()

    thr1 = merged[metric_high].median()
    thr2 = merged[metric_low].median()

    result = merged[
        (merged[metric_high] >= thr1) & (merged[metric_low] < thr2)
    ].copy()

    result["fmt_high"] = result[metric_high].apply(lambda v: fmt_val(v, metric_high))
    result["fmt_low"]  = result[metric_low].apply(lambda v: fmt_val(v, metric_low))
    result = result.sort_values(metric_high, ascending=False)
    return result.head(20).reset_index(drop=True)


def fastest_growing_zones(n: int = 10, weeks_back: int = 5) -> pd.DataFrame:
    """
    Zonas con mayor crecimiento porcentual en órdenes
    en las últimas N semanas.
    """
    df = get_orders_df()
    start_col = ORDER_COLS[-(weeks_back + 1)]
    end_col   = "L0W"

    df = df.copy()
    df = df[(df[start_col] > 0) & (df[end_col] > 0)]
    df["growth_pct"] = ((df[end_col] - df[start_col]) / df[start_col] * 100).round(2)

    result = df.nlargest(n, "growth_pct")[
        ["COUNTRY","CITY","ZONE", start_col, end_col, "growth_pct"]
    ].copy()
    result.columns = ["COUNTRY","CITY","ZONE",
                      f"orders_{start_col}", "orders_L0W", "growth_pct"]
    result["country_name"] = result["COUNTRY"].map(COUNTRY_NAMES)
    result["growth_fmt"]   = result["growth_pct"].apply(lambda v: f"+{v:.1f}%")
    return result.reset_index(drop=True)


def zone_orders_trend(zone: str) -> pd.DataFrame:
    """Serie temporal de órdenes para una zona específica."""
    df = get_orders_df()
    row = df[df["ZONE"] == zone]
    if row.empty:
        return pd.DataFrame()
    row = row.iloc[0]
    return pd.DataFrame({
        "week":   WEEK_LABELS,
        "orders": [row[c] for c in ORDER_COLS],
        "zone":   zone
    })


def anomaly_detection(threshold_pct: float = 0.10) -> pd.DataFrame:
    """
    Detecta zonas con cambio brusco (> threshold) entre L1W y L0W.
    threshold_pct = 0.10 significa cambios mayores al 10%.
    """
    df = get_metrics_df()
    df = df.copy()
    df = df.dropna(subset=["L0W_ROLL","L1W_ROLL"])
    df = df[df["L1W_ROLL"] != 0]

    df["change_pct"] = (df["L0W_ROLL"] - df["L1W_ROLL"]) / df["L1W_ROLL"].abs()
    anomalies = df[df["change_pct"].abs() >= threshold_pct].copy()

    # Determinar si el cambio es bueno o malo según la dirección de la métrica
    def classify(row):
        direction_up_is_good = METRIC_DIRECTION.get(row["METRIC"], True)
        change = row["change_pct"]
        if direction_up_is_good:
            return "mejora" if change > 0 else "deterioro"
        else:
            return "mejora" if change < 0 else "deterioro"

    anomalies["tipo"] = anomalies.apply(classify, axis=1)
    anomalies["change_fmt"] = (anomalies["change_pct"] * 100).round(2).apply(
        lambda v: f"+{v:.1f}%" if v > 0 else f"{v:.1f}%"
    )

    # Ordenar antes de seleccionar columnas finales
    anomalies = anomalies.sort_values(
        "change_pct", key=abs, ascending=False
    ).head(50).reset_index(drop=True)

    cols = ["COUNTRY","CITY","ZONE","ZONE_TYPE","METRIC",
            "L1W_ROLL","L0W_ROLL","change_fmt","tipo"]
    return anomalies[cols]


def consistent_decline_zones(weeks: int = 3) -> pd.DataFrame:
    """
    Zonas con deterioro consistente durante N semanas seguidas.
    Tiene en cuenta la dirección correcta de cada métrica.
    """
    df = get_metrics_df()
    cols_to_check = WEEK_COLS[-(weeks + 1):]
    results = []

    for _, row in df.iterrows():
        vals = [row[c] for c in cols_to_check]
        if any(pd.isna(v) for v in vals):
            continue

        direction_up_is_good = METRIC_DIRECTION.get(row["METRIC"], True)

        if direction_up_is_good:
            # deterioro = valores bajando
            is_declining = all(vals[i] > vals[i+1] for i in range(len(vals)-1))
        else:
            # deterioro = valores subiendo (Markdowns subiendo es malo)
            is_declining = all(vals[i] < vals[i+1] for i in range(len(vals)-1))

        if is_declining:
            total_change = ((vals[-1] - vals[0]) / abs(vals[0]) * 100) if vals[0] != 0 else 0
            results.append({
                "COUNTRY":        row["COUNTRY"],
                "CITY":           row["CITY"],
                "ZONE":           row["ZONE"],
                "ZONE_TYPE":      row["ZONE_TYPE"],
                "METRIC":         row["METRIC"],
                "valor_inicio":   round(vals[0], 4),
                "valor_actual":   round(vals[-1], 4),
                "cambio_pct":     round(total_change, 2),
                "semanas_caida":  weeks
            })

    result_df = pd.DataFrame(results)
    if result_df.empty:
        return result_df
    return result_df.sort_values("cambio_pct").head(30).reset_index(drop=True)


def benchmarking(metric: str, country: str) -> pd.DataFrame:
    """
    Compara cada zona de un país contra el promedio de su ZONE_TYPE.
    Muestra quién está por encima y por debajo del benchmark.
    """
    df = get_metrics_df()
    df = df[
        (df["METRIC"] == metric) &
        (df["COUNTRY"].str.upper() == country.upper())
    ].copy()

    if df.empty:
        return pd.DataFrame()

    df["zone_type_avg"] = df.groupby("ZONE_TYPE")["L0W_ROLL"].transform("mean")
    df["vs_avg_pct"] = ((df["L0W_ROLL"] - df["zone_type_avg"]) / df["zone_type_avg"] * 100).round(2)
    df["vs_avg_fmt"] = df["vs_avg_pct"].apply(
        lambda v: f"+{v:.1f}%" if v > 0 else f"{v:.1f}%"
    )
    df["value_fmt"] = df["L0W_ROLL"].apply(lambda v: fmt_val(v, metric))

    cols = ["CITY","ZONE","ZONE_TYPE","ZONE_PRIORITIZATION",
            "L0W_ROLL","value_fmt","zone_type_avg","vs_avg_pct","vs_avg_fmt"]
    return df[cols].sort_values("vs_avg_pct", ascending=False).reset_index(drop=True)


def correlation_analysis(metric1: str, metric2: str) -> dict:
    """
    Correlación de Pearson entre dos métricas a nivel de zona.
    Retorna el coeficiente, interpretación y datos para scatter plot.
    """
    df = get_metrics_df()
    base = ["COUNTRY","CITY","ZONE"]

    m1 = df[df["METRIC"] == metric1][base + ["L0W_ROLL"]].rename(columns={"L0W_ROLL": "v1"})
    m2 = df[df["METRIC"] == metric2][base + ["L0W_ROLL"]].rename(columns={"L0W_ROLL": "v2"})
    merged = m1.merge(m2, on=base).dropna()

    if len(merged) < 5:
        return {"correlation": None, "n": 0, "interpretation": "Datos insuficientes"}

    r = merged["v1"].corr(merged["v2"])
    r_rounded = round(float(r), 4)

    a = abs(r_rounded)
    direction = "positiva" if r_rounded > 0 else "negativa"
    if a >= 0.7:   strength = "fuerte"
    elif a >= 0.4: strength = "moderada"
    elif a >= 0.2: strength = "débil"
    else:          strength = "muy débil o nula"

    interpretation = f"Correlación {strength} {direction} (r={r_rounded})"

    return {
        "correlation":     r_rounded,
        "n":               len(merged),
        "interpretation":  interpretation,
        "scatter_data":    df_to_records(merged.rename(columns={"v1": metric1, "v2": metric2}))
    }


def get_kpis_summary(week_col: str = "L0W_ROLL") -> dict:
    """
    Resumen ejecutivo de KPIs para el dashboard principal.
    Acepta week_col para mostrar cualquier semana del histórico.
    El delta siempre se calcula contra la semana anterior a la seleccionada.
    """
    df = get_metrics_df()
    key_metrics = ["Perfect Orders","Lead Penetration","Gross Profit UE",
                   "Pro Adoption (Last Week Status)"]

    # Calcular semana anterior dinámicamente
    week_idx = WEEK_COLS.index(week_col) if week_col in WEEK_COLS else len(WEEK_COLS) - 1
    prev_col = WEEK_COLS[week_idx - 1] if week_idx > 0 else week_col

    summary = {}
    for metric in key_metrics:
        m = df[df["METRIC"] == metric].copy()
        # Filtrar outliers para métricas de porcentaje
        if metric != "Gross Profit UE":
            m = m[(m[week_col] >= 0) & (m[week_col] <= 1)]
            m = m[(m[prev_col] >= 0) & (m[prev_col] <= 1)]
        current  = m[week_col].mean()
        previous = m[prev_col].mean()
        delta    = current - previous
        delta_pct = (delta / abs(previous) * 100) if previous != 0 else 0

        summary[metric] = {
            "current":     round(current, 4),
            "previous":    round(previous, 4),
            "delta":       round(delta, 4),
            "delta_pct":   round(delta_pct, 2),
            "value_fmt":   fmt_val(current, metric),
            "delta_fmt":   f"+{delta_pct:.1f}%" if delta_pct > 0 else f"{delta_pct:.1f}%",
            "trend":       "up" if delta_pct > 0 else ("down" if delta_pct < 0 else "flat"),
            "week":        week_col
        }

    return summary


def get_weekly_trend_all_metrics(metric: str) -> dict:
    """
    Promedio global semanal de una métrica para las 9 semanas.
    Útil para el gráfico de tendencia del dashboard.
    """
    df = get_metrics_df()
    df = df[df["METRIC"] == metric]
    avgs = [df[c].mean() for c in WEEK_COLS]
    return {
        "labels": WEEK_LABELS,
        "values": [round(v, 4) for v in avgs],
        "metric": metric
    }


def get_available_metrics() -> list[str]:
    return sorted(get_metrics_df()["METRIC"].unique().tolist())


def get_available_countries() -> list[str]:
    return sorted(get_metrics_df()["COUNTRY"].unique().tolist())


def get_available_zones(country: str = None) -> list[str]:
    df = get_metrics_df()
    if country:
        df = df[df["COUNTRY"].str.upper() == country.upper()]
    return sorted(df["ZONE"].unique().tolist())
