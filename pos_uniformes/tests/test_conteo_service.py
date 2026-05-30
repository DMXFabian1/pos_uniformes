"""Tests para conteo_service — el conteo opera SOLO sobre stock de tienda.

Regla de negocio: contar en tienda nunca debe ver ni afectar bodega/piso.
La diferencia se calcula contra stock_tienda (= stock_actual - bodega - piso),
y al confirmar el ajuste solo se mueve la porción de tienda (stock_actual),
dejando intacto el contenido físico en cajas de bodega.
"""

from __future__ import annotations

import unittest

from sqlalchemy import create_engine, func, select
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
from pos_uniformes.services.conteo_service import (
    confirmar_ajustes_lote,
    registrar_conteo,
)


def _make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_variante(session: Session, stock_actual: int = 20) -> Variante:
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
        stock_actual=stock_actual,
    )
    session.add(variante)
    session.flush()
    return variante


def _meter_en_bodega(session: Session, variante: Variante, cantidad: int) -> None:
    """Mete `cantidad` piezas en una caja con ubicación real (rack != PISO)."""
    ub = BodegaUbicacion(codigo="A1-N1", rack="A1", nivel=1)
    session.add(ub)
    session.flush()
    caja = BodegaCaja(
        codigo="A-001",
        categoria="A",
        ubicacion_id=ub.id,
        estado=EstadoCaja.ACTIVA.value,
    )
    session.add(caja)
    session.flush()
    session.add(BodegaContenido(caja_id=caja.id, variante_id=variante.id, cantidad=cantidad))
    session.flush()


class TestConteoScopeTienda(unittest.TestCase):
    def test_diferencia_se_mide_contra_tienda_no_total(self) -> None:
        """Bug crítico: con stock en bodega, contar lo de tienda no debe
        producir diferencia falsa contra el total."""
        session = _make_session()
        v = _seed_variante(session, stock_actual=20)
        _meter_en_bodega(session, v, 8)  # bodega=8 -> tienda=12

        # El usuario cuenta 12 en tienda (coincide con el sistema)
        conteo = registrar_conteo(session, v.id, stock_fisico=12, contado_por="Ana")

        # stock_sistema registrado debe ser el de tienda (12), no el total (20)
        self.assertEqual(conteo.stock_sistema, 12)
        # Y por tanto NO hay diferencia (antes daba 12 - 20 = -8)
        self.assertEqual(conteo.diferencia, 0)

    def test_diferencia_real_en_tienda(self) -> None:
        """Si se cuenta de más en tienda, la diferencia es contra tienda."""
        session = _make_session()
        v = _seed_variante(session, stock_actual=20)
        _meter_en_bodega(session, v, 8)  # tienda=12

        conteo = registrar_conteo(session, v.id, stock_fisico=15, contado_por="Ana")
        self.assertEqual(conteo.stock_sistema, 12)
        self.assertEqual(conteo.diferencia, 3)  # 15 - 12, no 15 - 20

    def test_ajuste_solo_mueve_tienda_no_toca_bodega(self) -> None:
        """Confirmar el ajuste solo cambia la porción de tienda; el contenido
        físico de bodega queda intacto."""
        session = _make_session()
        v = _seed_variante(session, stock_actual=20)
        _meter_en_bodega(session, v, 8)  # bodega=8, tienda=12

        conteo = registrar_conteo(session, v.id, stock_fisico=15, contado_por="Ana")
        session.flush()
        ajustados, _omitidos = confirmar_ajustes_lote(session, [conteo.id], "ADMIN")
        session.flush()

        self.assertEqual(ajustados, 1)
        session.refresh(v)
        # stock_actual sube exactamente la diferencia de tienda (+3): 20 -> 23
        self.assertEqual(v.stock_actual, 23)
        # La bodega física NO se tocó: sigue habiendo 8 piezas en la caja
        total_bodega = session.scalar(
            select(func.coalesce(func.sum(BodegaContenido.cantidad), 0))
            .where(BodegaContenido.variante_id == v.id)
        )
        self.assertEqual(total_bodega, 8)

    def test_sin_bodega_tienda_igual_a_total(self) -> None:
        """Sin stock en bodega, tienda == total (no hay regresión)."""
        session = _make_session()
        v = _seed_variante(session, stock_actual=10)

        conteo = registrar_conteo(session, v.id, stock_fisico=10, contado_por="Ana")
        self.assertEqual(conteo.stock_sistema, 10)
        self.assertEqual(conteo.diferencia, 0)


if __name__ == "__main__":
    unittest.main()
