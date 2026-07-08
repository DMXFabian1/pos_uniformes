"""Tests para BodegaService — lógica de bodega, cajas y contenido."""

from __future__ import annotations

import re
import unittest

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    BodegaCaja,
    BodegaContenido,
    BodegaUbicacion,
    Categoria,
    CategoriaCaja,
    EstadoCaja,
    Marca,
    Producto,
    Variante,
)
from pos_uniformes.services.bodega_service import BodegaService


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _register_regexp(dbapi_connection, connection_record):
        # SQLite no trae REGEXP; el orden de argumentos es (pattern, value).
        dbapi_connection.create_function(
            "regexp", 2,
            lambda pat, val: re.search(pat, val or "") is not None,
        )

    Base.metadata.create_all(engine)
    return Session(engine)


def _make_ubicacion(session: Session, rack: str = "PISO", nivel: int = 1) -> BodegaUbicacion:
    """Las ubicaciones son fijas (PISO/ALMACEN); se siembran directo en BD."""
    ub = BodegaUbicacion(codigo=f"{rack}-N{nivel}", rack=rack, nivel=nivel)
    session.add(ub)
    session.flush()
    return ub


def _seed_variante(session: Session, stock: int = 20, talla: str = "T12") -> Variante:
    cat = session.query(Categoria).first()
    marca = session.query(Marca).first()
    if not cat:
        cat = Categoria(nombre="Uniformes")
        marca = Marca(nombre="Genérica")
        session.add_all([cat, marca])
        session.flush()
    prod = session.query(Producto).first()
    if not prod:
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
        sku=f"PP2-{talla}",
        talla=talla,
        color="NEGRO",
        precio_venta=350.00,
        stock_actual=stock,
    )
    session.add(variante)
    session.flush()
    return variante


class TestBodegaUbicaciones(unittest.TestCase):
    def test_listar_ordenado_por_rack_y_nivel(self) -> None:
        session = _make_session()
        _make_ubicacion(session, "PISO", 2)
        _make_ubicacion(session, "PISO", 1)
        _make_ubicacion(session, "ALMACEN", 1)

        todas = BodegaService.listar_ubicaciones(session)
        self.assertEqual(len(todas), 3)
        self.assertEqual(
            [(u.rack, u.nivel) for u in todas],
            [("ALMACEN", 1), ("PISO", 1), ("PISO", 2)],
        )

    def test_listar_filtra_inactivas(self) -> None:
        session = _make_session()
        _make_ubicacion(session, "PISO", 1)
        inactiva = _make_ubicacion(session, "ALMACEN", 1)
        inactiva.activo = False
        session.flush()

        activas = BodegaService.listar_ubicaciones(session, activas=True)
        self.assertEqual(len(activas), 1)
        self.assertEqual(activas[0].rack, "PISO")

        todas = BodegaService.listar_ubicaciones(session, activas=False)
        self.assertEqual(len(todas), 2)


