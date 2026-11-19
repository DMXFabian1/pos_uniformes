"""hash_del_dueno contra una base SQLite en memoria (la consulta de verdad)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pos_uniformes.database.models import Empleada
from pos_uniformes.services import pin_dueno_service as pd
from pos_uniformes.services.auth_service import AuthService
from pos_uniformes.services.nomina_service import OWNER_CODE

PIN_INVENTADO = "5307"


def _factory():
    engine = create_engine("sqlite://")
    Empleada.__table__.create(engine)
    return sessionmaker(bind=engine)


class HashDelDuenoSqliteTests(unittest.TestCase):
    def test_lee_el_hash_del_dueno_activo(self) -> None:
        Sesion = _factory()
        hash_ = AuthService.hash_password(PIN_INVENTADO)
        with Sesion() as s:
            s.add_all([
                Empleada(codigo=OWNER_CODE, nombre_completo="Dueño de pruebas", pin_hash=hash_, activo=True),
                Empleada(codigo="VEND-2", nombre_completo="Empleada de pruebas",
                         pin_hash=AuthService.hash_password("1111"), activo=True),
            ])
            s.commit()
            self.assertEqual(pd.hash_del_dueno(s), hash_)
        with tempfile.TemporaryDirectory() as d, \
                patch.object(pd, "_ruta_local", lambda: Path(d) / "pin_dueno.json"):
            self.assertEqual(pd.verificar_pin_dueno(PIN_INVENTADO, sesion_factory=Sesion).estado, pd.OK)
            self.assertEqual(pd.verificar_pin_dueno("1111", sesion_factory=Sesion).estado, pd.INCORRECTO)
            self.assertEqual(pd.leer_copia_local(), hash_)

    def test_dueno_inactivo_o_sin_pin(self) -> None:
        Sesion = _factory()
        with Sesion() as s:
            s.add(Empleada(codigo=OWNER_CODE, nombre_completo="Dueño de pruebas",
                           pin_hash=AuthService.hash_password(PIN_INVENTADO), activo=False))
            s.commit()
            self.assertIsNone(pd.hash_del_dueno(s))
        Sesion = _factory()
        with Sesion() as s:
            s.add(Empleada(codigo=OWNER_CODE, nombre_completo="Dueño de pruebas", pin_hash=None, activo=True))
            s.commit()
            self.assertIsNone(pd.hash_del_dueno(s))


if __name__ == "__main__":
    unittest.main()
