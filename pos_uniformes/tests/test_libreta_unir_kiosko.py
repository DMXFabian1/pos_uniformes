"""«Unir con la anterior» en MOVIMIENTOS del kiosko (Daniel, 2026-11-13).

Solo con el gafete del dueño; confirma con «Cancelar» por defecto; las ventas
unidas se marcan «🔗 misma clienta» sin perder cada renglón.
"""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import LibretaVenta
from pos_uniformes.ui.helpers import libreta_unir_helper as h

AHORA = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)


def _fila(i, *, minutos=0, tipo="venta", grupo=None, code="VEND-4", empleada=False):
    return SimpleNamespace(
        id=i, tipo=tipo, piezas=1, comisiones=1, monto_total=Decimal("300.00"), monto_neto=Decimal("300.00"),
        pago_tarjeta=False, employee_code=code, employee_name="Fanny Ortiz", cliente=None,
        created_at=AHORA + timedelta(minutes=minutos), descuento_empleada=empleada, privado=False,
        detalle=[{"nombre": "Playera", "cantidad": 1}], operacion_grupo_id=grupo,
        operacion_unida_por="VEND-1" if grupo else None, operacion_unida_en=AHORA if grupo else None,
    )


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


class PurosDeLaPantallaTests(_Qt):
    def test_marca_en_la_tabla(self) -> None:
        filas = [_fila(1640, minutos=7, grupo=1639), _fila(1639, grupo=1639), _fila(1641, minutos=9)]
        from pos_uniformes.services.libreta_unir_service import horas_de_las_otras

        horas = horas_de_las_otras(filas)
        self.assertEqual(horas, {1639: ["12:07"], 1640: ["12:00"]})
        # Con cuál va cada una se lee en la celda, por la hora (sin tooltip).
        self.assertEqual(h.marcar_tipo("Venta — Fanny", filas[0], horas), "🔗 con 12:00 — Fanny")
        self.assertEqual(h.marcar_tipo("Venta — Fanny", filas[1], horas), "🔗 con 12:07 — Fanny")
        self.assertEqual(h.marcar_tipo("Venta — Fanny", filas[2], horas), "Venta — Fanny")
        self.assertEqual(
            h.texto_detalle(filas[0], filas), "🔗 Misma clienta que la de 12:00 (#1639): cuentan como 1 operación."
        )
        self.assertEqual(h.texto_detalle(filas[2], filas), "")

    def test_dos_grupos_y_otra_empleada_en_medio_se_distinguen(self) -> None:
        """Fanny: 12:00+12:07 y 15:00+15:05; Stayce vende entre las 12:00 y 12:07."""
        from pos_uniformes.services.libreta_unir_service import horas_de_las_otras

        filas = [
            _fila(1, grupo=1), _fila(2, minutos=3, code="VEND-6"), _fila(3, minutos=7, grupo=1),
            _fila(4, minutos=180, grupo=4), _fila(5, minutos=185, grupo=4), _fila(6, minutos=190, grupo=4),
        ]
        horas = horas_de_las_otras(filas)
        marcas = {f.id: h.marcar_tipo("Venta — Fanny", f, horas) for f in filas}
        self.assertEqual(marcas[1], "🔗 con 12:07 — Fanny")
        self.assertEqual(marcas[2], "Venta — Fanny")
        self.assertEqual(marcas[3], "🔗 con 12:00 — Fanny")
        self.assertEqual(marcas[4], "🔗 con 15:05 y 15:10 — Fanny")
        # Con tarjeta o candado la hora sigue delante.
        self.assertEqual(h.marcar_tipo("🔒 Venta (tarjeta) — Fanny", filas[0], horas), "🔗 🔒 con 12:07 (tarjeta) — Fanny")
        self.assertIn("las de 15:00 (#4) y 15:10 (#6)", h.texto_detalle(filas[4], filas))

    def test_primera_venta_del_dia_no_ofrece_unir(self) -> None:
        from PyQt6.QtWidgets import QPushButton

        b = QPushButton()
        primera, otra, segunda = _fila(1), _fila(2, minutos=1, code="VEND-6"), _fila(3, minutos=2)
        rows = [segunda, otra, primera]
        h.actualizar_boton(b, primera, es_dueno=True, rows=rows)
        self.assertEqual((not b.isHidden(), b.text(), b.isEnabled()), (True, h.TEXTO_ELIGE_SEGUNDA, False))
        h.actualizar_boton(b, segunda, es_dueno=True, rows=rows)
        self.assertEqual((b.text(), b.isEnabled()), (h.TEXTO_UNIR, True))
        h.actualizar_boton(b, otra, es_dueno=True, rows=rows)
        self.assertEqual((b.text(), b.isEnabled()), (h.TEXTO_ELIGE_SEGUNDA, False))

    def test_el_boton_segun_la_fila(self) -> None:
        from PyQt6.QtWidgets import QPushButton

        b = QPushButton()
        h.actualizar_boton(b, _fila(1), es_dueno=True)
        self.assertEqual((not b.isHidden(), b.text(), b.isEnabled()), (True, h.TEXTO_UNIR, True))
        h.actualizar_boton(b, _fila(1, grupo=1), es_dueno=True)
        self.assertEqual(b.text(), h.TEXTO_SEPARAR)
        h.actualizar_boton(b, _fila(2, tipo="abono"), es_dueno=True)
        self.assertTrue(b.isHidden())
        h.actualizar_boton(b, _fila(3, empleada=True), es_dueno=True)
        self.assertTrue(b.isHidden())
        h.actualizar_boton(b, _fila(1), es_dueno=False)
        self.assertTrue(b.isHidden())

    def test_confirmacion_con_cancelar_por_defecto(self) -> None:
        caja, si = h.construir_confirmacion(None, "Unir en una operación", "texto", "detalle", "Unir")
        self.assertEqual(caja.defaultButton().text(), "Cancelar")
        self.assertEqual(caja.escapeButton().text(), "Cancelar")
        self.assertEqual(si.text(), "Unir")


