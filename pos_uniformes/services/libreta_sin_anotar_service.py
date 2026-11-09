"""Operaciones YA cobradas que no se pudieron anotar (A2/A3 · C1, 2026-11-08).

Cuando falla escribir la cola de la Libreta (`libreta_local_queue_service`),
el cliente ya pagó. Antes la foto de la operación solo vivía en memoria: si el
kiosko se cerraba o se reiniciaba antes de «Reintentar anotar», la venta se
perdía sin rastro. Aquí se guarda en disco, APARTE de la cola (no depende del
archivo que está fallando):

    <datos del satélite>/data/sin_anotar/<operacion_uuid>.json

Un archivo por operación cobrada. `entradas` es la foto completa (venta, o
apartado + anticipo) y NUNCA cambia. Cada entrada pasa por tres estados:

    falta anotar  →  en la cola local  →  confirmada en PostgreSQL

- `en_cola`: uuids que entraron a la cola local (bitácora; lo que manda es la
  cola real, ver `cargar`);
- `en_base`: uuids que el drenado encontró en `libreta_venta`.

**El archivo se borra SOLO cuando todas sus entradas están en PostgreSQL**
(`conciliar_con_base`, que corre al final de cada drenado). Mientras tanto
es la última copia durable aunque la cola se dañe o se vacíe (H-M2).

Lo que «falta anotar» se calcula contra la cola REAL al arrancar: si una
entrada que la bitácora daba por encolada ya no está en la cola ni en la base
(la cola se perdió), vuelve a quedar pendiente. Reencolarla no duplica: la
cola deduplica por uuid y el drenado revisa la base por uuid antes de subir.

Reglas:
- escritura atómica y durable (temporal + fsync + `os.replace`);
- nunca se sobrescribe un pendiente con OTRA foto (`PendienteEnConflicto`);
- `en_cola` y `en_base` solo crecen;
- un archivo ilegible no tumba el arranque: se reporta para revisión manual y
  se deja tal cual (nunca se borra ni se mueve).

No hay contraseñas, PIN ni tokens: solo lo que ya lleva la cola.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

logger = logging.getLogger(__name__)

VERSION = 1
_SUBDIR = "sin_anotar"
_LOCK = threading.Lock()
_UUID_RE = re.compile(r"^[0-9a-fA-F-]{8,64}$")


class PendienteEnConflicto(RuntimeError):
    """Ya hay un pendiente con ese uuid y OTRA foto: no se sobrescribe."""


@dataclass
class OperacionPendiente:
    operacion_uuid: str
    entradas: list[dict]
    en_cola: list[str] = field(default_factory=list)
    en_base: list[str] = field(default_factory=list)
    guardado_at: str = ""
    archivo: Path | None = None
    # Lo que de verdad está hoy en la cola (None = no se pudo leer: se usa
    # la bitácora `en_cola`).
    cola_real: set[str] | None = None

    def _encoladas(self) -> set[str]:
        return set(self.cola_real) if self.cola_real is not None else set(self.en_cola)

    @property
    def faltantes(self) -> list[dict]:
        """Entradas que no están ni en la cola ni en la base: hay que anotarlas."""
        listas = self._encoladas() | set(self.en_base)
        return [e for e in self.entradas if e.get("operacion_uuid") not in listas]

    @property
    def en_espera(self) -> list[dict]:
        """Ya en la cola, esperando que PostgreSQL las confirme."""
        base = set(self.en_base)
        encoladas = self._encoladas()
        return [e for e in self.entradas if e["operacion_uuid"] in encoladas and e["operacion_uuid"] not in base]

    @property
    def completa(self) -> bool:
        return {e["operacion_uuid"] for e in self.entradas} <= set(self.en_base)


def carpeta() -> Path:
    """Misma carpeta de datos que la cola (`satellite_data_dir()/data`).

    Se resuelve a través del módulo de la cola para que haya UNA sola fuente
    de verdad del directorio de datos del kiosko empaquetado."""
    from pos_uniformes.services import libreta_local_queue_service as cola

    return cola._queue_path().parent / _SUBDIR


def _ruta(operacion_uuid: str) -> Path:
    if not _UUID_RE.match(str(operacion_uuid or "")):
        raise ValueError(f"uuid de operación inválido: {operacion_uuid!r}")
    return carpeta() / f"{operacion_uuid}.json"


def uuid_de_operacion(entradas: list[dict]) -> str | None:
    """La operación se identifica con el uuid de su primera entrada."""
    if not entradas:
        return None
    uuid = entradas[0].get("operacion_uuid")
    return str(uuid) if uuid else None


# ── validación ───────────────────────────────────────────────────────────


def _validar_entrada(e: object) -> str | None:
    if not isinstance(e, dict):
        return "una entrada no es un objeto"
    if not e.get("operacion_uuid") or not _UUID_RE.match(str(e["operacion_uuid"])):
        return "una entrada no tiene operacion_uuid válido"
    if not str(e.get("tipo") or "").strip():
        return "una entrada no tiene tipo"
    if not str(e.get("employee_code") or "").strip():
        return "una entrada no tiene empleada"
    try:
        Decimal(str(e.get("monto_total")))
    except (InvalidOperation, ValueError, TypeError):
        return "una entrada no tiene monto_total válido"
    try:
        datetime.fromisoformat(str(e.get("created_at")))
    except (TypeError, ValueError):
        return "una entrada no tiene created_at válido"
    return None


def _lista_de_uuids(payload: dict, clave: str) -> list[str] | None:
    valor = payload.get(clave, [])
    if not isinstance(valor, list):
        return None
    return [str(u) for u in valor]


def validar(payload: object) -> str | None:
    """None si es un pendiente válido; si no, el motivo."""
    if not isinstance(payload, dict):
        return "no es un objeto JSON"
    if payload.get("version") != VERSION:
        return f"versión desconocida: {payload.get('version')!r}"
    entradas = payload.get("entradas")
    if not isinstance(entradas, list) or not entradas:
        return "no trae entradas"
    for e in entradas:
        motivo = _validar_entrada(e)
        if motivo:
            return motivo
    uuids = [str(e["operacion_uuid"]) for e in entradas]
    if len(set(uuids)) != len(uuids):
        return "uuid repetido entre entradas"
    if str(payload.get("operacion_uuid")) != uuids[0]:
        return "el uuid de la operación no coincide con su primera entrada"
    for clave in ("en_cola", "en_base"):
        lista = _lista_de_uuids(payload, clave)
        if lista is None or not set(lista) <= set(uuids):
            return f"{clave} no corresponde a las entradas"
    return None


# ── escritura ────────────────────────────────────────────────────────────


def _escribir_atomico(path: Path, payload: dict) -> None:
    from pos_uniformes.utils.archivo_durable import escribir_atomico

    escribir_atomico(path, json.dumps(payload, ensure_ascii=False, indent=1))


def _leer(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def guardar(entradas: list[dict], *, confirmadas: list[str] | None = None) -> Path:
    """Guarda la foto de una operación cobrada que falta anotar.

    `confirmadas`: uuids de las entradas que SÍ entraron a la cola local antes
    del error. Si ya existe el archivo con la MISMA foto, solo las suma. Si
    existe con otra foto, no lo toca y lanza `PendienteEnConflicto`. Cualquier
    error de disco sube a quien llamó (que debe pedir anotarla en papel)."""
    # Normalizada como quedaría en disco, para comparar fotos sin sorpresas.
    entradas = json.loads(json.dumps(entradas, ensure_ascii=False, default=str))
    uuid = uuid_de_operacion(entradas)
    if not uuid:
        raise ValueError("la operación no tiene operacion_uuid")
    path = _ruta(uuid)
    en_cola = [str(u) for u in (confirmadas or [])]
    en_base: list[str] = []
    with _LOCK:
        if path.exists():
            existente = _leer(path)
            if validar(existente) is not None or existente.get("entradas") != entradas:
                raise PendienteEnConflicto(f"{path.name} ya existe con otra información")
            en_cola = sorted(set(existente.get("en_cola", [])) | set(en_cola))
            en_base = sorted(set(existente.get("en_base", [])))
            guardado_at = existente.get("guardado_at") or datetime.now().astimezone().isoformat()
        else:
            guardado_at = datetime.now().astimezone().isoformat()
        payload = {
            "version": VERSION,
            "operacion_uuid": uuid,
            "guardado_at": guardado_at,
            "entradas": entradas,
            "en_cola": sorted(set(en_cola)),
            "en_base": en_base,
        }
        motivo = validar(payload)
        if motivo:
            raise ValueError(f"pendiente inválido: {motivo}")
        _escribir_atomico(path, payload)
    return path


def _sumar(path: Path, clave: str, uuids: set[str]) -> dict | None:
    """Agrega uuids a `clave` (bajo _LOCK). Devuelve el contenido nuevo, o
    None si el archivo ya no existe. Un archivo ilegible NO se toca."""
    if not path.exists():
        return None
    actual = _leer(path)
    motivo = validar(actual)
    if motivo:
        raise PendienteEnConflicto(f"{path.name} ilegible: {motivo}")
    todas = {str(e["operacion_uuid"]) for e in actual["entradas"]}
    nuevos = (set(actual.get(clave, [])) | set(uuids)) & todas
    if nuevos != set(actual.get(clave, [])):
        actual[clave] = sorted(nuevos)
        _escribir_atomico(path, actual)
    return actual


def marcar_en_cola(operacion_uuid: str, uuids: list[str]) -> None:
    """Anota en la bitácora que estas entradas ya entraron a la cola local.
    NUNCA borra el archivo: eso solo pasa cuando PostgreSQL las confirma.

    Si falla (disco), no pasa nada grave: al arrancar, lo pendiente se
    calcula contra la cola real."""
    path = _ruta(operacion_uuid)
    with _LOCK:
        _sumar(path, "en_cola", {str(u) for u in uuids})


# ── conciliación con PostgreSQL ──────────────────────────────────────────


def conciliar_con_base(session) -> list[str]:
    """Para cada respaldo, pregunta a PostgreSQL qué entradas ya están en
    `libreta_venta` (por `operacion_uuid`). Lo anota en `en_base` y BORRA el
    archivo solo si están TODAS. Devuelve las operaciones borradas.

    Corre al final de cada drenado (después del commit). Si borrar falla, el
    archivo queda con `en_base` completo: no se muestra como pendiente y el
    siguiente drenado lo vuelve a intentar. Reencolar algo que ya está en la
    base no duplica (el drenado lo reconoce por uuid)."""
    ops, _revisar = cargar()
    if not ops:
        return []
    from sqlalchemy import select

    from pos_uniformes.database.models import LibretaVenta

    todos = sorted({e["operacion_uuid"] for op in ops for e in op.entradas})
    en_base = {
        str(u)
        for u in session.scalars(
            select(LibretaVenta.operacion_uuid).where(LibretaVenta.operacion_uuid.in_(todos))
        )
    }
    borradas: list[str] = []
    for op in ops:
        suyas = {e["operacion_uuid"] for e in op.entradas}
        confirmadas = suyas & en_base
        if not confirmadas - set(op.en_base) and not (suyas <= set(op.en_base)):
            continue  # nada nuevo que anotar
        path = op.archivo or _ruta(op.operacion_uuid)
        with _LOCK:
            try:
                actual = _sumar(path, "en_base", confirmadas)
            except Exception:  # noqa: BLE001 — ilegible o tomado: se deja como está
                logger.exception("Sin anotar: no se pudo anotar la confirmación de %s", path.name)
                continue
            if actual is None:
                continue
            if suyas <= set(actual.get("en_base", [])):
                try:
                    path.unlink()
                except OSError:
                    logger.exception(
                        "Sin anotar: %s ya está completo en la base pero no se pudo borrar; "
                        "se reintenta en el siguiente drenado", path.name,
                    )
                    continue
                borradas.append(op.operacion_uuid)
                logger.warning(
                    "Sin anotar: operación %s confirmada en PostgreSQL; respaldo borrado",
                    op.operacion_uuid,
                )
    return borradas


# ── lectura ──────────────────────────────────────────────────────────────


def cargar(cola_real: set[str] | None = None) -> tuple[list[OperacionPendiente], list[str]]:
    """(respaldos válidos, nombres de archivos que requieren revisión).

    `cola_real`: uuids que están hoy en la cola local (None = no se sabe; se
    usa la bitácora `en_cola`). Nunca lanza ni borra nada: un archivo dañado o
    tomado se reporta y se deja intacto."""
    base = carpeta()
    validos: list[OperacionPendiente] = []
    revisar: list[str] = []
    if not base.exists():
        return validos, revisar
    try:
        archivos = sorted(p for p in base.glob("*.json") if not p.name.startswith("."))
    except OSError:
        logger.exception("Sin anotar: no se pudo listar %s", base)
        return validos, [base.name]
    for path in archivos:
        try:
            with _LOCK:
                payload = _leer(path)
        except (OSError, ValueError) as exc:
            logger.error("Sin anotar: %s no se pudo leer (%s); requiere revisión manual", path.name, exc)
            revisar.append(path.name)
            continue
        motivo = validar(payload)
        if motivo is None and path.stem != str(payload.get("operacion_uuid")):
            motivo = "el nombre del archivo no coincide con su uuid"
        if motivo:
            logger.error("Sin anotar: %s inválido (%s); requiere revisión manual", path.name, motivo)
            revisar.append(path.name)
            continue
        validos.append(OperacionPendiente(
            operacion_uuid=str(payload["operacion_uuid"]),
            entradas=payload["entradas"],
            en_cola=[str(u) for u in payload.get("en_cola", [])],
            en_base=[str(u) for u in payload.get("en_base", [])],
            guardado_at=str(payload.get("guardado_at") or ""),
            archivo=path,
            cola_real=set(cola_real) if cola_real is not None else None,
        ))
    return validos, revisar


def resumen_para_log(entradas: list[dict]) -> str:
    """Contexto técnico sin datos personales (sin cliente ni teléfono)."""
    partes = []
    for e in entradas:
        piezas = sum(int(it.get("cantidad", 0) or 0) for it in e.get("items") or [])
        partes.append(
            f"{e.get('tipo')} uuid={e.get('operacion_uuid')} empleada={e.get('employee_code')} "
            f"total={e.get('monto_total')} neto={e.get('monto_neto')} piezas={piezas} "
            f"tarjeta={bool(e.get('pago_tarjeta'))} desc_empleada={bool(e.get('descuento_empleada'))} "
            f"origen={e.get('origen')} created_at={e.get('created_at')}"
        )
    return " | ".join(partes)
