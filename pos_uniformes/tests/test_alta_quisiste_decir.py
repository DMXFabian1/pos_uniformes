"""«¿Quisiste decir…?» en el asistente de alta (tanda 1, 2026-11-13).

Lo que se prueba: el asistente ofrece el parecido, no crea nada sin que el
usuario lo elija, bloquea el $0 y editar no duplica la escuela."""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer  # noqa: E402
from PyQt6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QDialog,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from pos_uniformes.database.connection import Base  # noqa: E402
from pos_uniformes.database.models import (  # noqa: E402
    Categoria,
    Escuela,
    Marca,
    NivelEducativo,
    Producto,
    RolUsuario,
    TipoPieza,
    TipoPrenda,
    Usuario,
    Variante,
)
from pos_uniformes.services import catalogo_valores_service as cv  # noqa: E402
from pos_uniformes.services.catalog_service import CatalogService  # noqa: E402
from pos_uniformes.ui.dialogs import catalog_product_dialog as cpd  # noqa: E402
from pos_uniformes.ui.dialogs import catalog_variant_dialog as cvd  # noqa: E402
from pos_uniformes.ui.dialogs.quisiste_decir_dialog import (  # noqa: E402
    ACCION_CORREGIR,
    ACCION_CREAR,
    ACCION_USAR,
    Campo,
    Eleccion,
    confirmar_valores,
    preguntar_quisiste_decir,
)

_app = QApplication.instance() or QApplication([])


class PreguntaFalsa:
    """Responde en orden y guarda lo que se le preguntó."""

    def __init__(self, *respuestas: str) -> None:
        self.respuestas = list(respuestas)
        self.preguntas: list[tuple[cv.Revision, bool]] = []

    def __call__(self, parent, revision, puede_crear=True) -> Eleccion:
        self.preguntas.append((revision, puede_crear))
        accion = self.respuestas.pop(0) if self.respuestas else ACCION_CORREGIR
        valor = revision.sugerencias[0].valor if accion == ACCION_USAR and revision.sugerencias else revision.escrito
        return Eleccion(accion, valor)


USOS = {
    cv.CAMPO_COLOR: {"Blanca": 306, "Blanco": 125, "Gris": 80},
    cv.CAMPO_TALLA: {"Uni": 66, "Unitalla": 23, "CH": 256},
    cv.CAMPO_ESCUELA: {"ESTV 154": 12, "Ignacio Allende (Jaral)": 7},
    cv.CAMPO_TIPO_PIEZA: {"Chamarra": 68, "Pants 3pz": 47},
}


