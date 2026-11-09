"""«Reintentar anotar»: el cliente ya pagó y solo falló guardar (A2/A3).

Cobrar, imprimir, anotar y sincronizar son cosas distintas. Cuando lo único
que falla es ANOTAR (escribir la cola local de esta PC):
- el aviso dice que el cliente ya pagó y no pide volver a cobrar;
- la operación se guarda tal cual (foto exacta) y «Reintentar anotar»
  guarda ESA misma: mismo tipo, montos, anticipo, descuento y uuid;
- reintentar no imprime, no cobra y no duplica;
- si falla, solo hay mensaje de error; nunca uno de éxito.

Se usa la cola real en una carpeta temporal; la falla se simula en la
escritura del archivo (como cuando Windows o el antivirus lo tienen tomado).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox

from pos_uniformes.services import libreta_local_queue_service as cola
from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

_MOD = "pos_uniformes.ui.views.quick_sale_view"
_GUARDAR_REAL = cola._save_raw


def _items():
    return [
        {"sku": "SKU1", "nombre": "Pants 3pz", "talla": "8", "color": "", "precio": Decimal("590.00"), "cantidad": 2},
        {"sku": "SKU2", "nombre": "Playera", "talla": "8", "color": "", "precio": Decimal("200.00"), "cantidad": 1},
    ]


class _Ocupado:
    """`_save_raw` que falla las primeras `n` veces (archivo tomado)."""

    def __init__(self, n: int) -> None:
        self.n = n
        self.llamadas = 0

    def __call__(self, entries):
        self.llamadas += 1
        if self.llamadas <= self.n:
            raise PermissionError("el archivo está en uso por otro proceso")
        return _GUARDAR_REAL(entries)


class ReintentarAnotarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.raiz = Path(tempfile.mkdtemp(prefix="anotar_"))
        for p in (
            patch.object(cola, "satellite_data_dir", return_value=self.raiz),
            patch.object(cola, "_ESPERA_ARCHIVO_OCUPADO", 0),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(shutil.rmtree, self.raiz, True)
        self.w = QuickSaleWidget(SimpleNamespace(offline_mode=True, _kiosk_lookup_from_cache=None))
        self.addCleanup(self._cerrar_widget)
        self.w._employee_code, self.w._employee_name = "VEND-3", "Evelyn Ruiz"
        self.w._items = _items()
        for nombre in ("_drenar_libreta_en_background", "_flash_scan_hint", "_avisar_sin_ticket"):
            p = patch.object(self.w, nombre)
            setattr(self, nombre.strip("_"), p.start())
            self.addCleanup(p.stop)

    def _cerrar_widget(self) -> None:
        """No dejar avisos modales abiertos: contaminaban la cartelera."""
        from PyQt6.QtCore import QEvent
        if getattr(self, "_widget_cerrado", False):
            return
        self._widget_cerrado = True
        for box in self.w.findChildren(QMessageBox):
            box.done(0)
        self.w.close()
        self.w.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        QApplication.processEvents()

    # ── utilidades ────────────────────────────────────────────────────
    def _cola(self) -> list[dict]:
        path = self.raiz / "data" / "libreta_pendiente.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def _fallar(self, n=10_000):
        ocupado = _Ocupado(n)
        return patch.object(cola, "_save_raw", side_effect=ocupado), ocupado

    def _aviso_texto(self) -> str:
        return self.w._aviso_anotacion.text()

    def _exitos(self) -> list[str]:
        return [c.args[0] for c in self.flash_scan_hint.call_args_list if "✅" in c.args[0]]

    def _anotar_fallando(self, tipo="venta", **kw):
        parche, _ = self._fallar()
        with parche:
            return self.w._registrar_y_vaciar(tipo, **kw)

    # ── venta normal ──────────────────────────────────────────────────
    def test_venta_normal_falla_y_el_reintento_guarda_la_misma(self) -> None:
        self.assertFalse(self._anotar_fallando("venta", pago_tarjeta=True))
        self.assertEqual(self._cola(), [])
        [foto] = self.w._anotaciones_pendientes
        self.assertEqual(self.w._items, [])  # el carrito ya no invita a cobrar otra vez
        self.assertFalse(self.w._btn_reintentar_anotar.isHidden())

        texto = self._aviso_texto()
        self.assertIn("YA PAGÓ", texto)
        self.assertIn("NO le vuelvas a cobrar", texto)
        self.assertNotIn("vuelve a cobrarla", texto)
        self.assertIn("Reintentar anotar", [b.text() for b in self.w._aviso_anotacion.buttons()])
        self.assertEqual(self._exitos(), [])

        # Mientras tanto el carrito cambia (otra clienta): no debe importar.
        self.w._items = [{"sku": "X", "nombre": "Calceta", "talla": "U", "precio": Decimal("50"), "cantidad": 9}]
        with patch(f"{_MOD}.route_tickets") as imprimir, \
                patch.object(self.w, "_cobrar_con_monedero") as cobrar:
            self.assertTrue(self.w._reintentar_anotacion())
        imprimir.assert_not_called()
        cobrar.assert_not_called()

        [guardada] = self._cola()
        self.assertEqual(guardada, foto)  # idéntica: tipo, montos, uuid, hora
        self.assertEqual((guardada["tipo"], guardada["monto_total"]), ("venta", "1380.00"))
        self.assertEqual([i["cantidad"] for i in guardada["items"]], [2, 1])
        self.assertTrue(guardada["pago_tarjeta"])
        self.assertEqual(self.w._anotaciones_pendientes, [])
        self.assertTrue(self.w._btn_reintentar_anotar.isHidden())
        self.assertEqual(len(self._exitos()), 1)

    # ── apartado con anticipo ─────────────────────────────────────────
    def test_apartado_con_anticipo_sigue_siendo_apartado(self) -> None:
        self.assertFalse(self._anotar_fallando(
            "apartado", cliente="Blanca", anticipo=Decimal("300"), anticipo_tarjeta=True,
        ))
        self.w._reintentar_anotacion()
        apartado, abono = self._cola()
        self.assertEqual((apartado["tipo"], apartado["monto_total"], apartado["cliente"]),
                         ("apartado", "1380.00", "Blanca"))
        self.assertEqual((abono["tipo"], abono["monto_total"], abono["comisiones"]), ("abono", "300.00", 0))
        self.assertTrue(abono["pago_tarjeta"])
        self.assertIn("anticipo", abono["cliente"])
        self.assertNotEqual(apartado["operacion_uuid"], abono["operacion_uuid"])

    def test_apartado_si_solo_falla_el_anticipo_no_se_duplica_el_apartado(self) -> None:
        # El apartado sí se guarda; el anticipo (segunda escritura) no.
        llamadas = {"n": 0}

        def segunda_falla(entries):
            llamadas["n"] += 1
            if llamadas["n"] == 2:
                raise PermissionError("tomado")
            return _GUARDAR_REAL(entries)

        with patch.object(cola, "_save_raw", side_effect=segunda_falla):
            self.assertFalse(self.w._registrar_y_vaciar(
                "apartado", cliente="Blanca", anticipo=Decimal("300"), anticipo_tarjeta=False,
            ))
        self.assertEqual([e["tipo"] for e in self._cola()], ["apartado"])
        self.w._reintentar_anotacion()
        self.assertEqual([e["tipo"] for e in self._cola()], ["apartado", "abono"])  # sin repetir

    # ── descuento de empleada ─────────────────────────────────────────
    def test_venta_con_descuento_de_empleada_conserva_el_descuento(self) -> None:
        self.w._discount_active = True
        _s, _d, total = self.w._compute_totals()
        esperado = str(Decimal(str(total)).quantize(Decimal("0.01")))
        self.assertNotEqual(esperado, "1380.00")  # sí hay descuento
        self.assertFalse(self._anotar_fallando("venta"))
        self.assertFalse(self.w._discount_active)  # el carrito se limpió...
        self.assertIn("descuento de empleada", self._aviso_texto())
        self.w._reintentar_anotacion()
        [guardada] = self._cola()
        self.assertTrue(guardada["descuento_empleada"])  # ...pero la foto lo conserva
        self.assertEqual(guardada["monto_total"], esperado)

    # ── fallo persistente ─────────────────────────────────────────────
    def test_fallo_persistente_solo_muestra_error(self) -> None:
        self.assertFalse(self._anotar_fallando("venta"))
        parche, ocupado = self._fallar()
        with parche:
            self.assertFalse(self.w._reintentar_anotacion())
            self.assertFalse(self.w._reintentar_anotacion())
        self.assertGreaterEqual(ocupado.llamadas, 2)
        self.assertEqual(len(self.w._anotaciones_pendientes), 1)
        self.assertIn("YA PAGÓ", self._aviso_texto())
        self.assertEqual(self._exitos(), [])
        self.avisar_sin_ticket.assert_not_called()
        self.assertEqual(self._cola(), [])

    def test_sin_ticket_fallido_no_dice_registrada(self) -> None:
        parche, _ = self._fallar()
        with patch.object(self.w, "_load_business_info", return_value=("M", "", "")), \
                patch.object(self.w, "_ask_venta_options", return_value=(False, False, True)), \
                patch(f"{_MOD}.route_tickets") as imprimir, parche:
            self.w._on_ticket_venta()
        imprimir.assert_not_called()
        self.avisar_sin_ticket.assert_not_called()  # nada de «✅ registrada»
        self.assertIn("YA PAGÓ", self._aviso_texto())
        self.assertEqual(len(self.w._anotaciones_pendientes), 1)

    def test_sin_ticket_exitoso_si_avisa(self) -> None:
        with patch.object(self.w, "_load_business_info", return_value=("M", "", "")), \
                patch.object(self.w, "_ask_venta_options", return_value=(False, False, True)), \
                patch(f"{_MOD}.route_tickets"):
            self.w._on_ticket_venta()
        self.avisar_sin_ticket.assert_called_once()
        self.assertEqual(len(self._cola()), 1)

    # ── identidad y doble toque ───────────────────────────────────────
    def test_uuid_estable_entre_intentos(self) -> None:
        self._anotar_fallando("venta")
        uuid = self.w._anotaciones_pendientes[0]["operacion_uuid"]
        parche, _ = self._fallar()
        with parche:
            self.w._reintentar_anotacion()
        self.assertEqual(self.w._anotaciones_pendientes[0]["operacion_uuid"], uuid)
        self.w._reintentar_anotacion()
        self.assertEqual(self._cola()[0]["operacion_uuid"], uuid)

    def test_doble_toque_en_reintentar_no_duplica(self) -> None:
        self._anotar_fallando("venta")
        self.w._btn_reintentar_anotar.click()
        self.w._btn_reintentar_anotar.click()
        self.w._reintentar_anotacion()
        self.assertEqual(len(self._cola()), 1)
        # Un toque que llega mientras el primero sigue guardando se ignora.
        self.w._anotaciones_pendientes = [dict(self._cola()[0])]
        self.w._reintentando_anotacion = True
        self.assertFalse(self.w._reintentar_anotacion())
        self.w._reintentando_anotacion = False
        # Y aunque llegara, la cola reconoce el uuid y no lo agrega otra vez.
        self.w._reintentar_anotacion()
        self.assertEqual(len(self._cola()), 1)

    def test_la_cola_rechaza_el_mismo_uuid(self) -> None:
        entrada = {"employee_code": "VEND-3", "tipo": "venta", "items": [], "monto_total": "1",
                   "operacion_uuid": "u-1"}
        self.assertTrue(cola.encolar_operacion(dict(entrada)))
        self.assertFalse(cola.encolar_operacion(dict(entrada)))
        sin_uuid = {"employee_code": "VEND-3", "tipo": "abono", "items": [], "monto_total": "1"}
        self.assertTrue(cola.encolar_operacion(dict(sin_uuid)))
        self.assertTrue(cola.encolar_operacion(dict(sin_uuid)))  # sin uuid: como antes
        self.assertEqual(len(self._cola()), 3)

    # ── impresión ≠ anotación ─────────────────────────────────────────
    def test_si_la_impresion_no_arranca_no_se_anota_ni_se_retiene(self) -> None:
        with patch.object(self.w, "_load_business_info", return_value=("M", "", "")), \
                patch.object(self.w, "_ask_venta_options", return_value=(False, False, False)), \
                patch(f"{_MOD}.route_tickets") as imprimir:
            self.w._on_ticket_venta()  # la impresora nunca arrancó: on_printed no se llama
        imprimir.assert_called_once()
        self.assertEqual(self._cola(), [])
        self.assertEqual(self.w._anotaciones_pendientes, [])
        self.assertEqual(len(self.w._items), 2)  # el carrito sigue: no se cobró nada aún

    def test_impreso_y_no_anotado_ofrece_reintentar(self) -> None:
        parche, _ = self._fallar()
        with patch.object(self.w, "_load_business_info", return_value=("M", "", "")), \
                patch.object(self.w, "_ask_venta_options", return_value=(False, False, False)), \
                patch(f"{_MOD}.route_tickets") as imprimir, parche:
            self.w._on_ticket_venta()
            imprimir.call_args.kwargs["on_printed"]()
        self.assertEqual(len(self.w._anotaciones_pendientes), 1)
        self.assertIn("NO vuelvas a imprimir", self._aviso_texto())

    # ── higiene Qt ────────────────────────────────────────────────────
    def test_no_deja_avisos_ni_modal_activo(self) -> None:
        """Antes dejaba un QMessageBox modal y fallaban 10 pruebas de la
        cartelera que corrían después en el mismo proceso."""
        antes = _modales_visibles()
        self.assertFalse(self._anotar_fallando("venta"))
        self.assertTrue(_modales_visibles() - antes)  # sí hubo aviso
        self._cerrar_widget()
        self.assertEqual(_modales_visibles() - antes, set())
        self.assertIsNone(QApplication.activeModalWidget())


def _modales_visibles() -> set[int]:
    return {id(w) for w in QApplication.topLevelWidgets() if isinstance(w, QMessageBox) and w.isVisible()}


if __name__ == "__main__":
    unittest.main()
