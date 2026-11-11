"""La fotografía de la venta (T2): entrada + cálculo, en JSON canónico.

`fotografia(entrada, calculo)` da un dict serializable; `a_json` lo escribe
siempre igual (llaves ordenadas, importes como texto, fechas ISO), y
`huella` es su SHA-256. La misma venta da los mismos bytes en cualquier
equipo: así se puede verificar que una fotografía no cambió y que el
servidor y el kiosko calcularon lo mismo.

En M1a solo se construye; guardarla en `libreta_venta.calculo` es M2.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import datetime
from decimal import Decimal

from pos_uniformes.services.beneficios.contrato import Calculo, EntradaVenta

VERSION_FOTOGRAFIA = 1


def _plano(valor):
    if isinstance(valor, Decimal):
        return format(valor, "f")
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, (frozenset, set)):
        return sorted(_plano(v) for v in valor)
    if dataclasses.is_dataclass(valor) and not isinstance(valor, type):
        return {f.name: _plano(getattr(valor, f.name)) for f in dataclasses.fields(valor)}
    if isinstance(valor, (list, tuple)):
        return [_plano(v) for v in valor]
    if isinstance(valor, dict):
        return {str(k): _plano(v) for k, v in valor.items()}
    return valor


def fotografia(entrada: EntradaVenta, calculo: Calculo) -> dict:
    return {
        "version_fotografia": VERSION_FOTOGRAFIA,
        "version_motor": calculo.version_motor,
        "version_reglas": calculo.version_reglas,
        "entrada": _plano(entrada),
        "calculo": _plano(calculo),
    }


def a_json(foto: dict) -> str:
    return json.dumps(foto, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def huella(foto: dict) -> str:
    return hashlib.sha256(a_json(foto).encode("utf-8")).hexdigest()
