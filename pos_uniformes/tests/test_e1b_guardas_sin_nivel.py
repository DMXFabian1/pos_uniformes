"""E1-B (R3, R4): guardas para clientes SIN nivel en la Caja y los Apartados
antiguos y en el recálculo (T-B14 a T-B21).

Sin base de datos: sesiones falsas y objetos ORM transitorios. Las reglas del
programa se fijan a los valores por omisión del código. Para cada camino se
contrasta con un cliente BASICO, que debe seguir igual que hoy.
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
from pos_uniformes.services import loyalty_service as loyalty_module
from pos_uniformes.services.apartado_service import ApartadoItemInput, ApartadoService
from pos_uniformes.services.layaway_pricing_service import resolve_layaway_client_discount_percent
from pos_uniformes.services.loyalty_service import LoyaltyProgramRules, LoyaltyService
from pos_uniformes.services.sale_checkout_service import (
    load_sale_client_checkout_snapshot,
    resolve_sale_loyalty_transition_notice,
)
from pos_uniformes.services.sale_discount_service import normalize_discount_value
from pos_uniformes.services.sale_selected_client_service import (
    load_sale_selected_client_benefit,
    load_sale_selected_client_discount_percent,
    resolve_sale_selected_client_sync_state,
)
from pos_uniformes.services.venta_service import VentaService

REGLAS = LoyaltyProgramRules(365, Decimal("3000.00"), 3, Decimal("2000.00"),
                             Decimal("5.00"), Decimal("10.00"), Decimal("15.00"), Decimal("20.00"))


class _Sesion:
    def __init__(self, clientes=(), compras=(1, "3500.00")):
        self._c = {c.id: c for c in clientes}
        self._compras = compras

    def get(self, _m, i):
        return self._c.get(int(i))

    def add(self, _o):
        pass

    def flush(self):
        pass

    def execute(self, _s):
        n, t = self._compras
        return SimpleNamespace(one=lambda: (n, Decimal(t)))

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


@contextlib.contextmanager
def _reglas():
    with patch.object(LoyaltyService, "_load_program_rules", return_value=REGLAS), patch.object(
        loyalty_module, "get_session", lambda: contextlib.nullcontext(None)
    ):
        yield


class CajaAntiguaTests(unittest.TestCase):
    def test_tb14_sin_nivel_da_cero_sin_llamar_a_discount_for_level(self) -> None:
        s = _Sesion([_cliente(1, None)])
        with _reglas(), patch.object(LoyaltyService, "discount_for_level", wraps=LoyaltyService.discount_for_level) as espia:
            pct = load_sale_selected_client_discount_percent(s, selected_client_id=1, normalize_discount_value=normalize_discount_value)
        self.assertEqual(pct, Decimal("0.00"))
        espia.assert_not_called()

    def test_tb14_contraste_basico_sigue_en_5(self) -> None:
        s = _Sesion([_cliente(1, NivelLealtad.BASICO)])
        with _reglas():
            pct = load_sale_selected_client_discount_percent(s, selected_client_id=1, normalize_discount_value=normalize_discount_value)
        self.assertEqual(pct, Decimal("5.00"))

    def test_tb15_etiqueta_sin_nivel(self) -> None:
        with _reglas():
            b = load_sale_selected_client_benefit(_Sesion([_cliente(1, None)]), selected_client_id=1,
                                                  normalize_discount_value=normalize_discount_value)
            b_basico = load_sale_selected_client_benefit(_Sesion([_cliente(1, NivelLealtad.BASICO)]), selected_client_id=1,
                                                         normalize_discount_value=normalize_discount_value)
        self.assertEqual(b.source_label, "Sin nivel")
        self.assertNotIn("asic", b.source_label)
        self.assertEqual(b_basico.source_label, "Basico")

    def test_tb15_preferente_manual_conserva_su_regla(self) -> None:
        # E1-B nunca escribe un preferente a un cliente sin nivel; si lo tuviera
        # por datos manipulados, su regla (K3) no cambia.
        with _reglas():
            pct = load_sale_selected_client_discount_percent(_Sesion([_cliente(1, None, "7.50")]), selected_client_id=1,
                                                             normalize_discount_value=normalize_discount_value)
        self.assertEqual(pct, Decimal("7.50"))

    def test_tb16_estado_de_sincronizacion_de_la_caja(self) -> None:
        with _reglas():
            sync = resolve_sale_selected_client_sync_state(_Sesion([_cliente(1, None)]), selected_client_id=1,
                                                           normalize_discount_value=normalize_discount_value)
        self.assertTrue(sync.locked)
        self.assertEqual(sync.discount_percent, Decimal("0.00"))
        self.assertEqual(sync.source_label, "Sin nivel")

    def test_tb16_contexto_de_descuento_de_la_caja(self) -> None:
        from pos_uniformes.services import sale_discount_context_service as ctx_mod

        fuente = open(ctx_mod.__file__, encoding="utf-8").read()
        # El contexto de descuento de la Caja usa la misma función protegida.
        self.assertIn("resolve_sale_selected_client_sync_state", fuente)

    def test_tb18_sin_aviso_de_nivel_despues_de_vender(self) -> None:
        c = _cliente(1, None)
        s = _Sesion([c], compras=(1, "3500.00"))
        with _reglas():
            snap = load_sale_client_checkout_snapshot(s, selected_client_id=1)
            LoyaltyService.refresh_client_level_from_sales(s, c, actor_user=ADMIN, reason="venta_confirmada")
            aviso = resolve_sale_loyalty_transition_notice(snap, build_notice=lambda *a: "AVISO")
        self.assertEqual(aviso, "")
        self.assertIsNone(c.nivel_lealtad)


class ApartadosAntiguosTests(unittest.TestCase):
    """T-B17: con un cliente sin nivel, el apartado se precia a precio de lista."""

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
        with _reglas(), self._inventario(), patch.object(ApartadoService, "obtener_variante_por_sku", return_value=self._variante()):
            return ApartadoService.crear_apartado(
                s, cajero, "AP-1", "Cliente", None, [ApartadoItemInput(sku="SKU-1", cantidad=1)], Decimal("50.00"), cliente=cliente
            )

    def test_crear_sin_nivel_conserva_precio_de_lista(self) -> None:
        ap = self._crear(_cliente(1, None))
        self.assertEqual(ap.detalles[0].precio_unitario, Decimal("100.00"))

    def test_crear_basico_sigue_con_su_descuento(self) -> None:
        ap = self._crear(_cliente(1, NivelLealtad.BASICO))
        self.assertEqual(ap.detalles[0].precio_unitario, Decimal("95.00"))

    def test_agregar_detalle_sin_nivel(self) -> None:
        c = _cliente(1, None)
        s = _Sesion([c])
        cajero = Usuario(id=2, username="caja", nombre_completo="Caja", password_hash="x", rol=RolUsuario.CAJERO, activo=True)
        ap = Apartado(folio="AP-2", cliente=c, estado=EstadoApartado.ACTIVO, cliente_nombre="C")
        with _reglas(), self._inventario(), patch.object(
            ApartadoService, "obtener_variante_por_sku", return_value=self._variante("SKU-2")
        ), patch.object(ApartadoService, "_recalcular_totales"):
            det = ApartadoService.agregar_detalle(s, ap, cajero, "SKU-2", 1)
        self.assertEqual(det.precio_unitario, Decimal("100.00"))
        self.assertEqual(resolve_layaway_client_discount_percent(s, selected_client_id=1), Decimal("0.00"))


class RecalculoTests(unittest.TestCase):
    def test_tb19_refresh_omite_sin_nivel_sin_evaluar_ni_asignar(self) -> None:
        c = _cliente(1, None)
        antes = _foto(c)
        with _reglas(), patch.object(LoyaltyService, "evaluate_auto_level") as ev, patch.object(
            LoyaltyService, "assign_level"
        ) as asg, self.assertLogs("pos_uniformes.services.loyalty_service", level="INFO") as log:
            r = LoyaltyService.refresh_client_level_from_sales(_Sesion([c]), c, actor_user=ADMIN, reason="venta_confirmada")
        self.assertIs(r, c)
        ev.assert_not_called()
        asg.assert_not_called()
        self.assertEqual(_foto(c), antes)
        self.assertIn("omitido", log.output[0])

    def test_tb19_solo_none_se_omite_y_un_error_real_sigue_fallando(self) -> None:
        # Omitir es solo para `None` exacto: un objeto sin nivel_lealtad o un
        # nivel inválido siguen fallando como hoy.
        with _reglas():
            with self.assertRaises(AttributeError):
                LoyaltyService.refresh_client_level_from_sales(_Sesion(), object(), actor_user=ADMIN, reason="x")
            # Un valor que no es `None` (p. ej. cadena vacía) NO se omite: sigue
            # el recálculo de siempre.
            raro = _cliente(1, NivelLealtad.BASICO)
            raro.nivel_lealtad = ""
            LoyaltyService.refresh_client_level_from_sales(_Sesion([raro], (0, "0")), raro, actor_user=ADMIN, reason="x")
            self.assertEqual(raro.nivel_lealtad, NivelLealtad.BASICO)

    def test_tb19_cliente_ausente_sigue_igual(self) -> None:
        self.assertIsNone(LoyaltyService.refresh_client_level_from_sales(_Sesion(), None, actor_user=ADMIN, reason="x"))

    def _venta(self, cliente, estado):
        return Venta(usuario=ADMIN, cliente=cliente, folio="V-1", estado=estado, detalles=[])

    def test_tb20_confirmar_cancelar_y_entregar_apartado(self) -> None:
        for nombre in ("confirmar", "cancelar", "apartado"):
            for nivel in (None, NivelLealtad.BASICO):
                with self.subTest(camino=nombre, nivel=nivel):
                    c = _cliente(1, nivel)
                    s = _Sesion([c], compras=(1, "3500.00"))
                    with _reglas():
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
                    if nivel is None:
                        self.assertIsNone(c.nivel_lealtad)
                        self.assertEqual(Decimal(c.descuento_preferente), Decimal("0.00"))
                        self.assertIsNone(c.nivel_asignacion_motivo)
                    else:
                        self.assertEqual(c.nivel_lealtad, NivelLealtad.LEAL)  # igual que hoy con 3500 en compras

    def test_tb21_recalcular_todos_deja_intactos_los_sin_nivel(self) -> None:
        sin = [_cliente(i, None) for i in (1, 2)]
        con = [_cliente(3, NivelLealtad.BASICO), _cliente(4, NivelLealtad.LEAL), _cliente(5, NivelLealtad.PROFESOR, tipo=TipoCliente.PROFESOR)]
        fotos = [_foto(c) for c in sin]
        with _reglas():
            resumen = LoyaltyService.recalculate_all_clients(_Sesion(sin + con, (1, "3500.00")), actor_user=ADMIN, reason="recalculo")
        self.assertEqual([_foto(c) for c in sin], fotos)
        self.assertEqual([c.nivel_lealtad for c in con], [NivelLealtad.LEAL, NivelLealtad.LEAL, NivelLealtad.PROFESOR])
        self.assertEqual(resumen["total"], 5)
        self.assertEqual(resumen["changed"], 3)  # los 3 con nivel cambian metadatos/nivel; los NULL no cuentan


if __name__ == "__main__":
    unittest.main()
