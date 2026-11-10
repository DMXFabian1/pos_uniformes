"""E1-B: servicio de identidad, altas sin nivel y edición (T-B1–T-B4, T-B9, T-B10, T-B12).

Corre contra la base local de prueba (127.0.0.1/pos_uniformes_test) DENTRO de
una transacción que se deshace al final: nada queda escrito. T-B4 necesita
dos sesiones que confirman de verdad, así que usa una base desechable propia
(`pos_uniformes_test_e1b_<azar>`) que se borra al terminar. Sin la base local
de prueba, todo se salta.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import unittest
import uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Cliente, ClienteEvento, NivelLealtad, RolUsuario, TipoCliente
from pos_uniformes.services.client_service import ClientService
from pos_uniformes.services.clientes import identidad_service as ids
from pos_uniformes.services.loyalty_service import LoyaltyService
from pos_uniformes.utils.config import settings

_RAIZ_PAQUETE = Path(__file__).resolve().parents[1]


def _url_local():
    url = make_url(settings.database_url)
    if url.host not in {"127.0.0.1", "localhost", "::1"} or url.database != "pos_uniformes_test":
        return None
    return url


def _sin_loyalty():
    """Un doble que FALLA si cualquier alta llama a LoyaltyService."""
    falla = AssertionError("El alta no debe llamar a LoyaltyService (K1)")
    return (
        patch.object(LoyaltyService, "assign_level", side_effect=falla),
        patch.object(LoyaltyService, "discount_for_level", side_effect=falla),
        patch.object(LoyaltyService, "resolve_initial_level", side_effect=falla),
        patch.object(LoyaltyService, "default_level_for_client_type", side_effect=falla),
    )


class _EnTransaccion(unittest.TestCase):
    def setUp(self) -> None:
        url = _url_local()
        if url is None:
            self.skipTest("Solo corre contra la base local de prueba.")
        self.engine = create_engine(url)
        self.addCleanup(self.engine.dispose)
        self.conn = self.engine.connect()
        self.addCleanup(self.conn.close)
        self.tx = self.conn.begin()
        self.addCleanup(self.tx.rollback)  # nada queda escrito
        self.s = Session(bind=self.conn, join_transaction_mode="create_savepoint")
        self.addCleanup(self.s.close)
        self.marca = uuid.uuid4().hex[:6].upper()
        for p in _sin_loyalty():
            p.start()
            self.addCleanup(p.stop)

    def _tel(self, sufijo: str) -> str:
        # Teléfonos de prueba que no existen en la base de prueba.
        return f"99{int(self.marca, 16) % 10**6:06d}{sufijo}"

    def _eventos(self, cliente) -> list[ClienteEvento]:
        return list(self.s.scalars(select(ClienteEvento).where(ClienteEvento.cliente_id == cliente.id)).all())

    def _assert_sin_nivel(self, c: Cliente, origen: str) -> None:
        self.s.refresh(c)
        self.assertIsNone(c.nivel_lealtad)
        self.assertEqual(Decimal(c.descuento_preferente), Decimal("0.00"))
        self.assertIsNone(c.nivel_asignado_por_user_id)
        self.assertIsNone(c.nivel_asignado_por_rol)
        self.assertIsNone(c.nivel_asignacion_motivo)
        self.assertEqual(c.origen_alta, origen)


class BusquedaTests(_EnTransaccion):
    """T-B1: solo activos; por código, nombre y sufijo del teléfono."""

    def test_busca_por_codigo_nombre_y_sufijo(self) -> None:
        tel = self._tel("01")
        c = ids.dar_de_alta(self.s, nombre=f"Ana Buscable {self.marca}", telefono=tel, origen=ids.ORIGEN_VENTA_RAPIDA)
        inactivo = ids.dar_de_alta(self.s, nombre=f"Ana Inactiva {self.marca}", telefono=self._tel("02"), origen=ids.ORIGEN_VENTA_RAPIDA)
        inactivo.activo = False
        self.s.flush()

        por_nombre = ids.buscar_clientes(self.s, f"buscable {self.marca}")
        self.assertEqual([r.id for r in por_nombre], [c.id])
        self.assertEqual([r.id for r in ids.buscar_clientes(self.s, c.codigo_cliente)], [c.id])
        por_sufijo = [r.id for r in ids.buscar_clientes(self.s, tel[-6:])]
        self.assertIn(c.id, por_sufijo)
        self.assertEqual(ids.buscar_clientes(self.s, f"Inactiva {self.marca}"), [])

    def test_el_resultado_trae_telefono_enmascarado(self) -> None:
        tel = self._tel("03")
        ids.dar_de_alta(self.s, nombre=f"Masc {self.marca}", telefono=tel, origen=ids.ORIGEN_VENTA_RAPIDA)
        (r,) = ids.buscar_clientes(self.s, f"Masc {self.marca}")
        self.assertNotIn(tel[:6], r.telefono_enmascarado)
        self.assertTrue(r.telefono_enmascarado.endswith(f"{tel[-4:-2]} {tel[-2:]}"))
        self.assertFalse(hasattr(r, "descuento_preferente"))

    def test_limite_de_30(self) -> None:
        for i in range(32):
            ids.dar_de_alta(self.s, nombre=f"Lote {self.marca} {i:02d}", telefono=None, origen=ids.ORIGEN_VENTA_RAPIDA)
        self.assertEqual(len(ids.buscar_clientes(self.s, f"Lote {self.marca}", limite=500)), 30)


class AltaVentaRapidaTests(_EnTransaccion):
    """T-B2 y T-B3."""

    def test_alta_sin_nivel_con_origen_y_evento(self) -> None:
        c = ids.dar_de_alta(
            self.s, nombre=f"Nuevo {self.marca}", telefono=f"+52 1 {self._tel('04')}", origen=ids.ORIGEN_VENTA_RAPIDA,
            employee_code="VEND-2", exigir_telefono_valido=True, revisar_duplicados=True,
        )
        self._assert_sin_nivel(c, ids.ORIGEN_VENTA_RAPIDA)
        self.assertEqual(c.telefono_normalizado, self._tel("04"))
        (ev,) = self._eventos(c)
        self.assertEqual(ev.tipo, ids.EVENTO_ALTA)
        self.assertEqual(ev.employee_code, "VEND-2")
        self.assertEqual(ev.detalle["origen"], ids.ORIGEN_VENTA_RAPIDA)

    def test_coincidencia_sin_confirmar_se_rechaza(self) -> None:
        tel = self._tel("05")
        primero = ids.dar_de_alta(self.s, nombre=f"Uno {self.marca}", telefono=tel, origen=ids.ORIGEN_VENTA_RAPIDA)
        antes = self.s.scalar(select(Cliente.id).order_by(Cliente.id.desc()).limit(1))
        with self.assertRaises(ids.CoincidenciasPorConfirmarError) as ctx:
            ids.dar_de_alta(self.s, nombre=f"Dos {self.marca}", telefono=f"+52 {tel[:3]} {tel[3:]}",
                            origen=ids.ORIGEN_VENTA_RAPIDA, exigir_telefono_valido=True, revisar_duplicados=True)
        self.assertEqual([c.id for c in ctx.exception.coincidencias], [primero.id])
        self.assertEqual(self.s.scalar(select(Cliente.id).order_by(Cliente.id.desc()).limit(1)), antes, "se creó en silencio")

    def test_otra_persona_con_el_mismo_telefono_deja_constancia(self) -> None:
        tel = self._tel("06")
        primero = ids.dar_de_alta(self.s, nombre=f"Mamá {self.marca}", telefono=tel, origen=ids.ORIGEN_VENTA_RAPIDA)
        segundo = ids.dar_de_alta(
            self.s, nombre=f"Hija {self.marca}", telefono=tel, origen=ids.ORIGEN_VENTA_RAPIDA,
            exigir_telefono_valido=True, revisar_duplicados=True, confirmar_telefono_compartido=True,
        )
        self._assert_sin_nivel(segundo, ids.ORIGEN_VENTA_RAPIDA)
        (ev,) = self._eventos(segundo)
        self.assertEqual(ev.tipo, ids.EVENTO_ALTA_TELEFONO_COMPARTIDO)
        self.assertEqual(ev.detalle["coincidencias"], [primero.id])

    def test_telefono_invalido_se_rechaza(self) -> None:
        for malo in ("", "667123", "0000000000", "66712345678"):
            with self.subTest(telefono=malo), self.assertRaises(ids.TelefonoInvalidoError):
                ids.dar_de_alta(self.s, nombre=f"X {self.marca}", telefono=malo, origen=ids.ORIGEN_VENTA_RAPIDA,
                                exigir_telefono_valido=True, revisar_duplicados=True)

    def test_nombre_vacio_se_rechaza(self) -> None:
        with self.assertRaises(ValueError):
            ids.dar_de_alta(self.s, nombre="  ", telefono=self._tel("07"), origen=ids.ORIGEN_VENTA_RAPIDA)


class AltasDeClientServiceTests(_EnTransaccion):
    """T-B9 (ADMIN) y T-B10 (Presupuesto del kiosko)."""

    def _usuario(self, rol):
        return SimpleNamespace(id=None, rol=rol, activo=True)

    def test_alta_admin_ignora_tipo_y_descuento_comercial(self) -> None:
        c = ClientService.create_client(
            self.s, self._usuario(RolUsuario.ADMIN), f"Admin {self.marca}",
            tipo_cliente=TipoCliente.PROFESOR, descuento_preferente=Decimal("10.00"),
            telefono=self._tel("08"), notas="nota",
        )
        self._assert_sin_nivel(c, ids.ORIGEN_POS_ADMIN)
        self.assertEqual(c.tipo_cliente, TipoCliente.PROFESOR)  # informativo, sin beneficio
        self.assertEqual(c.notas, "nota")
        self.assertEqual([e.tipo for e in self._eventos(c)], [ids.EVENTO_ALTA])

    def test_alta_admin_sigue_exigiendo_admin_y_rango(self) -> None:
        with self.assertRaises(PermissionError):
            ClientService.create_client(self.s, self._usuario(RolUsuario.CAJERO), "X")
        with self.assertRaises(ValueError):
            ClientService.create_client(self.s, self._usuario(RolUsuario.ADMIN), "X", descuento_preferente=Decimal("101"))

    def test_alta_rapida_de_presupuesto(self) -> None:
        tel = self._tel("09")
        previo = ids.dar_de_alta(self.s, nombre=f"Previo {self.marca}", telefono=tel, origen=ids.ORIGEN_VENTA_RAPIDA)
        c = ClientService.create_client_quick(self.s, self._usuario(RolUsuario.CAJERO), f"Presup {self.marca}", telefono=tel)
        self._assert_sin_nivel(c, ids.ORIGEN_PRESUPUESTO_KIOSKO)
        (ev,) = self._eventos(c)
        self.assertEqual(ev.tipo, ids.EVENTO_ALTA)
        self.assertEqual(ev.detalle["coincidencias"], [previo.id])


class EdicionSinNivelTests(_EnTransaccion):
    """T-B12: editar a un cliente SIN nivel no le asigna nivel ni toca su descuento."""

    def test_edicion_conserva_nivel_descuento_y_metadatos(self) -> None:
        c = ids.dar_de_alta(self.s, nombre=f"Edit {self.marca}", telefono=self._tel("10"), origen=ids.ORIGEN_VENTA_RAPIDA)
        admin = SimpleNamespace(id=None, rol=RolUsuario.ADMIN, activo=True)
        ClientService.update_client(
            self.s, admin, c, f"Editado {self.marca}", tipo_cliente=TipoCliente.MAYORISTA,
            descuento_preferente=Decimal("10.00"), telefono=self._tel("11"), notas="nueva nota",
        )
        self.s.flush()
        self._assert_sin_nivel(c, ids.ORIGEN_VENTA_RAPIDA)
        self.assertEqual(c.nombre, f"Editado {self.marca}")
        self.assertEqual(c.tipo_cliente, TipoCliente.MAYORISTA)
        self.assertEqual(c.telefono_normalizado, self._tel("11"))
        self.assertEqual(c.notas, "nueva nota")


class ChoqueDeCodigoTests(unittest.TestCase):
    """T-B4: dos sesiones generan el mismo código; la segunda reintenta y gana otro."""

    def setUp(self) -> None:
        base = _url_local()
        if base is None:
            self.skipTest("Solo corre contra la base local de prueba.")
        self.nombre = f"pos_uniformes_test_e1b_{uuid.uuid4().hex[:8]}"
        self.admin_url = base.set(database="postgres")
        admin = create_engine(self.admin_url, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{self.nombre}"'))
        admin.dispose()
        self.addCleanup(self._borrar)
        env = {k: v for k, v in os.environ.items() if k != "POS_UNIFORMES_DB_URL"}
        env.update(POS_UNIFORMES_DB_HOST=base.host, POS_UNIFORMES_DB_NAME=self.nombre, POS_UNIFORMES_AUTO_CREATE_SCHEMA="0")
        res = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=_RAIZ_PAQUETE, env=env,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.engine = create_engine(base.set(database=self.nombre))

    def _borrar(self) -> None:
        if getattr(self, "engine", None) is not None:
            self.engine.dispose()
        admin = create_engine(self.admin_url, isolation_level="AUTOCOMMIT")
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{self.nombre}" WITH (FORCE)'))
        admin.dispose()

    def test_reintento_con_exito(self) -> None:
        a = Session(self.engine)
        b = Session(self.engine)
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        ca = ids.dar_de_alta(a, nombre="PC uno", telefono=None, origen=ids.ORIGEN_VENTA_RAPIDA)  # sin confirmar aún
        resultado = {}

        def segunda_pc():
            try:
                resultado["cliente"] = ids.dar_de_alta(b, nombre="PC dos", telefono=None, origen=ids.ORIGEN_VENTA_RAPIDA)
                b.commit()
            except Exception as exc:  # pragma: no cover - se reporta abajo
                resultado["error"] = exc

        hilo = threading.Thread(target=segunda_pc)
        hilo.start()
        time.sleep(0.8)  # la segunda PC queda esperando el mismo código
        a.commit()
        hilo.join(timeout=20)
        self.assertNotIn("error", resultado, resultado.get("error"))
        cb = resultado["cliente"]
        self.assertNotEqual(ca.codigo_cliente, cb.codigo_cliente)
        with self.engine.connect() as conn:
            codigos = conn.execute(text("SELECT codigo_cliente FROM cliente ORDER BY id")).scalars().all()
            eventos = conn.execute(text("SELECT count(*) FROM cliente_evento")).scalar_one()
        self.assertEqual(len(codigos), 2)
        self.assertEqual(len(set(codigos)), 2)
        self.assertEqual(eventos, 2)


if __name__ == "__main__":
    unittest.main()
