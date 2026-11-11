"""«¿Quién compra?» del kiosko, segunda vuelta de estética (2026-11-10):
tarjetas por cliente, búsqueda al escribir, lo buscado pasa al alta y pista
del teléfono. Sin base de datos.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from pos_uniformes.services.clientes.identidad_service import ClienteEncontrado
from pos_uniformes.ui.dialogs import cliente_rapido_dialog as crd
from pos_uniformes.ui.dialogs.cliente_rapido_dialog import ClienteRapidoDialog, iniciales, sugerencia_de_alta

ANA = ClienteEncontrado(id=7, codigo="CLI-000007", nombre="Ana López", telefono_enmascarado="•••• ••45 21")
LUIS = ClienteEncontrado(id=9, codigo="CLI-000009", nombre="Luis Ruiz", telefono_enmascarado="")


class PuroTests(unittest.TestCase):
    def test_iniciales(self) -> None:
        self.assertEqual(iniciales("Daniel Fabian"), "DF")
        self.assertEqual(iniciales("ana"), "A")
        self.assertEqual(iniciales("Profa. Carmen Ruiz"), "PC")
        self.assertEqual(iniciales(""), "?")

    def test_lo_buscado_como_alta(self) -> None:
        self.assertEqual(sugerencia_de_alta("laura pérez"), ("Laura Pérez", ""))
        self.assertEqual(sugerencia_de_alta("667 123 4521"), ("", "6671234521"))
        self.assertEqual(sugerencia_de_alta("4287"), ("", ""), "unos dígitos no son un teléfono")
        self.assertEqual(sugerencia_de_alta("CLI-000015"), ("", ""))


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def _dialogo(self, encontrados=None):
        buscar = MagicMock(return_value=list(encontrados or []))
        d = ClienteRapidoDialog(None, buscar=buscar, registrar=MagicMock(), reenviar=MagicMock())
        return d, buscar


class TarjetasTests(_Qt):
    def test_una_tarjeta_por_cliente_y_marca_la_elegida(self) -> None:
        d, _ = self._dialogo([ANA, LUIS])
        d.busqueda_input.setText("a")
        d._on_buscar()
        filas = [d.resultados.itemWidget(d.resultados.item(i)) for i in range(2)]
        self.assertTrue(all(isinstance(f, crd._FilaCliente) for f in filas))
        self.assertEqual([f.property("sel") for f in filas], [True, False])
        self.assertFalse(filas[0].check.isHidden())
        d.resultados.setCurrentRow(1)
        self.assertEqual([f.property("sel") for f in filas], [False, True])
        self.assertIn("Ana López", d.resultados.item(0).text(), "el texto sigue para buscar y leer")
        self.assertEqual(d.estado_label.text(), "2 clientes encontrados.")

    def test_un_cliente_en_singular(self) -> None:
        d, _ = self._dialogo([ANA])
        d.busqueda_input.setText("ana")
        d._on_buscar()
        self.assertEqual(d.estado_label.text(), "1 cliente encontrado.")


class BuscarAlEscribirTests(_Qt):
    def test_busca_sola_al_dejar_de_escribir(self) -> None:
        d, buscar = self._dialogo([ANA])
        d.busqueda_input.textEdited.emit("an")
        self.assertFalse(d._buscar_timer.isActive(), "con menos de 3 letras no busca")
        d.busqueda_input.setText("ana")
        d.busqueda_input.textEdited.emit("ana")
        self.assertTrue(d._buscar_timer.isActive())
        self.assertEqual(d._buscar_timer.interval(), crd.BUSCAR_AL_ESCRIBIR_MS)
        d._buscar_timer.timeout.emit()
        buscar.assert_called_once_with("ana")
        self.assertEqual(d.resultados.count(), 1)

    def test_enter_busca_de_una_vez(self) -> None:
        d, buscar = self._dialogo([ANA])
        d.busqueda_input.setText("ana")
        d.busqueda_input.textEdited.emit("ana")
        d._on_buscar()
        self.assertFalse(d._buscar_timer.isActive())
        buscar.assert_called_once()


class SinResultadosTests(_Qt):
    def test_lo_buscado_pasa_al_alta(self) -> None:
        d, _ = self._dialogo([])
        d.busqueda_input.setText("laura pérez")
        d._on_buscar()
        self.assertEqual(d.nombre_input.text(), "Laura Pérez")
        self.assertIn("No encontramos «laura pérez»", d.estado_label.text())

    def test_un_telefono_completo_pasa_al_telefono(self) -> None:
        d, _ = self._dialogo([])
        d.busqueda_input.setText("6671234521")
        d._on_buscar()
        self.assertEqual((d.nombre_input.text(), d.telefono_input.text()), ("", "6671234521"))

    def test_no_pisa_lo_que_ella_escribio(self) -> None:
        d, _ = self._dialogo([])
        d.nombre_input.setText("Laura Pérez Gómez")
        d.busqueda_input.setText("laura")
        d._on_buscar()
        self.assertEqual(d.nombre_input.text(), "Laura Pérez Gómez")

    def test_al_seguir_escribiendo_se_actualiza_la_sugerencia(self) -> None:
        d, _ = self._dialogo([])
        d.busqueda_input.setText("lau")
        d._on_buscar(en_vivo=True)
        d.busqueda_input.setText("laura")
        d._on_buscar(en_vivo=True)
        self.assertEqual(d.nombre_input.text(), "Laura")


class PistaTelefonoTests(_Qt):
    def test_cuenta_los_digitos_y_avisa_cuando_esta_listo(self) -> None:
        d, _ = self._dialogo()
        self.assertEqual(d.telefono_pista.text(), "0/10 dígitos")
        d.telefono_input.setText("667 123")
        self.assertEqual(d.telefono_pista.text(), "6/10 dígitos")
        self.assertFalse(d.telefono_pista.property("ok"))
        d.telefono_input.setText("667 123 4521")
        self.assertEqual(d.telefono_pista.text(), "✓ Teléfono listo")
        self.assertTrue(d.telefono_pista.property("ok"))


if __name__ == "__main__":
    unittest.main()
