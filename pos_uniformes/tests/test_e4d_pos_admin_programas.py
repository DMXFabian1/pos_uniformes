"""E4-D: programas en el POS para el ADMIN — columna y filtro de la lista,
pestaña Fidelización de la ficha con sus acciones y ventana Programas.

Base local de prueba con transacción revertida; ventanas offscreen.
"""

from __future__ import annotations

import os
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QLabel, QLineEdit, QMessageBox, QTableWidget, QTabWidget

from pos_uniformes.services.clientes import admin_service as adm
from pos_uniformes.services.clientes import ficha_service
from pos_uniformes.services.fidelizacion import admin_programas_service as aps
from pos_uniformes.services.fidelizacion import membresia_service as ms
from pos_uniformes.tests.test_e4a_membresias import _Base
from pos_uniformes.tests.test_e4b_telegram_membresias import _Fabrica
from pos_uniformes.ui.dialogs import cliente_fidelizacion_panel as cfp
from pos_uniformes.ui.dialogs import programas_dialog as pd
from pos_uniformes.ui.dialogs.cliente_ficha_dialog import PROGRAMAS_PENDIENTES, construir_ficha_dialog
from pos_uniformes.ui.helpers.settings_clients_helper import CLIENTES_ADMIN_COLUMNAS


def _app():
    return QApplication.instance() or QApplication([])


class _ConMarca(_Base):
    def setUp(self) -> None:
        super().setUp()
        self.marca = f"E4D{uuid.uuid4().hex[:6]}"

    def _c(self, nombre):
        return self._cliente(f"{nombre} {self.marca}")

    def _club(self, cliente):
        return ms.inscribir_por_empleada(self.s, cliente_id=cliente.id, programa_clave="CLUB", employee_code=self.lupita.codigo)

    def _lista(self, **kw):
        return {f.nombre.split()[0]: f.programa for f in adm.listar_para_admin(self.s, self.admin.id, texto=self.marca, **kw)}


class ListaTests(_ConMarca):
    def setUp(self) -> None:
        super().setUp()
        self.sin = self._c("Sinprog")
        self.club = self._c("Club")
        self._club(self.club)
        self.esperando = self._c("Esperando")
        self._club(self.esperando)
        self._proponer(cliente=self.esperando)
        self.prof = self._c("Prof")
        ms.aprobar_por_dueno(self.s, self._proponer(cliente=self.prof).id)

    def test_columna_programa(self) -> None:
        self.assertEqual(self._lista(), {
            "Sinprog": "", "Club": "Maximoda Club",
            "Esperando": "Maximoda Club (propuesta a Profesional)", "Prof": "Maximoda Profesional",
        })

    def test_filtro_programa(self) -> None:
        casos = {
            adm.PROGRAMA_NINGUNO: {"Sinprog"},
            adm.PROGRAMA_PENDIENTE: {"Esperando"},
            "CLUB": {"Club", "Esperando"},
            "profesional": {"Prof"},
            "MAYORISTA": set(),
        }
        for programa, esperados in casos.items():
            with self.subTest(programa=programa):
                self.assertEqual(set(self._lista(programa=programa)), esperados)
        self.assertEqual(len(self._lista()), 4, "sin filtro, todos")

    def test_la_columna_va_antes_de_notas_sin_mover_las_de_e1c(self) -> None:
        self.assertEqual(CLIENTES_ADMIN_COLUMNAS[-2:], ("Programa", "Notas"))
        self.assertEqual(CLIENTES_ADMIN_COLUMNAS.index("QR"), 6)
        self.assertEqual(CLIENTES_ADMIN_COLUMNAS.index("Estado"), 8)

    def test_la_ventana_pasa_el_filtro_y_pinta_la_columna(self) -> None:
        type(self).app = _app()  # guardada: si no, Python la recoge y Qt aborta
        from pos_uniformes.ui.main_window import MainWindow

        estado = QComboBox()
        estado.addItem("Activos", adm.ESTADO_ACTIVOS)
        programa = QComboBox()
        programa.addItem("Todos", None)
        programa.addItem("Club", "CLUB")
        programa.setCurrentIndex(1)
        falso = SimpleNamespace(
            user_id=1, settings_clients_search_input=QLineEdit(), settings_clients_status_label=QLabel(),
            settings_clients_table=QTableWidget(0, 11), settings_clients_estado_combo=estado,
            settings_clients_tipo_combo=QComboBox(), settings_clients_origen_combo=QComboBox(),
            settings_clients_programa_combo=programa,
        )
        filas = [adm.FilaClienteAdmin(id=7, codigo="CLI-000007", nombre="Ana", telefono="", tipo="", origen="",
                                      alta=None, activo=True, archivado=False, notas="n", programa="Maximoda Club")]
        with patch("pos_uniformes.ui.main_window.admin_service.listar_para_admin", return_value=filas) as listar, \
                patch("pos_uniformes.ui.main_window.tipos_para_combo", return_value=[]), \
                patch("pos_uniformes.ui.main_window.QrGenerator.exists_for_client", return_value=False), \
                patch("pos_uniformes.ui.main_window.CustomerCardService.exists_for_client", return_value=False):
            MainWindow._refresh_settings_clients(falso, session=object())
        self.assertEqual(listar.call_args.kwargs["programa"], "CLUB")
        self.assertEqual(falso.settings_clients_table.item(0, 9).text(), "Maximoda Club")
        self.assertEqual(falso.settings_clients_table.item(0, 10).text(), "n")


