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
    #: El mensaje de Telegram de la propuesta (o del recordatorio, que la
    #: reemplaza): el corte de la tarde vive en UN mensaje (2026-11-20).
    message_id: int = 0

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
            message_id=int(datos.get("message_id") or 0),
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
            "message_id": int(p.message_id or 0),
        }),
        encoding="utf-8",
    )


def cancelada_hoy(hoy: date | None = None) -> bool:
    """¿Daniel ya dijo /nocorte para hoy (antes o después de la propuesta)?"""
    p = leer()
    return p.hay and p.fecha == (hoy or date.today()) and p.cancelado


def anotar_propuesta(momento: datetime, message_id: int = 0) -> Propuesta:
    """Hoy se propuso el corte. Si Daniel ya había dicho /nocorte para hoy,
    el «no» se respeta: queda anotada pero cancelada."""
    p = Propuesta(fecha=momento.date(), momento=momento, recordado=False,
                  cancelado=cancelada_hoy(momento.date()), message_id=int(message_id or 0))
    _guardar(p)
    return p


def anotar_recordatorio(message_id: int = 0) -> None:
    """Ya se recordó. `message_id`: el recordatorio reemplaza a la propuesta."""
    p = leer()
    if p.hay:
        _guardar(Propuesta(p.fecha, p.momento, True, p.cancelado,
                           int(message_id or 0) or p.message_id))


def mensaje_de_hoy(hoy: date | None = None) -> int:
    """El id del mensaje de la propuesta de hoy (0 si no hay)."""
    p = leer()
    return p.message_id if p.hay and p.fecha == (hoy or date.today()) else 0


def retirar_mensaje(hoy: date | None = None, *, salvo: int = 0) -> bool:
    """El corte ya se hizo por otro lado: la propuesta (con sus botones) se
    quita del chat para que quede un solo mensaje del corte. `salvo`: el
    mensaje que se está reescribiendo con el resultado no se borra."""
    mid = mensaje_de_hoy(hoy)
    if not mid or mid == int(salvo or 0):
        return False
    try:
        from pos_uniformes.services import telegram_service

        motivo = telegram_service.borrar_con_motivo(mid)
    except Exception:  # noqa: BLE001 — sin credenciales o sin red: se queda para el barrido
        return False
    if motivo != "red":
        p = leer()
        _guardar(Propuesta(p.fecha, p.momento, p.recordado, p.cancelado, 0))
    return motivo == "ok"


def cancelar(hoy: date | None = None) -> bool:
    """Daniel contestó /nocorte. Vale para hoy aunque la propuesta no haya
    llegado todavía: antes contestaba «no hay nada que cancelar» y el cierre
    automático de las 18:50 seguía en pie (2026-10-10). Devuelve True si
    había una propuesta de hoy; False si se anotó por adelantado."""
    hoy = hoy or date.today()
    p = leer()
    if p.hay and p.fecha == hoy:
        _guardar(Propuesta(p.fecha, p.momento, p.recordado, True, p.message_id))
        return True
    _guardar(Propuesta(fecha=hoy, momento=None, recordado=False, cancelado=True))
    return False


#: Cuánto se espera después de cerrar antes de hacer el corte sin él. Da tiempo
#: a que conteste tras el recordatorio y a que termine la última venta.
MINUTOS_DESPUES_DE_CERRAR = 45
#: Si el recordatorio no corrió (Windows se saltó la tarea), se espera esto
#: de más y se cierra igual: el último eslabón existe justo para cuando los
#: demás fallan, y antes se quedaba callado (2026-10-10).
MINUTOS_EXTRA_SIN_RECORDATORIO = 20


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
    if hubo_corte_despues:
        return False          # ya hay corte
    if not hubo_movimiento:
        return False          # día sin ventas: nada que cortar
    espera = MINUTOS_DESPUES_DE_CERRAR
    if not p.recordado:
        espera += MINUTOS_EXTRA_SIN_RECORDATORIO   # no se le insistió: un rato más
    return minutos_tras_cierre >= espera


def toca_recordar(p: Propuesta, *, hoy: date, hubo_corte_despues: bool) -> bool:
    """¿Reenviar la propuesta? Una sola vez, y solo si sigue viva (puro)."""
    if not p.hay or p.fecha != hoy:
        return False
    if p.cancelado or p.recordado or hubo_corte_despues:
        return False
    return True
