from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import unittest

from pos_uniformes.database.models import TipoMovimientoInventario
from pos_uniformes.services.inventario_service import InventarioService


def _make_variante(stock_actual: int = 10, variante_id: int = 1) -> SimpleNamespace:
    """Crea un stub de Variante con los atributos mínimos requeridos."""
    return SimpleNamespace(id=variante_id, stock_actual=stock_actual)


class _SessionStub:
    """Stub mínimo de SQLAlchemy Session para tests unitarios."""

    def __init__(self, variante_to_lock: object | None = None) -> None:
        self.added: list[object] = []
        self._variante_to_lock = variante_to_lock
        # Rastrear si se llamó scalar con with_for_update
        self.scalar_called = False

    def add(self, value: object) -> None:
        self.added.append(value)

    def scalar(self, stmt: object) -> object | None:
        """Simula SELECT ... FOR UPDATE devolviendo la variante bloqueada."""
        self.scalar_called = True
        return self._variante_to_lock


class InventarioServiceTests(unittest.TestCase):
    def test_registrar_movimiento_still_blocks_negative_stock_by_default(self) -> None:
        variante = _make_variante(stock_actual=1)
        session = _SessionStub(variante_to_lock=variante)

        with self.assertRaisesRegex(ValueError, "stock negativo"):
            InventarioService.registrar_movimiento(
                session=session,
                variante=variante,
                tipo_movimiento=TipoMovimientoInventario.SALIDA_VENTA,
                cantidad=-2,
            )

    def test_registrar_salida_venta_allows_negative_stock_when_policy_is_disabled(self) -> None:
        variante = _make_variante(stock_actual=1)
        session = _SessionStub(variante_to_lock=variante)

        with patch(
            "pos_uniformes.services.inventario_service.allow_negative_sale_stock",
            return_value=True,
        ), patch(
            "pos_uniformes.services.inventario_service.MovimientoInventario",
            side_effect=lambda **kwargs: SimpleNamespace(**kwargs),
        ):
            movimiento = InventarioService.registrar_salida_venta(
                session=session,
                variante=variante,
                cantidad=2,
                referencia="VTA-001",
                creado_por="caja",
            )

        self.assertEqual(variante.stock_actual, -1)
        self.assertEqual(movimiento.stock_anterior, 1)
        self.assertEqual(movimiento.stock_posterior, -1)
        self.assertEqual(movimiento.cantidad, -2)

    def test_entrada_en_talla_negativa_se_registra_aunque_no_alcance_a_cero(self) -> None:
        """Golpe Escolta Blanco en −20 y llegan 10: la entrada se registra y
        queda en −10. Antes se rechazaba («deje stock negativo») y la llegada
        no se podía capturar ni en la PC ni en el celular."""
        variante = _make_variante(stock_actual=-20)
        session = _SessionStub(variante_to_lock=variante)

        with patch(
            "pos_uniformes.services.inventario_service.MovimientoInventario",
            side_effect=lambda **kwargs: SimpleNamespace(**kwargs),
        ):
            movimiento = InventarioService.registrar_ingreso_compra(
                session=session, variante=variante, cantidad=10, referencia="maquilador",
            )

        self.assertEqual(variante.stock_actual, -10)
        self.assertEqual((movimiento.stock_anterior, movimiento.stock_posterior), (-20, -10))

    def test_ajuste_hacia_arriba_en_negativo_se_permite_y_hacia_abajo_no(self) -> None:
        variante = _make_variante(stock_actual=-5)
        session = _SessionStub(variante_to_lock=variante)
        with patch(
            "pos_uniformes.services.inventario_service.MovimientoInventario",
            side_effect=lambda **kwargs: SimpleNamespace(**kwargs),
        ):
            InventarioService.registrar_movimiento(
                session=session, variante=variante,
                tipo_movimiento=TipoMovimientoInventario.AJUSTE_ENTRADA, cantidad=2,
            )
            self.assertEqual(variante.stock_actual, -3)
            with self.assertRaisesRegex(ValueError, "stock negativo"):
                InventarioService.registrar_movimiento(
                    session=session, variante=variante,
                    tipo_movimiento=TipoMovimientoInventario.AJUSTE_SALIDA, cantidad=-1,
                )
        self.assertEqual(variante.stock_actual, -3)

    def test_registrar_movimiento_adquiere_lock_antes_de_modificar_stock(self) -> None:
        """registrar_movimiento debe emitir SELECT FOR UPDATE antes de leer stock_actual."""
        variante = _make_variante(stock_actual=5)
        session = _SessionStub(variante_to_lock=variante)

        with patch(
            "pos_uniformes.services.inventario_service.MovimientoInventario",
            side_effect=lambda **kwargs: SimpleNamespace(**kwargs),
        ):
            InventarioService.registrar_movimiento(
                session=session,
                variante=variante,
                tipo_movimiento=TipoMovimientoInventario.ENTRADA_COMPRA,
                cantidad=3,
            )

        self.assertTrue(
            session.scalar_called,
            "Se esperaba que scalar() fuera llamado para adquirir el row-level lock.",
        )

    def test_registrar_movimiento_lanza_si_variante_desaparece_entre_lock_y_escritura(self) -> None:
        """Si la variante fue eliminada justo antes del lock, se lanza ValueError."""
        variante = _make_variante(stock_actual=5)
        # scalar() devuelve None → la variante ya no existe
        session = _SessionStub(variante_to_lock=None)

        with self.assertRaisesRegex(ValueError, "ya no existe"):
            InventarioService.registrar_movimiento(
                session=session,
                variante=variante,
                tipo_movimiento=TipoMovimientoInventario.ENTRADA_COMPRA,
                cantidad=3,
            )



class AjusteMasivoEnNegativoTests(unittest.TestCase):
    """Ajuste masivo con la misma regla que registrar_movimiento: solo se frena lo que baja."""

    def _sesion_con_talla(self, stock: int):
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from pos_uniformes.database.connection import Base
        from pos_uniformes.database.models import Categoria, Marca, Producto, Variante

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        s = Session(engine)
        cat, marca = Categoria(nombre="Accesorios"), Marca(nombre="Genérica")
        s.add_all([cat, marca]); s.flush()
        prod = Producto(nombre="Golpe Escolta Blanco", nombre_base="Golpe Escolta Blanco", categoria_id=cat.id, marca_id=marca.id)
        s.add(prod); s.flush()
        v = Variante(producto_id=prod.id, sku="GOLPE-U", talla="Unitalla", color="Blanco", precio_venta=65, stock_actual=stock)
        s.add(v); s.flush()
        return s, v

    def test_sumar_a_una_talla_en_negativo_es_valido(self) -> None:
        from pos_uniformes.services.inventario_service import AjusteMasivoFilaInput

        s, v = self._sesion_con_talla(-20)
        prev = InventarioService.previsualizar_ajuste_masivo(
            s, [AjusteMasivoFilaInput(variante_id=v.id, valor_capturado=10)], tipo_ajuste="DELTA")
        self.assertEqual((prev.filas[0].estado, prev.filas[0].stock_final), ("VALIDO", -10))

    def test_restar_hasta_negativo_sigue_siendo_error(self) -> None:
        from pos_uniformes.services.inventario_service import AjusteMasivoFilaInput

        s, v = self._sesion_con_talla(-20)
        prev = InventarioService.previsualizar_ajuste_masivo(
            s, [AjusteMasivoFilaInput(variante_id=v.id, valor_capturado=-1)], tipo_ajuste="DELTA")
        self.assertEqual(prev.filas[0].estado, "ERROR")

if __name__ == "__main__":
    unittest.main()