class PanelServicioTests(_ConMarca):
    def test_solo_admin(self) -> None:
        with self.assertRaises(PermissionError):
            aps.cargar_panel(self.s, cliente_id=self.cliente.id, usuario_id=self.cajero.id)

    def test_pendiente_historial_y_destinos(self) -> None:
        self._club(self.cliente)
        self._proponer()
        p = aps.cargar_panel(self.s, cliente_id=self.cliente.id, usuario_id=self.admin.id)
        self.assertEqual((p.actual, p.actual_clave), ("Maximoda Club", "CLUB"))
        self.assertEqual((p.pendiente.programa, p.pendiente.propuesta_por), ("Maximoda Profesional", "Lupita Prueba"))
        self.assertEqual(p.pendiente.motivo, "Maestra de la Benito Juárez")
        self.assertEqual([h.evento for h in p.historial], ["Propuesta", "Alta"])
        self.assertNotIn("CLUB", [c for c, _n in p.destinos])

    def test_cambio_y_salida_quedan_en_el_historial(self) -> None:
        ms.inscribir_por_admin(self.s, cliente_id=self.cliente.id, programa_clave="CLUB", usuario_id=self.admin.id, motivo="Cliente frecuente")
        ms.inscribir_por_admin(self.s, cliente_id=self.cliente.id, programa_clave="MAYORISTA", usuario_id=self.admin.id, motivo="Abrió papelería")
        ms.sacar_del_programa(self.s, cliente_id=self.cliente.id, usuario_id=self.admin.id, motivo="Cerró el negocio")
        p = aps.cargar_panel(self.s, cliente_id=self.cliente.id, usuario_id=self.admin.id)
        self.assertIsNone(p.actual)
        eventos = [(h.evento, h.motivo) for h in p.historial]
        self.assertEqual(eventos[0], ("Sacado del programa", "Cerró el negocio"))
        self.assertIn(("Cambio de programa", "Abrió papelería"), eventos)
        self.assertIn("Reemplazada por otro programa", [e for e, _m in eventos])


