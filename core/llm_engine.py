"""
llm_engine.py
-------------
Responsabilidad única: manejar la conversación con Claude API,
incluyendo el loop de tool use, memoria conversacional y anti-alucinación.

Estrategias implementadas:
  1. temperature=0  → respuestas deterministas, menos alucinación
  2. Tool Use       → Claude no puede inventar datos numéricos
  3. Truncado       → conversaciones largas no explotan el context window
  4. Resumen        → memoria persistente al retomar conversaciones viejas
"""

import os
import json
import logging
from anthropic import Anthropic
from core.prompts import get_system_prompt
from core.tools import TOOLS_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

MODEL                = "claude-sonnet-4-20250514"
MAX_TOOL_ITERATIONS  = 6
MAX_TOKENS           = 4096
MAX_HISTORY_MESSAGES = 20
SUMMARY_THRESHOLD    = 24


def _get_client() -> Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY no está configurada. "
            "Verifica tu archivo .env"
        )
    return Anthropic(api_key=api_key)


# ── Gestión de contexto y memoria ─────────────────────────────────────────────

def _compress_old_messages(messages: list) -> list:
    """
    Si el historial supera MAX_HISTORY_MESSAGES, comprime los mensajes
    más antiguos en un resumen y conserva los recientes completos.
    """
    if len(messages) <= MAX_HISTORY_MESSAGES:
        return messages

    old_messages    = messages[:-MAX_HISTORY_MESSAGES]
    recent_messages = messages[-MAX_HISTORY_MESSAGES:]

    summary_lines = ["[RESUMEN DE CONVERSACIÓN PREVIA]"]
    for msg in old_messages:
        role    = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, str) and content.strip():
            preview = content[:150].replace("\n", " ")
            if role == "user":
                summary_lines.append(f"Usuario preguntó: {preview}...")
            elif role == "assistant":
                summary_lines.append(f"Asistente respondió: {preview}...")

    summary_text = "\n".join(summary_lines)

    compressed = [
        {
            "role": "user",
            "content": summary_text
        },
        {
            "role": "assistant",
            "content": "Entendido. Tengo el contexto de la conversación previa."
        }
    ] + recent_messages

    logger.info(f"Historial comprimido: {len(messages)} → {len(compressed)} mensajes")
    return compressed


def build_context_with_summary(
    conversation_history: list,
    prior_summary: str = None
) -> list:
    """
    Construye el contexto para Claude combinando resumen previo + historial actual.
    Permite retomar conversaciones del día anterior con memoria comprimida.
    """
    messages = []

    if prior_summary:
        messages = [
            {
                "role": "user",
                "content": (
                    f"[CONTEXTO DE CONVERSACIÓN ANTERIOR]\n{prior_summary}\n\n"
                    "Por favor ten en cuenta este contexto para nuestra conversación."
                )
            },
            {
                "role": "assistant",
                "content": (
                    "Perfecto, tengo el contexto de nuestra conversación anterior. "
                    "¿En qué te puedo ayudar ahora?"
                )
            }
        ]

    current = _compress_old_messages(conversation_history)
    messages.extend(current)
    return messages


def summarize_conversation(conversation_history: list) -> str:
    """
    Genera un resumen comprimido de una conversación para memoria persistente.
    Se guarda en disco al cerrar la sesión y se inyecta al retomar.
    """
    client = _get_client()

    convo_text = ""
    for msg in conversation_history:
        role    = "Usuario"    if msg.get("role") == "user" else "Asistente"
        content = msg.get("content", "")
        if isinstance(content, str):
            convo_text += f"{role}: {content[:300]}\n"

    if not convo_text.strip():
        return ""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=400,
            temperature=0,
            messages=[{
                "role": "user",
                "content": (
                    "Resume esta conversación de análisis de datos en máximo 5 oraciones. "
                    "Incluye: qué métricas y zonas se analizaron, hallazgos clave, "
                    "y cualquier contexto importante para retomar la conversación. "
                    "Sé específico con nombres de zonas y países.\n\n"
                    f"CONVERSACIÓN:\n{convo_text}"
                )
            }]
        )
        return _extract_text(response.content)
    except Exception as e:
        logger.error(f"Error generando resumen: {e}")
        user_msgs = [m for m in conversation_history if m.get("role") == "user"]
        topics    = [str(m.get("content", ""))[:80] for m in user_msgs[:5]]
        return f"Conversación previa sobre: {'; '.join(topics)}"


