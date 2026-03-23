"""
tools.py
--------
Responsabilidad única: definir las herramientas (tools) que Claude puede
invocar durante una conversación, y ejecutarlas cuando Claude las llama.

Estructura de cada tool:
  1. Definición JSON (le dice a Claude qué puede hacer y qué parámetros acepta)
  2. Función de ejecución (corre el análisis real con data_engine)

Regla: cada tool mapea 1:1 a una función de data_engine.py.
Si agregas una función en data_engine, agrega su tool aquí.
"""

import json
import pandas as pd
from core.data_engine import (
    top_zones_by_metric,
    compare_zone_types,
    zone_trend,
    average_by_country,
    multivariable_analysis,
    fastest_growing_zones,
    zone_orders_trend,
    anomaly_detection,
    consistent_decline_zones,
    benchmarking,
    correlation_analysis,
    get_available_metrics,
    get_available_countries,
    get_available_zones,
    df_to_records,
    COUNTRY_NAMES,
    WEEK_LABELS,
)


# ── Definiciones de tools para la API de Claude ───────────────────────────────
# Estas definiciones son las que Claude lee para saber qué puede hacer.
# La descripción es crítica: Claude decide qué tool usar basándose en ella.

TOOLS_DEFINITIONS = [
    {
        "name": "top_zones_by_metric",
        "description": (
            "Obtiene las top N zonas rankeadas por una métrica específica. "
            "Úsala para preguntas como: 'top 5 zonas con mayor Lead Penetration', "
            "'zonas con peor Perfect Orders en México', "
            "'cuáles son las zonas con mayor Gross Profit UE esta semana'. "
            "También sirve para bottom N usando ascending=true."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "description": "Nombre exacto de la métrica. Opciones: Perfect Orders, Lead Penetration, Gross Profit UE, Pro Adoption (Last Week Status), Turbo Adoption, Non-Pro PTC > OP, MLTV Top Verticals Adoption, % PRO Users Who Breakeven, % Restaurants Sessions With Optimal Assortment, Restaurants SS > ATC CVR, Restaurants SST > SS CVR, Retail SST > SS CVR, Restaurants Markdowns / GMV"
                },
                "n": {
                    "type": "integer",
                    "description": "Número de zonas a retornar. Default: 5"
                },
                "ascending": {
                    "type": "boolean",
                    "description": "Si true, retorna las peores (bottom N). Default: false"
                },
                "country": {
                    "type": "string",
                    "description": "Código de país de 2 letras para filtrar: AR, BR, CL, CO, CR, EC, MX, PE, UY"
                },
                "zone_type": {
                    "type": "string",
                    "description": "Filtrar por tipo de zona: 'Wealthy' o 'Non Wealthy'"
                },
                "week": {
                    "type": "string",
                    "description": "Semana a consultar. Default: L0W_ROLL (semana actual). Opciones: L8W_ROLL hasta L0W_ROLL"
                }
            },
            "required": ["metric"]
        }
    },
    {
        "name": "compare_zone_types",
        "description": (
            "Compara el promedio semanal de una métrica entre zonas Wealthy y Non Wealthy. "
            "Úsala para: 'compara Perfect Order entre Wealthy y Non Wealthy en México', "
            "'diferencia entre tipos de zona en Lead Penetration', "
            "'cómo se comporta Gross Profit UE según el tipo de zona'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "description": "Nombre exacto de la métrica"},
                "country": {"type": "string", "description": "Código de país opcional (AR, BR, CL, CO, CR, EC, MX, PE, UY)"}
            },
            "required": ["metric"]
        }
    },
    {
        "name": "zone_trend",
        "description": (
            "Obtiene la evolución de una métrica para una zona específica durante las últimas 8 semanas. "
            "Úsala para: 'muestra la tendencia de Chapinero en Perfect Orders', "
            "'cómo ha evolucionado Gross Profit UE en Polanco', "
            "'evolución de Lead Penetration en Miraflores últimas 8 semanas'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {"type": "string", "description": "Nombre exacto de la zona"},
                "metric": {"type": "string", "description": "Nombre exacto de la métrica"},
                "country": {"type": "string", "description": "Código de país opcional para desambiguar"}
            },
            "required": ["zone", "metric"]
        }
    },
    {
        "name": "average_by_country",
        "description": (
            "Calcula el promedio de una métrica agrupado por país. "
            "Úsala para: '¿cuál es el promedio de Lead Penetration por país?', "
            "'ranking de países por Perfect Orders', "
            "'en qué países está mejor el Gross Profit UE'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "description": "Nombre exacto de la métrica"},
                "week": {"type": "string", "description": "Semana a usar. Default: L0W_ROLL"}
            },
            "required": ["metric"]
        }
    },
    {
        "name": "multivariable_analysis",
        "description": (
            "Encuentra zonas con una métrica alta Y otra métrica baja simultáneamente. "
            "Úsala para: 'zonas con alto Lead Penetration pero bajo Perfect Order', "
            "'zonas con buena cobertura pero mala calidad', "
            "'dónde tenemos mucha penetración pero poco margen'. "
            "metric_high = la que debe ser alta, metric_low = la que debe ser baja."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric_high": {"type": "string", "description": "Métrica que debe estar por encima de la mediana"},
                "metric_low": {"type": "string", "description": "Métrica que debe estar por debajo de la mediana"},
                "country": {"type": "string", "description": "Código de país opcional"}
            },
            "required": ["metric_high", "metric_low"]
        }
    },
    {
        "name": "fastest_growing_zones",
        "description": (
            "Encuentra las zonas con mayor crecimiento porcentual en volumen de órdenes. "
            "Úsala para: 'zonas que más crecen en órdenes', "
            "'dónde está creciendo más el negocio', "
            "'top zonas por crecimiento en las últimas 5 semanas'. "
            "También es el punto de partida para analizar qué explica ese crecimiento."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "n": {"type": "integer", "description": "Número de zonas. Default: 10"},
                "weeks_back": {"type": "integer", "description": "Semanas hacia atrás para calcular crecimiento. Default: 5"}
            },
            "required": []
        }
    },
    {
        "name": "zone_orders_trend",
        "description": (
            "Obtiene la serie temporal de órdenes (volumen) para una zona específica. "
            "Úsala cuando necesites ver cómo evoluciona el volumen de una zona, "
            "o cuando quieras graficar el crecimiento de órdenes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "zone": {"type": "string", "description": "Nombre exacto de la zona"}
            },
            "required": ["zone"]
        }
    },
    {
        "name": "anomaly_detection",
        "description": (
            "Detecta zonas con cambios bruscos (mayores al threshold) entre la semana pasada y la actual. "
            "Úsala para: 'zonas problemáticas', 'anomalías esta semana', "
            "'qué cambió drásticamente', 'alertas operacionales'. "
            "Clasifica automáticamente si el cambio es mejora o deterioro según la dirección correcta de cada métrica."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "threshold_pct": {
                    "type": "number",
                    "description": "Cambio mínimo para considerar anomalía. Default: 0.10 (10%)"
                }
            },
            "required": []
        }
    },
    {
        "name": "consistent_decline_zones",
        "description": (
            "Encuentra zonas con deterioro consistente durante N semanas consecutivas. "
            "Úsala para: 'tendencias preocupantes', 'zonas en deterioro sostenido', "
            "'qué zonas llevan varias semanas empeorando', 'zonas en riesgo'. "
            "Tiene en cuenta la dirección correcta de cada métrica."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "weeks": {
                    "type": "integer",
                    "description": "Semanas consecutivas de deterioro requeridas. Default: 3"
                }
            },
            "required": []
        }
    },
    {
        "name": "benchmarking",
        "description": (
            "Compara todas las zonas de un país para una métrica, mostrando cuáles están "
            "por encima y por debajo del promedio de su tipo de zona. "
            "Úsala para: 'benchmarking de Colombia en Perfect Orders', "
            "'qué zonas de México están por encima del promedio', "
            "'comparación de zonas similares en Brasil'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "description": "Nombre exacto de la métrica"},
                "country": {"type": "string", "description": "Código de país (AR, BR, CL, CO, CR, EC, MX, PE, UY)"}
            },
            "required": ["metric", "country"]
        }
    },
    {
        "name": "correlation_analysis",
        "description": (
            "Calcula la correlación de Pearson entre dos métricas a través de todas las zonas. "
            "Úsala para: 'relación entre Lead Penetration y Perfect Orders', "
            "'¿las zonas con más descuentos tienen peores órdenes?', "
            "'correlación entre Pro Adoption y Gross Profit UE'. "
            "Retorna el coeficiente r, interpretación y datos para scatter plot."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric1": {"type": "string", "description": "Primera métrica"},
                "metric2": {"type": "string", "description": "Segunda métrica"}
            },
            "required": ["metric1", "metric2"]
        }
    },
    {
        "name": "list_available_options",
        "description": (
            "Lista las métricas, países o zonas disponibles en el dataset. "
            "Úsala cuando necesites saber qué opciones existen antes de hacer otro análisis, "
            "o cuando el usuario pregunte qué métricas o países están disponibles."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "description": "Qué listar: 'metrics', 'countries', o 'zones'",
                    "enum": ["metrics", "countries", "zones"]
                },
                "country": {
                    "type": "string",
                    "description": "Solo para type='zones': filtrar zonas por país"
                }
            },
            "required": ["type"]
        }
    }
]