class ConfirmarValoresTests(unittest.TestCase):
    def _confirmar(self, campos, pregunta, *, admin=True):
        return confirmar_valores(
            None, campos, usos_de=lambda c: USOS.get(c, {}), puede_crear_escuela=admin, preguntar=pregunta
        )

    def test_ofrece_el_parecido_y_usa_el_existente(self) -> None:
        pregunta = PreguntaFalsa(ACCION_USAR)
        r = self._confirmar([Campo("color:Blanca", cv.CAMPO_COLOR, "Blanca")], pregunta)
        revision, _ = pregunta.preguntas[0]
        self.assertEqual(revision.texto_pregunta(), "«Blanca» se parece a «Blanco» (125 tallas).")
        self.assertEqual(r.valores["color:Blanca"], "Blanco")
        self.assertEqual(r.nuevos, {})

    def test_lo_que_existe_no_pregunta(self) -> None:
        pregunta = PreguntaFalsa()
        r = self._confirmar(
            [Campo("t", cv.CAMPO_TALLA, "CH"), Campo("p", cv.CAMPO_TIPO_PIEZA, "Chamarra")], pregunta
        )
        self.assertEqual(pregunta.preguntas, [])
        self.assertEqual(r.valores, {"t": "CH", "p": "Chamarra"})

    def test_corregir_deja_el_formulario_abierto(self) -> None:
        r = self._confirmar([Campo("p", cv.CAMPO_TIPO_PIEZA, "Chamara")], PreguntaFalsa(ACCION_CORREGIR))
        self.assertIsNone(r)

    def test_solo_lo_que_se_elige_crear_queda_como_nuevo(self) -> None:
        r = self._confirmar([Campo("p", cv.CAMPO_TIPO_PIEZA, "Overol")], PreguntaFalsa(ACCION_CREAR))
        self.assertEqual(r.valores["p"], "Overol")
        self.assertEqual(r.nuevos_de(cv.CAMPO_TIPO_PIEZA), ["Overol"])

    def test_escuela_nueva_solo_admin(self) -> None:
        pregunta = PreguntaFalsa(ACCION_CREAR)
        r = self._confirmar([Campo("e", cv.CAMPO_ESCUELA, "Rancho Nuevo")], pregunta, admin=False)
        self.assertIsNone(r)
        self.assertFalse(pregunta.preguntas[0][1])  # no se le ofreció crear

    def test_al_editar_lo_que_no_se_toco_no_pregunta(self) -> None:
        pregunta = PreguntaFalsa()
        r = self._confirmar([Campo("a", cv.CAMPO_ATRIBUTO, "Deportiva", inicial="Deportiva")], pregunta)
        self.assertEqual(pregunta.preguntas, [])
        self.assertEqual(r.valores["a"], "Deportiva")


class VentanitaTests(unittest.TestCase):
    def _responder(self, texto_boton: str, vistos: list) -> None:
        def clic() -> None:
            caja = QApplication.activeModalWidget()
            if not isinstance(caja, QMessageBox):
                QTimer.singleShot(10, clic)
                return
            vistos.append((caja.windowTitle(), caja.text(), [b.text() for b in caja.buttons()],
                           caja.defaultButton().text()))
            for b in caja.buttons():
                if b.text() == texto_boton:
                    b.click()
                    return
            caja.escapeButton().click()  # que la prueba falle, no que se cuelgue

        QTimer.singleShot(0, clic)

    def test_usar_es_el_boton_por_defecto(self) -> None:
        vistos: list = []
        revision = cv.revisar_valor(cv.CAMPO_COLOR, "Blanca", USOS[cv.CAMPO_COLOR])
        self._responder("Usar Blanco", vistos)
        eleccion = preguntar_quisiste_decir(None, revision)
        titulo, texto, botones, por_defecto = vistos[0]
        self.assertEqual(texto, "«Blanca» se parece a «Blanco» (125 tallas).")
        self.assertEqual(sorted(botones), ["Corregir", "Dejar «Blanca»", "Usar Blanco"])
        self.assertEqual(por_defecto, "Usar Blanco")
        self.assertEqual(eleccion, Eleccion(ACCION_USAR, "Blanco"))

    def test_escuela_pregunta_si_es_la_misma(self) -> None:
        vistos: list = []
        revision = cv.revisar_valor(cv.CAMPO_ESCUELA, "Ignacio Allende de Jaral", USOS[cv.CAMPO_ESCUELA])
        self._responder("No, es otra: crearla", vistos)
        eleccion = preguntar_quisiste_decir(None, revision, True)
        titulo, texto, botones, por_defecto = vistos[0]
        self.assertIn("¿Es la misma que «Ignacio Allende (Jaral)»", texto)
        self.assertEqual(por_defecto, "Sí, es «Ignacio Allende (Jaral)»")
        self.assertEqual(eleccion.accion, ACCION_CREAR)

    def test_sin_admin_no_hay_boton_de_crear_escuela(self) -> None:
        vistos: list = []
        revision = cv.revisar_valor(cv.CAMPO_ESCUELA, "Rancho Nuevo", USOS[cv.CAMPO_ESCUELA])
        self._responder("Corregir", vistos)
        eleccion = preguntar_quisiste_decir(None, revision, False)
        self.assertEqual(vistos[0][2], ["Corregir"])
        self.assertEqual(eleccion.accion, ACCION_CORREGIR)


