"""Cola local de la Libreta para operar sin conexión.

El registro de una venta NUNCA debe bloquear el mostrador ni perderse: cada
operación se anota primero en un JSON local (rápido, siempre disponible) y un
drenado en background la sube a Postgres cuando hay conexión — el mismo
espíritu offline-first del catálogo y los trabajos de impresión.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pos_uniformes.utils.config import satellite_data_dir

_DATA_SUBDIR = "data"
_QUEUE_FILENAME = "libreta_pendiente.json"
_LOCK = threading.Lock()


def _queue_path() -> Path:
    return satellite_data_dir() / _DATA_SUBDIR / _QUEUE_FILENAME


def _load_raw() -> list[dict]:
    path = _queue_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — un archivo corrupto no debe tumbar la venta
        return []
    return payload if isinstance(payload, list) else []


def _save_raw(entries: list[dict]) -> None:
    path = _queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)


def encolar_operacion(entry: dict) -> None:
    """Agrega una operación pendiente (siempre local primero)."""
    with _LOCK:
        entries = _load_raw()
        entries.append(entry)
        _save_raw(entries)


def pendientes() -> list[dict]:
    with _LOCK:
        return _load_raw()


def drenar_pendientes(session) -> int:
    """Sube las operaciones pendientes a la base. Devuelve cuántas subió.

    Si el commit falla, la cola local queda intacta (nada se pierde)."""
    from pos_uniformes.services.libreta_service import registrar_operacion

    with _LOCK:
        entries = _load_raw()
        if not entries:
            return 0
        for entry in entries:
            raw_created = entry.get("created_at")
            try:
                created_at = datetime.fromisoformat(raw_created) if raw_created else None
            except (TypeError, ValueError):
                created_at = None
            registrar_operacion(
                session,
                employee_code=str(entry.get("employee_code", "")),
                employee_name=str(entry.get("employee_name", "")),
                tipo=str(entry.get("tipo", "venta")),
                items=list(entry.get("items", [])),
                monto_total=Decimal(str(entry.get("monto_total", "0"))),
                descuento_empleada=bool(entry.get("descuento_empleada", False)),
                cliente=entry.get("cliente"),
                origen=entry.get("origen"),
                created_at=created_at,
                pago_tarjeta=bool(entry.get("pago_tarjeta", False)),
                monto_neto=(
                    Decimal(str(entry["monto_neto"]))
                    if entry.get("monto_neto") is not None
                    else None
                ),
                comisiones=(
                    int(entry["comisiones"]) if entry.get("comisiones") is not None else None
                ),
            )
        session.commit()
        _save_raw([])
        return len(entries)


# ─── Cola local de CORTES ────────────────────────────────────────────────
# Mismo espíritu que las operaciones: si al confirmar el corte la PC
# principal no responde, la cifra se guarda aquí y se sube sola en el
# siguiente refresh con conexión. Un corte jamás se pierde.

_CORTES_FILENAME = "libreta_cortes_pendientes.json"


def _cortes_path() -> Path:
    return satellite_data_dir() / _DATA_SUBDIR / _CORTES_FILENAME


def _load_cortes() -> list[dict]:
    path = _cortes_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []
    return payload if isinstance(payload, list) else []


def _save_cortes(entries: list[dict]) -> None:
    path = _cortes_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)


def encolar_corte(entry: dict) -> None:
    with _LOCK:
        entries = _load_cortes()
        entries.append(entry)
        _save_cortes(entries)


def cortes_pendientes() -> list[dict]:
    return _load_cortes()


def drenar_cortes(session) -> int:
    """Sube los cortes pendientes a la base (conserva su fecha original)."""
    from datetime import date as _date
    from decimal import Decimal as _Dec

    from pos_uniformes.services.libreta_service import guardar_corte

    with _LOCK:
        entries = _load_cortes()
        if not entries:
            return 0
        subidos = 0
        restantes: list[dict] = []
        for entry in entries:
            try:
                guardar_corte(
                    session,
                    fecha=_date.fromisoformat(entry["fecha"]),
                    monto_final=_Dec(str(entry["monto_final"])),
                    operaciones=int(entry.get("operaciones", 0)),
                    piezas=int(entry.get("piezas", 0)),
                    periodo_label=str(entry.get("periodo_label", "HOY")),
                    nota=str(entry.get("nota", "") or ""),
                    creado_por=str(entry.get("creado_por", "")),
                )
                subidos += 1
            except Exception:  # noqa: BLE001 — el que falle se reintenta luego
                session.rollback()
                restantes.append(entry)
        _save_cortes(restantes)
        return subidos