class AlTocarTests(_Qt):
    """El flujo completo con una base SQLite (sin red ni caja)."""

    def setUp(self) -> None:
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        self.engine = engine
        with Session(engine) as s:
            for i, m in ((1639, 0), (1640, 7)):
                s.add(LibretaVenta(id=i, employee_code="VEND-4", employee_name="Fanny Ortiz", tipo="venta",
                                   piezas=1, comisiones=1, monto_total=Decimal("300"), monto_neto=Decimal("300"),
                                   descuento_empleada=False, privado=False, detalle=[],
                                   created_at=AHORA + timedelta(minutes=m)))
            s.commit()
        self.refrescos = 0

    @contextmanager
    def _sesion(self):
        s = Session(self.engine)
        try:
            yield s
        finally:
            s.close()

    def _ventana(self, *, dueno=True):
        from PyQt6.QtWidgets import QTableWidget

        tabla = QTableWidget(1, 7)
        tabla.setCurrentCell(0, 0)

        def refrescar():
            self.refrescos += 1

        from PyQt6.QtWidgets import QWidget

        win = QWidget()   # la confirmación necesita un padre de verdad
        self.addCleanup(win.deleteLater)
        for nombre, valor in dict(
            _libreta_is_owner=dueno, _libreta_code="VEND-1" if dueno else "VEND-4", libreta_table=tabla,
            _libreta_rows_pintadas=[_fila(1640, minutos=7)], _set_status=lambda m: None,
            _refresh_libreta_view=refrescar, _libreta_resumen_de=lambda r: "12:00 · Venta",
        ).items():
            setattr(win, nombre, valor)
        return win

    def _grupos(self):
        with Session(self.engine) as s:
            return {r.id: r.operacion_grupo_id for r in s.query(LibretaVenta)}

    def _tocar(self, win, respuesta):
        textos = []

        def exec_(caja):
            textos.append(caja.text())
            boton = next(b for b in caja.buttons() if b.text() == respuesta)
            caja.clickedButton = lambda: boton
            return 0

        with patch("pos_uniformes.database.connection.get_session", self._sesion), \
             patch.object(QMessageBox, "exec", exec_), \
             patch.object(QMessageBox, "information", lambda *a, **k: textos.append(a[2])), \
             patch.object(QMessageBox, "warning", lambda *a, **k: self.fail(a[2])):
            h.al_tocar(win)
        return textos

    def test_cancelar_no_une(self) -> None:
        textos = self._tocar(self._ventana(), "Cancelar")
        self.assertEqual(self._grupos(), {1639: None, 1640: None})
        self.assertEqual(self.refrescos, 0)
        self.assertEqual(
            textos[0],
            "#1639 y #1640 de Fanny (VEND-4) cuentan como 1 operación. "
            "El dinero, las piezas y las comisiones no cambian.",
        )

    def test_unir_y_luego_separar(self) -> None:
        win = self._ventana()
        self._tocar(win, "Unir")
        self.assertEqual(self._grupos(), {1639: 1639, 1640: 1639})
        self.assertEqual(self.refrescos, 1)
        win._libreta_rows_pintadas = [_fila(1640, minutos=7, grupo=1639)]
        self._tocar(win, "Separar")
        self.assertEqual(self._grupos(), {1639: None, 1640: None})

    def test_corte_en_medio_avisa_sin_preguntar_ni_unir(self) -> None:
        from pos_uniformes.database.models import LibretaCorte

        with Session(self.engine) as s:
            momento = AHORA + timedelta(minutes=3)
            s.add(LibretaCorte(fecha=momento.date(), monto_final=Decimal("0"), operaciones=1, piezas=1,
                               creado_por="VEND-1", created_at=momento, hasta=momento))
            s.commit()
        textos = self._tocar(self._ventana(), "Unir")
        self.assertEqual(textos, [h.lu.TEXTO_CORTE_EN_MEDIO])
        self.assertEqual(self._grupos(), {1639: None, 1640: None})
        self.assertEqual(self.refrescos, 0)

    def test_quien_no_es_el_dueno_no_hace_nada(self) -> None:
        self._tocar(self._ventana(dueno=False), "Unir")
        self.assertEqual(self._grupos(), {1639: None, 1640: None})


