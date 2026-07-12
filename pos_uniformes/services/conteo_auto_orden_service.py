"""Generación automática de órdenes de conteo al vencer (Fase 3).

Corre periódicamente en el satélite: busca escuelas con conteo vencido, y para
las que aún no tienen orden generada en este ciclo, arma las hojas y las encola
al despachador (que las imprime). El candado anti-spam evita reimprimir a diario.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from pos_uniformes.services.conteo_auto_orden_cache_service import (
    load_auto_orden_cache,
    save_auto_orden_cache,
)
from pos_uniformes.services.conteo_calendario_service import (
    EstadoCalendarioConteo,
    escuelas_con_conteo_vencido,
)
from pos_uniformes.services.conteo_sheet_service import build_conteo_sheets
from pos_uniformes.services.trabajos_service import enviar_conteo


def marcador_de(estado: EstadoCalendarioConteo) -> str:
    """Identifica el ciclo actual de conteo de la escuela.

    Cambia cuando se registra un conteo (la próxima fecha se recorre), lo que
    hace que se vuelva a generar la orden en el siguiente vencimiento.
    """
    return estado.proxima_fecha.isoformat() if estado.proxima_fecha else "nunca"


def generar_ordenes_automaticas(
    session: Session,
    *,
    ahora: datetime | None = None,
    origen: str = "auto-conteo",
) -> list[str]:
    """Encola las órdenes de conteo pendientes que aún no se han generado.

    Devuelve los nombres de escuela para las que se encoló una orden nueva.
    Usa (y actualiza) el candado local para no repetir en el mismo ciclo.
    """
    vencidas = escuelas_con_conteo_vencido(session, ahora=ahora)
    if not vencidas:
        return []

    cache = load_auto_orden_cache()
    generadas: list[str] = []
    cache_cambiado = False

    for estado in vencidas:
        clave = str(estado.escuela_id)
        marcador = marcador_de(estado)
        if cache.get(clave) == marcador:
            continue  # ya se generó la orden de este ciclo

        hojas = build_conteo_sheets(session, estado.escuela_id, estado.escuela_nombre)
        if not hojas:
            continue  # sin productos para contar; no marcar (por si luego los tiene)

        enviar_conteo(
            session,
            hojas,
            titulo=f"Conteo — {estado.escuela_nombre}",
            origen=origen,
        )
        cache[clave] = marcador
        cache_cambiado = True
        generadas.append(estado.escuela_nombre)

    if generadas:
        session.commit()
    if cache_cambiado:
        save_auto_orden_cache(cache)
    return generadas