class ProgramasServicioTests(_ConMarca):
    def _fila(self, clave):
        return {f.clave: f for f in aps.listar_programas(self.s, usuario_id=self.admin.id)}[clave]

    def test_lista_con_miembros_y_propuestas(self) -> None:
        antes = self._fila("CLUB"), self._fila("PROFESIONAL")
        self._club(self.cliente)
        self._proponer()
        club, prof = self._fila("CLUB"), self._fila("PROFESIONAL")
        self.assertEqual(club.miembros - antes[0].miembros, 1)
        self.assertEqual(prof.pendientes - antes[1].pendientes, 1)
        self.assertEqual((club.estado, club.vigencia, prof.tipo_sugerido), ("Activo", "Sin vencimiento", "Docente"))
        with self.assertRaises(PermissionError):
            aps.listar_programas(self.s, usuario_id=self.cajero.id)

    def test_pausar_detiene_altas_nuevas_pero_no_saca_a_nadie(self) -> None:
        m = self._club(self.cliente)
        aps.editar_programa(self.s, usuario_id=self.admin.id, clave="CLUB", nombre="Maximoda Club",
                            descripcion="En pausa", estado="pausado")
        self.s.refresh(m)
        self.assertEqual(m.estado, ms.ACTIVA)
        with self.assertRaises(ms.NoSePuede):
            self._club(self._c("Nueva"))

    def test_validaciones(self) -> None:
        kw = dict(usuario_id=self.admin.id, clave="CLUB", descripcion="")
        for nombre, estado, error in (("ab", "activo", "3 caracteres"), ("Club", "borrado", "estado"),
                                      ("maximoda profesional", "activo", "Ya hay un programa")):
            with self.subTest(nombre=nombre), self.assertRaisesRegex(ms.NoSePuede, error):
                aps.editar_programa(self.s, nombre=nombre, estado=estado, **kw)
        with self.assertRaises(PermissionError):
            aps.editar_programa(self.s, nombre="Club", estado="activo", **dict(kw, usuario_id=self.cajero.id))
        p = aps.editar_programa(self.s, nombre="  Club Maximoda ", estado="activo", **kw)
        self.assertEqual((p.nombre, p.descripcion), ("Club Maximoda", None))


