"""Cómo se cuenta la Libreta — mismo texto en el kiosko y en el celular.

Puro (sin Qt, sin base): la ventana del satélite y la API móvil lo usan
para que la empleada lea exactamente lo mismo en los dos lados.
"""

from __future__ import annotations

_DIA_CORTO = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")


def tiles_ciclo(datos: dict) -> list[tuple[str, str]]:
    """(valor, leyenda) de la tarjeta del ciclo: comisiones desde su último
    pago, próximo pago y siguiente descanso."""
    from pos_uniformes.services.dia_calendario_service import DIAS_ES, MESES_ES

    def _fecha(d):
        return f"{DIAS_ES[d.weekday()][:3]} {d.day} {MESES_ES[d.month - 1][:3]}"

    hoy = datos.get("hoy")
    tiles = [(f"⭐ {int(datos.get('comisiones') or 0)}", "comisiones desde tu último pago")]
    pago = datos.get("proximo_pago")
    if pago is not None:
        faltan = datos.get("faltan")
        if hoy is not None and pago <= hoy:
            leyenda = "próximo pago · ¡hoy!" if pago == hoy else "pago pendiente de registrar"
        elif faltan is not None:
            leyenda = f"próximo pago · faltan {faltan} día{'s' if faltan != 1 else ''}"
        else:
            leyenda = "próximo pago"
        tiles.append((f"💵 {_fecha(pago)}", leyenda))
    descanso = datos.get("descanso")
    if descanso is not None:
        tiles.append((f"🛌 {_fecha(descanso)}", "tu siguiente descanso"))
    return tiles


def texto_movimiento(row, *, con_dia: bool = False) -> str:
    """Un movimiento en lenguaje simple y SIN dinero (regla de privacidad).
    Las prendas van en su propio renglón para que se envuelvan."""
    from pos_uniformes.services.libreta_service import describir_detalle

    local_dt = (
        row.created_at.astimezone()
        if getattr(row.created_at, "tzinfo", None) is not None
        else row.created_at
    )
    hora = local_dt.strftime("%H:%M")
    dia = f"{_DIA_CORTO[local_dt.weekday()]} {local_dt.strftime('%d/%m')} · " if con_dia else ""
    comisiones = int(getattr(row, "comisiones", 0) or 0)
    tipo = str(row.tipo)
    if tipo == "abono":
        cliente = getattr(row, "cliente", None)
        texto = f"💵  {dia}{hora} · Recibiste un abono"
        if cliente:
            texto += f" de {cliente}"
        return texto
    piezas = int(row.piezas or 0)
    verbo = "Apartaste" if tipo == "apartado" else "Vendiste"
    icono = "📦" if tipo == "apartado" else "🛍️"
    texto = f"{icono}  {dia}{hora} · {verbo} {piezas} pieza(s)"
    if comisiones:
        texto += f"  (+{comisiones} com.)"
    return texto + f"\n      {describir_detalle(list(row.detalle or []))}"
