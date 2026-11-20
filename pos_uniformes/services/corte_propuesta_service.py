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
from dataclasses import dataclass, replace
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
    #: Mensajes viejos de la propuesta que no se pudieron borrar (sin red) y
    #: que el recordatorio ya reemplazó: se siguen intentando (2026-11-20).
    viejos: tuple[int, ...] = ()

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
            viejos=tuple(int(v) for v in (datos.get("viejos") or []) if int(v)),
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
            "viejos": [int(v) for v in p.viejos],
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
        nuevo = int(message_id or 0)
        viejos = p.viejos
        if nuevo and p.message_id and p.message_id != nuevo:
            # La propuesta no se pudo borrar (sin red): no se pierde su id
            # al pisarlo, se sigue intentando (2026-11-20).
            viejos = viejos + (p.message_id,)
        _guardar(replace(p, recordado=True, message_id=nuevo or p.message_id, viejos=viejos))


def adoptar_mensaje(message_id: int, hoy: date | None = None) -> bool:
    """La propuesta (o el recordatorio) salió por la cola del bot: ese mensaje
    pasa a ser el de la propuesta de hoy; el anterior, si había, se queda en
    `viejos` para quitarlo después (revisión 2026-11-20)."""
    nuevo = int(message_id or 0)
    p = leer()
    if not nuevo or not p.hay or p.fecha != (hoy or date.today()) or p.message_id == nuevo:
        return False
    viejos = p.viejos + ((p.message_id,) if p.message_id else ())
    _guardar(replace(p, message_id=nuevo, viejos=viejos))
    return True


def mensaje_de_hoy(hoy: date | None = None) -> int:
    """El id del mensaje de la propuesta de hoy (0 si no hay)."""
    p = leer()
    return p.message_id if p.hay and p.fecha == (hoy or date.today()) else 0


def retirar_mensaje(hoy: date | None = None, *, salvo: int = 0) -> bool:
    """El corte ya se hizo por otro lado: la propuesta (con sus botones) se
    quita del chat para que quede un solo mensaje del corte. `salvo`: el
    mensaje que se está reescribiendo con el resultado no se borra; como ya
    es el registro del corte, deja de ser la propuesta (si no, un segundo
    corte lo borraba; 2026-11-20). También se intentan los `viejos`."""
    p = leer()
    if not p.hay or p.fecha != (hoy or date.today()):
        return False
    salvo = int(salvo or 0)

    def _borrar(mid: int) -> str:
        try:
            from pos_uniformes.services import telegram_service

            motivo = telegram_service.borrar_con_motivo(mid)
        except Exception:  # noqa: BLE001 — sin credenciales o sin red: se queda para otra vez
            return "red"
        if motivo != "red":
            # Fuera de la lista del barrido: si no, se reintentaba cada hora
            # hasta las 48 h (2026-11-20).
            try:
                from pos_uniformes.services import telegram_limpieza_service as limpieza

                limpieza.olvidar(mid)
            except Exception:  # noqa: BLE001
                pass
        return motivo

    viejos = tuple(v for v in p.viejos if v != salvo and _borrar(v) == "red")
    mid = p.message_id
    motivo = _borrar(mid) if mid and mid != salvo else ""
    queda = mid if motivo == "red" else 0
    if queda != p.message_id or viejos != p.viejos:
        _guardar(replace(p, message_id=queda, viejos=viejos))
    return motivo == "ok"


def retirar_si_corte_despues(momento: datetime) -> bool:
    """Hubo un corte en `momento` (kiosko, PWA, encargado…): si es de después
    de la propuesta de ese día, la propuesta se quita del chat. Lo llama el
    bot al mandar de la cola el aviso del corte (2026-11-20)."""
    p = leer()
    if not p.hay or (not p.message_id and not p.viejos) or momento is None:
        return False
    local = _sin_zona(momento)
    if local.date() != p.fecha:
        return False
    if p.momento is not None and local < _sin_zona(p.momento):
        return False          # un corte de antes de la propuesta no la contesta
    return retirar_mensaje(p.fecha)


def _sin_zona(momento: datetime) -> datetime:
    return momento.astimezone().replace(tzinfo=None) if momento.tzinfo else momento


def cancelar(hoy: date | None = None) -> bool:
    """Daniel contestó /nocorte. Vale para hoy aunque la propuesta no haya
    llegado todavía: antes contestaba «no hay nada que cancelar» y el cierre
    automático de las 18:50 seguía en pie (2026-10-10). Devuelve True si
    había una propuesta de hoy; False si se anotó por adelantado."""
    hoy = hoy or date.today()
    p = leer()
    if p.hay and p.fecha == hoy:
        _guardar(replace(p, cancelado=True))
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
