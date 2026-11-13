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


# ─── Archivo dañado vs archivo ocupado ───────────────────────────────────
# Antes, CUALQUIER error al leer se trataba como "cola vacía", y la siguiente
# venta reescribía el archivo: las ventas pendientes desaparecían sin aviso
# (auditoría 2026-11-08, VC-01). Ahora hay dos casos distintos:
#
# - contenido ilegible (JSON roto, no es una lista): el archivo se APARTA con
#   otro nombre — nunca se borra ni se sobrescribe —, se avisa en el kiosko y
#   a Daniel por Telegram, y se empieza una cola nueva;
# - el archivo no se puede abrir (Windows o el antivirus lo tienen tomado):
#   NO está dañado. Se reintenta un momento y, si sigue ocupado, el error
#   sube a quien llamó; el archivo queda intacto.

_SUFIJO_RESCATE = ".corrupto-"
_INTENTOS_ARCHIVO_OCUPADO = 3
_ESPERA_ARCHIVO_OCUPADO = 0.2  # segundos entre intentos
# Rescates de este proceso que aún no se avisan por Telegram (hace falta una
# sesión de base para encolar el aviso; se manda en el siguiente drenado).
_RESCATES_POR_AVISAR: list[str] = []
# El último rescate, para que la pantalla de venta lo diga una vez.
_RESCATE_RECIENTE: list[str] = []


def _leer_texto(path: Path) -> str:
    """Lee el archivo; un archivo ocupado se reintenta y luego se propaga."""
    import time

    for intento in range(_INTENTOS_ARCHIVO_OCUPADO):
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise
        except OSError:
            if intento == _INTENTOS_ARCHIVO_OCUPADO - 1:
                raise
            time.sleep(_ESPERA_ARCHIVO_OCUPADO)
    raise AssertionError("inalcanzable")


def _destino_rescate(path: Path) -> Path:
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = f"{path.stem}{_SUFIJO_RESCATE}{marca}"
    destino = path.with_name(f"{base}{path.suffix}")
    n = 1
    while destino.exists():
        destino = path.with_name(f"{base}-{n}{path.suffix}")
        n += 1
    return destino


def _rescatar(path: Path, motivo: str) -> Path:
    """Aparta el archivo ilegible con otro nombre (nunca lo borra). Si no se
    puede apartar, el error sube: la cola no se reescribe encima."""
    destino = _destino_rescate(path)
    path.rename(destino)
    logger.error(
        "Cola offline ilegible (%s): se apartó como %s y se empieza una cola nueva.",
        motivo, destino.name,
    )
    _RESCATES_POR_AVISAR.append(destino.name)
    _RESCATE_RECIENTE.append(destino.name)
    return destino


