"""E6 (Daniel, 2026-11-10): las empleadas compran con descuento según su esfuerzo.

- Las comisiones de un mes dan el % con el que compran el mes siguiente.
- Sus propias compras no cuentan para la meta.
- Tope al mes (precio de lista) con su nivel; de ahí, el 5 % base.
- La promo 3pz se queda con el 5 % base.
- En uniforme, a lo más 10 % (2026-11-11); la ropa casual llega a su nivel.

Reglas puras, la Libreta en SQLite en memoria y el kiosko sin base.
"""

from __future__ import annotations

import os
import unittest
import uuid
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import ConfiguracionNegocio, Empleada, LibretaVenta, NivelDescuentoEmpleada
from pos_uniformes.services import incentivo_empleada_service as inc
from pos_uniformes.services import libreta_local_queue_service as cola
from pos_uniformes.services import libreta_service as lib

D = Decimal
N = inc.Nivel
NIVELES = [N(0, D("5")), N(150, D("10")), N(250, D("15")), N(350, D("20"))]

CHAMARRA = {"sku": "C1", "nombre": "Chamarra", "talla": "M", "precio": D("400"), "cantidad": 1,
            "categoria": "Ropa casual"}
SUDADERA = {"sku": "S1", "nombre": "Sudadera", "talla": "12", "precio": D("600"), "cantidad": 1,
            "categoria": "Básico"}
PLAYERA_PROMO = {"sku": "PL", "nombre": "Playera promo", "talla": "8", "precio": D("100"), "cantidad": 1,
                 "sports_uniform_role": "playera", "categoria": "Deportivo"}


def _local(y, m, d, h=12) -> datetime:
    return datetime(y, m, d, h).astimezone()


class ReglasTests(unittest.TestCase):
    def test_nivel_y_lo_que_falta(self) -> None:
        self.assertEqual(inc.nivel_para(0, NIVELES).porcentaje, D("5"))
        self.assertEqual(inc.nivel_para(149, NIVELES).porcentaje, D("5"))
        self.assertEqual(inc.nivel_para(150, NIVELES).porcentaje, D("10"))
        self.assertEqual(inc.nivel_para(999, NIVELES).porcentaje, D("20"))
        self.assertEqual(inc.siguiente_nivel(200, NIVELES), N(250, D("15")))
        self.assertIsNone(inc.siguiente_nivel(350, NIVELES))

    def test_meses(self) -> None:
        self.assertEqual(inc.mes_anterior(date(2027, 1, 15)), date(2026, 12, 1))
        self.assertEqual(inc.mes_siguiente(date(2026, 12, 3)), date(2027, 1, 1))
        self.assertEqual(inc.ultimo_dia(date(2026, 2, 10)), date(2026, 2, 28))

    def test_validar(self) -> None:
        lista, tope = inc.validar(list(reversed(NIVELES)), 3000)
        self.assertEqual(lista, NIVELES)
        self.assertEqual(tope, D("3000.00"))
        malos = [
            ([], "al menos"),
            ([N(10, D("5"))], "empezar en 0"),
            ([N(0, D("5")), N(0, D("10"))], "dos niveles"),
            ([N(0, D("5")), N(100, D("5"))], "más descuento"),
            ([N(0, D("5")), N(100, D("40"))], "de 0 a 30"),
        ]
        for niveles, texto in malos:
            with self.subTest(texto=texto), self.assertRaisesRegex(inc.NivelesInvalidos, texto):
                inc.validar(niveles, 0)
        with self.assertRaisesRegex(inc.NivelesInvalidos, "negativo"):
            inc.validar(NIVELES, -1)

    def test_repartir_respeta_tope_y_promo(self) -> None:
        items = [CHAMARRA, SUDADERA, PLAYERA_PROMO]
        # La sudadera es uniforme: se queda en 10 % aunque su nivel sea 15.
        self.assertEqual(inc.repartir(items, pct_nivel=15, restante=None), [D("15"), D("10"), D("5")])
        self.assertEqual(inc.repartir(items, pct_nivel=20, restante=None), [D("20"), D("10"), D("5")])
        self.assertEqual(inc.repartir(items, pct_nivel=10, restante=None), [D("10"), D("10"), D("5")])
        # Cabe la chamarra (400); la sudadera (600) ya no cabe en los 500 que quedan.
        self.assertEqual(inc.repartir(items, pct_nivel=15, restante=D("500")), [D("15"), D("5"), D("5")])
        self.assertEqual(inc.repartir(items, pct_nivel=5, restante=None), [D("5"), D("5"), D("5")])
        self.assertEqual(inc.repartir(items, pct_nivel=15, restante=D("0")), [D("5"), D("5"), D("5")])

    def test_que_es_uniforme(self) -> None:
        for cat in ("Oficial", "Deportivo", "Uniformes", "Escolta", "Básico", "", None):
            self.assertTrue(inc.es_uniforme({"categoria": cat}), cat)
        self.assertTrue(inc.es_uniforme({}), "lo que no se sabe cuenta como uniforme")
        for cat in ("Ropa casual", "Temporada", "Accesorio", "Ropa interior", "Deportivo casual", "  ropa  CASUAL "):
            self.assertFalse(inc.es_uniforme({"categoria": cat}), cat)

    def test_importe_con_nivel(self) -> None:
        detalle = [
            {"precio": "400", "cantidad": 2, "desc_empleada_pct": "15"},
            {"precio": "100", "cantidad": 1, "desc_empleada_pct": "5"},
            {"precio": "300", "cantidad": 1},
        ]
        self.assertEqual(inc.importe_con_nivel(detalle), D("800.00"))

    def test_textos(self) -> None:
        av = inc.AvanceEmpleada(D("15"), D("1200"), 180, D("10"), N(250, D("15")), "diciembre")
        self.assertEqual(
            av.texto(),
            "🏷 Este mes compras con 15 % (10 % en uniforme), te quedan $1,200.00 · "
            "Vas en 180 comisiones: te faltan 70 para comprar con 15 % en diciembre",
        )
        tope = inc.AvanceEmpleada(D("5"), None, 400, D("20"), None, "enero")
        self.assertIn("compras con 5 %", tope.texto())
        self.assertIn("el máximo, 20 %", tope.texto())
        e = inc.EstadoCompradora("VEND-3", "Ana", D("15"), D("3000"), D("2500"))
        self.assertEqual(e.restante, D("500.00"))
        self.assertEqual(e.texto(), "Ana: 15 % (10 % en uniforme), le quedan $500.00 este mes")
        self.assertEqual(inc.EstadoCompradora("VEND-4", "Bety", D("10"), None, D("0")).texto(), "Bety: 10 %")


