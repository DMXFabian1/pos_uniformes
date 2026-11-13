"""Guardas de la Caja y los Apartados antiguos sin el nivel viejo.

E1-B (R3, R4) protegía a los clientes SIN nivel. 2026-11-12: «el nivel viejo
retíralo» (Daniel). Ahora ningún cliente, tenga o no `nivel_lealtad`, recibe
% por ese nivel ni por `descuento_preferente`, y cobrar, entregar un apartado
o cancelar una venta ya no tocan el nivel. Las columnas siguen en la base.

Sin base de datos: sesiones falsas y objetos ORM transitorios.
"""

from __future__ import annotations

import contextlib
import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from pos_uniformes.database.models import (
    Apartado,
    ApartadoDetalle,
    Cliente,
    EstadoApartado,
    EstadoVenta,
    NivelLealtad,
    Producto,
    RolUsuario,
    TipoCliente,
    Usuario,
    Variante,
    Venta,
    VentaDetalle,
)
from pos_uniformes.services.apartado_service import ApartadoItemInput, ApartadoService
from pos_uniformes.services.layaway_pricing_service import resolve_layaway_client_discount_percent
from pos_uniformes.services.sale_discount_service import normalize_discount_value
from pos_uniformes.services.sale_selected_client_service import (
    CLIENTE_LABEL,
    load_sale_selected_client_benefit,
    load_sale_selected_client_discount_percent,
    resolve_sale_selected_client_sync_state,
)
from pos_uniformes.services.venta_service import VentaService

NIVELES = (None, NivelLealtad.BASICO, NivelLealtad.LEAL, NivelLealtad.PROFESOR, NivelLealtad.MAYORISTA)


class _Sesion:
    def __init__(self, clientes=()):
        self._c = {c.id: c for c in clientes}

    def get(self, _m, i):
        return self._c.get(int(i))

    def add(self, _o):
        pass

    def flush(self):
        pass

    def execute(self, _s):  # si alguien todavía consultara ventas, que se note
        raise AssertionError("No debe consultar ventas para revisar el nivel")

    def scalars(self, _s):
        return SimpleNamespace(all=lambda: list(self._c.values()))


def _cliente(i, nivel, pref="0.00", tipo=TipoCliente.GENERAL):
    return Cliente(id=i, codigo_cliente=f"CLI-{i:06d}", nombre=f"C{i}", tipo_cliente=tipo,
                   descuento_preferente=Decimal(pref), nivel_lealtad=nivel, activo=True,
                   nivel_asignado_por_user_id=None, nivel_asignado_por_rol=None, nivel_asignacion_motivo=None)


def _foto(c):
    return (c.nivel_lealtad, Decimal(c.descuento_preferente), c.nivel_asignado_por_user_id,
            c.nivel_asignado_por_rol, c.nivel_asignacion_motivo)


ADMIN = Usuario(id=1, username="admin", nombre_completo="Admin", password_hash="x", rol=RolUsuario.ADMIN, activo=True)


class CajaAntiguaTests(unittest.TestCase):
    def test_ningun_nivel_da_descuento_en_la_caja(self) -> None:
        for nivel in NIVELES:
            for pref in ("0.00", "7.50", "20.00"):
                with self.subTest(nivel=nivel, preferente=pref):
                    s = _Sesion([_cliente(1, nivel, pref)])
                    pct = load_sale_selected_client_discount_percent(
                        s, selected_client_id=1, normalize_discount_value=normalize_discount_value
                    )
                    self.assertEqual(pct, Decimal("0.00"))

    def test_la_etiqueta_ya_no_dice_el_nivel_viejo(self) -> None:
        for nivel in NIVELES:
            with self.subTest(nivel=nivel):
                b = load_sale_selected_client_benefit(_Sesion([_cliente(1, nivel)]), selected_client_id=1,
                                                      normalize_discount_value=normalize_discount_value)
                self.assertEqual(b.source_label, CLIENTE_LABEL)

    def test_estado_de_sincronizacion_de_la_caja(self) -> None:
        sync = resolve_sale_selected_client_sync_state(_Sesion([_cliente(1, NivelLealtad.MAYORISTA, "20.00")]),
                                                       selected_client_id=1,
                                                       normalize_discount_value=normalize_discount_value)
        self.assertTrue(sync.locked)
        self.assertEqual(sync.discount_percent, Decimal("0.00"))
        self.assertEqual(sync.source_label, CLIENTE_LABEL)

    def test_sin_cliente_sigue_sin_bloqueo(self) -> None:
        sync = resolve_sale_selected_client_sync_state(_Sesion(), selected_client_id=None,
                                                       normalize_discount_value=normalize_discount_value)
        self.assertFalse(sync.locked)
        self.assertEqual(sync.discount_percent, Decimal("0.00"))

    # 2026-11-12: se quitaron las pruebas del contexto de descuento y del
    # snapshot de cobro de la Caja antigua: esos módulos se retiraron con ella.


