"""`/cajon` — corregir lo que NO salió del cajón, desde el celular.

El diálogo del corte lista los pagos y retiros del periodo con una casilla:
*«desmarca el que NO salió del cajón»*. Sirve para lo que se pagó por
transferencia, lo que ya se había contado, o un retiro apuntado dos veces.

Desde Telegram no existía (Daniel, 2026-10-04), y esa es la que mueve números:
el corte se cuadraba contra dinero que nunca salió y la diferencia aparecía como
**faltante**. De lejos, eso se ve como si la caja no cuadrara.

Se hace **antes** del corte y en un comando aparte a propósito: `/corte` sigue
siendo de un solo toque, como está en la cabeza de Daniel y como lo usa la tarea
automática. Aquí solo se corrige lo que ya está apuntado.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

#: Prefijo de los botones de esta pantalla.
PREFIJO = "cj:"


@dataclass(frozen=True)
class Fila:
    """Un pago o un retiro del periodo, como se ve en la lista."""

    clase: str          # "pago" | "retiro"
    id: int
    quien: str
    monto: Decimal
    cuando: str
    en_cajon: bool

    @property
    def dato(self) -> str:
        return f"{PREFIJO}{self.clase}:{self.id}"


def _cuando(momento) -> str:
    try:
        return momento.astimezone().strftime("%d/%m %H:%M")
    except Exception:  # noqa: BLE001
        return ""


def filas_del_periodo(session) -> list[Fila]:
    """Lo que salió (o no) del cajón en el periodo abierto, para revisarlo."""
    from datetime import datetime

    from pos_uniformes.services.corte_caja_service import (
        estado_caja,
        pagos_registrados_del_periodo,
    )
    from pos_uniformes.services.nombres_empleadas_service import mostrar, nombres_por_codigo

    ahora = datetime.now().astimezone()
    estado = estado_caja(session, ahora)
    nombres = nombres_por_codigo(session)

    filas: list[Fila] = []
    for p in pagos_registrados_del_periodo(session, estado.desde, estado.hasta, solo_en_cajon=False):
        quien = mostrar(p.employee_name or p.employee_code, nombres)
        filas.append(
            Fila("pago", int(p.id), str(quien).split()[0], Decimal(str(p.total)),
                 _cuando(p.created_at), bool(p.en_cajon))
        )
    try:
        from pos_uniformes.services.retiros_service import retiros_del_periodo

        for r in retiros_del_periodo(session, estado.desde, estado.hasta, solo_en_cajon=False):
            filas.append(
                Fila("retiro", int(r.id), str(r.motivo or "Retiro"), Decimal(str(r.monto)),
                     _cuando(r.created_at), bool(r.en_cajon))
            )
    except Exception:  # noqa: BLE001 — sin retiros se sigue con los pagos
        # Se anota: callarlo del todo escondió un bug mientras se escribía esto,
        # y en la tienda escondería una lista a medias sin decir por qué.
        logging.getLogger(__name__).exception("No se pudieron leer los retiros del periodo")
        session.rollback()
    return filas


def texto_y_botones(session) -> tuple[str, str]:
    """(texto, botones) de la lista. Un botón por renglón: tocarlo lo cambia."""
    from pos_uniformes.services import telegram_service

    filas = filas_del_periodo(session)
    if not filas:
        return (
            "No hay pagos ni retiros apuntados desde el último corte.\n\n"
            "Cuando los haya, aquí se pueden desmarcar los que no salieron "
            "del cajón (una transferencia, algo ya contado).",
            telegram_service.teclado([[("‹ Menú", "m:raiz")]]),
        )

    fuera = [f for f in filas if not f.en_cajon]
    lineas = ["💵 Lo apuntado desde el último corte:", ""]
    for f in filas:
        marca = "✅" if f.en_cajon else "⬜"
        lineas.append(f"{marca} {f.quien} — ${f.monto:,.2f} · {f.cuando}")
    lineas.append("")
    lineas.append("✅ salió del cajón · ⬜ no salió (no se le resta)")
    if fuera:
        total = sum(f.monto for f in fuera)
        lineas.append(f"Fuera del cajón: ${total:,.2f}")
    lineas.append("")
    lineas.append("Toca uno para cambiarlo. Luego /corte.")

    botones = [
        [(f"{'✅' if f.en_cajon else '⬜'} {f.quien} ${f.monto:,.0f}", f.dato)]
        for f in filas
    ]
    botones.append([("‹ Menú", "m:raiz")])
    return "\n".join(lineas), telegram_service.teclado(botones)


def es_del_cajon(dato: str) -> bool:
    return str(dato or "").startswith(PREFIJO)


def atender(dato: str, *, session_factory) -> tuple[str, str, str]:
    """Un botón: invierte si ese pago/retiro salió del cajón."""
    from pos_uniformes.services.corte_caja_service import marcar_fuera_del_cajon

    partes = str(dato or "")[len(PREFIJO):].split(":")
    if len(partes) != 2 or partes[0] not in ("pago", "retiro"):
        return "No conozco ese botón", "", ""
    try:
        fila_id = int(partes[1])
    except ValueError:
        return "No conozco ese botón", "", ""

    with session_factory() as session:
        actual = next(
            (f for f in filas_del_periodo(session) if f.clase == partes[0] and f.id == fila_id),
            None,
        )
        if actual is None:
            texto, botones = texto_y_botones(session)
            return "Ese ya no está en el periodo", texto, botones
        ids = {f"{partes[0]}s_ids": [fila_id]}
        marcar_fuera_del_cajon(session, en_cajon=not actual.en_cajon, **ids)
        session.commit()
        texto, botones = texto_y_botones(session)
    aviso = "Sí salió del cajón" if not actual.en_cajon else "No salió del cajón"
    return aviso, texto, botones
