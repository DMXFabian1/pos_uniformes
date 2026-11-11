"""E1-C5 (T-N8): script de archivado. Solo contra la base local de prueba,
dentro de una transacción que se revierte. Nunca contra la tienda.
"""

from __future__ import annotations

import io
import unittest
import uuid
from contextlib import redirect_stdout
from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Cliente, ClienteEvento, LibretaVenta, RolUsuario, Usuario
from pos_uniformes.scripts import archivar_clientes_prueba as script
from pos_uniformes.services.clientes import identidad_service as ids
from pos_uniformes.utils.config import settings
from tests.base_por_trabajador import es_base_de_prueba_local

MOTIVO = "Fichas de prueba previas a E1-C"


class ArchivarClientesPruebaTests(unittest.TestCase):
    def setUp(self) -> None:
        url = make_url(settings.database_url)
        if not es_base_de_prueba_local(url):
            self.skipTest("Solo corre contra la base local de prueba.")
        self.engine = create_engine(url)
        self.addCleanup(self.engine.dispose)
        self.conn = self.engine.connect()
        self.addCleanup(self.conn.close)
        self.tx = self.conn.begin()
        self.addCleanup(self.tx.rollback)
        self.s = Session(bind=self.conn, join_transaction_mode="create_savepoint")
        self.addCleanup(self.s.close)
        self.admin = Usuario(username=f"e1c5_{uuid.uuid4().hex[:6]}", nombre_completo="Admin", password_hash="x",
                             rol=RolUsuario.ADMIN, activo=True)
        self.cajero = Usuario(username=f"e1c5c_{uuid.uuid4().hex[:6]}", nombre_completo="Cajero", password_hash="x",
                              rol=RolUsuario.CAJERO, activo=True)
        self.s.add_all([self.admin, self.cajero])
        self.s.flush()
        base = uuid.uuid4().int % 10**6
        self.fichas = [
            ids.dar_de_alta(self.s, nombre=f"Prueba {i}", telefono=f"66{base:06d}{i:02d}", origen=ids.ORIGEN_POS_ADMIN,
                            usuario_id=self.admin.id)
            for i in range(3)
        ]
        self.fichas[1].activo = False
        self.s.add(LibretaVenta(employee_code="E01", employee_name="Lupita", tipo="venta", piezas=1,
                                monto_total=Decimal("100.00"), monto_neto=Decimal("100.00"), detalle=[],
                                cliente_id=self.fichas[0].id))
        self.s.flush()
        self.ids = [int(c.id) for c in self.fichas]

    def _foto(self):
        return [(c.id, c.codigo_cliente, c.nombre, c.telefono, c.nivel_lealtad, Decimal(c.descuento_preferente))
                for c in self.s.scalars(select(Cliente).where(Cliente.id.in_(self.ids)).order_by(Cliente.id))]

    def test_simulacion_no_escribe(self) -> None:
        antes = self._foto()
        eventos = self.s.scalar(select(func.count(ClienteEvento.id)))
        r = script.ejecutar(self.s, usuario_id=self.admin.id, motivo=MOTIVO, ids=self.ids)
        self.assertFalse(r.aplicado)
        self.assertEqual((r.candidatas, r.a_cambiar, r.omitidas, r.con_libreta), (3, 3, 0, 1))
        self.assertEqual(r.ids_cambiados, [])
        self.assertEqual(self._foto(), antes)
        self.assertEqual(self.s.scalar(select(func.count(ClienteEvento.id))), eventos)
        self.assertTrue(all(c.archivado_en is None for c in self.fichas))
        self.assertIn("SIMULACION", r.texto())

    def test_aplicar_archiva_sin_borrar_y_es_idempotente(self) -> None:
        antes = self._foto()
        r = script.ejecutar(self.s, usuario_id=self.admin.id, motivo=MOTIVO, ids=self.ids, aplicar=True)
        self.assertEqual(r.ids_cambiados, self.ids)
        self.assertEqual(self._foto(), antes, "no cambia identidad, nivel ni descuento")
        for c in self.fichas:
            self.assertIsNotNone(c.archivado_en)
            self.assertEqual(c.archivado_motivo, MOTIVO)
            self.assertFalse(c.activo)
        libreta = self.s.scalar(select(LibretaVenta).where(LibretaVenta.cliente_id == self.fichas[0].id))
        self.assertIsNotNone(libreta, "la Libreta conserva su cliente")
        encontrados = {x.id for x in ids.buscar_clientes(self.s, self.fichas[0].codigo_cliente)}
        self.assertNotIn(self.fichas[0].id, encontrados, "archivada ya no aparece en la búsqueda")

        otra = script.ejecutar(self.s, usuario_id=self.admin.id, motivo=MOTIVO, ids=self.ids, aplicar=True)
        self.assertEqual((otra.a_cambiar, otra.omitidas), (0, 3))
        archivados = self.s.scalar(
            select(func.count(ClienteEvento.id)).where(ClienteEvento.cliente_id.in_(self.ids), ClienteEvento.tipo == "archivado")
        )
        self.assertEqual(archivados, 3)

    def test_desarchivar_regresa_el_estado_previo(self) -> None:
        script.ejecutar(self.s, usuario_id=self.admin.id, motivo=MOTIVO, ids=self.ids, aplicar=True)
        r = script.ejecutar(self.s, usuario_id=self.admin.id, motivo="Era cliente real", ids=self.ids,
                            desarchivar=True, aplicar=True)
        self.assertEqual(r.a_cambiar, 3)
        self.assertEqual([bool(c.activo) for c in self.fichas], [True, False, True])
        self.assertTrue(all(c.archivado_en is None for c in self.fichas))

    def test_todos_incluye_cada_ficha_existente(self) -> None:
        # «Todos» recorre cada ficha de la base compartida. Con la suite en
        # paralelo, otra prueba podía borrar una ficha a media pasada
        # (StaleDataError). El candado deja fuera altas y bajas ajenas hasta
        # que esta transacción se revierte; las demás solo esperan.
        self.s.execute(text("SET LOCAL lock_timeout = '30s'"))
        self.s.execute(text("LOCK TABLE cliente IN SHARE ROW EXCLUSIVE MODE"))
        total = self.s.scalar(select(func.count(Cliente.id)))
        r = script.ejecutar(self.s, usuario_id=self.admin.id, motivo=MOTIVO, todos=True, aplicar=True)
        self.assertEqual(r.candidatas, total)
        self.assertEqual(self.s.scalar(select(func.count(Cliente.id)).where(Cliente.archivado_en.is_(None))), 0)
        self.assertEqual(self.s.scalar(select(func.count(Cliente.id))), total, "no se borró ninguna ficha")

    def test_validaciones(self) -> None:
        with self.assertRaises(PermissionError):
            script.ejecutar(self.s, usuario_id=self.cajero.id, motivo=MOTIVO, ids=self.ids)
        with self.assertRaises(ValueError):
            script.ejecutar(self.s, usuario_id=self.admin.id, motivo="x", ids=self.ids)
        with self.assertRaises(ValueError):
            script.ejecutar(self.s, usuario_id=self.admin.id, motivo=MOTIVO)
        r = script.ejecutar(self.s, usuario_id=self.admin.id, motivo=MOTIVO, ids=[self.ids[0], 999_999_999])
        self.assertEqual(r.no_encontradas, [999_999_999])

    def test_main_sin_confirmar_base_no_escribe(self) -> None:
        class _Ctx:
            def __enter__(inner):
                return self.s

            def __exit__(inner, *a):
                return False

        argv = ["--ids", ",".join(map(str, self.ids)), "--motivo", MOTIVO, "--usuario-id", str(self.admin.id), "--aplicar"]
        salida = io.StringIO()
        with patch("pos_uniformes.database.connection.get_session", return_value=_Ctx()), redirect_stdout(salida):
            codigo = script.main(argv + ["--confirmo-base", "otra_base"])
        self.assertEqual(codigo, 2)
        self.assertIn("Detenido", salida.getvalue())
        self.assertTrue(all(c.archivado_en is None for c in self.fichas))


if __name__ == "__main__":
    unittest.main()