class _VentanaFalsa(QWidget):
    def __init__(self, user_id: int) -> None:
        super().__init__()
        self.user_id = user_id
        self.current_role = RolUsuario.ADMIN

    def _create_modal_dialog(self, title, helper_text=None, width=460, *, expand_to_screen=False):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setMinimumWidth(width)
        layout = QVBoxLayout()
        dialog.setLayout(layout)
        return dialog, layout

    @staticmethod
    def _set_combo_value(combo, value) -> None:
        if value is None:
            return
        combo.setCurrentIndex(max(combo.findData(value), -1))

    def _format_sku_preview(self, total: int) -> str:
        return ""

    def _prompt_text_value(self, *args, **kwargs):
        return None


class _ConBase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        with self._sesion() as s:
            admin = Usuario(username="admin", nombre_completo="Admin", password_hash="x", rol=RolUsuario.ADMIN)
            cat, marca = Categoria(nombre="Uniformes"), Marca(nombre="Sin marca")
            estv = Escuela(nombre="ESTV 154")
            s.add_all([admin, cat, marca, estv, TipoPrenda(nombre="Deportivo"), TipoPieza(nombre="Pants 3pz"),
                       NivelEducativo(nombre="Secundaria")])
            s.flush()
            p = Producto(nombre="Pants 3pz Deportivo Estv 154 ESTV 154",
                         nombre_base="Pants 3pz Deportivo Estv 154 ESTV 154",
                         categoria_id=cat.id, marca_id=marca.id, escuela_id=estv.id)
            s.add(p)
            s.flush()
            s.add(Variante(producto_id=p.id, sku="SKU000001", talla="Uni", color="Blanca", precio_venta=Decimal("245")))
            s.add(Variante(producto_id=p.id, sku="SKU000002", talla="CH", color="Blanco", precio_venta=Decimal("245")))
            s.commit()
            self.admin_id, self.marca_id, self.producto_id = admin.id, marca.id, p.id
        self.ventana = _VentanaFalsa(self.admin_id)
        self.addCleanup(self.ventana.deleteLater)
        for modulo in (cpd, cvd):
            parche = patch.object(modulo, "get_session", self._sesion)
            parche.start()
            self.addCleanup(parche.stop)
        quieto = patch.object(CatalogService, "_avisar_busqueda")
        quieto.start()
        self.addCleanup(quieto.stop)

    @contextmanager
    def _sesion(self):
        s = Session(self.engine)
        try:
            yield s
        finally:
            s.close()

    def _con_dialogo(self, titulo: str, pasos) -> None:
        """Corre `pasos(dialogo)` cuando el diálogo ya está abierto."""
        def buscar() -> None:
            for w in QApplication.topLevelWidgets():
                if isinstance(w, QDialog) and w.isVisible() and w.windowTitle() == titulo:
                    try:
                        pasos(w)
                    finally:
                        if w.isVisible():
                            w.done(0)
                    return
            QTimer.singleShot(10, buscar)

        QTimer.singleShot(0, buscar)