class PanelUiTests(_ConMarca):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _app()

    def _panel(self):
        panel = cfp.FidelizacionPanel(_Fabrica(self.s), cliente_id=self.cliente.id, usuario_id=self.admin.id)
        self.addCleanup(panel.deleteLater)
        return panel

    def test_sin_programa(self) -> None:
        p = self._panel()
        self.assertEqual(p.actual_label.text(), "Sin programa")
        self.assertEqual(p.pendiente_label.text(), "Ninguna")
        self.assertFalse(p.aprobar_button.isEnabled() or p.rechazar_button.isEnabled() or p.sacar_button.isEnabled())
        self.assertTrue(p.inscribir_button.isEnabled())

    def test_aprobar_desde_el_pos(self) -> None:
        m = self._proponer()
        p = self._panel()
        self.assertIn("Maestra de la Benito Juárez", p.pendiente_label.text())
        self.assertFalse(p.inscribir_button.isEnabled(), "primero se resuelve la propuesta")
        with patch.object(cfp.QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            p.aprobar_button.click()
        self.s.refresh(m)
        self.assertEqual((m.estado, m.resuelta_por), (ms.ACTIVA, self.admin.username))
        self.assertEqual(self._tipo(self.cliente), "DOCENTE")
        self.assertTrue(p.hubo_cambios)
        self.assertIn("Maximoda Profesional", p.actual_label.text())

    def test_rechazar_pide_motivo(self) -> None:
        m = self._proponer()
        p = self._panel()
        with patch.object(cfp.QInputDialog, "getText", return_value=("no", True)), \
                patch.object(cfp.QMessageBox, "warning") as aviso:
            p.rechazar_button.click()
        aviso.assert_called_once()
        self.s.refresh(m)
        self.assertEqual(m.estado, ms.PENDIENTE)
        with patch.object(cfp.QInputDialog, "getText", return_value=("Todavía no compra seguido", True)):
            p.rechazar_button.click()
        self.s.refresh(m)
        self.assertEqual((m.estado, m.motivo_resolucion), (ms.RECHAZADA, "Todavía no compra seguido"))

    def test_inscribir_cambiar_y_sacar(self) -> None:
        p = self._panel()
        with patch.object(cfp.QInputDialog, "getItem", return_value=("Maximoda Mayorista", True)), \
                patch.object(cfp.QInputDialog, "getText", return_value=("Abrió papelería", True)):
            p.inscribir_button.click()
        self.assertIn("Maximoda Mayorista", p.actual_label.text())
        self.assertEqual(self._tipo(self.cliente), "MAYORISTA")
        self.assertNotIn("MAYORISTA", [c for c, _n in p.panel.destinos])
        with patch.object(cfp.QInputDialog, "getText", return_value=("Cerró el negocio", True)):
            p.sacar_button.click()
        self.assertEqual(p.actual_label.text(), "Sin programa")
        self.assertEqual(p.historial.item(0, 1).text(), "Sacado del programa")

    def test_un_error_de_regla_se_dice_y_no_cambia_nada(self) -> None:
        p = self._panel()
        adm.archivar(self.s, cliente_id=self.cliente.id, usuario_id=self.admin.id, motivo="Ficha de prueba")
        with patch.object(cfp.QInputDialog, "getItem", return_value=("Maximoda Club", True)), \
                patch.object(cfp.QInputDialog, "getText", return_value=("Cliente frecuente", True)), \
                patch.object(cfp.QMessageBox, "warning") as aviso:
            p.inscribir_button.click()
        self.assertIn("no está activa", aviso.call_args.args[2])
        self.assertFalse(p.hubo_cambios)

    def test_la_ficha_lleva_el_panel_y_sin_el_queda_el_aviso_de_antes(self) -> None:
        ficha = ficha_service.cargar_ficha(self.s, cliente_id=self.cliente.id, usuario_id=self.admin.id)
        panel = self._panel()
        dialogo = construir_ficha_dialog(None, ficha, panel_fidelizacion=panel)
        self.addCleanup(dialogo.deleteLater)
        pestanas = dialogo.findChild(QTabWidget)
        self.assertIs(pestanas.widget(1), panel)
        self.assertNotIn(PROGRAMAS_PENDIENTES, [l.text() for l in dialogo.findChildren(QLabel)])
        sin = construir_ficha_dialog(None, ficha)
        self.addCleanup(sin.deleteLater)
        self.assertIn(PROGRAMAS_PENDIENTES, [l.text() for l in sin.findChildren(QLabel)])


class ProgramasUiTests(_ConMarca):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = _app()

    def test_lista_y_edita(self) -> None:
        d = pd.ProgramasDialog(None, _Fabrica(self.s), usuario_id=self.admin.id)
        self.addCleanup(d.deleteLater)
        self.assertEqual([d.tabla.item(r, 0).text() for r in range(3)],
                         ["Maximoda Club", "Maximoda Profesional", "Maximoda Mayorista"])

        class _Editar:
            def __init__(self_inner, *a, **k):
                self_inner.resultado = ("Maximoda Club Familiar", "Para familias", "pausado")

            def exec(self_inner):
                return int(QDialog.DialogCode.Accepted)

        d.tabla.selectRow(0)
        with patch.object(pd, "EditarProgramaDialog", _Editar):
            d.editar_button.click()
        self.assertEqual((d.tabla.item(0, 0).text(), d.tabla.item(0, 1).text()), ("Maximoda Club Familiar", "Pausado"))
        self.assertEqual(ms.programa_por_clave(self.s, "CLUB").estado, "pausado")

    def test_el_dialogo_de_edicion_no_ofrece_borrar_ni_vigencia(self) -> None:
        fila = aps.listar_programas(self.s, usuario_id=self.admin.id)[0]
        e = pd.EditarProgramaDialog(None, fila)
        self.addCleanup(e.deleteLater)
        self.assertEqual([e.estado_combo.itemData(i) for i in range(e.estado_combo.count())],
                         ["activo", "pausado", "cerrado"])
        self.assertTrue(any("no se cambia" in l.text() for l in e.findChildren(QLabel)))
        e.nombre_input.setText("Club X")
        e.guardar_button.click()
        self.assertEqual(e.resultado, ("Club X", fila.descripcion, "activo"))


if __name__ == "__main__":
    unittest.main()
