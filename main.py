"""
main.py
-------
Punto de entrada de la aplicación.
Responsabilidad única: montar la app, registrar routers y servir el frontend.
"""

import os
import asyncio
import logging
from pathlib import Path
from fastapi import FastAPI, Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv

from api.auth     import router as auth_router
from api.chat     import router as chat_router
from api.reports  import router as reports_router
from api.insights import router as insights_router

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

app = FastAPI(
    title="Rappi Analytics Platform",
    description="Sistema de análisis inteligente para operaciones Rappi",
    version="1.0.0"
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(reports_router)
app.include_router(insights_router)


# ── Endpoint de recarga manual de datos ──────────────────────────────────────
@app.post("/api/data/reload")
async def reload_data_endpoint(session: str = Cookie(default=None)):
    """Recarga manual del Excel — útil para forzar actualización."""
    if not session or not session.startswith("user_"):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})
    from core.data_engine import reload_data
    reload_data()
    return {"success": True, "message": "Datos recargados correctamente"}


@app.get("/api/data/status")
async def data_status(session: str = Cookie(default=None)):
    """Retorna info del archivo de datos — última modificación."""
    if not session or not session.startswith("user_"):
        return JSONResponse(status_code=401, content={"detail": "No autenticado"})
    from core.data_engine import DATA_PATH, get_data_file_mtime
    from datetime import datetime, timezone
    mtime = get_data_file_mtime()
    return {
        "file":          DATA_PATH.name,
        "last_modified": datetime.fromtimestamp(mtime).isoformat() if mtime else None,
        "exists":        DATA_PATH.exists()
    }


# ── Frontend estático ─────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent / "frontend"
STATIC_DIR   = FRONTEND_DIR / "static"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
async def serve_root():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    return FileResponse(str(FRONTEND_DIR / "index.html"))


# ── Lifecycle: arrancar file watcher al iniciar ───────────────────────────────
@app.on_event("startup")
async def startup_event():
    from core.file_watcher import start_file_watcher
    asyncio.create_task(start_file_watcher())
    logging.getLogger(__name__).info("File watcher iniciado")


# ── Arranque local ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
