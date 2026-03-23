"""
job_manager.py
--------------
Responsabilidad única: manejar tareas asíncronas de larga duración.

Resuelve el problema de pérdida de respuesta cuando el usuario:
  - Cambia de pestaña mientras el bot procesa
  - Hace múltiples consultas en simultáneo
  - Genera un reporte mientras tiene el chat abierto
"""

import asyncio
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from core.persistence import save_job, load_job

logger = logging.getLogger(__name__)


class JobStatus:
    PENDING    = "pending"
    PROCESSING = "processing"
    DONE       = "done"
    ERROR      = "error"


class JobManager:

    def __init__(self):
        self._active: dict = {}

    def create_job(self, job_type: str, metadata: dict = None) -> str:
        job_id = str(uuid.uuid4())
        job = {
            "id":         job_id,
            "type":       job_type,
            "status":     JobStatus.PENDING,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "metadata":   metadata or {},
            "result":     None,
            "error":      None
        }
        self._active[job_id] = job
        save_job(job_id, job)
        return job_id

    def get_job(self, job_id: str) -> Optional[dict]:
        if job_id in self._active:
            return self._active[job_id]
        job = load_job(job_id)
        if job:
            self._active[job_id] = job
        return job

    def update_job(self, job_id: str, status: str,
                   result: dict = None, error: str = None):
        job = self.get_job(job_id)
        if not job:
            return
        job["status"]     = status
        job["updated_at"] = datetime.now(timezone.utc).isoformat()
        if result is not None:
            job["result"] = result
        if error is not None:
            job["error"] = error
        self._active[job_id] = job
        save_job(job_id, job)

    async def run_chat_job(
        self,
        job_id: str,
        user_message: str,
        conversation_history: list,
        session_id: str,
        prior_summary: str = None
    ):
        from core.llm_engine import chat
        from core.persistence import save_conversation

        self.update_job(job_id, JobStatus.PROCESSING)
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: chat(user_message, conversation_history, prior_summary)
            )

            if response.get("error") and not response.get("text"):
                self.update_job(job_id, JobStatus.ERROR, error=response["error"])
                return

            save_conversation(session_id, response["updated_history"])

            self.update_job(job_id, JobStatus.DONE, result={
                "text":       response["text"],
                "tool_calls": response["tool_calls"],
                "session_id": session_id
            })

        except Exception as e:
            logger.error(f"Error en chat job {job_id}: {e}", exc_info=True)
            self.update_job(job_id, JobStatus.ERROR, error=str(e))

    async def run_report_job(
        self,
        job_id: str,
        data_summary: str,
        title: str = None
    ):
        from core.llm_engine import generate_insights_report
        from core.persistence import save_report

        self.update_job(job_id, JobStatus.PROCESSING)
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: generate_insights_report(data_summary)
            )

            if result.get("error"):
                self.update_job(job_id, JobStatus.ERROR, error=result["error"])
                return

            report_id = save_report(result["report_markdown"], title=title)
            self.update_job(job_id, JobStatus.DONE, result={
                "report_id":       report_id,
                "report_markdown": result["report_markdown"]
            })

        except Exception as e:
            logger.error(f"Error en report job {job_id}: {e}", exc_info=True)
            self.update_job(job_id, JobStatus.ERROR, error=str(e))


job_manager = JobManager()
