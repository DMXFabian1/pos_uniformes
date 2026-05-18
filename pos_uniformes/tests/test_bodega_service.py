"""Tests para BodegaService — lógica de bodega, cajas y contenido."""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    BodegaCaja,
    BodegaContenido,
    BodegaUbicacion,
    Categoria,
    EstadoCaja,
    Marca,
    Producto,
    Variante,
)
from pos_uniformes.services.bodega_service import BodegaService


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_variante(session: Session, stock: int = 20) -> Variante:
    cat = Categoria(nombre="Uniformes")
    marca = Marca(nombre="Genérica")
    session.add_all([cat, marca])
    session.flush()
    prod = Producto(
        nombre="Pants punto 2pz",
        nombre_base="Pants punto 2pz",
        categoria_id=cat.id,
        marca_id=marca.id,
    )
    session.add(prod)
    session.flush()
    variante = Variante(
        producto_id=prod.id,
        sku="PP2-T12",
        talla="T12",
        color="NEGRO",
        precio_venta=350.00,
        stock_actual=stock,
    )
    session.add(variante)
    session.flush()
    return variante


class TestBodegaUbicaciones(unittest.TestCase):
    def test_crear_y_listar(self) -> None:
        session = _make_session()
        ub = BodegaService.crear_ubicacion(session, "A1", 2)
        self.assertEqual(ub.codigo, "A1-N2")
        self.assertEqual(ub.rack, "A1")
        self.assertEqual(ub.nivel, 2)

        todas = BodegaService.listar_ubicaciones(session)
        self.assertEqual(len(todas), 1)

    def test_desactivar(self) -> None:
        session = _make_session()
        ub = BodegaService.crear_ubicacion(session, "B1", 1)
        BodegaService.desactivar_ubicacion(session, ub.id)
        activas = BodegaService.listar_ubicaciones(session, activas=True)
        self.assertEqual(len(activas), 0)


class TestBodegaCajas(unittest.TestCase):
    def test_crear_caja_registra_movimiento(self) -> None:
        session = _make_session()
        ub = BodegaService.crear_ubicacion(session, "A1", 1)
        caja = BodegaService.crear_caja(session, "B-001", ub.id)
        self.assertEqual(caja.codigo, "B-001")
        self.assertEqual(caja.estado, EstadoCaja.ACTIVA.value)

        historial = BodegaService.historial_caja(session, caja.id)
        self.assertEqual(len(historial), 1)
        self.assertEqual(historial[0].tipo, "CREAR_CAJA")

    def test_mover_caja(self) -> None:
        session = _make_session()
        ub1 = BodegaService.crear_ubicacion(session, "A1", 1)
        ub2 = BodegaService.crear_ubicacion(session, "A1", 2)
        caja = BodegaService.crear_caja(session, "B-002", ub1.id)

        BodegaService.mover_caja(session, caja.id, ub2.id)
        self.assertEqual(caja.ubicacion_id, ub2.id)

        historial = BodegaService.historial_caja(session, caja.id)
        mover = [m for m in historial if m.tipo == "MOVER_CAJA"]
        self.assertEqual(len(mover), 1)

    def test_listar_filtros(self) -> None:
        session = _make_session()
        BodegaService.crear_caja(session, "B-010")
        BodegaService.crear_caja(session, "B-020")
        c3 = BodegaService.crear_caja(session, "B-030")
        BodegaService.cambiar_estado_caja(session, c3.id, EstadoCaja.CERRADA)

        activas = BodegaService.listar_cajas(session, estado=EstadoCaja.ACTIVA)
        self.assertEqual(len(activas), 2)

        todas = BodegaService.listar_cajas(session)
        self.assertEqual(len(todas), 3)


