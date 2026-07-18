"""Listener de NOTIFY para refrescar la cartelera al instante.

El trigger `anuncio_notify` hace pg_notify('anuncio', '{"accion":...,"id":...}')
en cada INSERT/UPDATE. Este listener corre en un hilo de fondo, escucha el canal
y emite `recibido(accion, id)` para que el satélite recargue sus anuncios y, si
la acción es 'inmediato', muestre el aviso enseguida. El refresco del watchdog
sigue de respaldo si el listener no puede conectarse.

Defensivo igual que `TrabajoNotifyListener`: reintenta y nunca tumba la app.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

_CANAL = "anuncio"


def _conninfo_desde_settings() -> str:
    from pos_uniformes.utils.config import settings

    return (
        f"host={settings.db_host} port={settings.db_port} "
        f"dbname={settings.db_name} user={settings.db_user} "
        f"password={settings.db_password} connect_timeout=2"
    )


class AnuncioNotifyListener(QThread):
    """Emite `recibido(accion, id)` con cada NOTIFY del canal 'anuncio'."""

    recibido = pyqtSignal(str, int)

    def __init__(
        self,
        parent=None,
        *,
        connect_fn: Callable[[], object] | None = None,
        canal: str = _CANAL,
        reconnect_delay_s: float = 5.0,
    ) -> None:
        super().__init__(parent)
        self._connect_fn = connect_fn or self._connect_default
        self._canal = canal
        self._reconnect_delay_s = reconnect_delay_s
        self._stop = False

    def _connect_default(self):
        import psycopg

        return psycopg.connect(_conninfo_desde_settings(), autocommit=True)

    def stop(self) -> None:
        self._stop = True

    @staticmethod
    def _parse(payload: str) -> tuple[str, int]:
        """Extrae (accion, id) del payload JSON; tolera formato inesperado."""
        try:
            data = json.loads(payload)
            return str(data.get("accion") or "refrescar"), int(data.get("id") or 0)
        except Exception:  # noqa: BLE001
            return "refrescar", 0

    def run(self) -> None:  # pragma: no cover — hilo con IO de red real
        while not self._stop:
            conn = None
            try:
                conn = self._connect_fn()
                conn.execute(f"LISTEN {self._canal}")
                for notify in conn.notifies():
                    if self._stop:
                        break
                    accion, anuncio_id = self._parse(getattr(notify, "payload", ""))
                    self.recibido.emit(accion, anuncio_id)
            except Exception as exc:  # noqa: BLE001 — reconectar, nunca crashear
                logger.warning(
                    "Listener de anuncios: %s (reintenta en %ss)",
                    exc,
                    self._reconnect_delay_s,
                )
                if not self._stop:
                    time.sleep(self._reconnect_delay_s)
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:  # noqa: BLE001
                        pass
