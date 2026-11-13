"""E7 (Daniel, 2026-11-11): prendas en Oferta o Liquidación.

- Se cobran a su precio rebajado; el precio normal no se toca.
- No llevan ningún otro descuento (empleada, nivel, mayoreo) ni Monedero.
- La oferta termina sola su último día; la liquidación dice «sin cambios».

Reglas puras, la base en SQLite en memoria y el kiosko sin base.
"""

from __future__ import annotations

import os
import tempfile
import unittest
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import (
    Categoria,
    Cliente,
    LibretaVenta,
    Marca,
    MonederoMovimiento,
    Producto,
    RebajaProducto,
    RolUsuario,
    Usuario,
    Variante,
)
from pos_uniformes.services import incentivo_empleada_service as inc
from pos_uniformes.services import libreta_service as lib
from pos_uniformes.services import monedero_service as mon
from pos_uniformes.services import rebaja_service as reb
from pos_uniformes.services.fidelizacion import descuento_programa_service as dps
from pos_uniformes.tests._programa_de_prueba import inscribir, programa_de_prueba

D = Decimal
UTC = timezone.utc
HOY = date(2026, 11, 11)

OFERTA_CHAMARRA = reb.RebajaVigente("C1", reb.OFERTA, D("350"), D("450"), date(2026, 11, 30))
LIQ_SUDADERA = reb.RebajaVigente("S1", reb.LIQUIDACION, D("200"), D("300"), None)


def _chamarra():
    return reb.aplicar({"sku": "C1", "nombre": "Chamarra", "talla": "M", "precio": D("450"), "cantidad": 1,
                        "categoria": "Ropa casual"}, OFERTA_CHAMARRA)


PANTS = {"sku": "P1", "nombre": "Pants", "talla": "10", "precio": D("400"), "cantidad": 1, "categoria": "Ropa casual"}


class ReglasTests(unittest.TestCase):
    def test_vigencia(self) -> None:
        self.assertTrue(reb.es_vigente(True, None, HOY))
        self.assertTrue(reb.es_vigente(True, HOY, HOY), "el último día todavía cuenta")
        self.assertFalse(reb.es_vigente(True, date(2026, 11, 10), HOY))
        self.assertFalse(reb.es_vigente(False, None, HOY))

    def test_precio_por_porcentaje_redondea_al_peso(self) -> None:
        self.assertEqual(reb.precio_por_porcentaje(D("450"), 20), D("360.00"))
        self.assertEqual(reb.precio_por_porcentaje(D("329"), 30), D("230.00"))  # 230.3
        with self.assertRaises(reb.RebajaInvalida):
            reb.precio_por_porcentaje(D("450"), 0)

    def test_validar(self) -> None:
        self.assertEqual(reb.validar(reb.OFERTA, 350, 450, HOY, HOY), D("350.00"))
        self.assertEqual(reb.validar(reb.LIQUIDACION, 200, 300, None, HOY), D("200.00"))
        self.assertEqual(reb.validar(reb.OFERTA, 175, 250, None, HOY), D("175.00"), "oferta sin fecha")
        malos = [
            (("otra", 1, 2, None), "Oferta o Liquidación"),
            ((reb.OFERTA, 450, 450, HOY), "no es menor"),
            ((reb.OFERTA, 0, 450, HOY), "mayor a"),
            ((reb.OFERTA, 300, 450, date(2026, 11, 1)), "ya pasó"),
        ]
        for args, texto in malos:
            with self.subTest(texto=texto), self.assertRaisesRegex(reb.RebajaInvalida, texto):
                reb.validar(*args, HOY)

    def test_el_renglon_rebajado(self) -> None:
        it = _chamarra()
        self.assertEqual((it["precio"], it["rebaja"], it["precio_normal"]), (D("350"), "oferta", D("450")))
        self.assertTrue(reb.es_rebajado(it))
        self.assertEqual(reb.texto_renglon(it), "OFERTA · antes $450.00")
        self.assertEqual(reb.ahorro({**it, "cantidad": 2}), D("200.00"))
        self.assertEqual(reb.fmt_corto(D("450.00")), "$450")
        self.assertEqual(reb.fmt_corto(D("450.50")), "$450.50")
        self.assertEqual(reb.precio_unitario_ticket(it, "$350.00"), f"{reb.tachar('$450')} $350.00")
        self.assertEqual(reb.precio_unitario_ticket(PANTS, "$400.00"), "$400.00")
        self.assertEqual(reb.texto_ahorro_total([PANTS]), "")
        # Daniel, 2026-11-11: el descuento de mayoreo se suma a lo ahorrado.
        self.assertEqual(reb.texto_ahorro_total([_chamarra()], D("54")), "¡Hoy ahorraste $154!")
        self.assertEqual(reb.texto_ahorro_total([PANTS], D("54")), "¡Hoy ahorraste $54!")
        self.assertEqual(reb.texto_ahorro_total([PANTS], D("0")), "")
        self.assertEqual(reb.marca_para_libreta(it), {"rebaja": "oferta", "precio_normal": "450"})
        self.assertEqual(reb.marca_para_libreta(PANTS), {})
        self.assertEqual(reb.importe_rebajado([it, PANTS, {**it, "cantidad": 2}]), D("1050.00"))
        self.assertFalse(reb.hay_liquidacion([it, PANTS]))
        self.assertTrue(reb.hay_liquidacion([{"rebaja": "liquidacion"}]))

    def test_no_lleva_ningun_otro_descuento(self) -> None:
        it = _chamarra()
        self.assertEqual(dps.porcentaje_de_linea(it, empleada=5, programa=15), D("0"))
        self.assertEqual(dps.porcentaje_de_linea({**it, "desc_empleada_pct": D("20")}, empleada=5), D("0"))
        self.assertEqual(dps.descuento([it, PANTS], empleada=5, programa=15), D("60.00"))
        # Ni gasta el tope del nivel de la empleada.
        self.assertEqual(inc.repartir([it, PANTS], pct_nivel=15, restante=D("400")), [D("0"), D("15")])