class ApartadosAntiguosTests(unittest.TestCase):
    """Con cualquier nivel, el apartado se precia a precio de lista."""

    def _variante(self, sku="SKU-1"):
        return Variante(sku=sku, precio_venta=Decimal("100.00"), activo=True, producto=Producto(nombre="Pants"))

    @contextlib.contextmanager
    def _inventario(self):
        with patch("pos_uniformes.services.apartado_service.InventarioService.validar_stock_disponible"), patch(
            "pos_uniformes.services.apartado_service.InventarioService.registrar_reserva_apartado"
        ):
            yield

    def _crear(self, cliente):
        s = _Sesion([cliente])
        cajero = Usuario(id=2, username="caja", nombre_completo="Caja", password_hash="x", rol=RolUsuario.CAJERO, activo=True)
        with self._inventario(), patch.object(ApartadoService, "obtener_variante_por_sku", return_value=self._variante()):
            return ApartadoService.crear_apartado(
                s, cajero, "AP-1", "Cliente", None, [ApartadoItemInput(sku="SKU-1", cantidad=1)], Decimal("50.00"), cliente=cliente
            )

    def test_crear_con_cualquier_nivel_es_precio_de_lista(self) -> None:
        for nivel in NIVELES:
            with self.subTest(nivel=nivel):
                ap = self._crear(_cliente(1, nivel, "7.50"))
                self.assertEqual(ap.detalles[0].precio_unitario, Decimal("100.00"))

    def test_agregar_detalle_es_precio_de_lista(self) -> None:
        c = _cliente(1, NivelLealtad.PROFESOR, "15.00", TipoCliente.PROFESOR)
        s = _Sesion([c])
        cajero = Usuario(id=2, username="caja", nombre_completo="Caja", password_hash="x", rol=RolUsuario.CAJERO, activo=True)
        ap = Apartado(folio="AP-2", cliente=c, estado=EstadoApartado.ACTIVO, cliente_nombre="C")
        with self._inventario(), patch.object(
            ApartadoService, "obtener_variante_por_sku", return_value=self._variante("SKU-2")
        ), patch.object(ApartadoService, "_recalcular_totales"):
            det = ApartadoService.agregar_detalle(s, ap, cajero, "SKU-2", 1)
        self.assertEqual(det.precio_unitario, Decimal("100.00"))
        self.assertEqual(resolve_layaway_client_discount_percent(s, selected_client_id=1), Decimal("0.00"))


class VentaNoTocaNivelTests(unittest.TestCase):
    def _venta(self, cliente, estado):
        return Venta(usuario=ADMIN, cliente=cliente, folio="V-1", estado=estado, detalles=[])

    def test_confirmar_cancelar_y_entregar_apartado(self) -> None:
        for nombre in ("confirmar", "cancelar", "apartado"):
            for nivel in NIVELES:
                with self.subTest(camino=nombre, nivel=nivel):
                    c = _cliente(1, nivel, "5.00")
                    antes = _foto(c)
                    s = _Sesion([c])
                    if nombre == "confirmar":
                        v = self._venta(c, EstadoVenta.BORRADOR)
                        v.detalles.append(VentaDetalle(variante=None, cantidad=1, precio_unitario=Decimal("1"),
                                                       subtotal_linea=Decimal("1")))
                        with patch.object(VentaService, "_validar_usuario_venta"):
                            VentaService.confirmar_venta(s, v)
                    elif nombre == "cancelar":
                        VentaService.cancelar_venta(s, self._venta(c, EstadoVenta.CONFIRMADA), ADMIN)
                    else:
                        variante = Variante(sku="SKU-9", precio_venta=Decimal("100"), producto=Producto(nombre="Pants"))
                        ap = Apartado(folio="AP-9", cliente=c, total=Decimal("100.00"))
                        ap.detalles.append(ApartadoDetalle(variante=variante, cantidad=1, precio_unitario=Decimal("100.00"),
                                                           subtotal_linea=Decimal("100.00")))
                        VentaService.crear_confirmada_desde_apartado(s, ADMIN, ap, "V-AP-9")
                    self.assertEqual(_foto(c), antes)


class ModuloRetiradoTests(unittest.TestCase):
    def test_loyalty_service_ya_no_existe(self) -> None:
        with self.assertRaises(ModuleNotFoundError):
            __import__("pos_uniformes.services.loyalty_service")


if __name__ == "__main__":
    unittest.main()