def _leer_cola(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        texto = _leer_texto(path)  # OSError (archivo ocupado) sube tal cual
    except UnicodeDecodeError as exc:  # bytes que no son UTF-8: dañado, no ocupado
        _rescatar(path, f"no es texto UTF-8: {exc}")
        return []
    try:
        payload = json.loads(texto)
    except ValueError as exc:  # JSON roto o bytes que no son UTF-8
        _rescatar(path, f"JSON inválido: {exc}")
        return []
    if not isinstance(payload, list):
        _rescatar(path, f"se esperaba una lista y vino {type(payload).__name__}")
        return []
    return payload


def archivos_rescatados() -> list[str]:
    """Archivos apartados por ilegibles que siguen en esta terminal. Mientras
    existan, la Libreta lo dice (los quita Daniel cuando los revise)."""
    carpeta = satellite_data_dir() / _DATA_SUBDIR
    if not carpeta.exists():
        return []
    try:
        return sorted(p.name for p in carpeta.glob(f"*{_SUFIJO_RESCATE}*.json"))
    except OSError:
        return []


def tomar_rescate_reciente() -> str | None:
    """El último archivo apartado en este proceso, una sola vez (para avisar
    en la pantalla de venta justo cuando pasa)."""
    with _LOCK:
        if not _RESCATE_RECIENTE:
            return None
        nombre = _RESCATE_RECIENTE[-1]
        _RESCATE_RECIENTE.clear()
        return nombre


def _avisar_rescates(session) -> None:
    """Manda por Telegram (cola de alertas) los rescates aún sin avisar."""
    with _LOCK:
        nombres = list(_RESCATES_POR_AVISAR)
    if not nombres:
        return
    try:
        from pos_uniformes.services.alertas_service import encolar
        from pos_uniformes.services.satellite_identity_service import get_satellite_name

        pc = get_satellite_name()
        for nombre in nombres:
            encolar(session, (
                f"⚠️ En {pc} el archivo de pendientes estaba dañado.\n"
                f"Se apartó como «{nombre}» (no se borró) y se empezó uno nuevo.\n"
                "Las ventas que traía NO han subido: hay que revisarlo a mano."
            ))
        session.commit()
    except Exception:  # noqa: BLE001 — el aviso nunca tumba el vaciado
        logger.exception("Libreta: no se pudo avisar del archivo apartado")
        return
    with _LOCK:
        for nombre in nombres:
            if nombre in _RESCATES_POR_AVISAR:
                _RESCATES_POR_AVISAR.remove(nombre)


def _load_raw() -> list[dict]:
    return _leer_cola(_queue_path())


def _save_raw(entries: list[dict]) -> None:
    """Durable: temporal + fsync + reemplazo atómico (+ fsync de la carpeta
    donde se puede). Un apagón ya no deja la cola vacía o truncada (C1 · H-M2)."""
    from pos_uniformes.utils.archivo_durable import escribir_atomico

    path = _queue_path()
    escribir_atomico(path, json.dumps(entries, ensure_ascii=False), temporal=path.with_suffix(".tmp"))


def encolar_operacion(entry: dict) -> bool:
    """Agrega una operación pendiente (siempre local primero).

    Idempotente por `operacion_uuid`: si esa misma operación ya está en la
    cola (un «Reintentar anotar» tocado dos veces, o un reintento después de
    que la primera parte sí se guardó), no se agrega otra vez. Devuelve True
    si la agregó y False si ya estaba. Si ya había subido a la base, el
    drenado la reconoce por el mismo uuid (`_ya_esta_en_la_base`)."""
    with _LOCK:
        entries = _load_raw()
        uuid = entry.get("operacion_uuid")
        if uuid and any(e.get("operacion_uuid") == uuid for e in entries):
            return False
        entries.append(entry)
        _save_raw(entries)
        return True


def uuids_en_cola() -> set[str]:
    """Los `operacion_uuid` que están HOY en la cola. A diferencia de
    `pendientes()`, si el archivo está ocupado el error SUBE: quien pregunta
    (el respaldo de operaciones sin anotar) necesita distinguir «no está» de
    «no se pudo leer»."""
    with _LOCK:
        return {str(e["operacion_uuid"]) for e in _load_raw() if e.get("operacion_uuid")}


def pendientes() -> list[dict]:
    """Solo lectura (para pintar). Si el archivo está ocupado se muestra vacío
    por esta vez: no se escribe nada, así que no se pierde nada."""
    with _LOCK:
        try:
            return _load_raw()
        except OSError:
            logger.warning("Libreta: el archivo de pendientes está ocupado; se reintenta luego", exc_info=True)
            return []


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

    # Ventas nuevas: identidad persistente, la misma en cada reintento.
    if entry.get("operacion_uuid"):
        return session.scalar(
            select(LibretaVenta.id).where(LibretaVenta.operacion_uuid == str(entry["operacion_uuid"])).limit(1)
        ) is not None
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


def _cliente_id_de(session, entry: dict) -> int | None:
    """El cliente del monedero: id si se resolvió en línea, o el código del
    QR escaneado sin conexión (se resuelve ahora, al subir)."""
    if entry.get("cliente_id") is not None:
        try:
            return int(entry["cliente_id"])
        except (TypeError, ValueError):
            return None
    codigo = str(entry.get("cliente_codigo") or "").strip()
    if not codigo:
        return None
    from pos_uniformes.services.sale_selected_client_service import find_active_sale_client_by_code

    cliente = find_active_sale_client_by_code(session, codigo)
    return cliente.id if cliente is not None else None


def _subir(session, entry: dict):
    from pos_uniformes.services.libreta_service import registrar_operacion

    # El canje nunca viaja por la cola (requiere conexión). Si aparece uno,
    # algo está mal: que falle y avise en vez de subir dinero que no se cobró.
    if Decimal(str(entry.get("monto_monedero", "0") or "0")) > 0:
        raise ValueError("Venta con saldo de monedero en la cola offline: no se sube.")
    return registrar_operacion(
        session,
        employee_code=str(entry.get("employee_code", "")),
        employee_name=str(entry.get("employee_name", "")),
        tipo=str(entry.get("tipo", "venta")),
        items=list(entry.get("items", [])),
        monto_total=Decimal(str(entry.get("monto_total", "0"))),
        descuento_empleada=bool(entry.get("descuento_empleada", False)),
        compradora_code=entry.get("compradora_code") or None,
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
        cliente_id=_cliente_id_de(session, entry),
        operacion_uuid=entry.get("operacion_uuid") or None,
        descuento_programa=entry.get("descuento_programa") or None,
        # M2: la fotografía del motor; el servidor la recalcula al subir.
        calculo=entry.get("calculo") or None,
    )


def registrar_entrada(session, entry: dict):
    """Sube UNA entrada armada para la cola directo a la base, sin commit
    (2026-11-12): la compra a cuenta la guarda junto con su préstamo y su
    retiro (`compra_a_cuenta_service.registrar_venta_a_cuenta`). Es la misma
    subida que hace el drenado; devuelve la LibretaVenta."""
    return _subir(session, entry)


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
        _avisar_rescates(session)
        _conciliar_respaldos(session)
        return 0
    with _LOCK:
        entries = _load_raw()
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
    _avisar_rescates(session)
    _conciliar_respaldos(session)
    return subidas


def _conciliar_respaldos(session) -> None:
    """Borra los respaldos de operaciones cobradas-sin-anotar cuyas entradas
    YA están en PostgreSQL (C1 · H-M2). Nunca tumba el drenado."""
    try:
        from pos_uniformes.services import libreta_sin_anotar_service as sin_anotar

        sin_anotar.conciliar_con_base(session)
    except Exception:  # noqa: BLE001
        logger.exception("Libreta: no se pudieron conciliar los respaldos sin anotar")
        try:
            session.rollback()
        except Exception:  # noqa: BLE001
            pass


def cashback_pendiente() -> Decimal:
    """Cashback estimado de ventas con cliente que aún no suben: se muestra
    como "pendiente de sincronizar", nunca como saldo usable."""
    total = Decimal("0.00")
    for e in pendientes():
        try:
            total += Decimal(str(e.get("cashback_estimado") or "0"))
        except Exception:  # noqa: BLE001
            continue
    return total.quantize(Decimal("0.01"))


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
    # Misma regla que las ventas: ilegible se aparta, ocupado se propaga.
    return _leer_cola(_cortes_path())


def _save_cortes(entries: list[dict]) -> None:
    from pos_uniformes.utils.archivo_durable import escribir_atomico

    path = _cortes_path()
    escribir_atomico(path, json.dumps(entries, ensure_ascii=False), temporal=path.with_suffix(".tmp"))


def encolar_corte(entry: dict) -> None:
    with _LOCK:
        entries = _load_cortes()
        entries.append(entry)
        _save_cortes(entries)


def cortes_pendientes() -> list[dict]:
    with _LOCK:
        try:
            return _load_cortes()
        except OSError:
            logger.warning("Libreta: el archivo de cortes pendientes está ocupado", exc_info=True)
            return []


def drenar_cortes(session) -> int:
    """Sube los cortes pendientes a la base (conserva su fecha original)."""
    from datetime import date as _date
    from decimal import Decimal as _Dec

    from pos_uniformes.services.libreta_service import guardar_corte

    subidos = 0
    with _LOCK:
        entries = _load_cortes()
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
        if entries:
            _save_cortes(restantes)
    _avisar_rescates(session)
    return subidos