class TestBodegaContenido(unittest.TestCase):
    def test_ingresar_producto(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        caja = BodegaService.crear_caja(session, "B-001")

        contenido = BodegaService.ingresar_producto(session, caja.id, variante.id, 8)
        self.assertEqual(contenido.cantidad, 8)
        self.assertEqual(BodegaService.stock_disponible_tienda(session, variante.id), 12)

    def test_ingresar_mas_de_stock_falla(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=5)
        caja = BodegaService.crear_caja(session, "B-001")

        with self.assertRaises(ValueError):
            BodegaService.ingresar_producto(session, caja.id, variante.id, 10)

    def test_ingresar_acumula(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        caja = BodegaService.crear_caja(session, "B-001")

        BodegaService.ingresar_producto(session, caja.id, variante.id, 5)
        BodegaService.ingresar_producto(session, caja.id, variante.id, 3)

        contenido = session.query(BodegaContenido).filter_by(
            caja_id=caja.id, variante_id=variante.id
        ).one()
        self.assertEqual(contenido.cantidad, 8)

    def test_retirar_producto(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        caja = BodegaService.crear_caja(session, "B-001")
        BodegaService.ingresar_producto(session, caja.id, variante.id, 10)

        BodegaService.retirar_producto(session, caja.id, variante.id, 4)
        contenido = session.query(BodegaContenido).filter_by(
            caja_id=caja.id, variante_id=variante.id
        ).one()
        self.assertEqual(contenido.cantidad, 6)
        self.assertEqual(BodegaService.stock_disponible_tienda(session, variante.id), 14)

    def test_retirar_todo_elimina_fila(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        caja = BodegaService.crear_caja(session, "B-001")
        BodegaService.ingresar_producto(session, caja.id, variante.id, 5)

        BodegaService.retirar_producto(session, caja.id, variante.id, 5)
        contenido = session.query(BodegaContenido).filter_by(
            caja_id=caja.id, variante_id=variante.id
        ).first()
        self.assertIsNone(contenido)

    def test_retirar_mas_de_lo_que_hay_falla(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        caja = BodegaService.crear_caja(session, "B-001")
        BodegaService.ingresar_producto(session, caja.id, variante.id, 5)

        with self.assertRaises(ValueError):
            BodegaService.retirar_producto(session, caja.id, variante.id, 10)

    def test_transferir_entre_cajas(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        c1 = BodegaService.crear_caja(session, "B-001")
        c2 = BodegaService.crear_caja(session, "B-002")
        BodegaService.ingresar_producto(session, c1.id, variante.id, 10)

        BodegaService.transferir_producto(session, c1.id, c2.id, variante.id, 4)

        cont1 = session.query(BodegaContenido).filter_by(caja_id=c1.id, variante_id=variante.id).one()
        cont2 = session.query(BodegaContenido).filter_by(caja_id=c2.id, variante_id=variante.id).one()
        self.assertEqual(cont1.cantidad, 6)
        self.assertEqual(cont2.cantidad, 4)
        # Stock en tienda no cambia (sigue siendo 10 en bodega total)
        self.assertEqual(BodegaService.stock_disponible_tienda(session, variante.id), 10)

    def test_ingreso_masivo(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        caja = BodegaService.crear_caja(session, "B-001")

        total = BodegaService.ingreso_masivo(
            session, caja.id,
            [{"variante_id": variante.id, "cantidad": 7}],
        )
        self.assertEqual(total, 7)


class TestBodegaBusqueda(unittest.TestCase):
    def test_buscar_variante_en_bodega(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        c1 = BodegaService.crear_caja(session, "B-001")
        c2 = BodegaService.crear_caja(session, "B-002")
        BodegaService.ingresar_producto(session, c1.id, variante.id, 5)
        BodegaService.ingresar_producto(session, c2.id, variante.id, 3)

        resultados = BodegaService.buscar_variante_en_bodega(session, variante.id)
        self.assertEqual(len(resultados), 2)
        cantidades = {r["caja_codigo"]: r["cantidad"] for r in resultados}
        self.assertEqual(cantidades["B-001"], 5)
        self.assertEqual(cantidades["B-002"], 3)


class TestBodegaEstadisticas(unittest.TestCase):
    def test_totales(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        BodegaService.crear_caja(session, "B-001")
        c2 = BodegaService.crear_caja(session, "B-002")
        BodegaService.ingresar_producto(session, c2.id, variante.id, 10)

        self.assertEqual(BodegaService.total_cajas_activas(session), 2)
        self.assertEqual(BodegaService.total_prendas_en_bodega(session), 10)


if __name__ == "__main__":
    unittest.main()
