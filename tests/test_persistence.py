"""
tests/test_persistence.py
--------------------------
Tests para el sistema de persistencia.
Verifica que guardar y cargar conversaciones y reportes
funcione correctamente sin corromper datos.
"""

import pytest
import json
import uuid
from pathlib import Path
from core.persistence import (
    save_conversation,
    load_conversation,
    list_conversations,
    delete_conversation,
    save_report,
    load_report,
    list_reports,
    HISTORY_DIR,
    REPORTS_DIR,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_conversation():
    """Conversación de prueba."""
    return {
        "session_id": f"test_{uuid.uuid4().hex[:8]}",
        "messages": [
            {"role": "user", "content": "¿Cuáles son las 5 zonas con mayor Lead Penetration?"},
            {"role": "assistant", "content": "Las 5 zonas con mayor Lead Penetration son..."},
        ],
        "created_at": "2026-03-23T01:00:00",
        "title": "Test conversación"
    }


@pytest.fixture
def sample_report_markdown():
    """Markdown de reporte de prueba."""
    return """# REPORTE EJECUTIVO SEMANAL — RAPPI OPERATIONS

## KPIs Globales

| Métrica | Valor Actual | Cambio WoW | Estado |
|---------|-------------|------------|--------|
| Perfect Orders | 85.3% | -0.4% | 🟡 |

## 1. Resumen Ejecutivo

Test de hallazgo crítico para verificar persistencia.

## 7. Recomendaciones Accionables

**Acción**: Test de recomendación
**Zona/País**: Colombia
**Resultado esperado**: Verificar que se guarda correctamente
"""


# ── Tests de conversaciones ───────────────────────────────────────────────────

def test_save_and_load_conversation(sample_conversation):
    """Guardar y cargar una conversación debe retornar los mismos datos."""
    session_id = sample_conversation["session_id"]

    save_conversation(session_id, sample_conversation["messages"])
    loaded = load_conversation(session_id)

    assert loaded is not None
    assert loaded["session_id"] == session_id
    assert len(loaded["messages"]) == 2

    # Cleanup
    path = HISTORY_DIR / f"{session_id}.json"
    path.unlink(missing_ok=True)


def test_save_conversation_creates_file(sample_conversation):
    """Guardar una conversación debe crear el archivo JSON."""
    session_id = sample_conversation["session_id"]
    path = HISTORY_DIR / f"{session_id}.json"

    assert not path.exists()
    save_conversation(session_id, sample_conversation["messages"])
    assert path.exists()

    # Cleanup
    path.unlink(missing_ok=True)


def test_save_conversation_valid_json(sample_conversation):
    """El archivo guardado debe ser JSON válido."""
    session_id = sample_conversation["session_id"]
    path = HISTORY_DIR / f"{session_id}.json"

    save_conversation(session_id, sample_conversation["messages"])

    content = path.read_text(encoding="utf-8")
    data = json.loads(content)
    assert "session_id" in data
    assert "messages" in data

    # Cleanup
    path.unlink(missing_ok=True)


def test_load_nonexistent_conversation():
    """Cargar una conversación inexistente debe retornar None."""
    result = load_conversation("session_que_no_existe_xyz123")
    assert result is None


def test_list_conversations_returns_list():
    """Listar conversaciones debe retornar una lista."""
    result = list_conversations()
    assert isinstance(result, list)


def test_list_conversations_includes_saved(sample_conversation):
    """La conversación guardada debe aparecer en la lista."""
    session_id = sample_conversation["session_id"]
    save_conversation(session_id, sample_conversation["messages"])

    conversations = list_conversations()
    session_ids = [c["session_id"] for c in conversations]
    assert session_id in session_ids

    # Cleanup
    path = HISTORY_DIR / f"{session_id}.json"
    path.unlink(missing_ok=True)


def test_delete_conversation(sample_conversation):
    """Eliminar una conversación debe borrar el archivo."""
    session_id = sample_conversation["session_id"]
    path = HISTORY_DIR / f"{session_id}.json"

    save_conversation(session_id, sample_conversation["messages"])
    assert path.exists()

    delete_conversation(session_id)
    assert not path.exists()


def test_conversation_preserves_message_order(sample_conversation):
    """El orden de los mensajes debe preservarse."""
    session_id = sample_conversation["session_id"]
    messages = [
        {"role": "user", "content": "Primera pregunta"},
        {"role": "assistant", "content": "Primera respuesta"},
        {"role": "user", "content": "Segunda pregunta"},
        {"role": "assistant", "content": "Segunda respuesta"},
    ]

    save_conversation(session_id, messages)
    loaded = load_conversation(session_id)

    assert loaded["messages"][0]["content"] == "Primera pregunta"
    assert loaded["messages"][2]["content"] == "Segunda pregunta"

    # Cleanup
    path = HISTORY_DIR / f"{session_id}.json"
    path.unlink(missing_ok=True)


# ── Tests de reportes ─────────────────────────────────────────────────────────

def test_save_and_load_report(sample_report_markdown):
    """Guardar y cargar un reporte debe retornar los mismos datos."""
    report_id = save_report(sample_report_markdown, title="Test Reporte")

    assert report_id is not None
    loaded = load_report(report_id)

    assert loaded is not None
    assert loaded["report_id"] == report_id
    assert loaded["markdown"] == sample_report_markdown

    # Cleanup
    for ext in [".json", ".html"]:
        path = REPORTS_DIR / f"{report_id}{ext}"
        path.unlink(missing_ok=True)


def test_save_report_creates_json_and_html(sample_report_markdown):
    """Guardar un reporte debe crear archivos JSON y HTML."""
    report_id = save_report(sample_report_markdown, title="Test HTML")

    json_path = REPORTS_DIR / f"{report_id}.json"
    html_path = REPORTS_DIR / f"{report_id}.html"

    assert json_path.exists(), "Archivo JSON no fue creado"
    assert html_path.exists(), "Archivo HTML no fue creado"

    # Cleanup
    json_path.unlink(missing_ok=True)
    html_path.unlink(missing_ok=True)


def test_save_report_html_has_rappi_branding(sample_report_markdown):
    """El HTML generado debe tener el branding de Rappi."""
    report_id = save_report(sample_report_markdown, title="Test Branding")
    html_path = REPORTS_DIR / f"{report_id}.html"

    html_content = html_path.read_text(encoding="utf-8")
    assert "Nunito" in html_content, "Tipografía Nunito no encontrada"
    assert "#FF441F" in html_content, "Color naranja Rappi no encontrado"
    assert "Rappi Analytics" in html_content, "Nombre Rappi Analytics no encontrado"

    # Cleanup
    for ext in [".json", ".html"]:
        (REPORTS_DIR / f"{report_id}{ext}").unlink(missing_ok=True)


def test_save_report_with_title(sample_report_markdown):
    """El título del reporte debe guardarse correctamente."""
    title = "Reporte Test Titulo Especial"
    report_id = save_report(sample_report_markdown, title=title)
    loaded = load_report(report_id)

    assert loaded["title"] == title

    # Cleanup
    for ext in [".json", ".html"]:
        (REPORTS_DIR / f"{report_id}{ext}").unlink(missing_ok=True)


def test_save_report_has_created_at(sample_report_markdown):
    """El reporte guardado debe tener timestamp de creación."""
    report_id = save_report(sample_report_markdown, title="Test Timestamp")
    loaded = load_report(report_id)

    assert "created_at" in loaded
    assert loaded["created_at"] is not None

    # Cleanup
    for ext in [".json", ".html"]:
        (REPORTS_DIR / f"{report_id}{ext}").unlink(missing_ok=True)


def test_load_nonexistent_report():
    """Cargar un reporte inexistente debe retornar None."""
    result = load_report("reporte_que_no_existe_xyz123")
    assert result is None


def test_list_reports_returns_list():
    """Listar reportes debe retornar una lista."""
    result = list_reports()
    assert isinstance(result, list)


def test_list_reports_includes_saved(sample_report_markdown):
    """El reporte guardado debe aparecer en la lista."""
    report_id = save_report(sample_report_markdown, title="Test Lista")
    reports = list_reports()
    report_ids = [r["report_id"] for r in reports]
    assert report_id in report_ids

    # Cleanup
    for ext in [".json", ".html"]:
        (REPORTS_DIR / f"{report_id}{ext}").unlink(missing_ok=True)


def test_report_stats_extracted(sample_report_markdown):
    """Las estadísticas del reporte deben extraerse del markdown."""
    report_id = save_report(sample_report_markdown, title="Test Stats")
    loaded = load_report(report_id)

    assert "stats" in loaded
    assert isinstance(loaded["stats"], dict)

    # Cleanup
    for ext in [".json", ".html"]:
        (REPORTS_DIR / f"{report_id}{ext}").unlink(missing_ok=True)


def test_archive_report(sample_report_markdown):
    """Archivar un reporte debe marcarlo como archived=True."""
    report_id = save_report(sample_report_markdown, title="Test Archive")

    # Load and mark as archived
    json_path = REPORTS_DIR / f"{report_id}.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    data["archived"] = True
    json_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    # Verify archived report excluded from main list
    main_list = list_reports(include_archived=False)
    main_ids = [r["report_id"] for r in main_list]
    assert report_id not in main_ids

    # Verify archived report included in history
    history_list = list_reports(include_archived=True)
    history_ids = [r["report_id"] for r in history_list]
    assert report_id in history_ids

    # Cleanup
    for ext in [".json", ".html"]:
        (REPORTS_DIR / f"{report_id}{ext}").unlink(missing_ok=True)
