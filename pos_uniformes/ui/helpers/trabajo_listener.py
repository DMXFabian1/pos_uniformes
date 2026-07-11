"""Listener de NOTIFY para despachar trabajos al instante (Fase 6).

El trigger `trabajo_notify_insert` hace `pg_notify('trabajo_nuevo', id)` en cada
INSERT. Este listener corre en un hilo de fondo, escucha ese canal y emite la
señal `notificado` para que el despachador drene de inmediato —sin esperar al
polling—. El polling sigue activo como respaldo: si el listener no puede
conectarse (o el driver no soporta NOTIFY), no se pierde nada, solo se despacha
con la latencia del polling.

Todo es defensivo: cualquier fallo se reintenta tras `reconnect_delay_s` y nunca
tumba la app.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

_CANAL = "trabajo_nuevo"


def _conninfo_desde_settings() -> str:
    from pos_uniformes.utils.config import settings

    return (
        f"host={settings.db_host} port={settings.db_port} "
        f"dbname={settings.db_name} user={settings.db_user} "
        f"password={settings.db_password}"
    )


class TrabajoNotifyListener(QThread):
    """Emite `notificado` cada vez que llega un NOTIFY 'trabajo_nuevo'."""

    notificado = pyqtSignal()

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
        import psycopg  # driver ya usado por el proyecto (postgresql+psycopg)

        return psycopg.connect(_conninfo_desde_settings(), autocommit=True)

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:  # pragma: no cover — hilo con IO de red real
        while not self._stop:
            conn = None
            try:
                conn = self._connect_fn()
                conn.execute(f"LISTEN {self._canal}")
                for _notify in conn.notifies():
                    if self._stop:
                        break
                    self.notificado.emit()
            except Exception as exc:  # noqa: BLE001 — reconectar, nunca crashear
                logger.warning("Listener de trabajos: %s (reintenta en %ss)", exc, self._reconnect_delay_s)
                if not self._stop:
                    time.sleep(self._reconnect_delay_s)
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:  # noqa: BLE001
                        pass