class TestBodegaCajas(unittest.TestCase):
    def test_crear_caja_auto_codigo(self) -> None:
        session = _make_session()
        ub = _make_ubicacion(session, "PISO", 1)
        caja = BodegaService.crear_caja(session, CategoriaCaja.A, ub.id)
        self.assertEqual(caja.codigo, "A-P1-001")
        self.assertEqual(caja.categoria, "A")
        self.assertEqual(caja.estado, EstadoCaja.ACTIVA.value)

        historial = BodegaService.historial_caja(session, caja.id)
        self.assertEqual(len(historial), 1)
        self.assertEqual(historial[0].tipo, "CREAR_CAJA")

    def test_codigos_secuenciales(self) -> None:
        session = _make_session()
        c1 = BodegaService.crear_caja(session, CategoriaCaja.A)
        c2 = BodegaService.crear_caja(session, CategoriaCaja.A)
        c3 = BodegaService.crear_caja(session, CategoriaCaja.B)
        self.assertEqual(c1.codigo, "A-XX-001")
        self.assertEqual(c2.codigo, "A-XX-002")
        self.assertEqual(c3.codigo, "B-XX-001")

    def test_mover_caja(self) -> None:
        session = _make_session()
        ub1 = _make_ubicacion(session, "PISO", 1)
        ub2 = _make_ubicacion(session, "ALMACEN", 1)
        caja = BodegaService.crear_caja(session, CategoriaCaja.A, ub1.id)
        self.assertEqual(caja.codigo, "A-P1-001")

        BodegaService.mover_caja(session, caja.id, ub2.id)
        self.assertEqual(caja.ubicacion_id, ub2.id)
        self.assertEqual(caja.codigo, "A-A1-001")

        historial = BodegaService.historial_caja(session, caja.id)
        mover = [m for m in historial if m.tipo == "MOVER_CAJA"]
        self.assertEqual(len(mover), 1)

    def test_listar_filtro_categoria(self) -> None:
        session = _make_session()
        BodegaService.crear_caja(session, CategoriaCaja.A)
        BodegaService.crear_caja(session, CategoriaCaja.A)
        BodegaService.crear_caja(session, CategoriaCaja.B)

        cat_a = BodegaService.listar_cajas(session, categoria=CategoriaCaja.A)
        self.assertEqual(len(cat_a), 2)

        cat_b = BodegaService.listar_cajas(session, categoria=CategoriaCaja.B)
        self.assertEqual(len(cat_b), 1)

    def test_listar_filtro_estado(self) -> None:
        session = _make_session()
        BodegaService.crear_caja(session, CategoriaCaja.A)
        BodegaService.crear_caja(session, CategoriaCaja.A)
        c3 = BodegaService.crear_caja(session, CategoriaCaja.C)
        BodegaService.cambiar_estado_caja(session, c3.id, EstadoCaja.CERRADA)

        activas = BodegaService.listar_cajas(session, estado=EstadoCaja.ACTIVA)
        self.assertEqual(len(activas), 2)

        todas = BodegaService.listar_cajas(session)
        self.assertEqual(len(todas), 3)

    def test_reclasificar_caja(self) -> None:
        session = _make_session()
        caja = BodegaService.crear_caja(session, CategoriaCaja.A)
        self.assertEqual(caja.categoria, "A")

        BodegaService.reclasificar_caja(session, caja.id, CategoriaCaja.D)
        self.assertEqual(caja.categoria, "D")

        historial = BodegaService.historial_caja(session, caja.id)
        ajuste = [m for m in historial if m.tipo == "AJUSTE"]
        self.assertEqual(len(ajuste), 1)
        self.assertIn("Reclasificada", ajuste[0].observacion)


