"""
api/chat.py
-----------
Rutas del chat conversacional.

Patrón usado: fire-and-forget con polling.
  POST /api/chat/message  → crea job, retorna job_id inmediatamente
  GET  /api/chat/job/{id} → retorna estado del job (pending/done/error)

Esto resuelve el problema de pérdida de respuesta al cambiar de pestaña
o hacer múltiples consultas en simultáneo.
"""

import asyncio
import uuid
from fastapi import APIRouter, Cookie
from fastapi.responses import JSONResponse
from models.schemas import ChatRequest, ChatJobResponse, JobStatusResponse
from core.job_manager import job_manager
from core.persistence import (
    load_conversation, save_conversation,
    list_conversations, delete_conversation,
    new_session_id
)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _require_auth(session: str) -> bool:
    return session is not None and session.startswith("user_")


@router.post("/message", response_model=ChatJobResponse)
async def send_message(
    request: ChatRequest,
    session: str = Cookie(default=None)
):
    """
    Envía un mensaje al bot.
    Retorna job_id inmediatamente — el procesamiento ocurre en background.
    El frontend hace polling a GET /api/chat/job/{job_id} para obtener la respuesta.
    """
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})

    # Resolver o crear sesión de conversación
    session_id = request.session_id or new_session_id()

    # Cargar historial existente
    convo = load_conversation(session_id)
    history = convo.get("messages", []) if convo else []
    prior_summary = convo.get("summary") if convo else None

    # Crear job y retornar inmediatamente
    job_id = job_manager.create_job(
        job_type="chat",
        metadata={"session_id": session_id, "message": request.message[:100]}
    )

    # Lanzar procesamiento en background — no bloquea la respuesta HTTP
    asyncio.create_task(
        job_manager.run_chat_job(
            job_id=job_id,
            user_message=request.message,
            conversation_history=history,
            prior_summary=prior_summary,
            session_id=session_id
        )
    )

    return ChatJobResponse(job_id=job_id, session_id=session_id)


@router.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, session: str = Cookie(default=None)):
    """
    Polling endpoint — el frontend llama esto cada 2s hasta que status=done.
    Retorna el resultado cuando el job termina.
    Persiste en disco, así que funciona aunque el usuario cambie de pestaña.
    """
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})

    job = job_manager.get_job(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"detail": "Job no encontrado"})

    result = job.get("result")
    # Garantizar que result.text sea siempre string plano antes de enviarlo al frontend
    if result and "text" in result:
        text_val = result["text"]
        if not isinstance(text_val, str):
            if isinstance(text_val, list):
                # Lista de bloques de contenido
                result["text"] = " ".join(
                    b.get("text", "") if isinstance(b, dict) else str(b)
                    for b in text_val
                    if (isinstance(b, dict) and b.get("type") == "text") or isinstance(b, str)
                )
            elif isinstance(text_val, dict):
                result["text"] = text_val.get("text", "")
            else:
                result["text"] = str(text_val) if text_val else ""
        # Limpiar artefactos
        if result["text"] in ("undefined", "null", "[object Object]"):
            result["text"] = ""

    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        result=result,
        error=job.get("error")
    )


@router.get("/history")
async def get_history(session: str = Cookie(default=None)):
    """Lista todas las conversaciones del historial."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})
    return {"conversations": list_conversations()}


@router.get("/history/{session_id}")
async def get_conversation(session_id: str, session: str = Cookie(default=None)):
    """Carga una conversación completa para retomarla."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})

    convo = load_conversation(session_id)
    if not convo:
        return JSONResponse(status_code=404, content={"detail": "Conversación no encontrada"})
    return convo


@router.delete("/history/{session_id}")
async def delete_history(session_id: str, session: str = Cookie(default=None)):
    """Elimina una conversación del historial."""
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})

    ok = delete_conversation(session_id)
    return {"success": ok}


@router.post("/history/{session_id}/summarize")
async def summarize_session(session_id: str, session: str = Cookie(default=None)):
    """
    Genera y guarda el resumen de una conversación para memoria persistente.
    Se llama cuando el usuario cierra una sesión o cambia de conversación.
    """
    if not _require_auth(session):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})

    convo = load_conversation(session_id)
    if not convo:
        return JSONResponse(status_code=404, content={"detail": "Conversación no encontrada"})

    messages = convo.get("messages", [])
    if len(messages) < 2:
        return {"success": True, "summary": ""}

    # Generar resumen en background
    async def _summarize():
        from core.llm_engine import summarize_conversation
        loop = asyncio.get_event_loop()
        summary = await loop.run_in_executor(
            None, lambda: summarize_conversation(messages)
        )
        convo["summary"] = summary
        save_conversation(session_id, messages, convo.get("title"))

    asyncio.create_task(_summarize())
    return {"success": True, "message": "Resumen generándose en background"}
