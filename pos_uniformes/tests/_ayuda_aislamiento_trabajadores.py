"""Ayuda de `test_base_por_trabajador`: NO se recolecta sola (no empieza con
`test_`). Esa prueba la corre en un pytest aparte con `-n 2`.

Cada prueba escribe y CONFIRMA retiros con su marca, espera a que el otro
proceso esté escribiendo lo suyo, y cuenta TODOS los retiros marcados de la
base. Con la base compartida de antes, cada proceso veía los del otro.
"""

from __future__ import annotations

import os
import time
import unittest
from decimal import Decimal

import pytest
from sqlalchemy import delete, func, select

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import CajaRetiro
from pos_uniformes.utils.config import settings

_MARCA = "AISLA-XDIST"


@pytest.mark.parametrize("vuelta", range(8))
def test_solo_ve_lo_suyo(vuelta: int) -> None:
    trabajador = os.environ.get("PYTEST_XDIST_WORKER", "")
    assert trabajador, "esta ayuda se corre con -n 2"
    assert settings.db_name.endswith(f"_{trabajador}_test"), settings.db_name
    with get_session() as s:
        s.add_all([CajaRetiro(monto=Decimal("1.00"), motivo=_MARCA, creado_por=trabajador) for _ in range(3)])
        s.commit()
        try:
            time.sleep(0.4)  # el otro proceso escribe en este rato
            total, quienes = s.execute(
                select(func.count(), func.count(func.distinct(CajaRetiro.creado_por))).where(CajaRetiro.motivo == _MARCA)
            ).one()
            assert (total, quienes) == (3, 1), f"{trabajador} vio {total} retiros de {quienes} procesos"
        finally:
            s.execute(delete(CajaRetiro).where(CajaRetiro.motivo == _MARCA))
            s.commit()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