class _Db(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        cat, marca = Categoria(nombre="Ropa casual"), Marca(nombre="Maximoda")
        self.s.add_all([cat, marca])
        self.s.flush()
        self.prod = Producto(categoria_id=cat.id, marca_id=marca.id, nombre="Chamarra", nombre_base="Chamarra")
        self.s.add(self.prod)
        self.s.flush()
        self.m = Variante(producto_id=self.prod.id, sku="C1", talla="M", color="Azul", precio_venta=D("450"))
        self.g = Variante(producto_id=self.prod.id, sku="C2", talla="G", color="Azul", precio_venta=D("500"))
        self.s.add_all([self.m, self.g])
        self.s.flush()


class BaseTests(_Db):
    def test_marcar_por_porcentaje_todas_las_tallas(self) -> None:
        reb.marcar(self.s, [self.m.id, self.g.id], tipo=reb.OFERTA, porcentaje=D("20"), hasta=date(2026, 11, 30), hoy=HOY)
        vig = reb.vigentes_por_sku(self.s, hoy=HOY)
        self.assertEqual({k: v.precio for k, v in vig.items()}, {"C1": D("360.00"), "C2": D("400.00")})
        self.assertEqual(vig["C1"].precio_antes, D("450.00"))
        self.assertEqual(self.m.precio_venta, D("450"), "el precio normal no se toca")

    def test_volver_a_marcar_reemplaza_y_vence_sola(self) -> None:
        reb.marcar(self.s, [self.m.id], tipo=reb.OFERTA, precio=D("400"), hasta=date(2026, 11, 20), hoy=HOY)
        reb.marcar(self.s, [self.m.id], tipo=reb.OFERTA, precio=D("380"), hasta=date(2026, 11, 20), hoy=HOY)
        activas = self.s.scalars(select(RebajaProducto).where(RebajaProducto.activa.is_(True))).all()
        self.assertEqual([r.precio for r in activas], [D("380.00")])
        self.assertEqual(reb.vigentes_por_sku(self.s, hoy=date(2026, 11, 21)), {})
        self.assertEqual(reb.listar(self.s, hoy=date(2026, 11, 21)), [])
        self.assertEqual(self.s.scalar(select(func.count()).where(RebajaProducto.activa.is_(True))), 0)

    def test_oferta_sin_fecha_sigue_hasta_quitarla(self) -> None:
        reb.marcar(self.s, [self.m.id], tipo=reb.OFERTA, precio=D("175"), hoy=HOY)
        self.assertEqual(reb.vigentes_por_sku(self.s, hoy=date(2030, 1, 1))["C1"].precio, D("175.00"))
        (fila,) = reb.listar(self.s, hoy=date(2030, 1, 1))
        self.assertIsNone(fila.hasta)

    def test_liquidacion_sin_fecha_y_quitar(self) -> None:
        reb.marcar(self.s, [self.g.id], tipo=reb.LIQUIDACION, precio=D("299"), hasta=date(2026, 12, 1), hoy=HOY)
        (fila,) = reb.listar(self.s, hoy=HOY)
        self.assertEqual((fila.tipo, fila.hasta, fila.descuento_pct, fila.etiqueta), ("liquidacion", None, D("40"), "Liquidación"))
        self.assertEqual(reb.quitar(self.s, [self.g.id]), 1)
        self.assertEqual(reb.vigentes_por_sku(self.s, hoy=HOY), {})

    def test_no_cambia_nada_si_una_no_es_valida(self) -> None:
        with self.assertRaisesRegex(reb.RebajaInvalida, "C1"):
            reb.marcar(self.s, [self.m.id, self.g.id], tipo=reb.OFERTA, precio=D("460"), hasta=HOY, hoy=HOY)
        self.assertEqual(self.s.scalars(select(RebajaProducto)).all(), [])
        with self.assertRaisesRegex(reb.RebajaInvalida, "precio o un porcentaje"):
            reb.marcar(self.s, [self.m.id], tipo=reb.OFERTA, hasta=HOY, hoy=HOY)

    def test_si_el_precio_normal_baja_gana_el_normal(self) -> None:
        reb.marcar(self.s, [self.m.id], tipo=reb.LIQUIDACION, precio=D("300"), hoy=HOY)
        self.m.precio_venta = D("280")
        self.s.flush()
        self.assertEqual(reb.vigentes_por_sku(self.s, hoy=HOY), {})

    def test_buscar_prendas(self) -> None:
        self.assertEqual([p.sku for p in reb.buscar_prendas(self.s, "chama")], ["C2", "C1"])
        self.assertEqual([p.sku for p in reb.buscar_prendas(self.s, "c1")], ["C1"])
        self.assertEqual(reb.buscar_prendas(self.s, "  "), [])


class LibretaYMonederoTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        admin = Usuario(username="admin", nombre_completo="Dueño", password_hash="x", rol=RolUsuario.ADMIN, activo=True)
        self.cliente = Cliente(codigo_cliente="CLI-000009", nombre="Ana")
        self.s.add_all([admin, self.cliente])
        self.s.flush()
        cfg = mon.guardar_config(self.s, tasa="1", habilitado=True, usuario_id=admin.id)
        cfg.vigente_desde = datetime(2020, 1, 1, tzinfo=UTC)
        inscribir(self.s, self.cliente.id, programa_de_prueba(self.s, "10", clave="CLUB_PRUEBA"))
        stock = patch.object(lib, "descontar_stock", return_value=0)
        stock.start()
        self.addCleanup(stock.stop)

    ITEMS = [{"sku": "C1", "nombre": "Chamarra", "talla": "M", "cantidad": 1, "precio": "350",
              "rebaja": "oferta", "precio_normal": "450"},
             {"sku": "P1", "nombre": "Pants", "talla": "10", "cantidad": 1, "precio": "400"}]

    def test_la_libreta_guarda_la_marca_y_el_monedero_no_cuenta_lo_rebajado(self) -> None:
        v = lib.registrar_operacion(self.s, employee_code="VEND-2", employee_name="Fanny", tipo="venta",
                                    items=self.ITEMS, monto_total=D("750"), cliente_id=self.cliente.id,
                                    operacion_uuid=str(uuid.uuid4()))
        self.assertEqual(v.detalle[0]["rebaja"], "oferta")
        self.assertEqual(v.detalle[0]["precio_normal"], "450")
        self.assertNotIn("rebaja", v.detalle[1])
        (mov,) = self.s.scalars(select(MonederoMovimiento).where(MonederoMovimiento.tipo == mon.CASHBACK)).all()
        self.assertEqual(D(str(mov.monto)), D("40.00"), "solo los pants: 10 % de 400")

    def test_corregir_a_tarjeta_sin_descuento_en_lo_rebajado(self) -> None:
        v = lib.registrar_operacion(self.s, employee_code="VEND-1", employee_name="Daniel", tipo="venta",
                                    items=self.ITEMS, monto_total=D("730"), descuento_empleada=True)
        lib.cambiar_pago_tarjeta(self.s, v.id, True)
        # T4 (M2): una sola comisión sobre lo cobrado.
        self.assertEqual(v.monto_neto, lib.aplicar_comision_terminal(D("730")))


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def _kiosko(self):
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code = "VEND-1"
        w._employee_name = "Daniel"
        w._rebajas = {"C1": OFERTA_CHAMARRA, "S1": LIQ_SUDADERA}
        w._rebajas_leidas_en = 10**12  # que no la vuelva a leer
        return w


class KioskoTests(_Qt):
    def test_al_agregar_toma_el_precio_rebajado(self) -> None:
        w = self._kiosko()
        snap = SimpleNamespace(sku="C1", product_name="Chamarra", sale_name="Chamarra", size_label="M",
                               color_label="Azul", price=D("450"))
        with patch.object(w, "_lookup_sku", return_value=snap), patch.object(w, "_find_satellite_row", return_value=None):
            self.assertTrue(w.add_sku("C1"))
        (it,) = w._items
        self.assertEqual((it["precio"], it["rebaja"]), (D("350"), "oferta"))
        self.assertIn("🔖 Oferta", w._items_table.item(0, 0).text())

    def test_el_5_de_empleada_no_le_aplica(self) -> None:
        w = self._kiosko()
        w._items = [_chamarra(), dict(PANTS)]
        w._discount_active = True
        self.assertEqual(w._compute_totals(), (D("750"), D("20.00"), D("730")))
        # T4 (M2): la comisión una vez sobre el total, no renglón por renglón.
        self.assertEqual(w._monto_neto_actual(D("730"), pago_tarjeta=True), w._apply_terminal_commission(D("730")))
        # Sin copia de empleada (2026-11-12): el ticket de venta lleva el
        # precio rebajado y el total con el 5 % solo en lo que no es rebaja.
        with patch.object(w, "_load_business_info", return_value=("MAXIMODA", "", "")):
            texto = w._build_venta_text()
        self.assertIn("350.00", texto)
        self.assertIn("730.00", texto)

    def test_lo_que_va_a_la_libreta(self) -> None:
        w = self._kiosko()
        w._items = [_chamarra(), dict(PANTS)]
        with patch.object(w, "_origen_satelite", return_value="Entrada"):
            (entrada,) = w._armar_anotacion("venta", cliente=None, pago_tarjeta=False, anticipo=None,
                                            anticipo_tarjeta=False)
        self.assertEqual(entrada["items"][0]["rebaja"], "oferta")
        self.assertEqual(entrada["items"][0]["precio_normal"], "450")
        self.assertNotIn("rebaja", entrada["items"][1])

    def test_el_monedero_estimado_no_cuenta_lo_rebajado(self) -> None:
        w = self._kiosko()
        w._items = [_chamarra(), dict(PANTS)]
        w._cliente = {"id": 9, "estado": "activo", "tasa": D("10"), "descuento_disponible": None}
        self.assertEqual(w._cashback_estimado(D("750"), D("0")), D("40.00"))

    def test_el_ticket(self) -> None:
        w = self._kiosko()
        w._items = [_chamarra(), reb.aplicar({"sku": "S1", "nombre": "Sudadera", "talla": "10", "precio": D("300"),
                                              "cantidad": 1}, LIQ_SUDADERA)]
        with patch.object(w, "_load_business_info", return_value=("Maximoda", "", "")):
            texto = w._build_venta_text()
        # Cada prenda solo dice su marca; lo ahorrado va sumado al final.
        self.assertIn("│ OFERTA" + " " * 29 + "│", texto)
        # Con una pieza el $350 no se repite: solo el de antes tachado y el importe.
        self.assertIn(f"T.M  1 x {reb.tachar('$450')}" + " " * 14 + "$350.00 │", texto)
        self.assertEqual(texto.count("$350.00"), 1)
        self.assertIn("│ LIQUIDACIÓN" + " " * 24 + "│", texto)
        self.assertNotIn("ahorras $", texto)
        self.assertEqual(texto.count("ahorraste"), 1)
        self.assertIn("¡Hoy ahorraste $200 en ofertas!", texto)
        self.assertIn("sin cambios ni devoluciones", texto)
        # Cada renglón del recuadro mide lo mismo a la vista (el tachado no ocupa casilla).
        for linea in texto.split("\n"):
            if linea.startswith("│"):
                self.assertEqual(reb.largo_visible(linea), 38, linea)

    def test_lo_de_abajo_va_en_su_recuadro(self) -> None:
        w = self._kiosko()
        w._items = [_chamarra(), reb.aplicar({"sku": "S1", "nombre": "Sudadera", "talla": "10", "precio": D("300"),
                                              "cantidad": 1}, LIQ_SUDADERA)]
        with patch.object(w, "_load_business_info", return_value=("Maximoda", "", "")):
            texto = w._build_venta_text(monedero={"cashback": D("9"), "saldo": D("46.42")})
        abajo = texto.split("╝\n", 1)[1].split("\n\n", 1)[0].split("\n")
        self.assertTrue(abajo[0].startswith("┌") and abajo[-1].startswith("└"), abajo)
        self.assertIn("¡Hoy ahorraste $200 en ofertas!", abajo[1])
        self.assertTrue(abajo[2].startswith("├"))
        self.assertIn("Acumulado en esta compra:", abajo[3])
        self.assertIn("Saldo en monedero:", abajo[4])
        self.assertTrue(abajo[5].startswith("├"))
        self.assertIn("sin cambios ni devoluciones", "\n".join(abajo[6:]))
        for linea in abajo:
            self.assertEqual(reb.largo_visible(linea), 38, linea)

    def test_sin_nada_que_decir_no_hay_recuadro(self) -> None:
        w = self._kiosko()
        w._items = [dict(PANTS)]
        with patch.object(w, "_load_business_info", return_value=("Maximoda", "", "")):
            texto = w._build_venta_text()
        self.assertFalse(texto.split("╝\n", 1)[1].lstrip("\n").startswith("┌"))

    def test_con_varias_piezas_va_el_precio_de_cada_una(self) -> None:
        w = self._kiosko()
        chamarras = _chamarra()
        chamarras["cantidad"] = 2
        w._items = [chamarras]
        with patch.object(w, "_load_business_info", return_value=("Maximoda", "", "")):
            texto = w._build_venta_text()
        self.assertIn(f"T.M  2 x {reb.tachar('$450')} $350.00", texto)
        self.assertIn("$700.00 │", texto)

    def test_sin_rebajas_no_hay_renglon_de_ahorro(self) -> None:
        w = self._kiosko()
        w._items = [dict(PANTS)]
        with patch.object(w, "_load_business_info", return_value=("Maximoda", "", "")):
            texto = w._build_venta_text()
        self.assertNotIn("ahorr", texto)
        self.assertNotIn("OFERTA", texto)

    def test_el_ticket_se_dibuja_con_la_raya(self) -> None:
        from pos_uniformes.services.ticket_imagen_service import partir_tachado, render_ticket

        self.assertEqual(partir_tachado(f"x {reb.tachar('$450')} y"), ("x $450 y", {2, 3, 4, 5}))
        w = self._kiosko()
        w._items = [_chamarra()]
        with patch.object(w, "_load_business_info", return_value=("Maximoda", "", "")):
            imagen = render_ticket(w._build_venta_text(), adornos=False)
        self.assertGreater(imagen.height(), 100)

    def test_reimprimir_con_la_marca(self) -> None:
        w = self._kiosko()
        detalle = [{"sku": "C1", "nombre": "Chamarra", "talla": "M", "cantidad": 1, "precio": "350",
                    "rebaja": "liquidacion", "precio_normal": "450"}]
        with patch.object(w, "_load_business_info", return_value=("Maximoda", "", "")):
            texto = w.build_reprint_ticket(tipo="venta", detalle=detalle, cliente=None, employee_name="Daniel",
                                           descuento_empleada=True, created_at=datetime(2026, 11, 11, 12, 0))
        self.assertIn("LIQUIDACIÓN", texto)
        self.assertIn(reb.tachar("$450"), texto)
        self.assertNotIn("Descuento", texto.split("TOTAL")[0].split("ARTÍCULOS")[1])

    def test_sin_conexion_usa_la_ultima_lista_o_precio_normal(self) -> None:
        w = self._kiosko()
        w._rebajas, w._rebajas_leidas_en = None, 0.0
        with patch("pos_uniformes.database.connection.get_session", side_effect=OSError("sin red")):
            self.assertEqual(w._cargar_rebajas(), {})


class DialogoYEtiquetaTests(_Qt):
    def test_la_etiqueta(self) -> None:
        from PIL import Image

        from pos_uniformes.utils.rebaja_label_generator import render_rebaja

        with tempfile.TemporaryDirectory() as tmp:
            for tipo, hasta in ((reb.OFERTA, date(2026, 11, 30)), (reb.LIQUIDACION, None)):
                ruta = render_rebaja(tipo=tipo, nombre="Chamarra rompevientos", talla="M", precio=D("350"),
                                     precio_antes=D("450"), hasta=hasta, output_path=Path(tmp) / f"{tipo}.png")
                with Image.open(ruta) as img:
                    self.assertEqual(img.size, (202, 202))
                    self.assertEqual(img.mode, "1")

    def test_el_dialogo_marca_y_quita(self) -> None:
        from PyQt6.QtWidgets import QMessageBox

        from pos_uniformes.ui.dialogs.rebajas_dialog import RebajasDialog

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        with Session(engine) as s:
            cat, marca = Categoria(nombre="Ropa casual"), Marca(nombre="M")
            s.add_all([cat, marca])
            s.flush()
            p = Producto(categoria_id=cat.id, marca_id=marca.id, nombre="Chamarra", nombre_base="Chamarra")
            s.add(p)
            s.flush()
            s.add(Variante(producto_id=p.id, sku="C1", talla="M", color="Azul", precio_venta=D("450")))
            s.commit()

        impresas = []
        dlg = RebajasDialog(None, lambda: Session(engine), usuario_id=None, imprimir=impresas.append)
        dlg.buscar_input.setText("chamarra")
        dlg._buscar()
        dlg.tabla_prendas.selectAll()
        dlg.tipo_combo.setCurrentIndex(1)  # Liquidación
        dlg.pct_input.setValue(20)
        dlg._poner()
        self.assertEqual(dlg.tabla_rebajas.rowCount(), 1)
        self.assertEqual(dlg.tabla_rebajas.item(0, 4).text(), "$360.00")
        self.assertTrue(dlg.hasta_input.isHidden())
        dlg.tabla_rebajas.selectAll()
        dlg._imprimir_seleccion()
        self.assertEqual([f.sku for f in impresas], ["C1"])
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dlg._quitar()
        self.assertEqual(dlg.tabla_rebajas.rowCount(), 0)
        self.assertTrue(dlg.hubo_cambios)


if __name__ == "__main__":
    unittest.main()
