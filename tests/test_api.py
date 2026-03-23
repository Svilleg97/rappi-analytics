"""
tests/test_api.py
-----------------
Tests de integración para los endpoints de la API.
Verifica que los endpoints respondan correctamente
con y sin autenticación.
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def fresh_client():
    """Cliente sin cookies para tests sin autenticacion."""
    return TestClient(app, cookies={})


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_auth_cookies():
    """Hace login y retorna las cookies de sesión."""
    res = client.post("/api/auth/login",
        json={"username": "rappi_demo", "password": "demo123"})
    assert res.status_code == 200
    return res.cookies


# ── Tests de autenticación ────────────────────────────────────────────────────

def test_login_correcto():
    """Login con credenciales correctas debe retornar 200."""
    res = client.post("/api/auth/login",
        json={"username": "rappi_demo", "password": "demo123"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] == True
    assert "username" in data


def test_login_password_incorrecto():
    """Login con password incorrecto debe retornar 401."""
    res = client.post("/api/auth/login",
        json={"username": "rappi_demo", "password": "password_malo"})
    assert res.status_code == 401


def test_login_usuario_incorrecto():
    """Login con usuario incorrecto debe retornar 401."""
    res = client.post("/api/auth/login",
        json={"username": "usuario_malo", "password": "demo123"})
    assert res.status_code == 401


def test_me_sin_auth():
    """Endpoint /me sin autenticación debe retornar 401."""
    res = fresh_client().get("/api/auth/me")
    assert res.status_code == 401


def test_me_con_auth():
    """Endpoint /me con autenticación debe retornar datos del usuario."""
    cookies = get_auth_cookies()
    res = client.get("/api/auth/me", cookies=cookies)
    assert res.status_code == 200
    data = res.json()
    assert "username" in data


def test_logout():
    """Logout debe retornar 200."""
    cookies = get_auth_cookies()
    res = client.post("/api/auth/logout", cookies=cookies)
    assert res.status_code == 200


# ── Tests de dashboard ────────────────────────────────────────────────────────

def test_dashboard_sin_auth():
    """Dashboard sin autenticación debe retornar 401."""
    res = client.get("/api/insights/dashboard")
    assert res.status_code == 401


def test_dashboard_con_auth():
    """Dashboard con autenticación debe retornar KPIs."""
    cookies = get_auth_cookies()
    res = client.get("/api/insights/dashboard", cookies=cookies)
    assert res.status_code == 200
    data = res.json()
    assert "kpis" in data
    assert "alert_counts" in data


def test_dashboard_semana_historica():
    """Dashboard debe aceptar parámetro de semana histórica."""
    cookies = get_auth_cookies()
    res = client.get("/api/insights/dashboard?week=L4W", cookies=cookies)
    assert res.status_code == 200


def test_dashboard_kpis_structure():
    """Los KPIs del dashboard deben tener la estructura correcta."""
    cookies = get_auth_cookies()
    res = client.get("/api/insights/dashboard", cookies=cookies)
    data = res.json()
    kpis = data.get("kpis", {})
    assert "Perfect Orders" in kpis
    po = kpis["Perfect Orders"]
    assert "current" in po
    assert "value_fmt" in po
    assert "trend" in po


# ── Tests de insights ─────────────────────────────────────────────────────────

def test_anomalies_sin_auth():
    """Anomalías sin autenticación debe retornar 401."""
    res = fresh_client().get("/api/insights/anomalies")
    assert res.status_code == 401


def test_anomalies_con_auth():
    """Anomalías con autenticación debe retornar lista."""
    cookies = get_auth_cookies()
    res = client.get("/api/insights/anomalies", cookies=cookies)
    assert res.status_code == 200
    data = res.json()
    assert "anomalies" in data
    assert isinstance(data["anomalies"], list)


def test_countries_endpoint():
    """Endpoint de países debe retornar los 9 países."""
    cookies = get_auth_cookies()
    res = client.get("/api/insights/countries", cookies=cookies)
    assert res.status_code == 200
    data = res.json()
    assert "countries" in data
    assert len(data["countries"]) == 9


def test_benchmarking_endpoint():
    """Benchmarking debe funcionar con país y métrica válidos."""
    cookies = get_auth_cookies()
    res = client.get(
        "/api/insights/benchmarking?metric=Perfect%20Orders&country=CO",
        cookies=cookies
    )
    assert res.status_code == 200


# ── Tests de reportes ─────────────────────────────────────────────────────────

def test_reports_list_sin_auth():
    """Lista de reportes sin autenticación debe retornar 401."""
    res = fresh_client().get("/api/reports/list")
    assert res.status_code == 401


def test_reports_list_con_auth():
    """Lista de reportes con autenticación debe retornar lista."""
    cookies = get_auth_cookies()
    res = client.get("/api/reports/list", cookies=cookies)
    assert res.status_code == 200
    data = res.json()
    assert "reports" in data
    assert isinstance(data["reports"], list)


# ── Tests de chat ─────────────────────────────────────────────────────────────

def test_chat_message_sin_auth():
    """Enviar mensaje sin autenticación debe retornar 401."""
    res = fresh_client().post("/api/chat/message",
        json={"message": "hola", "session_id": None})
    assert res.status_code == 401


def test_chat_message_con_auth():
    """Enviar mensaje con autenticación debe crear un job."""
    cookies = get_auth_cookies()
    res = client.post("/api/chat/message",
        json={"message": "¿Cuántos países hay en el sistema?", "session_id": None},
        cookies=cookies)
    assert res.status_code == 200
    data = res.json()
    assert "job_id" in data


def test_chat_job_status():
    """El job creado debe tener un estado válido."""
    cookies = get_auth_cookies()
    # Crear job
    res = client.post("/api/chat/message",
        json={"message": "hola", "session_id": None},
        cookies=cookies)
    job_id = res.json()["job_id"]
    # Verificar estado
    res2 = client.get(f"/api/chat/job/{job_id}", cookies=cookies)
    assert res2.status_code == 200
    data = res2.json()
    assert data["status"] in ["pending", "processing", "done", "error"]


def test_chat_history_con_auth():
    """Historial de chat debe retornar lista."""
    cookies = get_auth_cookies()
    res = client.get("/api/chat/history", cookies=cookies)
    assert res.status_code == 200
    data = res.json()
    assert "conversations" in data


# ── Tests de data status ──────────────────────────────────────────────────────

def test_data_status_con_auth():
    """Endpoint de estado de datos debe confirmar que el Excel existe."""
    cookies = get_auth_cookies()
    res = client.get("/api/data/status", cookies=cookies)
    assert res.status_code == 200
    data = res.json()
    assert data["exists"] == True
    assert "last_modified" in data