# ── Ejecutor de tools ─────────────────────────────────────────────────────────
# Cuando Claude decide usar una tool, esta función la ejecuta y devuelve
# el resultado en formato JSON para que Claude pueda leerlo.

def execute_tool(tool_name: str, tool_input: dict) -> dict:
    """
    Ejecuta la tool indicada con los parámetros dados.
    Retorna siempre un dict con:
      - success: bool
      - data: lista de dicts (para tablas/charts)
      - summary: string con resumen textual
      - chart_type: sugerencia de tipo de gráfico
      - error: string (solo si success=False)
    """
    try:
        if tool_name == "top_zones_by_metric":
            df = top_zones_by_metric(**tool_input)
            return {
                "success": True,
                "data": df_to_records(df),
                "summary": f"{len(df)} zonas encontradas para {tool_input.get('metric')}",
                "chart_type": "bar",
                "columns": list(df.columns)
            }

        elif tool_name == "compare_zone_types":
            df = compare_zone_types(**tool_input)
            records = df.reset_index().to_dict(orient="records")
            return {
                "success": True,
                "data": records,
                "summary": f"Comparación Wealthy vs Non Wealthy para {tool_input.get('metric')}",
                "chart_type": "line",
                "columns": ["ZONE_TYPE"] + WEEK_LABELS
            }

        elif tool_name == "zone_trend":
            df = zone_trend(**tool_input)
            if df.empty:
                return {
                    "success": False,
                    "error": f"No se encontró la zona '{tool_input.get('zone')}' con la métrica '{tool_input.get('metric')}'. Verifica el nombre exacto de la zona."
                }
            return {
                "success": True,
                "data": df_to_records(df),
                "summary": f"Tendencia de {tool_input.get('zone')} en {tool_input.get('metric')}",
                "chart_type": "line",
                "columns": ["week", "value", "value_fmt"]
            }

        elif tool_name == "average_by_country":
            df = average_by_country(**tool_input)
            return {
                "success": True,
                "data": df_to_records(df),
                "summary": f"Promedio de {tool_input.get('metric')} por país",
                "chart_type": "bar",
                "columns": ["COUNTRY", "country_name", "avg_value", "value_fmt"]
            }

        elif tool_name == "multivariable_analysis":
            df = multivariable_analysis(**tool_input)
            if df.empty:
                return {
                    "success": True,
                    "data": [],
                    "summary": "No se encontraron zonas que cumplan ambas condiciones",
                    "chart_type": "table"
                }
            return {
                "success": True,
                "data": df_to_records(df),
                "summary": f"Zonas con {tool_input.get('metric_high')} alto y {tool_input.get('metric_low')} bajo",
                "chart_type": "scatter",
                "columns": list(df.columns)
            }

        elif tool_name == "fastest_growing_zones":
            df = fastest_growing_zones(**tool_input)
            return {
                "success": True,
                "data": df_to_records(df),
                "summary": f"Top {len(df)} zonas con mayor crecimiento en órdenes",
                "chart_type": "bar",
                "columns": list(df.columns)
            }

        elif tool_name == "zone_orders_trend":
            df = zone_orders_trend(**tool_input)
            if df.empty:
                return {
                    "success": False,
                    "error": f"No se encontraron datos de órdenes para '{tool_input.get('zone')}'"
                }
            return {
                "success": True,
                "data": df_to_records(df),
                "summary": f"Tendencia de órdenes en {tool_input.get('zone')}",
                "chart_type": "line",
                "columns": ["week", "orders"]
            }

        elif tool_name == "anomaly_detection":
            df = anomaly_detection(**tool_input)
            deterioro = df[df["tipo"] == "deterioro"]
            mejora    = df[df["tipo"] == "mejora"]
            return {
                "success": True,
                "data": df_to_records(df),
                "summary": f"{len(deterioro)} deterioros y {len(mejora)} mejoras detectadas (>{int(tool_input.get('threshold_pct', 0.10)*100)}% cambio)",
                "chart_type": "table",
                "columns": list(df.columns)
            }

        elif tool_name == "consistent_decline_zones":
            df = consistent_decline_zones(**tool_input)
            return {
                "success": True,
                "data": df_to_records(df),
                "summary": f"{len(df)} zonas con deterioro consistente en {tool_input.get('weeks', 3)}+ semanas",
                "chart_type": "table",
                "columns": list(df.columns) if not df.empty else []
            }

        elif tool_name == "benchmarking":
            df = benchmarking(**tool_input)
            if df.empty:
                return {
                    "success": False,
                    "error": f"No se encontraron datos para {tool_input.get('country')} en {tool_input.get('metric')}"
                }
            return {
                "success": True,
                "data": df_to_records(df),
                "summary": f"Benchmarking de {tool_input.get('country')} en {tool_input.get('metric')}",
                "chart_type": "bar",
                "columns": list(df.columns)
            }

        elif tool_name == "correlation_analysis":
            result = correlation_analysis(**tool_input)
            return {
                "success": True,
                "data": result.get("scatter_data", []),
                "summary": result.get("interpretation", ""),
                "chart_type": "scatter",
                "correlation": result.get("correlation"),
                "n": result.get("n")
            }

        elif tool_name == "list_available_options":
            list_type = tool_input.get("type")
            if list_type == "metrics":
                items = get_available_metrics()
                return {"success": True, "data": [{"metric": m} for m in items], "summary": f"{len(items)} métricas disponibles"}
            elif list_type == "countries":
                items = get_available_countries()
                data = [{"code": c, "name": COUNTRY_NAMES.get(c, c)} for c in items]
                return {"success": True, "data": data, "summary": f"{len(items)} países disponibles"}
            elif list_type == "zones":
                country = tool_input.get("country")
                items = get_available_zones(country)
                return {"success": True, "data": [{"zone": z} for z in items], "summary": f"{len(items)} zonas disponibles"}

        return {"success": False, "error": f"Tool '{tool_name}' no reconocida"}

    except Exception as e:
        return {
            "success": False,
            "error": f"Error ejecutando {tool_name}: {str(e)}"
        }
