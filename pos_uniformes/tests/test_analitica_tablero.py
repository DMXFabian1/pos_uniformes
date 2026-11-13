"""La pestaña Analítica del POS, rehecha sobre la Libreta (2026-11-07).

Daniel: «mejoremos la pestaña de analítica» → «hazlo completo». La mitad de la
de antes leía la tabla `venta` del POS (8 registros de abril)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from pos_uniformes.database.connection import Base  # noqa: E402
from pos_uniformes.database.models import (  # noqa: E402
    Categoria, Escuela, LibretaCorte, LibretaVenta, Marca, Producto, Variante,
)
from pos_uniformes.services import analitica_tablero_service as tb  # noqa: E402

_APP = QApplication.instance() or QApplication([])
HOY = date(2026, 11, 7)   # sábado


def _op(tipo="venta", monto="100", *, piezas=1, tarjeta=False, dia=HOY, hora=11, sku="SKU1", neto=None):
    return SimpleNamespace(
        tipo=tipo, monto_total=Decimal(monto), monto_neto=Decimal(neto) if neto else Decimal(monto),
        pago_tarjeta=tarjeta, piezas=piezas,
        created_at=datetime.combine(dia, time(hora, 0)).astimezone(),
        detalle=[{"sku": sku, "nombre": "Pants", "talla": "8", "precio": monto, "cantidad": piezas, "subtotal": monto}],
    )


class PeriodosTests(unittest.TestCase):
    def test_rangos(self) -> None:
        self.assertEqual(tb.rango(tb.HOY, HOY), (HOY, HOY))
        self.assertEqual(tb.rango(tb.SEMANA, HOY), (date(2026, 11, 2), date(2026, 11, 8)))
        self.assertEqual(tb.rango(tb.MES, HOY), (date(2026, 11, 1), date(2026, 11, 30)))
        self.assertEqual(tb.rango(tb.TREINTA, HOY), (date(2026, 10, 9), HOY))
        self.assertEqual(tb.rango(tb.MANUAL, HOY, (date(2026, 11, 5), date(2026, 11, 1))), (date(2026, 11, 1), date(2026, 11, 5)))

    def test_anterior_es_del_mismo_tamano_y_el_mes_es_el_mes_pasado(self) -> None:
        self.assertEqual(tb.anterior(HOY, HOY, tb.HOY), (date(2026, 11, 6), date(2026, 11, 6)))
        self.assertEqual(tb.anterior(date(2026, 11, 2), date(2026, 11, 8), tb.SEMANA), (date(2026, 10, 26), date(2026, 11, 1)))
        self.assertEqual(tb.anterior(date(2026, 11, 1), date(2026, 11, 30), tb.MES), (date(2026, 10, 1), date(2026, 10, 31)))

    def test_mover(self) -> None:
        self.assertEqual(tb.mover(tb.HOY, HOY, -1), date(2026, 11, 6))
        self.assertEqual(tb.mover(tb.SEMANA, HOY, -1), date(2026, 10, 31))
        self.assertEqual(tb.mover(tb.MES, date(2026, 1, 15), -1), date(2025, 12, 1))

    def test_textos(self) -> None:
        self.assertEqual(tb.texto_periodo(tb.HOY, HOY, HOY, hoy=HOY), "Hoy, sáb 7 de noviembre")
        self.assertEqual(tb.texto_periodo(tb.MES, date(2026, 11, 1), date(2026, 11, 30)), "Noviembre 2026")
        self.assertEqual(tb.texto_periodo(tb.SEMANA, date(2026, 10, 26), date(2026, 11, 1)), "26 de octubre al 1 de noviembre")
        self.assertEqual(tb.nombre_comparacion(tb.SEMANA), "la semana pasada")


class CifrasTests(unittest.TestCase):
    def test_cobrado_es_dinero_real_y_no_suma_apartados(self) -> None:
        rows = [
            _op("venta", "300"),
            _op("venta", "200", tarjeta=True, neto="191"),    # llega tras el 4.5 %
            _op("apartado", "1000", piezas=2),                 # comprometido, no cobrado
            _op("abono", "150"),
        ]
        c = tb.cifras(rows)
        self.assertEqual(c.efectivo, Decimal("450.00"))
        self.assertEqual(c.tarjeta_neto, Decimal("191.00"))
        self.assertEqual(c.cobrado, Decimal("641.00"))
        # El abono no es operación (Daniel, 2026-11-12: «no cuentan como
        # operación»); su dinero sí está arriba, en efectivo y cobrado.
        self.assertEqual((c.operaciones, c.ventas, c.piezas), (3, 2, 4))
        self.assertEqual(c.ticket_promedio, Decimal("250.00"))

    def test_operaciones_nunca_menos_que_ventas(self) -> None:
        """Revisión 2026-11-12: solo se quitan los abonos. La compra de una
        empleada con precio especial sigue en operaciones, ventas y piezas
        de la tarjeta, para que «1 operación · 2 ventas» no pase."""
        empleada = _op("venta", "100", piezas=5)
        empleada.descuento_empleada = True
        c = tb.cifras([_op("venta", "100", piezas=2), empleada, _op("abono", "300", piezas=0)])
        self.assertEqual((c.operaciones, c.ventas, c.piezas), (2, 2, 7))
        self.assertGreaterEqual(c.operaciones, c.ventas)
        self.assertEqual(c.efectivo, Decimal("500.00"))   # el dinero del abono sí

    def test_el_ajuste_del_dueno_va_por_defecto(self) -> None:
        c = tb.cifras([_op("venta", "1000")], ajuste=Decimal("-200"))
        self.assertEqual(c.cobrado, Decimal("800.00"))

    def test_cambio(self) -> None:
        self.assertEqual(tb.cambio(112, 100), ("↑ 12 %", "sube"))
        self.assertEqual(tb.cambio(80, 100), ("↓ 20 %", "baja"))
        self.assertEqual(tb.cambio(5, 0), ("nuevo", "nuevo"))
        self.assertEqual(tb.cambio(0, 0), ("—", "igual"))

    def test_cobrado_por_dia_trae_todos_los_dias(self) -> None:
        rows = [_op("venta", "300", dia=HOY - timedelta(days=2)), _op("venta", "100", dia=HOY)]
        dias = tb.cobrado_por_dia(rows, HOY - timedelta(days=3), HOY)
        self.assertEqual([d.cobrado for d in dias], [Decimal("0.00"), Decimal("300.00"), Decimal("0.00"), Decimal("100.00")])

    def test_la_diferencia_de_un_cambio_es_cobrado_pero_no_venta(self) -> None:
        """Revisión 2026-11-12 («arregla el cobrado de Analítica»): como el
        Resumen, el corte y el bot, lo que el cliente paga de más en un cambio
        de prenda es dinero cobrado. No es venta, ni operación, ni piezas."""
        c = tb.cifras([_op("venta", "300", piezas=2), _op("cambio", "120", piezas=1)])
        self.assertEqual(c.efectivo, Decimal("420.00"))
        self.assertEqual(c.cobrado, Decimal("420.00"))
        self.assertEqual((c.operaciones, c.ventas, c.piezas), (1, 1, 2))
        self.assertEqual(c.ticket_promedio, Decimal("300.00"))

    def test_el_dinero_sale_de_los_cobrables_y_los_conteos_de_todo(self) -> None:
        """La compra a cuenta de una empleada (quitada de `cobrables` con
        `sin_compras_a_cuenta`) no es dinero del cajón, pero la prenda sí se
        vendió: sigue en operaciones, ventas y piezas (decisión 2026-11-12)."""
        normal = _op("venta", "300", piezas=1)
        a_cuenta = _op("venta", "500", piezas=2)
        a_cuenta.descuento_empleada = True
        c = tb.cifras([normal, a_cuenta], cobrables=[normal])
        self.assertEqual(c.cobrado, Decimal("300.00"))
        self.assertEqual((c.operaciones, c.ventas, c.piezas), (2, 2, 3))
        self.assertGreaterEqual(c.operaciones, c.ventas)

    def test_cobrado_por_dia_con_la_misma_regla(self) -> None:
        ayer = HOY - timedelta(days=1)
        normal, a_cuenta = _op("venta", "300", dia=ayer), _op("venta", "500", dia=ayer, piezas=2)
        rows = [normal, a_cuenta, _op("cambio", "50", dia=ayer, piezas=1), _op("apartado", "900", dia=HOY),
                _op("abono", "100", dia=HOY, piezas=0)]
        cobrables = [r for r in rows if r is not a_cuenta]
        dias = tb.cobrado_por_dia(rows, ayer, HOY, cobrables=cobrables, ajustes={HOY: Decimal("-40")})
        self.assertEqual([d.cobrado for d in dias], [Decimal("350.00"), Decimal("60.00")])
        self.assertEqual([d.piezas for d in dias], [3, 1])   # el cambio no suma piezas; la compra a cuenta sí


class PorAcabarseTests(unittest.TestCase):
    def test_lo_que_no_alcanza_primero_lo_agotado(self) -> None:
        vendidas = {"A": 12, "B": 8, "C": 1, "D": 30}
        existencias = {
            "A": {"stock": 0, "nombre": "Pants", "talla": "8"},     # ya no hay
            "B": {"stock": 2, "nombre": "Playera", "talla": "10"},  # 8 en 30 días → 1.9/sem → 1 sem
            "C": {"stock": 0, "nombre": "Short", "talla": "6"},     # muy pocas ventas: no se cree
            "D": {"stock": 100, "nombre": "Falda", "talla": "12"},  # alcanza de sobra
        }
        r = tb.por_acabarse(vendidas, existencias)
        self.assertEqual([p.sku for p in r], ["A", "B"])
        self.assertEqual(r[0].texto_semanas, "ya no hay")
        self.assertEqual(r[1].texto_semanas, "7 días")


class _ConBase(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.addCleanup(self.s.close)
        e = Escuela(nombre="CBTIS 148")
        cat, marca = Categoria(nombre="Uniformes"), Marca(nombre="Maximoda")
        self.s.add_all([e, cat, marca])
        self.s.flush()
        prod = Producto(nombre="Pants 2pz CBTIS 148", nombre_base="Pants 2pz", categoria_id=cat.id, marca_id=marca.id, escuela_id=e.id)
        self.s.add(prod)
        self.s.flush()
        self.s.add_all([
            Variante(producto_id=prod.id, sku="SKU8", talla="8", color="", precio_venta=300, stock_actual=1),
            Variante(producto_id=prod.id, sku="SKU10", talla="10", color="", precio_venta=300, stock_actual=40),
        ])
        self.s.commit()

    def _vender(self, dia, monto="300", sku="SKU8", tarjeta=False, tipo="venta"):
        self.s.add(LibretaVenta(
            employee_code="VEND-4", employee_name="Fanny Ortiz", tipo=tipo, piezas=1,
            monto_total=Decimal(monto), monto_neto=Decimal(monto), pago_tarjeta=tarjeta,
            detalle=[{"sku": sku, "nombre": "Pants 2pz CBTIS 148", "talla": "8", "precio": monto, "cantidad": 1, "subtotal": monto}],
            created_at=datetime.combine(dia, time(12, 0)).astimezone(),
        ))
        self.s.commit()


class CargarTests(_ConBase):
    def test_cargar_la_semana_con_su_comparacion(self) -> None:
        for d in (HOY, HOY - timedelta(days=1), HOY - timedelta(days=2)):
            self._vender(d)
        self._vender(HOY - timedelta(days=8))              # la semana pasada
        t = tb.cargar(self.s, tb.SEMANA, HOY, hoy=HOY)
        self.assertEqual(t.ahora.cobrado, Decimal("900.00"))
        self.assertEqual(t.antes.cobrado, Decimal("300.00"))
        self.assertEqual(len(t.dias), 7)
        self.assertEqual(len(t.filas), 3)
        self.assertEqual([p.sku for p in t.acabarse], ["SKU8"])   # 4 vendidas en 30 días y queda 1

    def test_el_ajuste_del_corte_se_aplica_salvo_con_lo_real(self) -> None:
        self._vender(HOY, "1000")
        self.s.add(LibretaCorte(fecha=HOY, creado_por="VEND-1", monto_final=Decimal("9800"), monto_esperado=Decimal("10000"),
                                reactivo_inicial=Decimal("9000"), reactivo_final=Decimal("9000"),
                                desde=datetime.combine(HOY, time(9)).astimezone(),
                                hasta=datetime.combine(HOY, time(17)).astimezone(), periodo_label="hoy"))
        self.s.commit()
        self.assertEqual(tb.cargar(self.s, tb.HOY, HOY, hoy=HOY).ahora.cobrado, Decimal("800.00"))
        self.assertEqual(tb.cargar(self.s, tb.HOY, HOY, real=True, hoy=HOY).ahora.cobrado, Decimal("1000.00"))


class CobradoComoElResumenTests(_ConBase):
    """Revisión 2026-11-12 («arregla el cobrado de Analítica»): el cobrado de
    Analítica sigue la regla del Resumen, el corte y el bot."""

    def _anotar(self, dia, tipo="venta", monto="300", *, hora=12, piezas=1, **extra) -> LibretaVenta:
        row = LibretaVenta(
            employee_code="VEND-4", employee_name="Fanny Ortiz", tipo=tipo, piezas=piezas,
            monto_total=Decimal(monto), monto_neto=Decimal(extra.pop("neto", monto)),
            detalle=[{"sku": "SKU10", "nombre": "Pants 2pz CBTIS 148", "talla": "10", "precio": monto,
                      "cantidad": piezas, "subtotal": monto}] if piezas else [],
            created_at=datetime.combine(dia, time(hora, 0)).astimezone(), **extra,
        )
        self.s.add(row)
        self.s.commit()
        return row

    def _a_cuenta(self, venta: LibretaVenta) -> None:
        from pos_uniformes.database.models import PrestamoEmpleada
        from pos_uniformes.services import prestamos_service as pr

        self.s.add(PrestamoEmpleada(
            employee_code="VEND-4", employee_name="Fanny Ortiz", monto=venta.monto_total, motivo="Compra a cuenta",
            estado=pr.APROBADO, tipo=pr.TIPO_COMPRA, libreta_venta_id=venta.id,
        ))
        self.s.commit()

    def _corte_del_dueno(self, dia, diferencia: str) -> None:
        self.s.add(LibretaCorte(
            fecha=dia, creado_por="VEND-1", monto_final=Decimal("10000") + Decimal(diferencia),
            monto_esperado=Decimal("10000"), reactivo_inicial=Decimal("9000"), reactivo_final=Decimal("9000"),
            desde=datetime.combine(dia, time(9)).astimezone(),
            hasta=datetime.combine(dia, time(17)).astimezone(), periodo_label="hoy",
        ))
        self.s.commit()

    def _un_dia_completo(self, dia) -> None:
        self._anotar(dia, "venta", "300", hora=10)
        self._anotar(dia, "venta", "200", hora=11, pago_tarjeta=True, neto="191")
        self._anotar(dia, "apartado", "900", hora=12, piezas=3)
        self._anotar(dia, "abono", "150", hora=13, piezas=0)
        self._anotar(dia, "cambio", "120", hora=14, piezas=1)
        self._anotar(dia, "venta", "400", hora=15, privado=True)
        self._a_cuenta(self._anotar(dia, "venta", "500", hora=16, piezas=2, descuento_empleada=True))
        self._corte_del_dueno(dia, "-70")

    def test_hoy_es_igual_al_hoy_del_resumen(self) -> None:
        from pos_uniformes.services import resumen_pos_service as rp

        self._un_dia_completo(HOY)
        t = tb.cargar(self.s, tb.HOY, HOY, hoy=HOY)
        r = rp.cargar(self.s, HOY, incluir_privados=True)
        # 300 + 150 + 120 + 400 − 70 de efectivo, + 191 de tarjeta; sin el
        # apartado ni la compra a cuenta.
        self.assertEqual(t.ahora.cobrado, Decimal("1091.00"))
        self.assertEqual(t.ahora.cobrado, r.hoy.cobrado)
        self.assertEqual((t.ahora.efectivo, t.ahora.tarjeta_neto), (Decimal("900.00"), Decimal("191.00")))
        # Con lo real (Ctrl+Shift+R) no lleva el ajuste del dueño.
        self.assertEqual(tb.cargar(self.s, tb.HOY, HOY, real=True, hoy=HOY).ahora.cobrado, Decimal("1161.00"))

    def test_los_conteos_no_cambian_de_significado(self) -> None:
        self._un_dia_completo(HOY)
        c = tb.cargar(self.s, tb.HOY, HOY, hoy=HOY).ahora
        # Ventas: 300, 200, 400 y la compra a cuenta (500); el apartado es
        # operación; ni el abono ni el cambio. Piezas: 1+1+3+1+2.
        self.assertEqual((c.operaciones, c.ventas, c.piezas), (5, 4, 8))
        self.assertEqual(c.ticket_promedio, Decimal("350.00"))

    def test_el_periodo_anterior_y_la_grafica_con_la_misma_regla(self) -> None:
        ayer = HOY - timedelta(days=1)
        self._un_dia_completo(HOY)
        self._un_dia_completo(ayer)
        self._un_dia_completo(HOY - timedelta(days=7))      # la semana pasada (sábado)
        t = tb.cargar(self.s, tb.SEMANA, HOY, hoy=HOY)
        por_dia = {d.dia: d.cobrado for d in t.dias}
        self.assertEqual(por_dia[HOY], Decimal("1091.00"))
        self.assertEqual(por_dia[ayer], Decimal("1091.00"))
        self.assertEqual(sum(por_dia.values()), t.ahora.cobrado)
        self.assertEqual(t.antes.cobrado, Decimal("1091.00"))
        real = tb.cargar(self.s, tb.SEMANA, HOY, real=True, hoy=HOY)
        self.assertEqual({d.dia: d.cobrado for d in real.dias}[HOY], Decimal("1161.00"))

    def test_un_dia_puede_salir_negativo_y_la_suma_cuadra(self) -> None:
        lunes = HOY - timedelta(days=HOY.weekday())
        martes = lunes + timedelta(days=1)
        self._anotar(martes, "venta", "300")
        self._corte_del_dueno(martes, "-800")
        t = tb.cargar(self.s, tb.SEMANA, martes, hoy=martes)
        por_dia = {d.dia: d.cobrado for d in t.dias}
        self.assertEqual(por_dia[martes], Decimal("-500.00"))
        self.assertEqual(sum(por_dia.values()), t.ahora.cobrado)

    def test_una_base_sin_la_liga_de_compras_a_cuenta_no_tumba_la_pestana(self) -> None:
        # Base atrasada sin prestamo_empleada.libreta_venta_id: sin_compras_a_cuenta
        # lanza ProgrammingError. Analítica sigue (ninguna venta puede estar
        # ligada) en vez de quedarse en blanco; otro error sí sube.
        from sqlalchemy.exc import OperationalError, ProgrammingError

        from pos_uniformes.services import corte_caja_service as cc

        self._anotar(HOY, "venta", "300")
        falla = ProgrammingError("SELECT …", {}, Exception("column libreta_venta_id does not exist"))
        with patch.object(cc, "sin_compras_a_cuenta", side_effect=falla):
            t = tb.cargar(self.s, tb.HOY, HOY, real=True, hoy=HOY)
        self.assertEqual((t.ahora.cobrado, t.ahora.ventas), (Decimal("300.00"), 1))
        with patch.object(cc, "sin_compras_a_cuenta", side_effect=OperationalError("x", {}, Exception("caída"))):
            with self.assertRaises(OperationalError):
                tb.cargar(self.s, tb.HOY, HOY, real=True, hoy=HOY)

    def test_ajustes_por_dia_suman_el_ajuste_del_periodo(self) -> None:
        from pos_uniformes.services.corte_caja_service import ajustes_en_rango

        self._corte_del_dueno(HOY, "-70")
        self._corte_del_dueno(HOY - timedelta(days=2), "25")
        ini, fin = tb.limites(HOY - timedelta(days=6), HOY)
        dias = tb.ajustes_por_dia(self.s, ini, fin)
        self.assertEqual(dias, {HOY: Decimal("-70.00"), HOY - timedelta(days=2): Decimal("25.00")})
        self.assertEqual(sum(dias.values()), ajustes_en_rango(self.s, ini, fin))


_CARGAR = tb.cargar


class PestanaTests(_ConBase):
    def _pestana(self):
        from PyQt6.QtWidgets import QWidget

        from pos_uniformes.ui.helpers import analytics_tablero as ui

        # «Hoy» es el sábado de HOY, no el día en que corre la prueba: si no,
        # la semana de HOY deja de ir «a medias» en cuanto pasa y la tarjeta ya
        # no dice «(mismos días)».
        cargar = tb.cargar
        fijo = patch.object(tb, "cargar", side_effect=lambda *a, **kw: cargar(*a, **{"hoy": HOY, **kw}))
        fijo.start()
        self.addCleanup(fijo.stop)

        ventana = QWidget()
        raiz = ui.construir(ventana)
        self.addCleanup(raiz.deleteLater)
        self.addCleanup(ventana.deleteLater)
        return ventana, ui

    def test_pinta_tarjetas_barras_y_lo_que_se_acaba(self) -> None:
        for d in (HOY, HOY - timedelta(days=1), HOY - timedelta(days=2)):
            self._vender(d)
        self._vender(HOY, "200", sku="SKU10", tarjeta=True)
        ventana, ui = self._pestana()
        ventana._ana_estado.update(clave=tb.SEMANA, ancla=HOY)
        ui.refrescar(ventana, self.s)
        self.assertEqual(ventana.ana_cobrado.valor.text(), "$1,100.00")
        self.assertIn("efectivo $900.00 + tarjeta $200.00", ventana.ana_cobrado.pie.text())
        self.assertEqual(ventana.ana_operaciones.valor.text(), "4")
        self.assertEqual(ventana.ana_cobrado.cambio.text(), "nuevo vs la semana pasada (mismos días)")
        self.assertEqual(len(ventana.ana_barras.datos), 7)
        self.assertEqual(ventana.ana_acabarse.rowCount(), 1)
        self.assertEqual(ventana.ana_acabarse.item(0, 1).text(), "8")
        self.assertEqual(ventana.libreta_top_productos_table.rowCount(), 1)
        # la barrita de la tabla de productos
        from PyQt6.QtCore import Qt
        self.assertEqual(ventana.libreta_top_productos_table.item(0, 1).data(Qt.ItemDataRole.UserRole), 1.0)

    def test_hoy_pinta_piezas_por_hora(self) -> None:
        self._vender(HOY)
        ventana, ui = self._pestana()
        ventana._ana_estado.update(clave=tb.HOY, ancla=HOY)
        ui.refrescar(ventana, self.s)
        self.assertEqual(ventana.ana_barras_titulo.text(), "PIEZAS POR HORA")

    def test_no_se_avanza_al_futuro(self) -> None:
        ventana, ui = self._pestana()
        ventana._ana_estado.update(clave=tb.SEMANA, ancla=date.today())
        antes = ventana._ana_estado["ancla"]
        ui._mover(ventana, 1)
        self.assertEqual(ventana._ana_estado["ancla"], antes)

    def test_un_dia_pasado_negativo_se_pinta_y_el_futuro_no(self) -> None:
        # Revisión 2026-11-12: con el ajuste del dueño por día, un día pasado
        # puede salir negativo. Antes −1 era la marca de «día futuro» y ese día
        # se pintaba vacío; ahora el futuro va como None y el negativo es dato.
        lunes = HOY - timedelta(days=HOY.weekday())
        martes = lunes + timedelta(days=1)
        self._vender(martes, "300")
        self.s.add(LibretaCorte(fecha=martes, creado_por="VEND-1", monto_final=Decimal("9200"),
                                monto_esperado=Decimal("10000"), reactivo_inicial=Decimal("9000"),
                                reactivo_final=Decimal("9000"),
                                desde=datetime.combine(martes, time(9)).astimezone(),
                                hasta=datetime.combine(martes, time(21)).astimezone(), periodo_label="semana"))
        self.s.commit()
        ventana, ui = self._pestana()
        ventana._ana_estado.update(clave=tb.SEMANA, ancla=martes)
        with patch.object(tb, "cargar", side_effect=lambda *a, **kw: _CARGAR(*a, **{**kw, "hoy": martes})):
            ui.refrescar(ventana, self.s)
        datos = ventana.ana_barras.datos
        self.assertEqual(len(datos), 7)
        self.assertEqual(datos[1][1], -500.0)
        self.assertEqual(datos[1][2], "−$500")
        self.assertTrue(all(v is None for _e, v, _t in datos[2:]))     # miércoles en adelante
        self.assertEqual(datos[0][1], 0.0)
        # Pintar con negativos y días por venir no truena.
        ventana.ana_barras.resize(500, 200)
        ventana.ana_barras.grab()

    def test_la_combinacion_alterna_lo_real(self) -> None:
        from unittest.mock import patch

        ventana, ui = self._pestana()
        with patch.object(ui, "_refrescar_con_sesion", lambda w: None):
            ui._alternar_real(ventana)
            self.assertTrue(ventana._ana_estado["real"])
            ui._alternar_real(ventana)
            self.assertFalse(ventana._ana_estado["real"])


class ElPosUsaLaNuevaTests(unittest.TestCase):
    def test_la_pestana_ya_no_lee_la_tabla_venta(self) -> None:
        import inspect

        from pos_uniformes.ui import main_window
        from pos_uniformes.ui.views import analytics_view

        self.assertIn("from pos_uniformes.ui.helpers.analytics_tablero import construir",
                      inspect.getsource(analytics_view.build_analytics_tab))
        fuente = inspect.getsource(main_window.MainWindow._refresh_analytics)
        self.assertIn("analytics_tablero import refrescar", fuente)
        self.assertNotIn("load_confirmed_sales_for_analytics", fuente)


if __name__ == "__main__":
    unittest.main()


class PeriodoAMediasTests(_ConBase):
    def test_la_semana_en_curso_se_compara_con_los_mismos_dias(self) -> None:
        # Hoy es sábado: lunes–sábado contra lunes–sábado; el domingo pasado no cuenta.
        self._vender(HOY)                                   # este sábado
        self._vender(HOY - timedelta(days=7))               # sábado pasado: sí cuenta
        self._vender(HOY - timedelta(days=6))               # domingo pasado: NO cuenta
        t = tb.cargar(self.s, tb.SEMANA, HOY, hoy=HOY)
        self.assertTrue(t.a_medias)
        self.assertEqual(t.antes.cobrado, Decimal("300.00"))

    def test_una_semana_cerrada_se_compara_completa(self) -> None:
        self._vender(HOY - timedelta(days=7))
        self._vender(HOY - timedelta(days=6))
        t = tb.cargar(self.s, tb.SEMANA, HOY, hoy=HOY + timedelta(days=14))
        self.assertFalse(t.a_medias)
        self.assertEqual(t.antes.cobrado, Decimal("600.00"))


class HoyHastaLaHoraTests(_ConBase):
    def test_hoy_se_compara_con_ayer_hasta_esta_hora(self) -> None:
        self._vender(HOY)                                              # hoy a las 12
        ayer = HOY - timedelta(days=1)
        self.s.add_all([
            LibretaVenta(employee_code="VEND-4", employee_name="F", tipo="venta", piezas=1, monto_total=Decimal("300"),
                         monto_neto=Decimal("300"), detalle=[], created_at=datetime.combine(ayer, time(11, 0)).astimezone()),
            LibretaVenta(employee_code="VEND-4", employee_name="F", tipo="venta", piezas=1, monto_total=Decimal("500"),
                         monto_neto=Decimal("500"), detalle=[], created_at=datetime.combine(ayer, time(17, 0)).astimezone()),
        ])
        self.s.commit()
        t = tb.cargar(self.s, tb.HOY, HOY, hoy=HOY, ahora=datetime.combine(HOY, time(13, 0)))
        self.assertTrue(t.hasta_la_hora)
        self.assertEqual(t.antes.cobrado, Decimal("300.00"))         # lo de las 17:00 de ayer no cuenta
        t = tb.cargar(self.s, tb.HOY, ayer, hoy=HOY)                   # ayer, ya cerrado: completo
        self.assertFalse(t.hasta_la_hora)
