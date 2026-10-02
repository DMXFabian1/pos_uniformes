"""Propuesta de corte: primero te pregunto, luego imprimo.

A la hora del corte (30 min antes de cerrar) el sistema ya no cierra la caja
solo: manda a Telegram lo que hay y espera a que Daniel conteste `/corte`.
Si no contesta, se lo recuerda UNA vez.

Y si después de cerrar sigue sin contestar, **el corte se hace solo** con la
cifra real y se le dice (2026-10-01, antes de un viaje de una semana). Antes la
caja se quedaba sin corte y la alerta de "cierre sin corte" avisaba — pero
avisar desde lejos no hace el corte: el cajón se acumulaba sin registro y al
volver no se sabía de qué día era cada peso. Un corte automático que él puede
ajustar después es mejor que un día sin corte, porque el ajuste deja rastro y
el hueco no.

`/nocorte` se sigue respetando: si dijo que hoy no, no se hace.

El estado vive en un JSON local de la PC servidor: no hace falta tabla nueva
porque la propuesta solo importa el día que se hace.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


def ruta_estado() -> Path:
    from pos_uniformes.utils.config import runtime_base_dir

    return runtime_base_dir() / "data" / "corte_propuesto.json"


@dataclass(frozen=True)
class Propuesta:
    fecha: date | None = None
    momento: datetime | None = None
    recordado: bool = False
    cancelado: bool = False

    @property
    def hay(self) -> bool:
        return self.fecha is not None


def leer() -> Propuesta:
    try:
        datos = json.loads(ruta_estado().read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — sin archivo o ilegible: no hay propuesta
        return Propuesta()
    try:
        return Propuesta(
            fecha=date.fromisoformat(datos["fecha"]),
            momento=datetime.fromisoformat(datos["momento"]) if datos.get("momento") else None,
            recordado=bool(datos.get("recordado")),
            cancelado=bool(datos.get("cancelado")),
        )
    except Exception:  # noqa: BLE001
        return Propuesta()


def _guardar(p: Propuesta) -> None:
    ruta = ruta_estado()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(
        json.dumps({
            "fecha": p.fecha.isoformat() if p.fecha else None,
            "momento": p.momento.isoformat() if p.momento else None,
            "recordado": p.recordado,
            "cancelado": p.cancelado,
        }),
        encoding="utf-8",
    )


def anotar_propuesta(momento: datetime) -> Propuesta:
    p = Propuesta(fecha=momento.date(), momento=momento, recordado=False, cancelado=False)
    _guardar(p)
    return p


def anotar_recordatorio() -> None:
    p = leer()
    if p.hay:
        _guardar(Propuesta(p.fecha, p.momento, True, p.cancelado))


def cancelar(hoy: date | None = None) -> bool:
    """Daniel contestó /nocorte. Devuelve si había algo que cancelar."""
    p = leer()
    if not p.hay or p.fecha != (hoy or date.today()):
        return False
    _guardar(Propuesta(p.fecha, p.momento, p.recordado, True))
    return True


#: Cuánto se espera después de cerrar antes de hacer el corte sin él. Da tiempo
#: a que conteste tras el recordatorio y a que termine la última venta.
MINUTOS_DESPUES_DE_CERRAR = 45


def toca_cerrar_solo(
    p: Propuesta,
    *,
    hoy: date,
    minutos_tras_cierre: float,
    hubo_corte_despues: bool,
    hubo_movimiento: bool,
) -> bool:
    """¿Hacer el corte sin que haya contestado? (puro, sin reloj ni DB)

    Pide que todo el camino normal haya pasado primero: que hoy se haya
    propuesto, que ya se le recordara, que no haya dicho `/nocorte`, que no
    exista ya un corte, que haya habido movimiento, y que el cierre haya pasado
    hace rato. Si falta cualquiera, no se toca nada.
    """
    if not p.hay or p.fecha != hoy:
        return False          # hoy no se propuso: no es el camino normal
    if p.cancelado:
        return False          # dijo /nocorte
    if not p.recordado:
        return False          # todavía no se le ha insistido
    if hubo_corte_despues:
        return False          # ya hay corte
    if not hubo_movimiento:
        return False          # día sin ventas: nada que cortar
    return minutos_tras_cierre >= MINUTOS_DESPUES_DE_CERRAR


def toca_recordar(p: Propuesta, *, hoy: date, hubo_corte_despues: bool) -> bool:
    """¿Reenviar la propuesta? Una sola vez, y solo si sigue viva (puro)."""
    if not p.hay or p.fecha != hoy:
        return False
    if p.cancelado or p.recordado or hubo_corte_despues:
        return False
    return True