# ── Chat principal ─────────────────────────────────────────────────────────────

def chat(
    user_message: str,
    conversation_history: list,
    prior_summary: str = None
) -> dict:
    """
    Envía un mensaje a Claude y retorna la respuesta completa.

    Args:
        user_message:         Mensaje del usuario
        conversation_history: Historial de la sesión actual
        prior_summary:        Resumen de sesión previa (para retomar conversaciones)

    Returns:
        dict con: text, tool_calls, updated_history, error
    """
    client        = _get_client()
    system_prompt = get_system_prompt()

    messages = build_context_with_summary(conversation_history, prior_summary)
    messages.append({"role": "user", "content": user_message})

    tool_calls_log = []

    for iteration in range(MAX_TOOL_ITERATIONS):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                temperature=0,
                system=system_prompt,
                tools=TOOLS_DEFINITIONS,
                messages=messages
            )
        except Exception as e:
            logger.error(f"Error Claude API (iter {iteration}): {e}")
            return {
                "text": (
                    "Hubo un error al conectar con el servicio de IA. "
                    "Por favor intenta de nuevo en unos segundos."
                ),
                "tool_calls":      tool_calls_log,
                "updated_history": conversation_history,
                "error":           str(e)
            }

        # Respuesta final
        if response.stop_reason == "end_turn":
            final_text = _extract_text(response.content)

            updated_history = conversation_history.copy()
            updated_history.append({"role": "user",      "content": user_message})
            updated_history.append({"role": "assistant",  "content": final_text})

            return {
                "text":            final_text,
                "tool_calls":      tool_calls_log,
                "updated_history": updated_history,
                "error":           None
            }

        # Tool use
        elif response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name  = block.name
                tool_input = block.input
                tool_id    = block.id

                logger.info(f"Tool: {tool_name} | params: {tool_input}")
                result = execute_tool(tool_name, tool_input)

                tool_calls_log.append({
                    "tool":       tool_name,
                    "input":      tool_input,
                    "result":     result,
                    "chart_type": result.get("chart_type", "table")
                })

                tool_results.append(_build_tool_result(tool_id, result))

            messages.append({"role": "user", "content": tool_results})

        else:
            logger.warning(f"Stop reason inesperado: {response.stop_reason}")
            break

    # Fallback si se agotaron iteraciones
    last_text = _extract_text(response.content) if response else ""
    updated_history = conversation_history.copy()
    updated_history.append({"role": "user",      "content": user_message})
    updated_history.append({"role": "assistant",  "content": last_text or "No se pudo completar el análisis."})

    return {
        "text":            last_text or "Se alcanzó el límite de análisis. Reformula tu pregunta.",
        "tool_calls":      tool_calls_log,
        "updated_history": updated_history,
        "error":           None
    }


# ── Generación de reportes ─────────────────────────────────────────────────────

def generate_insights_report(data_summary: str) -> dict:
    """
    Genera el reporte ejecutivo automático.
    Single-shot — temperature=0 para máxima precisión.
    """
    from core.prompts import get_insights_prompt

    client = _get_client()
    prompt = get_insights_prompt(data_summary)

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        return {
            "report_markdown": _extract_text(response.content),
            "error":           None
        }
    except Exception as e:
        logger.error(f"Error generando reporte: {e}")
        return {"report_markdown": "", "error": str(e)}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_tool_result(tool_use_id: str, result: dict) -> dict:
    """Construye el bloque tool_result con límite de tamaño."""
    if result.get("success"):
        data = result.get("data", [])
        if len(data) > 150:
            result = {**result, "data": data[:150], "truncated": True}
        content = json.dumps(result, ensure_ascii=False, default=str)
    else:
        content = json.dumps(
            {"error": result.get("error", "Error desconocido")},
            ensure_ascii=False
        )
    return {
        "type":        "tool_result",
        "tool_use_id": tool_use_id,
        "content":     content
    }


def _extract_text(content_blocks) -> str:
    """Extrae bloques de texto de la respuesta de Claude."""
    if not content_blocks:
        return ""
    texts = []
    for block in content_blocks:
        block_type = getattr(block, "type", None) or (
            block.get("type", "") if isinstance(block, dict) else ""
        )
        if block_type == "text":
            text = getattr(block, "text", None) or (
                block.get("text", "") if isinstance(block, dict) else ""
            )
            if text:
                texts.append(text)
    return "\n".join(texts)
