"""Alta en el kiosko (Daniel, 2026-11-10): el cliente nuevo entra directo a
Maximoda Club, y «Proponer programa…» está a la mano al registrarlo.

Las reglas van contra la base local de prueba (`pos_uniformes_test`) en una
transacción que se revierte; la pantalla, sin base.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor, QImage
from PyQt6.QtWidgets import QApplication
from sqlalchemy import select

from pos_uniformes.database.models import Membresia
from pos_uniformes.services.clientes import credencial_whatsapp_service as cws
from pos_uniformes.services.fidelizacion import membresia_service as ms
from pos_uniformes.tests.test_e4a_membresias import _Base
from pos_uniformes.ui.dialogs import credencial_whatsapp_dialog as cwd
from pos_uniformes.ui.helpers import quick_sale_cliente_helper as kiosko
from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget


class ClubAlRegistrarTests(_Base):
    def _membresias(self, cliente) -> list[Membresia]:
        return list(self.s.scalars(select(Membresia).where(Membresia.cliente_id == cliente.id)))

    def test_entra_directo_al_club(self) -> None:
        m = ms.inscribir_al_club_al_registrar(self.s, cliente_id=self.cliente.id, employee_code=self.lupita.codigo)
        self.assertIsNotNone(m)
        estado = ms.estado_de_cliente(self.s, self.cliente.id)
        self.assertEqual(estado.activa.programa.clave, "CLUB")
        self.assertEqual(estado.activa.propuesta_por_employee_code, self.lupita.codigo)

    def test_sin_empleada_el_alta_queda_sin_programa(self) -> None:
        for codigo in (None, "", self.baja.codigo):
            with self.subTest(codigo=codigo):
                self.assertIsNone(ms.inscribir_al_club_al_registrar(self.s, cliente_id=self.cliente.id, employee_code=codigo))
        self.assertEqual(self._membresias(self.cliente), [])
        self.assertTrue(self.s.get(type(self.cliente), self.cliente.id).activo, "la ficha sigue igual")

    def test_si_ya_tiene_programa_no_truena(self) -> None:
        ms.inscribir_al_club_al_registrar(self.s, cliente_id=self.cliente.id, employee_code=self.lupita.codigo)
        self.assertIsNone(ms.inscribir_al_club_al_registrar(self.s, cliente_id=self.cliente.id, employee_code=self.lupita.codigo))
        self.assertEqual(len(self._membresias(self.cliente)), 1)
        # La sesión sigue sirviendo después del punto de guardado revertido.
        self.assertIsNotNone(self._cliente("Otra E4A").id)


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


class KioskoTests(_Qt):
    def test_el_alta_del_kiosko_inscribe_al_club_antes_de_guardar(self) -> None:
        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        w._employee_code = "VEND-2"
        orden = []
        sesion = SimpleNamespace(commit=lambda: orden.append("commit"))

        class _Ctx:
            def __enter__(self_inner):
                return sesion

            def __exit__(self_inner, *a):
                return False

        def alta(_s, **kw):
            orden.append("alta")
            return SimpleNamespace(id=11, codigo_cliente="CLI-000011", nombre=kw["nombre"], telefono=kw["telefono"])

        def club(_s, **kw):
            orden.append(("club", kw["cliente_id"], kw["employee_code"]))

        with patch("pos_uniformes.database.connection.get_session", return_value=_Ctx()), \
                patch.object(kiosko.identidad_service, "dar_de_alta", side_effect=alta), \
                patch.object(ms, "inscribir_al_club_al_registrar", side_effect=club):
            w._registrar_cliente_identidad("Luis", "6670001122", False)
        self.assertEqual(orden, ["alta", ("club", 11, "VEND-2"), "commit"])

    def test_la_credencial_ofrece_proponer_programa(self) -> None:
        w = QuickSaleWidget(SimpleNamespace(offline_mode=False, _kiosk_lookup_from_cache=None, _db_online=True))
        envio = SimpleNamespace()
        with patch.object(cws, "preparar", return_value=envio), \
                patch("pos_uniformes.database.connection.get_session", MagicMock()), \
                patch.object(cwd, "CredencialWhatsappDialog") as dialogo:
            w._ofrecer_credencial_whatsapp(11)
        self.assertEqual(dialogo.call_args.kwargs["proponer"], w._on_proponer_programa)


class DialogoTests(_Qt):
    def _envio(self, programa="Maximoda Club") -> cws.EnvioCredencial:
        ruta = Path(tempfile.mkdtemp()) / "c.png"
        imagen = QImage(80, 50, QImage.Format.Format_RGB32)
        imagen.fill(QColor("#a84f2d"))
        imagen.save(str(ruta))
        return cws.EnvioCredencial(7, "Ana López", "CLI-000007", "526671234521", "Hola", ruta,
                                   cws.enlace_web("526671234521", "Hola"), programa)

    def test_dice_que_ya_es_del_club(self) -> None:
        d = cwd.CredencialWhatsappDialog(None, self._envio())
        self.assertIn("Maximoda Club", d.programa_label.text())
        self.assertFalse(hasattr(cwd.CredencialWhatsappDialog(None, self._envio(None)), "programa_label"))

    def test_proponer_programa_desde_el_alta(self) -> None:
        proponer = MagicMock(return_value=True)
        d = cwd.CredencialWhatsappDialog(None, self._envio(), proponer=proponer)
        self.assertFalse(d.proponer_button.isHidden())
        d.proponer_button.click()
        proponer.assert_called_once_with()
        self.assertFalse(d.proponer_button.isEnabled())
        self.assertIn("Propuesta enviada", d.proponer_button.text())

    def test_si_cancela_la_propuesta_el_boton_sigue(self) -> None:
        d = cwd.CredencialWhatsappDialog(None, self._envio(), proponer=MagicMock(return_value=False))
        d.proponer_button.click()
        self.assertTrue(d.proponer_button.isEnabled())

    def test_sin_quien_proponga_no_hay_boton(self) -> None:
        d = cwd.CredencialWhatsappDialog(None, self._envio())
        self.assertTrue(d.proponer_button.isHidden())


class MensajeTests(unittest.TestCase):
    def test_el_mensaje_dice_que_ya_es_miembro_sin_prometer(self) -> None:
        texto = cws.mensaje_bienvenida("Ana López", "CLI-000007", "Maximoda", "Maximoda Club")
        self.assertIn("Ya eres miembro de Maximoda Club.", texto)
        for prohibido in ("%", "descuento", "Descuento", "gratis"):
            self.assertNotIn(prohibido, texto)
        self.assertNotIn("miembro", cws.mensaje_bienvenida("Ana López", "CLI-000007", "Maximoda"))


if __name__ == "__main__":
    unittest.main()
