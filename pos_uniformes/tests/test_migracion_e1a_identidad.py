"""T-A3 / T-A4 (E1-A): migración `e1a_identidad_cliente`.

Cada prueba crea su PROPIA base desechable en el Postgres local
(127.0.0.1, `pos_uniformes_test_e1a_<azar>`), la lleva con Alembic hasta la
revisión anterior, siembra clientes, prueba y la borra al final. No toca
`pos_uniformes_test` ni ninguna otra base. Si el entorno no apunta a la base
local de prueba (por ejemplo con `--db-real`), se salta.
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

from pos_uniformes.services.clientes.telefono import normalizar_telefono
from pos_uniformes.utils.config import settings
from tests.base_por_trabajador import es_base_de_prueba_local

REV_ANTERIOR = "e2f3a4b5c6d7"
REV_E1A = "e767eaf1db92"
_RAIZ_PAQUETE = Path(__file__).resolve().parents[1]  # donde vive alembic.ini

TELEFONOS = (
    None,
    "",
    "   ",
    "sin telefono",
    "6671234567",
    " 667 123 4567 ",
    "667-123-45-67",
    "(667) 123.4567",
    "+52 667 123 4567",
    "526671234567",
    "+52 1 667 123 4567",
    "5216671234567",
    "667123456",
    "66712345678",
    "12345678901234",
    "536671234567",
    "5226671234567",
    "0000000000",
    "111-111-1111",
    "520000000000",
    "abc6671234567xyz",
    "tel 667",
    "6671234567",  # duplicado exacto
    "667 123 4567",  # compartido con otro formato
)

_COLUMNAS_INTACTAS = (
    "telefono, tipo_cliente::text, descuento_preferente, nivel_lealtad::text, "
    "nivel_asignado_por_user_id, nivel_asignado_por_rol, nivel_asignacion_motivo"
)


def _url_local():
    url = make_url(settings.database_url)
    if not es_base_de_prueba_local(url):
        return None
    return url


class MigracionE1ATests(unittest.TestCase):
    def setUp(self) -> None:
        base = _url_local()
        if base is None:
            self.skipTest("Solo corre contra la base local de prueba (127.0.0.1/pos_uniformes_test).")
        self.nombre = f"pos_uniformes_test_e1a_{uuid.uuid4().hex[:8]}"
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
        self._alembic("upgrade", REV_ANTERIOR)
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
        env.pop("POS_E1A_DOWNGRADE_ACEPTO_PERDIDA", None)
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
            for i, tel in enumerate(TELEFONOS, start=1):
                conn.execute(
                    text(
                        "INSERT INTO cliente (codigo_cliente, nombre, tipo_cliente, descuento_preferente, "
                        "nivel_lealtad, telefono, nivel_asignado_por_rol, nivel_asignacion_motivo, activo) "
                        "VALUES (:c, :n, CAST(:t AS tipo_cliente), :d, CAST(:l AS nivel_lealtad), :tel, :rol, :mot, true)"
                    ),
                    {
                        "c": f"CLI-T{i:04d}",
                        "n": f"Cliente {i}",
                        "t": ("GENERAL", "PROFESOR", "MAYORISTA")[i % 3],
                        "d": f"{(i % 4) * 5}.00",
                        "l": ("BASICO", "LEAL", "PROFESOR", "MAYORISTA")[i % 4],
                        "tel": tel,
                        "rol": "ADMIN",
                        "mot": f"motivo {i}",
                    },
                )

    def _foto(self) -> list:
        with self.engine.connect() as conn:
            return conn.execute(text(f"SELECT codigo_cliente, {_COLUMNAS_INTACTAS} FROM cliente ORDER BY codigo_cliente")).all()

    def _columnas_cliente(self) -> set[str]:
        with self.engine.connect() as conn:
            return set(
                conn.execute(
                    text("SELECT column_name FROM information_schema.columns WHERE table_name = 'cliente'")
                ).scalars()
            )

    def _nivel_es_nullable(self) -> bool:
        with self.engine.connect() as conn:
            return (
                conn.execute(
                    text(
                        "SELECT is_nullable FROM information_schema.columns "
                        "WHERE table_name = 'cliente' AND column_name = 'nivel_lealtad'"
                    )
                ).scalar_one()
                == "YES"
            )

    def _existe_tabla_eventos(self) -> bool:
        with self.engine.connect() as conn:
            return conn.execute(text("SELECT to_regclass('public.cliente_evento') IS NOT NULL")).scalar_one()

    # -- T-A3 ---------------------------------------------------------------

    def test_upgrade_rellena_igual_que_python_y_no_cambia_datos(self) -> None:
        antes = self._foto()
        self._alembic("upgrade", REV_E1A)
        self.assertEqual(self._foto(), antes, "upgrade modificó datos existentes")

        with self.engine.connect() as conn:
            filas = conn.execute(
                text("SELECT codigo_cliente, telefono, telefono_normalizado, origen_alta FROM cliente ORDER BY codigo_cliente")
            ).all()
        self.assertEqual(len(filas), len(TELEFONOS))
        for codigo, telefono, normalizado, origen in filas:
            with self.subTest(codigo=codigo, telefono=telefono):
                self.assertEqual(normalizado, normalizar_telefono(telefono))
                self.assertIsNone(origen)

        # Duplicados y compartidos conviven con el mismo valor normalizado.
        with self.engine.connect() as conn:
            repetidos = conn.execute(
                text("SELECT count(*) FROM cliente WHERE telefono_normalizado = '6671234567'")
            ).scalar_one()
        self.assertGreaterEqual(repetidos, 8)

        self.assertTrue(self._nivel_es_nullable())
        self.assertTrue(self._existe_tabla_eventos())
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO cliente (codigo_cliente, nombre, tipo_cliente, descuento_preferente, activo) "
                    "VALUES ('CLI-SIN', 'Sin nivel', 'GENERAL', 0, true)"
                )
            )
            nivel = conn.execute(text("SELECT nivel_lealtad FROM cliente WHERE codigo_cliente = 'CLI-SIN'")).scalar_one()
        self.assertIsNone(nivel, "la base asignó un nivel por omisión")

    def test_python_y_sql_coinciden_caso_por_caso(self) -> None:
        self._alembic("upgrade", REV_E1A)
        with self.engine.connect() as conn:
            for tel in TELEFONOS:
                with self.subTest(telefono=tel):
                    sql = conn.execute(
                        text(
                            "SELECT telefono_normalizado FROM cliente WHERE telefono IS NOT DISTINCT FROM :t LIMIT 1"
                        ),
                        {"t": tel},
                    ).scalar_one()
                    self.assertEqual(sql, normalizar_telefono(tel))

    # -- T-A4 ---------------------------------------------------------------

    def test_downgrade_limpio_deja_el_esquema_anterior_y_se_puede_volver_a_subir(self) -> None:
        columnas_antes = self._columnas_cliente()
        antes = self._foto()
        self._alembic("upgrade", REV_E1A)
        self._alembic("downgrade", REV_ANTERIOR)
        self.assertEqual(self._columnas_cliente(), columnas_antes)
        self.assertFalse(self._nivel_es_nullable())
        self.assertFalse(self._existe_tabla_eventos())
        self.assertEqual(self._foto(), antes)
        self._alembic("upgrade", REV_E1A)
        self.assertTrue(self._existe_tabla_eventos())
        self.assertEqual(self._foto(), antes)

    def test_downgrade_con_eventos_se_detiene_salvo_aceptacion_explicita(self) -> None:
        self._alembic("upgrade", REV_E1A)
        with self.engine.begin() as conn:
            cid = conn.execute(text("SELECT min(id) FROM cliente")).scalar_one()
            conn.execute(
                text("INSERT INTO cliente_evento (cliente_id, tipo, origen) VALUES (:c, 'prueba', 'test')"),
                {"c": cid},
            )
        salida = self._alembic("downgrade", REV_ANTERIOR, debe_fallar=True)
        self.assertIn("POS_E1A_DOWNGRADE_ACEPTO_PERDIDA", salida)
        self.assertTrue(self._existe_tabla_eventos(), "se borró la tabla pese al aviso")

        self._alembic("downgrade", REV_ANTERIOR, extra_env={"POS_E1A_DOWNGRADE_ACEPTO_PERDIDA": "1"})
        self.assertFalse(self._existe_tabla_eventos())
        self._alembic("upgrade", REV_E1A)

    def test_downgrade_con_origen_alta_se_detiene(self) -> None:
        self._alembic("upgrade", REV_E1A)
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE cliente SET origen_alta = 'venta_rapida' WHERE codigo_cliente = 'CLI-T0001'"))
        self._alembic("downgrade", REV_ANTERIOR, debe_fallar=True)
        self.assertIn("origen_alta", self._columnas_cliente())

    def test_downgrade_con_cliente_sin_nivel_se_detiene_siempre(self) -> None:
        self._alembic("upgrade", REV_E1A)
        with self.engine.begin() as conn:
            conn.execute(text("UPDATE cliente SET nivel_lealtad = NULL WHERE codigo_cliente = 'CLI-T0002'"))
        salida = self._alembic(
            "downgrade", REV_ANTERIOR, extra_env={"POS_E1A_DOWNGRADE_ACEPTO_PERDIDA": "1"}, debe_fallar=True
        )
        self.assertIn("sin nivel", salida)
        with self.engine.connect() as conn:
            nivel = conn.execute(
                text("SELECT nivel_lealtad FROM cliente WHERE codigo_cliente = 'CLI-T0002'")
            ).scalar_one()
        self.assertIsNone(nivel, "el downgrade asignó un nivel")
        self.assertTrue(self._existe_tabla_eventos())


if __name__ == "__main__":
    unittest.main()
