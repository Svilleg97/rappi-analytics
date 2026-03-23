"""
file_watcher.py
---------------
Responsabilidad única: monitorear cambios en el archivo de datos
y limpiar el caché automáticamente cuando cambia.

Usa watchdog para detectar cambios en el sistema de archivos.
Si watchdog no está instalado, cae en un polling simple cada 5 minutos.

No sabe nada de HTTP ni de frontend — solo monitorea archivos.
"""

import asyncio
import logging
from pathlib import Path
from core.data_engine import DATA_PATH, reload_data, get_data_file_mtime

logger = logging.getLogger(__name__)

# Intervalo de polling como fallback (segundos)
POLL_INTERVAL = 300  # 5 minutos


async def start_file_watcher():
    """
    Inicia el monitoreo del archivo de datos.
    Intenta usar watchdog primero, cae en polling si no está disponible.
    """
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class DataFileHandler(FileSystemEventHandler):
            def on_modified(self, event):
                if Path(event.src_path).resolve() == DATA_PATH.resolve():
                    logger.info(f"Cambio detectado en {DATA_PATH.name} — recargando datos...")
                    reload_data()

            def on_created(self, event):
                if Path(event.src_path).resolve() == DATA_PATH.resolve():
                    logger.info(f"Nuevo archivo de datos detectado — recargando...")
                    reload_data()

        observer = Observer()
        observer.schedule(
            DataFileHandler(),
            path=str(DATA_PATH.parent),
            recursive=False
        )
        observer.start()
        logger.info(f"Watchdog activo — monitoreando {DATA_PATH}")

        # Mantener el observer corriendo en background
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            observer.stop()
            observer.join()

    except ImportError:
        # watchdog no instalado — usar polling simple
        logger.info("watchdog no disponible — usando polling cada 5 minutos")
        await _polling_watcher()


async def _polling_watcher():
    """
    Fallback: revisa la fecha de modificación del archivo cada N segundos.
    Funciona sin dependencias extra.
    """
    last_mtime = get_data_file_mtime()

    while True:
        await asyncio.sleep(POLL_INTERVAL)
        try:
            current_mtime = get_data_file_mtime()
            if current_mtime != last_mtime:
                logger.info(f"Cambio detectado en {DATA_PATH.name} (polling) — recargando...")
                reload_data()
                last_mtime = current_mtime
        except Exception as e:
            logger.error(f"Error en polling watcher: {e}")
