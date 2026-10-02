"""Cola local de acuses: «Enterada» no se pierde porque se cayó la PC.

Cuando alguien toca «Enterada» y la PC principal no contesta, el acuse se
quedaba en la memoria del kiosko y se iba con el primer reinicio: el aviso le
volvía a salir a quien ya lo había leído, y a Daniel nunca le llegaba el
mensaje de quién lo vio. Aquí se guarda hasta que haya conexión.

Mismo espíritu que la cola de la Libreta: local primero, se sube sola después.
La diferencia es que un acuse viejo **sigue valiendo** — lo que cuenta es que
esa persona lo leyó, y eso ya pasó aunque se suba tres horas más tarde. Por eso
se conserva la hora del toque y no la de la subida.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from pos_uniformes.utils.config import satellite_data_dir

_DATA_SUBDIR = "data"
_QUEUE_FILENAME = "acuses_pendientes.json"
_LOCK = threading.Lock()

#: Tope defensivo: si la PC principal lleva semanas caída, no vale la pena
#: guardar miles de toques. Los avisos vencen solos de todos modos.
MAX_PENDIENTES = 200


def _queue_path() -> Path:
    return satellite_data_dir() / _DATA_SUBDIR / _QUEUE_FILENAME


def _load_raw() -> list[dict]:
    path = _queue_path()
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — un archivo corrupto no tumba la venta
        return []
    return payload if isinstance(payload, list) else []


def _save_raw(entries: list[dict]) -> None:
    path = _queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def encolar(
    anuncio_id: int,
    *,
    satelite: str = "",
    satelite_nombre: str | None = None,
    empleada: str | None = None,
    etiqueta: str = "",
) -> None:
    """Guarda un acuse que no se pudo escribir en la base.

    Idempotente por anuncio: tocar dos veces no encola dos veces, igual que en
    la base. Lo que vale es la primera vez.
    """
    with _LOCK:
        entries = _load_raw()
        if any(int(e.get("anuncio_id", 0)) == int(anuncio_id) for e in entries):
            return
        entries.append(
            {
                "anuncio_id": int(anuncio_id),
                "satelite": str(satelite or ""),
                "satelite_nombre": satelite_nombre,
                "empleada": empleada,
                "etiqueta": etiqueta,
                "visto_en": datetime.now(timezone.utc).isoformat(),
            }
        )
        _save_raw(entries[-MAX_PENDIENTES:])


def ids_pendientes() -> set[int]:
    """Los anuncios acusados aquí que todavía no llegan a la base.

    La cartelera los lee al arrancar: así, aunque el kiosko se reinicie con la
    PC todavía apagada, el recado no le vuelve a salir a quien ya lo leyó.
    """
    with _LOCK:
        return {int(e["anuncio_id"]) for e in _load_raw() if e.get("anuncio_id")}


def pendientes() -> list[dict]:
    with _LOCK:
        return _load_raw()


def drenar(session) -> list[dict]:
    """Sube los acuses pendientes. Devuelve los que subió, para avisarlos.

    Si algo falla, la cola queda intacta: un acuse no escrito se vuelve a
    intentar, y uno escrito dos veces no hace daño (`marcar_visto` es
    idempotente por pantalla).
    """
    from pos_uniformes.services import anuncio_service as asvc

    with _LOCK:
        entries = _load_raw()
        if not entries:
            return []
        subidos: list[dict] = []
        for e in entries:
            try:
                visto = asvc.marcar_visto(
                    session,
                    int(e["anuncio_id"]),
                    satelite=str(e.get("satelite") or ""),
                    satelite_nombre=e.get("satelite_nombre"),
                    empleada=e.get("empleada"),
                )
            except Exception:  # noqa: BLE001 — se reintenta en la siguiente vuelta
                return []
            if visto is None:
                # El anuncio ya no existe: el acuse no tiene a qué pegarse y no
                # hay nada que reintentar. Se da por despachado sin avisar.
                continue
            cerrado, faltan = asvc.cerrar_si_ya_lo_vieron(session, int(e["anuncio_id"]))
            subidos.append({**e, "cerrado": cerrado, "faltan": faltan})
        session.commit()
        _save_raw([])
        return subidos


def limpiar() -> None:
    """Vacía la cola. Para pruebas y para el menú admin."""
    with _LOCK:
        _save_raw([])