class VentanaTests(_Qt):
    """El botón vive en «Movimiento elegido» y la marca en la tabla."""

    def _ventana(self):
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow
        from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

        win = QuoteSatelliteWindow(user_id=1, offline_mode=True)
        win._gafete_libreta_valido = lambda c: True
        win._refresh_libreta_view = lambda: None
        win.libreta_gate_input.setText(QuickSaleWidget._OWNER_CODE)
        win._on_libreta_gate_scan()
        self.addCleanup(win.close)
        return win

    def test_marca_y_boton(self) -> None:
        win = self._ventana()
        win._pintar_libreta([_fila(1641, minutos=9), _fila(1640, minutos=7, grupo=1639), _fila(1639, grupo=1639)])
        tipos = [win.libreta_table.item(i, 2).text() for i in range(3)]
        self.assertFalse(tipos[0].startswith("🔗"))
        self.assertTrue(tipos[1].startswith("🔗 con 12:00 — "))
        self.assertTrue(tipos[2].startswith("🔗 con 12:07 — "))
        self.assertIn("Misma clienta", win.libreta_table.item(1, 2).toolTip())
        win.libreta_table.selectRow(1)
        win._on_libreta_seleccion()
        self.assertEqual(win.libreta_unir_button.text(), h.TEXTO_SEPARAR)
        self.assertIn("Misma clienta que la de 12:00 (#1639)", win.libreta_mov_detalle.text())
        win.libreta_table.selectRow(0)
        win._on_libreta_seleccion()
        self.assertEqual(win.libreta_unir_button.text(), h.TEXTO_UNIR)
        # Las cifras de arriba cuentan el grupo como 1: 3 renglones, 2 operaciones.
        self.assertTrue(win.libreta_resumen_label.text().startswith("2 operaciones"))


if __name__ == "__main__":
    unittest.main()
