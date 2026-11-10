"""E4-A: migración `e4a_programas_y_membresias`, en una base desechable propia
(`pos_uniformes_test_e4a_<azar>` en el Postgres local) que se borra al final.
No toca `pos_uniformes_test`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from pos_uniformes.utils.config import settings

REV_E1C0 = "15f0e6fd053a"
REV_E4A = "7741ff4c020d"
_RAIZ_PAQUETE = Path(__file__).resolve().parents[1]


def _url_local():
    url = make_url(settings.database_url)
    if url.host not in {"127.0.0.1", "localhost", "::1"} or url.database != "pos_uniformes_test":
        return None
    return url


class MigracionE4ATests(unittest.TestCase):
    def setUp(self) -> None:
        base = _url_local()
        if base is None:
            self.skipTest("Solo corre contra la base local de prueba.")
        self.nombre = f"pos_uniformes_test_e4a_{uuid.uuid4().hex[:8]}"
        self.admin_url = base.set(database="postgres")
        self.url = base.set(database=self.nombre)
        try:
            admin = create_engine(self.admin_url, isolation_level="AUTOCOMMIT")
            with admin.connect() as conn:
                conn.execute(text(f'CREATE DATABASE "{self.nombre}"'))
            admin.dispose()
        except Exception as exc:  # pragma: no cover
            self.skipTest(f"No se pudo crear la base desechable: {exc}")
        self.addCleanup(self._borrar_base)
        self._alembic("upgrade", REV_E1C0)
        self.engine = create_engine(self.url)
        with self.engine.begin() as conn:
            for i in range(1, 5):
                conn.execute(
                    text(
                        "INSERT INTO cliente (codigo_cliente, nombre, tipo_cliente, descuento_preferente, telefono, activo) "
                        "VALUES (:c, :n, 'GENERAL', 0, :t, true)"
                    ),
                    {"c": f"CLI-E4{i:04d}", "n": f"Cliente {i}", "t": f"66700000{i:02d}"},
                )

    def _borrar_base(self) -> None:
        if getattr(self, "engine", None) is not None:
            self.engine.dispose()
        admin = create_engine(self.admin_url, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{self.nombre}" WITH (FORCE)'))
        admin.dispose()

    def _alembic(self, accion, revision, *, extra_env=None, debe_fallar=False) -> str:
        env = {k: v for k, v in os.environ.items() if k not in {"POS_UNIFORMES_DB_URL", "POS_E4A_DOWNGRADE_ACEPTO_PERDIDA"}}
        env.update(POS_UNIFORMES_DB_HOST=self.url.host, POS_UNIFORMES_DB_NAME=self.nombre, POS_UNIFORMES_AUTO_CREATE_SCHEMA="0")
        env.update(extra_env or {})
        res = subprocess.run([sys.executable, "-m", "alembic", accion, revision], cwd=_RAIZ_PAQUETE, env=env,
                             capture_output=True, text=True)
        salida = res.stdout + res.stderr
        (self.assertNotEqual if debe_fallar else self.assertEqual)(res.returncode, 0, salida)
        return salida

    def _foto(self):
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT * FROM cliente ORDER BY id")).all()

    def _existe(self, tabla) -> bool:
        with self.engine.connect() as conn:
            return conn.execute(text(f"SELECT to_regclass('public.{tabla}') IS NOT NULL")).scalar_one()

    def test_upgrade_crea_programas_activos_sin_tocar_clientes(self) -> None:
        antes = self._foto()
        self._alembic("upgrade", REV_E4A)
        self.assertEqual(self._foto(), antes)
        with self.engine.connect() as conn:
            progs = conn.execute(text("SELECT clave, estado, ingreso_modo, vigencia_dias FROM programa ORDER BY orden")).all()
            membresias = conn.execute(text("SELECT count(*) FROM membresia")).scalar_one()
        self.assertEqual([tuple(p) for p in progs], [
            ("CLUB", "activo", "directo_empleada", None),
            ("PROFESIONAL", "activo", "aprobacion_dueno", None),
            ("MAYORISTA", "activo", "aprobacion_dueno", None),
        ])
        self.assertEqual(membresias, 0, "la migración no inscribe a nadie")

    def test_candado_de_una_activa_por_cliente_en_postgres(self) -> None:
        self._alembic("upgrade", REV_E4A)
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO membresia (cliente_id, programa_id, estado) VALUES (1, 1, 'activa'), (1, 2, 'pendiente'), (1, 3, 'rechazada'), (1, 3, 'rechazada')"))
        for estado in ("activa", "pendiente"):
            with self.subTest(estado=estado), self.assertRaises(Exception):
                with self.engine.begin() as conn:
                    conn.execute(text(f"INSERT INTO membresia (cliente_id, programa_id, estado) VALUES (1, 3, '{estado}')"))
        with self.assertRaises(Exception):
            with self.engine.begin() as conn:
                conn.execute(text("INSERT INTO membresia (cliente_id, programa_id, estado) VALUES (2, 1, 'inventado')"))

    def test_downgrade_limpio_y_candado_si_hay_membresias(self) -> None:
        antes = self._foto()
        self._alembic("upgrade", REV_E4A)
        self._alembic("downgrade", REV_E1C0)
        for tabla in ("programa", "membresia", "membresia_evento"):
            self.assertFalse(self._existe(tabla))
        self.assertEqual(self._foto(), antes)

        self._alembic("upgrade", REV_E4A)
        with self.engine.begin() as conn:
            conn.execute(text("INSERT INTO membresia (cliente_id, programa_id, estado) VALUES (1, 1, 'activa')"))
        self.assertIn("Downgrade E4-A detenido", self._alembic("downgrade", REV_E1C0, debe_fallar=True))
        self.assertTrue(self._existe("membresia"))
        self._alembic("downgrade", REV_E1C0, extra_env={"POS_E4A_DOWNGRADE_ACEPTO_PERDIDA": "1"})
        self.assertFalse(self._existe("membresia"))


if __name__ == "__main__":
    unittest.main()
