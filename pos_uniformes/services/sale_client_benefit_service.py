"""Beneficio visible de un cliente en la Caja antigua.

2026-11-12: se retiró el descuento por nivel viejo («el nivel viejo
retíralo», Daniel). Solo queda el contenedor; el porcentaje es 0.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class SaleClientBenefit:
    discount_percent: Decimal
    source_label: str
