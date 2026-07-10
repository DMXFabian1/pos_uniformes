"""Excepthook global del satelite: loguear en vez de morir.

PyQt6 aborta el proceso (qFatal) cuando una excepcion de Python escapa de un
slot y llega al excepthook por defecto. En un kiosko eso significa que un
RuntimeError perdido (p.ej. un QTimer que toca un widget ya destruido) cierra
el programa frente a la clienta. Con un excepthook propio instalado la
excepcion se escribe a stderr y a satellite_errors.log, y la app sigue viva.
"""

from __future__ import annotations

import sys
import traceback
from datetime import datetime
from pathlib import Path
from types import TracebackType

from pos_uniformes.utils.config import satellite_data_dir

_LOG_FILENAME = "satellite_errors.log"
_MAX_LOG_BYTES = 512 * 1024  # al superar esto el log se reinicia


def _log_path() -> Path:
    return satellite_data_dir() / "data" / _LOG_FILENAME


def format_unhandled_exception(
    exc_type: type[BaseException],
    exc: BaseException,
    tb: TracebackType | None,
    *,
    now: datetime | None = None,
) -> str:
    stamp = (now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    detail = "".join(traceback.format_exception(exc_type, exc, tb)).rstrip()
    return f"[{stamp}] Excepcion no manejada:\n{detail}\n\n"


def append_to_error_log(entry: str, path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > _MAX_LOG_BYTES:
            path.unlink()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(entry)
    except Exception:  # noqa: BLE001 — el log nunca debe tumbar al hook
        pass


def install_gui_excepthook(log_path: Path) -> None:
    """Reemplaza sys.excepthook (y threading.excepthook) para que ni una
    excepción en un slot ni en un hilo de fondo tumben el proceso.

    Sirve para cualquier app Qt del proyecto (satélite y POS principal);
    cada una pasa su propia ruta de log.
    """

    def hook(
        exc_type: type[BaseException],
        exc: BaseException,
        tb: TracebackType | None,
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        entry = format_unhandled_exception(exc_type, exc, tb)
        print(entry, end="", file=sys.stderr)
        append_to_error_log(entry, log_path)

    sys.excepthook = hook

    # Los hilos de fondo (reindex de Meilisearch, watchdog de reconexión)
    # tocan la DB; si la PC principal se apaga, su excepción no debe quedar
    # sin registrar. threading.excepthook nunca cierra el proceso, solo
    # queremos que el error vaya al mismo log.
    import threading

    def thread_hook(args: "threading.ExceptHookArgs") -> None:
        if issubclass(args.exc_type, SystemExit):
            return
        entry = format_unhandled_exception(
            args.exc_type, args.exc_value, args.exc_traceback
        )
        print(entry, end="", file=sys.stderr)
        append_to_error_log(entry, log_path)

    threading.excepthook = thread_hook


def install_satellite_excepthook() -> None:
    install_gui_excepthook(_log_path())
