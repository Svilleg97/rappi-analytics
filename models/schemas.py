"""
schemas.py
----------
Responsabilidad única: definir los tipos de datos (request y response)
que viajan entre el frontend y el backend.

Pydantic valida automáticamente que los datos sean del tipo correcto
antes de que lleguen a la lógica de negocio. Si el frontend manda
un string donde se espera un int, Pydantic lo rechaza con un error
claro — no llega a ejecutar código con datos incorrectos.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)

class LoginResponse(BaseModel):
    success:  bool
    message:  str
    username: Optional[str] = None


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message:    str          = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None   # None = nueva conversación

class ChatJobResponse(BaseModel):
    """Respuesta inmediata al enviar un mensaje — solo el job_id."""
    job_id:     str
    session_id: str

class JobStatusResponse(BaseModel):
    """Estado de un job — el frontend hace polling de este endpoint."""
    job_id:  str
    status:  str           # pending | processing | done | error
    result:  Optional[dict] = None
    error:   Optional[str]  = None

class ConversationSummary(BaseModel):
    """Metadata de una conversación para el historial (sin mensajes completos)."""
    session_id: str
    title:      str
    created_at: str
    updated_at: str
    msg_count:  int

class ConversationDetail(BaseModel):
    """Conversación completa con todos los mensajes."""
    session_id: str
    title:      str
    created_at: str
    updated_at: str
    messages:   list[dict]
    summary:    Optional[str] = None


# ── Reports ───────────────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    report_type: str = Field(default="weekly")  # weekly | country | custom
    country:     Optional[str] = None           # para reportes por país
    title:       Optional[str] = None

class ReportJobResponse(BaseModel):
    job_id: str

class ReportSummary(BaseModel):
    """Metadata de un reporte para el historial."""
    report_id:  str
    title:      str
    created_at: str
    type:       str
    stats:      dict

class ReportDetail(BaseModel):
    report_id: str
    title:     str
    created_at: str
    markdown:  str
    stats:     dict


# ── Dashboard ─────────────────────────────────────────────────────────────────

class KPIItem(BaseModel):
    current:    float
    previous:   float
    delta:      float
    delta_pct:  float
    value_fmt:  str
    delta_fmt:  str
    trend:      str   # up | down | flat

class DashboardResponse(BaseModel):
    kpis:        dict[str, KPIItem]
    anomalies:   list[dict]
    top_growing: list[dict]
    weekly_trends: dict


# ── Generic ───────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str

class SuccessResponse(BaseModel):
    success: bool
    message: str
