"""Cola local de la Libreta para operar sin conexión.

El registro de una venta NUNCA debe bloquear el mostrador ni perderse: cada
operación se anota primero en un JSON local (rápido, siempre disponible) y un
drenado en background la sube a Postgres cuando hay conexión — el mismo
espíritu offline-first del catálogo y los trabajos de impresión.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pos_uniformes.utils.config import satellite_data_dir

logger = logging.getLogger(__name__)

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


#: Intentos fallidos de UNA venta antes de avisarle a Daniel. No se borra ni
#: se aparta: se sigue intentando, pero ya no en silencio.
INTENTOS_PARA_AVISAR = 5


def _es_de_red(exc: BaseException) -> bool:
    """La base no contesta: no es culpa de la venta, es de la conexión."""
    from sqlalchemy import exc as sa_exc

    return isinstance(exc, (sa_exc.OperationalError, sa_exc.InterfaceError, sa_exc.DisconnectionError))


def _fecha(entry: dict):
    raw = entry.get("created_at")
    try:
        return datetime.fromisoformat(raw) if raw else None
    except (TypeError, ValueError):
        return None


def _ya_esta_en_la_base(session, entry: dict) -> bool:
    """¿Esta venta ya subió en un intento anterior?

    Pasa si la base guardó pero el kiosko no alcanzó a borrarla de su cola
    (se fue la red justo después). Sin esto se subiría dos veces. Se reconoce
    por terminal, hora exacta (con microsegundos), empleada y monto."""
    from sqlalchemy import select

    from pos_uniformes.database.models import LibretaVenta

    creada = _fecha(entry)
    if creada is None or not entry.get("origen"):
        return False
    return session.scalar(
        select(LibretaVenta.id).where(
            LibretaVenta.origen == entry.get("origen"),
            LibretaVenta.created_at == creada,
            LibretaVenta.employee_code == str(entry.get("employee_code", "")).upper(),
            LibretaVenta.monto_total == Decimal(str(entry.get("monto_total", "0"))).quantize(Decimal("0.01")),
        ).limit(1)
    ) is not None


def _subir(session, entry: dict) -> None:
    from pos_uniformes.services.libreta_service import registrar_operacion

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
        created_at=_fecha(entry),
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


def drenar_pendientes(session) -> int:
    """Sube las operaciones pendientes a la base. Devuelve cuántas subieron.

    Cada venta va en su propio tramo (savepoint). Antes subían todas juntas o
    ninguna: una sola venta que la base rechazara atoraba para siempre a todas
    las de atrás, y el error se tragaba en silencio (2026-10-15: Entrada pasó
    un día sin subir nada y el único rastro fueron 32 números de venta
    brincados). Ahora:

    - la que falla se queda en la cola con su intento anotado, y las demás
      suben;
    - si lo que falla es la RED, se suspende la vuelta entera sin anotar nada:
      no es culpa de ninguna venta;
    - al quinto intento fallido de una misma venta se le avisa a Daniel;
    - nunca se borra una venta que no subió.

    Si el commit final falla, la cola queda intacta (nada se pierde)."""
    with _LOCK:
        entries = _load_raw()
        if not entries:
            return 0
        subidas = 0
        restantes: list[dict] = []
        por_avisar: list[dict] = []
        for entry in entries:
            try:
                with session.begin_nested():
                    if not _ya_esta_en_la_base(session, entry):
                        _subir(session, entry)
                subidas += 1
            except Exception as exc:  # noqa: BLE001
                if _es_de_red(exc):
                    raise                     # cola intacta; se reintenta luego
                logger.warning("Libreta: no subió la venta de %s (%s): %s",
                               entry.get("employee_code"), entry.get("created_at"), exc)
                fallida = dict(entry)
                fallida["intentos"] = int(entry.get("intentos", 0) or 0) + 1
                fallida["ultimo_error"] = str(exc)[:300]
                if fallida["intentos"] >= INTENTOS_PARA_AVISAR and not entry.get("avisado"):
                    fallida["avisado"] = True
                    por_avisar.append(fallida)
                restantes.append(fallida)
        session.commit()
        _save_raw(restantes)
    if por_avisar:
        _avisar_a_daniel(session, por_avisar)
    return subidas


def atoradas() -> list[dict]:
    """Las que ya fallaron varias veces: para decirlo en la pantalla."""
    return [e for e in pendientes() if int(e.get("intentos", 0) or 0) >= INTENTOS_PARA_AVISAR]


def _avisar_a_daniel(session, ventas: list[dict]) -> None:
    """Por Telegram (la cola de alertas): una venta que no sube no se calla."""
    try:
        from pos_uniformes.services.alertas_service import encolar
        from pos_uniformes.services.satellite_identity_service import get_satellite_name

        pc = get_satellite_name()
        for v in ventas:
            encolar(session, (
                f"⚠️ Una venta de {pc} no se ha podido subir a la base "
                f"({v.get('intentos')} intentos).\n"
                f"{v.get('employee_code')} · ${v.get('monto_total')} · {v.get('created_at')}\n"
                f"Error: {v.get('ultimo_error')}\n\n"
                "Sigue guardada en esa terminal y se sigue intentando."
            ))
        session.commit()
    except Exception:  # noqa: BLE001 — el aviso nunca tumba el vaciado
        logger.exception("Libreta: no se pudo avisar de la venta atorada")


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