class DialogoProductoTests(_ConBase):
    def _abrir(self, pasos, pregunta, initial=None):
        self._con_dialogo("Producto", pasos)
        return cpd.build_catalog_product_dialog(
            self.ventana,
            initial=initial,
            picker_button_class=__import__("pos_uniformes.ui.main_window", fromlist=["x"]).MultiSelectPickerButton,
            product_templates=[],
            common_sizes=list(cv.TALLAS_SUGERIDAS),
            common_colors=list(cv.COLORES_SUGERIDOS),
            default_variant_size="Unitalla",
            default_variant_color="Sin color",
            preguntar_valor=pregunta,
        )

    def _llenar(self, d: QDialog, *, escuela: str, precio: str, tallas=(), colores=()) -> None:
        d.findChild(QComboBox, "altaMarca").setCurrentIndex(
            d.findChild(QComboBox, "altaMarca").findData(self.marca_id)
        )
        d.findChild(QLineEdit, "altaNombre").setText("Playera Deportiva")
        d.findChild(QComboBox, "altaEscuela").setEditText(escuela)
        for nombre, valores in (("altaTallas", tallas), ("altaColores", colores)):
            if valores:
                picker = d.findChild(QPushButton, nombre)
                # Como si se escribieran a mano en el selector («Otro…»).
                faltan = [(v, v) for v in valores if v not in picker.selected_values() | {x for _, x in picker._items}]
                picker.set_items(picker._items + faltan)
                picker.set_selected_values(list(valores))
        d.alta_modo_precio.setCurrentIndex(d.alta_modo_precio.findData("single"))
        d.alta_precio.setText(precio)

    def test_ofrece_el_parecido_y_no_crea_sin_elegir(self) -> None:
        pregunta = PreguntaFalsa(ACCION_CORREGIR, ACCION_USAR)
        estado = {}

        def pasos(d):
            self._llenar(d, escuela="ESTV 15", precio="245")
            guardar = d.findChild(QPushButton, "altaGuardar")
            guardar.click()                       # primero: «Corregir»
            estado["abierto"] = d.isVisible()
            guardar.click()                       # luego: «Usar ESTV 154»

        payload = self._abrir(pasos, pregunta)
        self.assertTrue(estado["abierto"])
        self.assertEqual(pregunta.preguntas[0][0].sugerencias[0].valor, "ESTV 154")
        self.assertEqual(payload["escuela"], "ESTV 154")
        self.assertEqual(payload["valores_nuevos"], {})
        with self._sesion() as s:
            self.assertEqual(len(s.scalars(select(Escuela)).all()), 1)

    def test_tallas_y_colores_viejos_pasan_a_su_forma_oficial(self) -> None:
        pregunta = PreguntaFalsa(ACCION_USAR, ACCION_USAR)

        def pasos(d):
            self._llenar(d, escuela="ESTV 154", precio="245", tallas=["CH", "Uni"], colores=["Blanca"])
            d.findChild(QPushButton, "altaGuardar").click()

        payload = self._abrir(pasos, pregunta)
        self.assertIsNotNone(payload)
        preguntados = [r.escrito for r, _ in pregunta.preguntas]
        self.assertEqual(sorted(preguntados), ["Blanca", "Uni"])
        self.assertEqual(payload["tallas"], ["CH", "Unitalla"])
        self.assertEqual(payload["colores"], ["Blanco"])

    def test_precio_en_cero_no_deja_guardar(self) -> None:
        pregunta = PreguntaFalsa()
        estado = {}

        def pasos(d):
            self._llenar(d, escuela="ESTV 154", precio="0", tallas=["CH"])
            with patch.object(cpd.QMessageBox, "warning") as aviso:
                d.findChild(QPushButton, "altaGuardar").click()
            estado["abierto"] = d.isVisible()
            estado["aviso"] = aviso.call_args[0][2] if aviso.called else ""

        payload = self._abrir(pasos, pregunta)
        self.assertIsNone(payload)
        self.assertTrue(estado["abierto"])
        self.assertIn("$0", estado["aviso"])

    def test_editar_carga_el_nombre_sin_escuela_y_no_la_duplica(self) -> None:
        estado = {}

        def pasos(d):
            estado["nombre"] = d.findChild(QLineEdit, "altaNombre").text()
            d.findChild(QPushButton, "altaGuardar").click()

        pregunta = PreguntaFalsa()
        payload = self._abrir(pasos, pregunta, initial={"producto_id": self.producto_id})
        self.assertEqual(estado["nombre"], "Pants 3pz Deportivo")
        self.assertEqual(pregunta.preguntas, [])  # nada cambió: nada que preguntar
        with self._sesion() as s:
            producto = s.get(Producto, self.producto_id)
            usuario = s.get(Usuario, self.admin_id)
            CatalogService.actualizar_producto(
                s, usuario, producto, producto.categoria, producto.marca, payload["nombre"],
                escuela=producto.escuela,
            )
            self.assertEqual(producto.nombre, "Pants 3pz Deportivo ESTV 154")