class _Db(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.s.add(ConfiguracionNegocio(nombre_negocio="Maximoda", tope_compra_empleada_mes=D("3000")))
        self.s.add_all(NivelDescuentoEmpleada(comisiones_minimas=n.comisiones_minimas, porcentaje=n.porcentaje)
                       for n in NIVELES)
        self.s.flush()
        stock = patch.object(lib, "descontar_stock", return_value=0)
        stock.start()
        self.addCleanup(stock.stop)

    def _venta(self, code, comisiones, cuando, *, empleada=False, compradora=None, detalle=None):
        v = LibretaVenta(employee_code=code, employee_name=code, tipo="venta", piezas=1, comisiones=comisiones,
                         monto_total=D("100"), monto_neto=D("100"), descuento_empleada=empleada,
                         compradora_code=compradora, detalle=detalle or [], created_at=cuando)
        self.s.add(v)
        self.s.flush()
        return v


class BaseTests(_Db):
    def test_sus_compras_no_cuentan_para_la_meta(self) -> None:
        self._venta("VEND-3", 120, _local(2026, 10, 5))
        self._venta("VEND-3", 50, _local(2026, 10, 30))
        self._venta("VEND-3", 40, _local(2026, 10, 20), empleada=True, compradora="VEND-4")
        self._venta("VEND-3", 900, _local(2026, 9, 30))
        self._venta("VEND-4", 300, _local(2026, 10, 10))
        self.assertEqual(inc.comisiones_del_mes(self.s, "vend-3", date(2026, 10, 1)), 170)

    def test_estado_de_la_compradora(self) -> None:
        self._venta("VEND-3", 260, _local(2026, 10, 8))
        self._venta("VEND-1", 0, _local(2026, 11, 3), empleada=True, compradora="VEND-3",
                    detalle=[{"precio": "400", "cantidad": 2, "desc_empleada_pct": "15"},
                             {"precio": "100", "cantidad": 1, "desc_empleada_pct": "5"}])
        self._venta("VEND-1", 0, _local(2026, 10, 3), empleada=True, compradora="VEND-3",
                    detalle=[{"precio": "999", "cantidad": 1, "desc_empleada_pct": "10"}])
        e = inc.estado_compradora(self.s, "VEND-3", "Ana", hoy=date(2026, 11, 10))
        self.assertEqual((e.porcentaje, e.tope, e.usado, e.restante), (D("15"), D("3000"), D("800.00"), D("2200.00")))

    def test_avance(self) -> None:
        self._venta("VEND-3", 160, _local(2026, 10, 8))
        self._venta("VEND-3", 200, _local(2026, 11, 2))
        av = inc.avance(self.s, "VEND-3", hoy=date(2026, 11, 10))
        self.assertEqual((av.pct_este_mes, av.comisiones_mes, av.pct_mes_siguiente), (D("10"), 200, D("10")))
        self.assertEqual(av.siguiente, N(250, D("15")))
        self.assertEqual(av.nombre_mes_siguiente, "diciembre")

    def test_sin_niveles_usa_los_de_omision_y_tope_cero_es_sin_tope(self) -> None:
        for n in self.s.scalars(select(NivelDescuentoEmpleada)).all():
            self.s.delete(n)
        self.s.scalars(select(ConfiguracionNegocio)).one().tope_compra_empleada_mes = D("0")
        self.s.flush()
        self.assertEqual(inc.niveles(self.s), list(inc.NIVELES_POR_OMISION))
        self.assertIsNone(inc.tope(self.s))

    def test_guardar_reemplaza(self) -> None:
        inc.guardar(self.s, [N(0, D("5")), N(100, D("12"))], 1500)
        self.assertEqual(inc.niveles(self.s), [N(0, D("5")), N(100, D("12"))])
        self.assertEqual(inc.tope(self.s), D("1500.00"))
        with self.assertRaises(inc.NivelesInvalidos):
            inc.guardar(self.s, [N(5, D("5"))], 0)

    def test_categorias_por_sku(self) -> None:
        from pos_uniformes.database.models import Categoria, Marca, Producto, Variante

        cat, marca = Categoria(nombre="Ropa casual"), Marca(nombre="Maximoda")
        self.s.add_all([cat, marca])
        self.s.flush()
        prod = Producto(categoria_id=cat.id, marca_id=marca.id, nombre="Chamarra", nombre_base="Chamarra")
        self.s.add(prod)
        self.s.flush()
        self.s.add(Variante(producto_id=prod.id, sku="C1", talla="M", color="Azul", precio_venta=D("400")))
        self.s.flush()
        self.assertEqual(inc.categorias_por_sku(self.s, ["C1", "NO", ""]), {"C1": "Ropa casual"})
        self.assertEqual(inc.categorias_por_sku(self.s, []), {})

    def test_empleadas_activas(self) -> None:
        self.s.add_all([Empleada(codigo="VEND-3", nombre_completo="Ana"),
                        Empleada(codigo="VEND-9", nombre_completo="Baja", activo=False)])
        self.s.flush()
        self.assertEqual(inc.empleadas_activas(self.s), [("VEND-3", "Ana")])


class LibretaTests(_Db):
    ITEMS = [{"sku": "P1", "nombre": "Pants", "talla": "10", "cantidad": 1, "precio": "400", "desc_empleada_pct": "15"},
             {"sku": "PL", "nombre": "Playera", "talla": "8", "cantidad": 1, "precio": "100", "desc_empleada_pct": "5"}]

    def test_guarda_quien_compra_y_el_pct_de_cada_renglon(self) -> None:
        v = lib.registrar_operacion(self.s, employee_code="VEND-1", employee_name="Daniel", tipo="venta",
                                    items=self.ITEMS, monto_total=D("435"), descuento_empleada=True,
                                    compradora_code="vend-3")
        self.assertEqual(v.compradora_code, "VEND-3")
        self.assertEqual([l["desc_empleada_pct"] for l in v.detalle], ["15", "5"])

    def test_sin_descuento_de_empleada_no_hay_compradora(self) -> None:
        v = lib.registrar_operacion(self.s, employee_code="VEND-1", employee_name="Daniel", tipo="venta",
                                    items=[{"sku": "P1", "nombre": "Pants", "talla": "10", "cantidad": 1, "precio": "400"}],
                                    monto_total=D("400"), compradora_code="VEND-3")
        self.assertIsNone(v.compradora_code)

    def test_la_cola_sube_la_compradora(self) -> None:
        cola._subir(self.s, {"employee_code": "VEND-1", "employee_name": "Daniel", "tipo": "venta",
                             "items": self.ITEMS, "monto_total": "435", "monto_neto": "435",
                             "descuento_empleada": True, "compradora_code": "VEND-3",
                             "operacion_uuid": str(uuid.uuid4()), "created_at": datetime.now().astimezone().isoformat()})
        v = self.s.scalars(select(LibretaVenta)).one()
        self.assertEqual(v.compradora_code, "VEND-3")

    def test_corregir_a_tarjeta_usa_el_pct_de_cada_renglon(self) -> None:
        v = lib.registrar_operacion(self.s, employee_code="VEND-1", employee_name="Daniel", tipo="venta",
                                    items=self.ITEMS, monto_total=D("435"), descuento_empleada=True,
                                    compradora_code="VEND-3")
        lib.cambiar_pago_tarjeta(self.s, v.id, True)
        esperado = lib.aplicar_comision_terminal(D("340.00")) + lib.aplicar_comision_terminal(D("95.00"))
        self.assertEqual(v.monto_neto, esperado)

    def test_las_de_antes_siguen_con_5(self) -> None:
        v = lib.registrar_operacion(self.s, employee_code="VEND-1", employee_name="Daniel", tipo="venta",
                                    items=[{"sku": "P1", "nombre": "Pants", "talla": "10", "cantidad": 1, "precio": "400"}],
                                    monto_total=D("380"), descuento_empleada=True)
        lib.cambiar_pago_tarjeta(self.s, v.id, True)
        self.assertEqual(v.monto_neto, lib.aplicar_comision_terminal(D("380.00")))


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _kiosko(self, compradora=None):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code = "VEND-1"
        w._employee_name = "Daniel"
        w._items = [dict(CHAMARRA), dict(SUDADERA), dict(PLAYERA_PROMO)]
        w._discount_active = True
        w._compradora = compradora
        w._refresh_totals()
        return w


ANA = inc.EstadoCompradora("VEND-3", "Ana", D("15"), D("3000"), D("2500"))  # le quedan 500


class KioskoTests(_Qt):
    def test_con_su_nivel_y_su_tope(self) -> None:
        w = self._kiosko(ANA)
        # Pants 15 % (60) · sudadera ya no cabe: 5 % (30) · promo 5 % (5)
        self.assertEqual(w._compute_totals()[1], D("95.00"))
        self.assertEqual([it["desc_empleada_pct"] for it in w._items], [D("15"), D("5"), D("5")])
        self.assertIn("Ana: 15 %", w._total_meta.text())
        self.assertEqual(
            w._monto_neto_actual(D("1005"), pago_tarjeta=True),
            w._apply_terminal_commission(D("340.00")) + w._apply_terminal_commission(D("570.00"))
            + w._apply_terminal_commission(D("95.00")),
        )

    def test_en_uniforme_a_lo_mas_10(self) -> None:
        w = self._kiosko(inc.EstadoCompradora("VEND-5", "Cristal", D("20"), None, D("0")))
        # Chamarra 20 % (80) · sudadera de uniforme 10 % (60) · promo 5 % (5)
        self.assertEqual(w._compute_totals()[1], D("145.00"))

    def test_la_categoria_sale_del_catalogo(self) -> None:
        w = self._kiosko()
        w._items = [{"sku": "C1", "nombre": "Chamarra", "talla": "M", "precio": D("400"), "cantidad": 1},
                    {"sku": "XX", "nombre": "Sin catálogo", "talla": "", "precio": D("100"), "cantidad": 1}]
        w._compradora = inc.EstadoCompradora("VEND-5", "Cristal", D("20"), None, D("0"))
        with patch.object(inc, "categorias_por_sku", return_value={"C1": "Ropa casual"}) as cats, \
             patch("pos_uniformes.database.connection.get_session"):
            w._compute_totals()
            w._compute_totals()
        cats.assert_called_once()  # una vez por SKU
        self.assertEqual([it["desc_empleada_pct"] for it in w._items], [D("20"), D("10")])

    def test_sin_conexion_la_categoria_cuenta_como_uniforme(self) -> None:
        w = self._kiosko()
        w._items = [{"sku": "C1", "nombre": "Chamarra", "talla": "M", "precio": D("400"), "cantidad": 1}]
        w._compradora = inc.EstadoCompradora("VEND-5", "Cristal", D("20"), None, D("0"))
        with patch("pos_uniformes.database.connection.get_session", side_effect=OSError("sin red")):
            w._compute_totals()
        self.assertEqual(w._items[0]["desc_empleada_pct"], D("10"))

    def test_sin_compradora_es_el_5_de_siempre(self) -> None:
        w = self._kiosko()
        self.assertEqual(w._compute_totals()[1], D("55.00"))
        self.assertTrue(all("desc_empleada_pct" not in it for it in w._items))
        self.assertNotIn("compradora_code", _entrada(w))

    def test_compradora_sin_nivel_es_el_5_de_siempre(self) -> None:
        w = self._kiosko(inc.EstadoCompradora("VEND-4", "Bety", D("5"), None, D("0")))
        self.assertEqual(w._compute_totals()[1], D("55.00"))
        self.assertTrue(all("desc_empleada_pct" not in it for it in w._items))

    def test_lo_que_va_a_la_libreta(self) -> None:
        w = self._kiosko(ANA)
        entrada = _entrada(w)
        self.assertEqual(entrada["compradora_code"], "VEND-3")
        self.assertEqual([i["desc_empleada_pct"] for i in entrada["items"]], ["15", "5", "5"])
        self.assertTrue(entrada["descuento_empleada"])

    def test_quitar_el_descuento_quita_todo(self) -> None:
        w = self._kiosko(ANA)
        w._discount_check.setChecked(True)
        w._discount_check.click()  # la empleada lo quita
        self.assertIsNone(w._compradora)
        self.assertEqual(w._compute_totals()[1], D("0.00"))
        self.assertTrue(all("desc_empleada_pct" not in it for it in w._items))

    def test_la_copia_de_empleada(self) -> None:
        w = self._kiosko(ANA)
        w._compute_totals()
        texto = w._build_employee_copy_text()
        self.assertIn("Compra:", texto)
        self.assertIn("Ana (15 %)", texto)
        self.assertIn("340.00", texto)
        self.assertIn("570.00", texto)

    def test_reimprimir_con_el_pct_guardado(self) -> None:
        w = self._kiosko()
        w._discount_active = False
        detalle = [{"sku": "P1", "nombre": "Pants", "talla": "10", "cantidad": 1, "precio": "400", "desc_empleada_pct": "15"},
                   {"sku": "PL", "nombre": "Playera", "talla": "8", "cantidad": 1, "precio": "100", "desc_empleada_pct": "5"}]
        with patch.object(w, "_load_business_info", return_value=("Maximoda", "", "")):
            texto = w.build_reprint_ticket(tipo="venta", detalle=detalle, cliente=None, employee_name="Daniel",
                                           descuento_empleada=True, created_at=datetime(2026, 11, 10, 12, 0))
        self.assertIn("65.00", texto)
        self.assertIsNone(w._compradora)

    def test_elegir_compradora(self) -> None:
        from PyQt6.QtWidgets import QDialog

        w = self._kiosko()
        with patch.object(w, "_cargar_empleadas_compradoras", return_value=[("VEND-3", "Ana")]), \
             patch.object(w, "_estado_de_compradora", return_value=ANA) as estado, \
             patch.object(QDialog, "exec", return_value=QDialog.DialogCode.Accepted):
            w._elegir_compradora()
        estado.assert_called_once_with("VEND-3", "Ana")
        self.assertIs(w._compradora, ANA)

    def test_sin_conexion_queda_el_5(self) -> None:
        w = self._kiosko(ANA)
        with patch.object(w, "_cargar_empleadas_compradoras", return_value=None):
            w._elegir_compradora()
        self.assertIsNone(w._compradora)

    def test_la_siguiente_venta_no_la_hereda(self) -> None:
        w = self._kiosko(ANA)
        w._vaciar_carrito()
        self.assertIsNone(w._compradora)


class DialogoTests(_Qt):
    def test_lee_valida_y_no_guarda_si_esta_mal(self) -> None:
        from pos_uniformes.ui.dialogs.descuento_empleadas_dialog import DescuentoEmpleadasDialog

        dlg = DescuentoEmpleadasDialog(NIVELES, D("3000"))
        self.assertEqual(dlg.leer(), NIVELES)
        self.assertFalse(dlg.tabla.cellWidget(0, 0).isEnabled())
        dlg._aceptar()
        self.assertEqual(dlg.niveles_resultado, NIVELES)
        self.assertEqual(dlg.tope_resultado, D("3000.00"))
        dlg.tabla.cellWidget(3, 1).setValue(12)  # menos que el nivel anterior
        with patch("pos_uniformes.ui.dialogs.descuento_empleadas_dialog.QMessageBox.warning") as aviso:
            dlg._aceptar()
        aviso.assert_called_once()


def _entrada(w) -> dict:
    with patch.object(w, "_origen_satelite", return_value="Entrada"):
        (entrada,) = w._armar_anotacion("venta", cliente=None, pago_tarjeta=False, anticipo=None,
                                        anticipo_tarjeta=False)
    return entrada


if __name__ == "__main__":
    unittest.main()
