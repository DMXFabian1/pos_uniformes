"""Tests de identidad local y registro/presencia de satélites (Fase E)."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.services import satelite_registry_service as reg
from pos_uniformes.services import satellite_identity_service as ident

_IDENT_MOD = "pos_uniformes.services.satellite_identity_service.satellite_data_dir"


class IdentityTests(unittest.TestCase):
    def test_id_estable_entre_llamadas(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_IDENT_MOD, return_value=Path(d)):
                sid1 = ident.get_satellite_id()
                sid2 = ident.get_satellite_id()
                self.assertTrue(sid1)
                self.assertEqual(sid1, sid2)

    def test_nombre_default_y_cambio(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_IDENT_MOD, return_value=Path(d)):
                self.assertTrue(ident.get_satellite_name())  # default = hostname
                efectivo = ident.set_satellite_name("  Entrada  ")
                self.assertEqual(efectivo, "Entrada")
                self.assertEqual(ident.get_satellite_name(), "Entrada")

    def test_nombre_vacio_vuelve_a_default(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_IDENT_MOD, return_value=Path(d)):
                ident.set_satellite_name("Caja 2")
                ident.set_satellite_name("   ")
                # Vuelve al hostname (no queda "Caja 2").
                self.assertNotEqual(ident.get_satellite_name(), "Caja 2")

    def test_cambiar_nombre_conserva_id(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with patch(_IDENT_MOD, return_value=Path(d)):
                sid = ident.get_satellite_id()
                ident.set_satellite_name("Probadores")
                self.assertEqual(ident.get_satellite_id(), sid)


class RegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self) -> None:
        self.session.close()

    def test_registrar_crea_y_actualiza_sin_duplicar(self) -> None:
        t0 = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        reg.registrar(self.session, "sat-1", "Entrada", ahora=t0)
        self.session.commit()
        # Segundo registro (heartbeat) con nombre nuevo: mismo registro.
        t1 = t0 + timedelta(minutes=1)
        reg.registrar(self.session, "sat-1", "Entrada Principal", ahora=t1)
        self.session.commit()
        sats = reg.listar(self.session)
        self.assertEqual(len(sats), 1)
        self.assertEqual(sats[0].nombre, "Entrada Principal")
        self.assertEqual(sats[0].ultimo_visto.replace(tzinfo=timezone.utc), t1)

    def test_esta_online_segun_umbral(self) -> None:
        ahora = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        reg.registrar(self.session, "sat-1", "A", ahora=ahora - timedelta(seconds=60))
        reg.registrar(self.session, "sat-2", "B", ahora=ahora - timedelta(seconds=600))
        self.session.commit()
        sats = {s.identificador: s for s in reg.listar(self.session)}
        self.assertTrue(reg.esta_online(sats["sat-1"], ahora=ahora))
        self.assertFalse(reg.esta_online(sats["sat-2"], ahora=ahora))

    def test_esta_online_sin_ultimo_visto(self) -> None:
        from pos_uniformes.database.models import Satelite

        sat = Satelite(identificador="x", nombre="X", ultimo_visto=None)
        self.assertFalse(reg.esta_online(sat))

    def test_listar_con_estado(self) -> None:
        ahora = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)
        reg.registrar(self.session, "sat-1", "A", ahora=ahora)
        reg.registrar(self.session, "sat-2", "B", ahora=ahora - timedelta(hours=1))
        self.session.commit()
        estado = {e["identificador"]: e for e in reg.listar_con_estado(self.session, ahora=ahora)}
        self.assertTrue(estado["sat-1"]["online"])
        self.assertFalse(estado["sat-2"]["online"])


if __name__ == "__main__":
    unittest.main()
