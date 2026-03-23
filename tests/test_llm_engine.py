"""
tests/test_llm_engine.py
------------------------
Tests para el motor LLM con mocks del API de Anthropic.
No hace llamadas reales al API — simula las respuestas
para verificar la lógica del loop de Tool Use.
"""

import pytest
from unittest.mock import patch, MagicMock


# ── Helpers para construir respuestas mock ────────────────────────────────────

def make_text_response(text: str):
    """Simula una respuesta final de Claude con texto."""
    block = MagicMock()
    block.type = "text"
    block.text = text

    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    return response


def make_tool_use_response(tool_name: str, tool_input: dict, tool_id: str = "tool_abc123"):
    """Simula una respuesta de Claude que llama una herramienta."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = tool_id
    tool_block.name = tool_name
    tool_block.input = tool_input

    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [tool_block]
    return response


def make_error_response():
    """Simula una respuesta de error del API."""
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = []
    return response


# ── Tests de flujo básico ─────────────────────────────────────────────────────

def test_simple_text_response():
    """
    Caso más simple: Claude responde directamente con texto sin usar tools.
    Verifica que el motor retorne el texto correctamente.
    """
    from core.llm_engine import chat

    with patch("core.llm_engine._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = make_text_response(
            "Hola, soy RappiInsights. ¿En qué puedo ayudarte?"
        )

        result = chat(
            user_message="Hola",
            conversation_history=[]
        )

        assert result["error"] is None
        assert "RappiInsights" in result["text"]
        assert isinstance(result["tool_calls"], list)


def test_single_tool_call():
    """
    Claude hace una tool call y luego responde con texto.
    Verifica que el loop de Tool Use funcione correctamente.
    """
    from core.llm_engine import chat

    tool_response = make_tool_use_response(
        tool_name="top_zones_by_metric",
        tool_input={"metric": "Perfect Orders", "n": 5},
        tool_id="tool_001"
    )
    final_response = make_text_response(
        "Las 5 zonas con mayor Perfect Orders son: Taubaté MP (100%), ..."
    )

    with patch("core.llm_engine._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.side_effect = [tool_response, final_response]

        result = chat(
            user_message="¿Cuáles son las 5 zonas con mayor Perfect Orders?",
            conversation_history=[]
        )

        assert result["error"] is None
        assert len(result["text"]) > 0
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["tool"] == "top_zones_by_metric"


def test_multiple_tool_calls():
    """
    Claude hace múltiples tool calls antes de responder.
    Verifica que el loop maneje correctamente varias iteraciones.
    """
    from core.llm_engine import chat

    responses = [
        make_tool_use_response("anomaly_detection", {"threshold_pct": 0.10}, "tool_001"),
        make_tool_use_response("consistent_decline_zones", {"weeks": 3}, "tool_002"),
        make_text_response("Encontré 44 zonas con deterioro y 30 con caída sostenida..."),
    ]

    with patch("core.llm_engine._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.side_effect = responses

        result = chat(
            user_message="¿Cuáles son las zonas problemáticas esta semana?",
            conversation_history=[]
        )

        assert result["error"] is None
        assert len(result["tool_calls"]) == 2
        assert mock_client.messages.create.call_count == 3


def test_api_error_returns_error_message():
    """
    Si el API de Anthropic falla, el motor debe retornar un mensaje de error claro.
    """
    from core.llm_engine import chat

    with patch("core.llm_engine._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.side_effect = Exception("API timeout")

        result = chat(
            user_message="Test pregunta",
            conversation_history=[]
        )

        assert result["error"] is not None
        assert isinstance(result["error"], str)


def test_tool_use_loop_limit():
    """
    El loop de Tool Use no debe superar MAX_TOOL_ITERATIONS.
    Verifica que el sistema no entre en un loop infinito.
    """
    from core.llm_engine import chat, MAX_TOOL_ITERATIONS

    # Simular que Claude siempre quiere usar tools (loop infinito)
    infinite_tool = make_tool_use_response(
        "top_zones_by_metric", {"metric": "Perfect Orders", "n": 5}
    )

    with patch("core.llm_engine._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = infinite_tool

        result = chat(
            user_message="Test loop infinito",
            conversation_history=[]
        )

        # No debe superar MAX_TOOL_ITERATIONS llamadas
        assert mock_client.messages.create.call_count <= MAX_TOOL_ITERATIONS + 1
        assert result is not None


def test_history_included_in_api_call():
    """
    El historial de conversación debe incluirse en cada llamada al API.
    Verifica la memoria conversacional.
    """
    from core.llm_engine import chat

    history = [
        {"role": "user", "content": "¿Cuántos países hay?"},
        {"role": "assistant", "content": "Hay 9 países en el sistema."},
    ]

    with patch("core.llm_engine._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = make_text_response(
            "Colombia tiene un Perfect Orders de 88.4%"
        )

        chat(
            user_message="¿Y cómo está Colombia?",
            conversation_history=history
        )

        # Verificar que se pasó el historial en la llamada
        call_args = mock_client.messages.create.call_args
        messages_sent = call_args.kwargs.get("messages", call_args.args[0] if call_args.args else [])
        assert len(messages_sent) >= len(history) + 1


def test_temperature_zero():
    """
    Todas las llamadas al API deben usar temperature=0 para determinismo.
    """
    from core.llm_engine import chat

    with patch("core.llm_engine._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = make_text_response("Test")

        chat(
            user_message="Test temperatura",
            conversation_history=[]
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs.get("temperature") == 0, \
            "temperature debe ser 0 para respuestas deterministas"


def test_system_prompt_included():
    """
    El system prompt debe incluirse en cada llamada al API.
    """
    from core.llm_engine import chat

    with patch("core.llm_engine._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = make_text_response("Test")

        chat(
            user_message="Test system prompt",
            conversation_history=[]
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        system = call_kwargs.get("system", "")
        assert len(system) > 100, "System prompt debe tener contenido sustancial"
        assert "Rappi" in system, "System prompt debe mencionar Rappi"


def test_result_has_required_fields():
    """
    El resultado del motor debe tener todos los campos requeridos.
    """
    from core.llm_engine import chat

    with patch("core.llm_engine._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = make_text_response("Respuesta test")

        result = chat(
            user_message="Test campos",
            conversation_history=[]
        )

        assert "text" in result
        assert "tool_calls" in result
        assert "error" in result
        assert "updated_history" in result


def test_empty_response_handled_gracefully():
    """
    Una respuesta vacía del API debe manejarse sin crash.
    """
    from core.llm_engine import chat

    with patch("core.llm_engine._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.return_value = make_error_response()

        result = chat(
            user_message="Test respuesta vacía",
            conversation_history=[]
        )

        assert result is not None
        assert "text" in result
        assert "error" in result


def test_tool_result_logged():
    """
    Los resultados de las tools deben guardarse en tool_calls del resultado.
    """
    from core.llm_engine import chat

    tool_response = make_tool_use_response(
        "average_by_country",
        {"metric": "Lead Penetration"},
        "tool_log_test"
    )
    final_response = make_text_response("El promedio por país es...")

    with patch("core.llm_engine._get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.side_effect = [tool_response, final_response]

        result = chat(
            user_message="¿Cuál es el promedio de Lead Penetration por país?",
            conversation_history=[]
        )

        assert len(result["tool_calls"]) == 1
        tool_log = result["tool_calls"][0]
        assert "tool" in tool_log
        assert "result" in tool_log
        assert tool_log["tool"] == "average_by_country"
