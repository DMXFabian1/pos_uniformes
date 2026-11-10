"""T-N1 (E1-C0): migración `e1c0_tipos_y_archivado`.

Igual que las pruebas de la migración de E1-A: cada prueba crea su PROPIA
base desechable en el Postgres local (127.0.0.1,
`pos_uniformes_test_e1c0_<azar>`), la lleva con Alembic hasta E1-A, siembra
clientes, prueba y la borra. No toca `pos_uniformes_test`. Si el entorno no
apunta a la base local de prueba, se salta.
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

REV_E1A = "e767eaf1db92"
REV_E1C0 = "15f0e6fd053a"
_RAIZ_PAQUETE = Path(__file__).resolve().parents[1]

_TODAS_LAS_COLUMNAS_VIEJAS = (
    "codigo_cliente, nombre, tipo_cliente::text, descuento_preferente, nivel_lealtad::text, telefono, "
    "telefono_normalizado, origen_alta, nivel_asignado_por_user_id, nivel_asignado_por_rol, "
    "nivel_asignacion_motivo, card_image_path, notas, activo, cliente_desde, created_at, updated_at"
)


def _url_local():
    url = make_url(settings.database_url)
    if url.host not in {"127.0.0.1", "localhost", "::1"} or url.database != "pos_uniformes_test":
        return None
    return url


class MigracionE1C0Tests(unittest.TestCase):
    def setUp(self) -> None:
        base = _url_local()
        if base is None:
            self.skipTest("Solo corre contra la base local de prueba (127.0.0.1/pos_uniformes_test).")
        self.nombre = f"pos_uniformes_test_e1c0_{uuid.uuid4().hex[:8]}"
        self.admin_url = base.set(database="postgres")
        self.url = base.set(database=self.nombre)
        try:
            admin = create_engine(self.admin_url, isolation_level="AUTOCOMMIT")
            with admin.connect() as conn:
                conn.execute(text(f'CREATE DATABASE "{self.nombre}"'))
            admin.dispose()
        except Exception as exc:  # pragma: no cover - sin Postgres local
            self.skipTest(f"No se pudo crear la base desechable: {exc}")
        self.addCleanup(self._borrar_base)
        self._alembic("upgrade", REV_E1A)
        self.engine = create_engine(self.url)
        self.addCleanup(self.engine.dispose)
        self._sembrar()

    # -- utilidades ---------------------------------------------------------

    def _borrar_base(self) -> None:
        if getattr(self, "engine", None) is not None:
            self.engine.dispose()
        admin = create_engine(self.admin_url, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{self.nombre}" WITH (FORCE)'))
        admin.dispose()

    def _alembic(self, accion: str, revision: str, *, extra_env: dict | None = None, debe_fallar=False) -> str:
        env = {k: v for k, v in os.environ.items() if k != "POS_UNIFORMES_DB_URL"}
        env.pop("POS_E1C0_DOWNGRADE_ACEPTO_PERDIDA", None)
        env.update(
            POS_UNIFORMES_DB_HOST=self.url.host,
            POS_UNIFORMES_DB_NAME=self.nombre,
            POS_UNIFORMES_AUTO_CREATE_SCHEMA="0",
        )
        env.update(extra_env or {})
        res = subprocess.run(
            [sys.executable, "-m", "alembic", accion, revision],
            cwd=_RAIZ_PAQUETE,
            env=env,
            capture_output=True,
            text=True,
        )
        salida = res.stdout + res.stderr
        if debe_fallar:
            self.assertNotEqual(res.returncode, 0, salida)
        else:
            self.assertEqual(res.returncode, 0, salida)
        return salida

    def _sembrar(self) -> None:
        with self.engine.begin() as conn:
            for i in range(1, 9):
                conn.execute(
                    text(
                        "INSERT INTO cliente (codigo_cliente, nombre, tipo_cliente, descuento_preferente, "
                        "nivel_lealtad, telefono, origen_alta, notas, activo) VALUES "
                        "(:c, :n, CAST(:t AS tipo_cliente), :d, CAST(:l AS nivel_lealtad), :tel, :o, :notas, :a)"
                    ),
                    {
                        "c": f"CLI-C0{i:03d}",
                        "n": f"Cliente {i}",
                        "t": ("GENERAL", "PROFESOR", "MAYORISTA")[i % 3],
                        "d": f"{(i % 4) * 5}.00",
                        "l": (None, "BASICO", "LEAL", "PROFESOR", "MAYORISTA")[i % 5],
                        "tel": f"66712345{i:02d}",
                        "o": (None, "venta_rapida")[i % 2],
                        "notas": f"nota {i}",
                        "a": i % 3 != 0,
                    },
                )

    def _foto(self) -> list:
        with self.engine.connect() as conn:
            return conn.execute(
                text(f"SELECT {_TODAS_LAS_COLUMNAS_VIEJAS} FROM cliente ORDER BY codigo_cliente")
            ).all()

    def _existe(self, tabla: str) -> bool:
        with self.engine.connect() as conn:
            return conn.execute(text(f"SELECT to_regclass('public.{tabla}') IS NOT NULL")).scalar_one()

    def _columnas(self) -> dict[str, str]:
        with self.engine.connect() as conn:
            filas = conn.execute(
                text(
                    "SELECT column_name, is_nullable FROM information_schema.columns "
                    "WHERE table_name = 'cliente'"
                )
            ).all()
        return {nombre: nulo for nombre, nulo in filas}

    # -- pruebas ------------------------------------------------------------

    def test_upgrade_crea_los_4_tipos_y_no_cambia_ningun_dato(self) -> None:
        antes = self._foto()
        self._alembic("upgrade", REV_E1C0)
        self.assertEqual(self._foto(), antes, "upgrade modificó datos existentes")

        with self.engine.connect() as conn:
            tipos = conn.execute(text("SELECT clave, nombre, activo, orden FROM cliente_tipo ORDER BY orden")).all()
        self.assertEqual(
            [tuple(t) for t in tipos],
            [
                ("GENERAL", "General", True, 1),
                ("DOCENTE", "Docente", True, 2),
                ("MAYORISTA", "Mayorista", True, 3),
                ("INSTITUCION", "Institución", True, 4),
            ],
        )
        self.assertNotIn("PERSONAL_ESCOLAR", [t[0] for t in tipos])

        columnas = self._columnas()
        for nueva in ("tipo_cliente_id", "archivado_en", "archivado_motivo"):
            with self.subTest(columna=nueva):
                self.assertEqual(columnas.get(nueva), "YES")
        with self.engine.connect() as conn:
            sin_tocar = conn.execute(
                text("SELECT count(*) FROM cliente WHERE tipo_cliente_id IS NULL AND archivado_en IS NULL")
            ).scalar_one()
        self.assertEqual(sin_tocar, 8, "la migración no debe asignar tipo ni archivar a nadie")

    def test_la_clave_del_tipo_es_unica(self) -> None:
        self._alembic("upgrade", REV_E1C0)
        with self.assertRaises(Exception):
            with self.engine.begin() as conn:
                conn.execute(text("INSERT INTO cliente_tipo (clave, nombre) VALUES ('GENERAL', 'Otro')"))

    def test_downgrade_limpio_regresa_al_esquema_de_e1a(self) -> None:
        antes = self._foto()
        self._alembic("upgrade", REV_E1C0)
        self._alembic("downgrade", REV_E1A)
        self.assertFalse(self._existe("cliente_tipo"))
        columnas = self._columnas()
        for nueva in ("tipo_cliente_id", "archivado_en", "archivado_motivo"):
            self.assertNotIn(nueva, columnas)
        self.assertEqual(self._foto(), antes)

    def test_downgrade_se_detiene_si_se_perderia_tipo_o_archivado(self) -> None:
        self._alembic("upgrade", REV_E1C0)
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE cliente SET tipo_cliente_id = (SELECT id FROM cliente_tipo WHERE clave = 'DOCENTE') "
                    "WHERE codigo_cliente = 'CLI-C0001'"
                )
            )
            conn.execute(
                text("UPDATE cliente SET archivado_en = now(), archivado_motivo = 'prueba' WHERE codigo_cliente = 'CLI-C0002'")
            )
        salida = self._alembic("downgrade", REV_E1A, debe_fallar=True)
        self.assertIn("Downgrade E1-C0 detenido", salida)
        self.assertTrue(self._existe("cliente_tipo"))

        self._alembic("downgrade", REV_E1A, extra_env={"POS_E1C0_DOWNGRADE_ACEPTO_PERDIDA": "1"})
        self.assertFalse(self._existe("cliente_tipo"))


if __name__ == "__main__":
    unittest.main()