class TestBodegaContenido(unittest.TestCase):
    def _caja(self, session: Session) -> BodegaCaja:
        return BodegaService.crear_caja(session, CategoriaCaja.A)

    def test_ingresar_producto(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        caja = self._caja(session)

        contenido = BodegaService.ingresar_producto(session, caja.id, variante.id, 8)
        self.assertEqual(contenido.cantidad, 8)
        self.assertEqual(BodegaService.stock_disponible_tienda(session, variante.id), 12)

    def test_ingresar_mas_de_stock_falla(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=5)
        caja = self._caja(session)

        with self.assertRaises(ValueError):
            BodegaService.ingresar_producto(session, caja.id, variante.id, 10)

    def test_ingresar_acumula(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        caja = self._caja(session)

        BodegaService.ingresar_producto(session, caja.id, variante.id, 5)
        BodegaService.ingresar_producto(session, caja.id, variante.id, 3)

        contenido = session.query(BodegaContenido).filter_by(
            caja_id=caja.id, variante_id=variante.id
        ).one()
        self.assertEqual(contenido.cantidad, 8)

    def test_retirar_producto(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        caja = self._caja(session)
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
        caja = self._caja(session)
        BodegaService.ingresar_producto(session, caja.id, variante.id, 5)

        BodegaService.retirar_producto(session, caja.id, variante.id, 5)
        contenido = session.query(BodegaContenido).filter_by(
            caja_id=caja.id, variante_id=variante.id
        ).first()
        self.assertIsNone(contenido)

    def test_retirar_mas_de_lo_que_hay_falla(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        caja = self._caja(session)
        BodegaService.ingresar_producto(session, caja.id, variante.id, 5)

        with self.assertRaises(ValueError):
            BodegaService.retirar_producto(session, caja.id, variante.id, 10)

    def test_transferir_entre_cajas(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        c1 = BodegaService.crear_caja(session, CategoriaCaja.A)
        c2 = BodegaService.crear_caja(session, CategoriaCaja.A)
        BodegaService.ingresar_producto(session, c1.id, variante.id, 10)

        BodegaService.transferir_producto(session, c1.id, c2.id, variante.id, 4)

        cont1 = session.query(BodegaContenido).filter_by(caja_id=c1.id, variante_id=variante.id).one()
        cont2 = session.query(BodegaContenido).filter_by(caja_id=c2.id, variante_id=variante.id).one()
        self.assertEqual(cont1.cantidad, 6)
        self.assertEqual(cont2.cantidad, 4)
        self.assertEqual(BodegaService.stock_disponible_tienda(session, variante.id), 10)

    def test_ingreso_masivo(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        caja = self._caja(session)

        total = BodegaService.ingreso_masivo(
            session, caja.id,
            [{"variante_id": variante.id, "cantidad": 7}],
        )
        self.assertEqual(total, 7)


class TestBodegaBusqueda(unittest.TestCase):
    def test_buscar_variante_en_bodega(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        c1 = BodegaService.crear_caja(session, CategoriaCaja.A)
        c2 = BodegaService.crear_caja(session, CategoriaCaja.B)
        BodegaService.ingresar_producto(session, c1.id, variante.id, 5)
        BodegaService.ingresar_producto(session, c2.id, variante.id, 3)

        resultados = BodegaService.buscar_variante_en_bodega(session, variante.id)
        self.assertEqual(len(resultados), 2)
        cantidades = {r["caja_codigo"]: r["cantidad"] for r in resultados}
        self.assertEqual(cantidades["A-XX-001"], 5)
        self.assertEqual(cantidades["B-XX-001"], 3)

    def test_buscar_por_texto_agrupado(self) -> None:
        session = _make_session()
        v1 = _seed_variante(session, stock=20, talla="T10")
        v2 = _seed_variante(session, stock=15, talla="T12")
        caja = BodegaService.crear_caja(session, CategoriaCaja.A)
        BodegaService.ingresar_producto(session, caja.id, v1.id, 4)
        BodegaService.ingresar_producto(session, caja.id, v2.id, 6)

        resultados = BodegaService.buscar_por_texto_agrupado(session, "Pants")
        self.assertEqual(len(resultados), 1)
        grupo = resultados[0]
        self.assertEqual(grupo["producto"], "Pants punto 2pz")
        self.assertEqual(len(grupo["variantes"]), 2)

        tallas = {v["talla"]: v for v in grupo["variantes"]}
        self.assertEqual(tallas["T10"]["en_bodega"], 4)
        self.assertEqual(tallas["T10"]["en_tienda"], 16)
        self.assertEqual(tallas["T12"]["en_bodega"], 6)
        self.assertEqual(tallas["T12"]["en_tienda"], 9)


class TestBodegaDesglose(unittest.TestCase):
    def test_desglose_contenido_caja(self) -> None:
        session = _make_session()
        v1 = _seed_variante(session, stock=20, talla="T10")
        v2 = _seed_variante(session, stock=15, talla="T14")
        caja = BodegaService.crear_caja(session, CategoriaCaja.A)
        BodegaService.ingresar_producto(session, caja.id, v1.id, 4)
        BodegaService.ingresar_producto(session, caja.id, v2.id, 8)

        desglose = BodegaService.desglose_contenido_caja(session, caja.id)
        self.assertEqual(len(desglose), 1)
        grupo = desglose[0]
        self.assertEqual(grupo["producto"], "Pants punto 2pz")
        self.assertEqual(grupo["total"], 12)
        self.assertEqual(len(grupo["tallas"]), 2)


class TestBodegaEstadisticas(unittest.TestCase):
    def test_totales(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        BodegaService.crear_caja(session, CategoriaCaja.A)
        c2 = BodegaService.crear_caja(session, CategoriaCaja.B)
        BodegaService.ingresar_producto(session, c2.id, variante.id, 10)

        self.assertEqual(BodegaService.total_cajas_activas(session), 2)
        self.assertEqual(BodegaService.total_prendas_en_bodega(session), 10)

    def test_resumen_por_categoria(self) -> None:
        session = _make_session()
        variante = _seed_variante(session, stock=20)
        c1 = BodegaService.crear_caja(session, CategoriaCaja.A)
        c2 = BodegaService.crear_caja(session, CategoriaCaja.A)
        c3 = BodegaService.crear_caja(session, CategoriaCaja.C)
        BodegaService.ingresar_producto(session, c1.id, variante.id, 5)
        BodegaService.ingresar_producto(session, c2.id, variante.id, 3)

        resumen = BodegaService.resumen_por_categoria(session)
        por_cat = {r["categoria"]: r for r in resumen}
        self.assertEqual(por_cat["A"]["cajas"], 2)
        self.assertEqual(por_cat["A"]["prendas"], 8)
        self.assertEqual(por_cat["C"]["cajas"], 1)
        self.assertEqual(por_cat["C"]["prendas"], 0)


if __name__ == "__main__":
    unittest.main()
