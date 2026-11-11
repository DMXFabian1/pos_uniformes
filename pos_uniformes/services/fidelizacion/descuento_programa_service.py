"""E5-A: el Mayorista elige en cada compra descuento o Monedero (Daniel, 2026-11-10).

«El precio de mayoreo es el que se consigue con ese 15, no es extra.» Si en
una compra elige descuento, esa venta no genera Monedero.

Reglas por renglón, sin base ni Qt:
- No aplica a las piezas de la promo 3pz (el pants base y la playera).
- No se suma con el 5 % de empleada ni con el descuento que autoriza el
  dueño: en cada renglón gana el más alto.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Iterable, Mapping

_CENT = Decimal("0.01")
_CERO = Decimal("0")
_CIEN = Decimal("100")

#: Llaves con las que el carrito marca la promo 3pz.
ROLES_PROMO_3PZ = ("base", "playera")
LLAVE_PROMO = "promo_3pz"
#: % de empleada de ese renglón (incentivo_empleada_service): si viene, manda
#: sobre el `empleada` general.
LLAVE_PCT_EMPLEADA = "desc_empleada_pct"


def es_promo_3pz(item: Mapping) -> bool:
    return bool(item.get(LLAVE_PROMO)) or str(item.get("sports_uniform_role") or "") in ROLES_PROMO_3PZ


def _pct(valor) -> Decimal:
    return Decimal(str(valor or 0))


def porcentaje_de_linea(item: Mapping, *, empleada=None, programa=None) -> Decimal:
    """El % que se descuenta en este renglón: el más alto de los que aplican."""
    pct = _pct(empleada)
    if pct > 0 and item.get(LLAVE_PCT_EMPLEADA) not in (None, ""):
        pct = _pct(item.get(LLAVE_PCT_EMPLEADA))
    if _pct(programa) > 0 and not es_promo_3pz(item):
        pct = max(pct, _pct(programa))
    return pct


def precio_con_descuento(precio, pct) -> Decimal:
    precio = Decimal(str(precio))
    pct = _pct(pct)
    if pct <= 0:
        return precio
    return (precio * (_CIEN - pct) / _CIEN).quantize(_CENT)


def descuento(items: Iterable[Mapping], *, empleada=None, programa=None) -> Decimal:
    """Pesos descontados en el carrito, renglón por renglón."""
    total = _CERO
    for it in items:
        pct = porcentaje_de_linea(it, empleada=empleada, programa=programa)
        if pct > 0:
            importe = Decimal(str(it.get("precio", 0) or 0)) * int(it.get("cantidad", 0) or 0)
            total += (importe * pct / _CIEN).quantize(_CENT)
    return total.quantize(_CENT)


def texto_boton(pct) -> str:
    return f"🏷 Descuento {_pct(pct).normalize():f} %"