class DialogoTallaTests(_ConBase):
    def _abrir(self, pasos, pregunta, prefill=None):
        self._con_dialogo("Presentacion", pasos)
        with patch.object(cvd, "load_legacy_config_choices", return_value={}):
            return cvd.build_catalog_variant_dialog(
                self.ventana,
                prefill=prefill,
                include_stock=True,
                default_product_id=self.producto_id,
                common_sizes=list(cv.TALLAS_SUGERIDAS),
                common_colors=list(cv.COLORES_SUGERIDOS),
                default_variant_size="Unitalla",
                default_variant_color="Sin color",
                preguntar_valor=pregunta,
            )

    def test_cero_se_queda_abierto_y_uni_pasa_a_unitalla(self) -> None:
        pregunta = PreguntaFalsa(ACCION_USAR)
        estado = {}

        def pasos(d):
            combos = d.findChildren(QComboBox)
            talla, color = combos[1], combos[2]
            talla.setEditText("Uni")
            color.setEditText("Gris")
            precio = [w for w in d.findChildren(QLineEdit) if w.placeholderText() == "0.00"][0]
            precio.setText("0")
            ok = [b for b in d.findChildren(QPushButton) if b.text() in ("OK", "&OK", "Aceptar")][0]
            with patch.object(cvd.QMessageBox, "warning") as aviso:
                ok.click()
            estado["abierto"] = d.isVisible()
            estado["aviso"] = aviso.call_args[0][2] if aviso.called else ""
            precio.setText("245")
            ok.click()

        payload = self._abrir(pasos, pregunta)
        self.assertTrue(estado["abierto"])
        self.assertIn("$0", estado["aviso"])
        self.assertEqual(payload["talla"], "Unitalla")
        self.assertEqual(payload["precio"], "245")
        self.assertEqual(payload["sku"], "")  # el servicio lo genera con el contador bloqueado


    def test_talla_nueva_de_prenda_existente_no_pregunta_por_su_color(self) -> None:
        pregunta = PreguntaFalsa()

        def pasos(d):
            combos = d.findChildren(QComboBox)
            combos[1].setEditText("16")
            ok = [b for b in d.findChildren(QPushButton) if b.text() in ("OK", "&OK", "Aceptar")][0]
            ok.click()

        payload = self._abrir(
            pasos,
            pregunta,
            prefill={"producto_id": self.producto_id, "color": "Blanca", "precio_venta": "245",
                     "costo_referencia": None},
        )
        self.assertEqual(pregunta.preguntas, [])
        self.assertEqual(payload["color"], "Blanca")
        self.assertEqual(payload["talla"], "16")


class ResolverEnMainWindowTests(_ConBase):
    def test_guardar_sin_confirmar_no_crea(self) -> None:
        from pos_uniformes.ui.main_window import MainWindow

        with self._sesion() as s:
            with self.assertRaises(cv.ValorNoConfirmado):
                MainWindow._resolve_named_taxonomy(self.ventana, s, TipoPieza, "Overol", {"valores_nuevos": {}})
            nueva = MainWindow._resolve_named_taxonomy(
                self.ventana, s, TipoPieza, "Overol", {"valores_nuevos": {cv.CAMPO_TIPO_PIEZA: ["Overol"]}}
            )
            self.assertEqual(nueva.nombre, "Overol")
            self.assertEqual(
                MainWindow._resolve_named_taxonomy(self.ventana, s, Escuela, "estv 154", {}).nombre, "ESTV 154"
            )


if __name__ == "__main__":
    unittest.main()
