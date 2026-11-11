"""E1-C1 (T-N2..T-N7): administración de fichas por el ADMIN.

Corre contra la base local de prueba dentro de una transacción que se
revierte; no deja nada escrito.
"""

from __future__ import annotations

import os
import unittest
import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QDialogButtonBox, QLineEdit, QWidget
from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Cliente, ClienteEvento, NivelLealtad, RolUsuario, TipoCliente, Usuario
from pos_uniformes.services.clientes import admin_service as adm
from pos_uniformes.services.clientes import identidad_service as ids
from pos_uniformes.services import settings_cliente_admin_actions as acciones
from pos_uniformes.ui.dialogs import cliente_admin_dialogs as dialogos
from pos_uniformes.ui.main_window import MainWindow
from pos_uniformes.utils.config import settings
from tests.base_por_trabajador import es_base_de_prueba_local


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        url = make_url(settings.database_url)
        if not es_base_de_prueba_local(url):
            self.skipTest("Solo corre contra la base local de prueba.")
        self.engine = create_engine(url)
        self.addCleanup(self.engine.dispose)
        self.conn = self.engine.connect()
        self.addCleanup(self.conn.close)
        self.tx = self.conn.begin()
        self.addCleanup(self.tx.rollback)
        self.s = Session(bind=self.conn, join_transaction_mode="create_savepoint")
        self.addCleanup(self.s.close)
        self.admin = self._usuario(RolUsuario.ADMIN)
        self.cajero = self._usuario(RolUsuario.CAJERO)
        self.sufijo = f"{uuid.uuid4().int % 10**6:06d}"

    def _usuario(self, rol, activo=True) -> Usuario:
        u = Usuario(username=f"e1c_{rol.value.lower()}_{uuid.uuid4().hex[:6]}", nombre_completo="E1-C",
                    password_hash="x", rol=rol, activo=activo)
        self.s.add(u)
        self.s.flush()
        return u

    def _alta(self, nombre="Ana E1C", telefono=None, tipo="GENERAL", **kw) -> Cliente:
        return ids.dar_de_alta(self.s, nombre=nombre, telefono=telefono or f"6679{self.sufijo}",
                               origen=ids.ORIGEN_POS_ADMIN, tipo_clave=tipo, usuario_id=self.admin.id, **kw)

    def _legado(self) -> Cliente:
        """Ficha vieja con nivel y descuento: se congela (D5)."""
        c = Cliente(codigo_cliente=f"CLI-E1C{self.sufijo}", nombre="Legado", tipo_cliente=TipoCliente.PROFESOR,
                    descuento_preferente=Decimal("15.00"), nivel_lealtad=NivelLealtad.PROFESOR,
                    telefono="6670001111", activo=True)
        self.s.add(c)
        self.s.flush()
        return c

    def _eventos(self, cliente, tipo=None) -> list[ClienteEvento]:
        stmt = select(ClienteEvento).where(ClienteEvento.cliente_id == cliente.id).order_by(ClienteEvento.id)
        if tipo:
            stmt = stmt.where(ClienteEvento.tipo == tipo)
        return list(self.s.scalars(stmt))


class EdicionTests(_Base):
    """T-N2: editar toca solo identidad y deja un evento con el antes y el después."""

    def test_editar_solo_cambia_identidad_y_deja_evento(self) -> None:
        c = self._alta()
        adm.editar_identidad(self.s, cliente_id=c.id, usuario_id=self.admin.id, nombre="Ana Editada",
                             telefono=c.telefono, notas="nota nueva")
        ev = self._eventos(c, adm.EVENTO_EDICION)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0].detalle["cambios"], {"nombre": ["Ana E1C", "Ana Editada"], "notas": [None, "nota nueva"]})
        self.assertNotIn("telefono", ev[0].detalle)
        self.assertEqual(ev[0].usuario_id, self.admin.id)
        self.assertEqual(ev[0].origen, ids.ORIGEN_POS_ADMIN)

    def test_guardar_sin_cambios_no_deja_evento(self) -> None:
        c = self._alta()
        antes = len(self._eventos(c))
        adm.editar_identidad(self.s, cliente_id=c.id, usuario_id=self.admin.id, nombre=c.nombre,
                             telefono=c.telefono, notas=None)
        self.assertEqual(len(self._eventos(c)), antes)

    def test_editar_ficha_vieja_no_toca_nivel_descuento_ni_enum(self) -> None:
        c = self._legado()
        adm.editar_identidad(self.s, cliente_id=c.id, usuario_id=self.admin.id, nombre="Legado 2",
                             telefono="6670001112", notas=None)
        self.s.refresh(c)
        self.assertEqual(c.nivel_lealtad, NivelLealtad.PROFESOR)
        self.assertEqual(Decimal(c.descuento_preferente), Decimal("15.00"))
        self.assertEqual(c.tipo_cliente, TipoCliente.PROFESOR)
        self.assertEqual(c.telefono_normalizado, "6670001112")

    def test_nombre_vacio_se_rechaza(self) -> None:
        c = self._alta()
        with self.assertRaises(ValueError):
            adm.editar_identidad(self.s, cliente_id=c.id, usuario_id=self.admin.id, nombre="  ", telefono=None, notas=None)


class TelefonoCompartidoTests(_Base):
    """T-N3 (Daniel, 2026-11-10): el teléfono es único. Un teléfono que ya es
    de otra ficha no se guarda, ni al crear ni al editar; ya no se confirma."""

    def test_editar_a_un_telefono_de_otra_ficha_no_se_guarda(self) -> None:
        a = self._alta(nombre="Persona A", telefono=f"6678{self.sufijo}")
        b = self._alta(nombre="Persona B", telefono=f"6677{self.sufijo}")
        with self.assertRaises(ids.CoincidenciasPorConfirmarError) as err:
            adm.editar_identidad(self.s, cliente_id=b.id, usuario_id=self.admin.id, nombre=b.nombre,
                                 telefono=a.telefono, notas=None)
        self.assertEqual([x.id for x in err.exception.coincidencias], [a.id])
        self.s.refresh(b)
        self.assertEqual(b.telefono, f"6677{self.sufijo}")
        self.assertEqual(self._eventos(b, adm.EVENTO_EDICION), [])

    def test_editar_a_un_telefono_invalido_no_se_guarda(self) -> None:
        b = self._alta(nombre="Persona B", telefono=f"6677{self.sufijo}")
        for malo in ("", "123"):
            with self.subTest(telefono=malo), self.assertRaises(ids.TelefonoInvalidoError):
                adm.editar_identidad(self.s, cliente_id=b.id, usuario_id=self.admin.id, nombre=b.nombre,
                                     telefono=malo, notas=None)
        self.s.refresh(b)
        self.assertEqual(b.telefono, f"6677{self.sufijo}")

    def test_su_propio_telefono_no_cuenta_como_coincidencia(self) -> None:
        a = self._alta()
        adm.editar_identidad(self.s, cliente_id=a.id, usuario_id=self.admin.id, nombre="Otro nombre",
                             telefono=a.telefono, notas=None)

    def test_alta_del_admin_con_telefono_repetido_no_se_crea(self) -> None:
        a = self._alta()
        datos = {"nombre": "Otra", "telefono": a.telefono, "tipo_clave": "DOCENTE", "notas": ""}
        antes = self.s.scalar(select(func.count()).select_from(Cliente))
        with self.assertRaises(ids.CoincidenciasPorConfirmarError):
            acciones.crear_cliente(self.s, admin_user_id=self.admin.id, datos=datos)
        self.assertEqual(self.s.scalar(select(func.count()).select_from(Cliente)), antes)

    def test_alta_del_admin_exige_telefono_de_10_digitos(self) -> None:
        for malo in ("", "123"):
            datos = {"nombre": "Sin tel", "telefono": malo, "tipo_clave": "GENERAL", "notas": ""}
            with self.subTest(telefono=malo), self.assertRaises(ids.TelefonoInvalidoError):
                acciones.crear_cliente(self.s, admin_user_id=self.admin.id, datos=datos)


class TipoTests(_Base):
    """T-N4: cambiar el tipo deja su propio evento y no da beneficios."""

    def test_cambio_de_tipo(self) -> None:
        c = self._alta(tipo="GENERAL")
        adm.cambiar_tipo(self.s, cliente_id=c.id, usuario_id=self.admin.id, clave="MAYORISTA")
        ev = self._eventos(c, adm.EVENTO_CAMBIO_TIPO)
        self.assertEqual(ev[-1].detalle, {"antes": "GENERAL", "despues": "MAYORISTA"})
        self.s.refresh(c)
        self.assertIsNone(c.nivel_lealtad)
        self.assertEqual(Decimal(c.descuento_preferente), Decimal("0.00"))
        self.assertEqual(c.tipo_cliente, TipoCliente.GENERAL)  # el enum viejo queda congelado

    def test_mismo_tipo_no_deja_evento_y_tipo_inexistente_falla(self) -> None:
        c = self._alta(tipo="DOCENTE")
        adm.cambiar_tipo(self.s, cliente_id=c.id, usuario_id=self.admin.id, clave="docente")
        self.assertEqual(self._eventos(c, adm.EVENTO_CAMBIO_TIPO), [])
        with self.assertRaises(ValueError):
            adm.cambiar_tipo(self.s, cliente_id=c.id, usuario_id=self.admin.id, clave="PROFESOR")

    def test_ficha_vieja_sin_tipo(self) -> None:
        c = self._legado()
        adm.cambiar_tipo(self.s, cliente_id=c.id, usuario_id=self.admin.id, clave="DOCENTE")
        self.assertEqual(self._eventos(c, adm.EVENTO_CAMBIO_TIPO)[-1].detalle, {"antes": None, "despues": "DOCENTE"})

    def test_editar_desde_configuracion_separa_eventos(self) -> None:
        c = self._alta()
        acciones.editar_cliente(self.s, admin_user_id=self.admin.id, client_id=c.id,
                                datos={"nombre": "Ana Nueva", "telefono": c.telefono, "tipo_clave": "INSTITUCION", "notas": ""})
        tipos = [e.tipo for e in self._eventos(c)]
        self.assertEqual(tipos[-2:], [adm.EVENTO_EDICION, adm.EVENTO_CAMBIO_TIPO])


class EstadoTests(_Base):
    """T-N5: activar o desactivar exige motivo y deja evento."""

    def test_desactivar_y_reactivar(self) -> None:
        c = self._alta()
        with self.assertRaises(ValueError):
            adm.cambiar_estado(self.s, cliente_id=c.id, usuario_id=self.admin.id, activo=False, motivo="no")
        r = acciones.alternar_estado(self.s, admin_user_id=self.admin.id, client_id=c.id, motivo="Ya no compra")
        self.assertEqual(r.status_text, "desactivado")
        acciones.alternar_estado(self.s, admin_user_id=self.admin.id, client_id=c.id, motivo="Regresó a comprar")
        ev = self._eventos(c)
        self.assertEqual([e.tipo for e in ev[-2:]], [adm.EVENTO_DESACTIVACION, adm.EVENTO_REACTIVACION])
        self.assertEqual(ev[-2].detalle, {"motivo": "Ya no compra", "tiene_monedero": False})
        self.assertTrue(c.activo)

    def test_inactivo_no_aparece_en_busqueda(self) -> None:
        c = self._alta(nombre=f"Buscable {self.sufijo}")
        adm.cambiar_estado(self.s, cliente_id=c.id, usuario_id=self.admin.id, activo=False, motivo="Prueba de baja")
        self.assertEqual(ids.buscar_clientes(self.s, f"Buscable {self.sufijo}"), [])


class ArchivadoTests(_Base):
    """T-N6: archivar es reversible y no borra nada (C12)."""

    def test_archivar_y_desarchivar_conserva_todo(self) -> None:
        c = self._legado()
        ident = (c.id, c.codigo_cliente)
        adm.cambiar_estado(self.s, cliente_id=c.id, usuario_id=self.admin.id, activo=False, motivo="Baja previa")
        adm.archivar(self.s, cliente_id=c.id, usuario_id=self.admin.id, motivo="Ficha de prueba")
        self.assertIsNotNone(c.archivado_en)
        self.assertFalse(c.activo)
        self.assertEqual(ids.buscar_clientes(self.s, c.codigo_cliente), [])
        self.assertEqual(ids.coincidencias_por_telefono(self.s, c.telefono), [])
        with self.assertRaises(ValueError):
            adm.editar_identidad(self.s, cliente_id=c.id, usuario_id=self.admin.id, nombre="x", telefono=None, notas=None)
        # archivar dos veces no duplica el evento
        adm.archivar(self.s, cliente_id=c.id, usuario_id=self.admin.id, motivo="Ficha de prueba")
        self.assertEqual(len(self._eventos(c, adm.EVENTO_ARCHIVADO)), 1)

        adm.desarchivar(self.s, cliente_id=c.id, usuario_id=self.admin.id, motivo="Era cliente real")
        self.s.refresh(c)
        self.assertIsNone(c.archivado_en)
        self.assertIsNone(c.archivado_motivo)
        self.assertFalse(c.activo, "regresa al estado que tenía antes de archivar")
        self.assertEqual((c.id, c.codigo_cliente), ident)
        self.assertEqual(c.nivel_lealtad, NivelLealtad.PROFESOR)
        self.assertEqual(Decimal(c.descuento_preferente), Decimal("15.00"))
        self.assertEqual(self._eventos(c, adm.EVENTO_DESARCHIVADO)[-1].detalle["activo"], False)

    def test_desarchivar_activo_regresa_activo(self) -> None:
        c = self._alta()
        adm.archivar(self.s, cliente_id=c.id, usuario_id=self.admin.id, motivo="Ficha de prueba")
        adm.desarchivar(self.s, cliente_id=c.id, usuario_id=self.admin.id, motivo="Error al archivar")
        self.assertTrue(c.activo)


class PermisosYListaTests(_Base):
    """T-N7: solo ADMIN activo; la lista filtra por estado, tipo, origen y texto."""

    def test_cajero_e_inactivo_no_pueden(self) -> None:
        c = self._alta()
        admin_inactivo = self._usuario(RolUsuario.ADMIN, activo=False)
        for usuario in (self.cajero.id, admin_inactivo.id, None):
            with self.subTest(usuario=usuario):
                with self.assertRaises(PermissionError):
                    adm.editar_identidad(self.s, cliente_id=c.id, usuario_id=usuario, nombre="x", telefono=None, notas=None)
                with self.assertRaises(PermissionError):
                    adm.cambiar_tipo(self.s, cliente_id=c.id, usuario_id=usuario, clave="DOCENTE")
                with self.assertRaises(PermissionError):
                    adm.archivar(self.s, cliente_id=c.id, usuario_id=usuario, motivo="motivo largo")
                with self.assertRaises(PermissionError):
                    adm.listar_para_admin(self.s, usuario)
                with self.assertRaises(PermissionError):
                    acciones.crear_cliente(self.s, admin_user_id=usuario or 0, datos={"nombre": "x"})

    def test_filtros_de_la_lista(self) -> None:
        marca = f"Lista{self.sufijo}"
        gen = self._alta(nombre=f"{marca} General", telefono=f"6611{self.sufijo}")
        doc = self._alta(nombre=f"{marca} Docente", telefono=f"6612{self.sufijo}", tipo="DOCENTE")
        arc = self._alta(nombre=f"{marca} Archivado", telefono=f"6613{self.sufijo}")
        adm.archivar(self.s, cliente_id=arc.id, usuario_id=self.admin.id, motivo="Ficha de prueba")

        def ids_de(**kw):
            return {f.id for f in adm.listar_para_admin(self.s, self.admin.id, texto=marca, **kw)}

        self.assertEqual(ids_de(), {gen.id, doc.id})
        self.assertEqual(ids_de(estado=adm.ESTADO_ARCHIVADOS), {arc.id})
        self.assertEqual(ids_de(estado=adm.ESTADO_TODOS), {gen.id, doc.id, arc.id})
        self.assertEqual(ids_de(tipo_clave="docente"), {doc.id})
        self.assertEqual(ids_de(origen=ids.ORIGEN_VENTA_RAPIDA), set())
        fila = adm.listar_para_admin(self.s, self.admin.id, texto=f"6612{self.sufijo}")[0]
        self.assertEqual((fila.id, fila.tipo, fila.origen), (doc.id, "Docente", ids.ORIGEN_POS_ADMIN))


class _Qt(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])


class DialogosTests(_Qt):
    TIPOS = [("GENERAL", "General"), ("DOCENTE", "Docente"), ("MAYORISTA", "Mayorista"), ("INSTITUCION", "Institución")]

    def test_ficha_sin_descuento_y_con_tipos_del_catalogo(self) -> None:
        visto = {}

        def ejecutar(dialog):
            combo = dialog.findChild(QComboBox)
            visto["tipos"] = [combo.itemData(i) for i in range(combo.count())]
            visto["actual"] = combo.currentData()
            combo.setCurrentIndex(combo.findData("MAYORISTA"))
            return int(QDialog.DialogCode.Accepted)

        with patch.object(dialogos.QDialog, "exec", ejecutar):
            datos = dialogos.prompt_cliente_ficha(QWidget(), title="t", helper_text="h", tipos=self.TIPOS,
                                                  current_values={"nombre": "Ana", "telefono": "6671234567",
                                                                  "tipo_clave": "DOCENTE", "notas": "n"})
        self.assertEqual(visto["tipos"], ["GENERAL", "DOCENTE", "MAYORISTA", "INSTITUCION"])
        self.assertEqual(visto["actual"], "DOCENTE")
        self.assertEqual(datos, {"nombre": "Ana", "telefono": "6671234567", "tipo_clave": "MAYORISTA", "notas": "n"})

    def test_formulario_no_tiene_campo_de_descuento(self) -> None:
        from PyQt6.QtWidgets import QDoubleSpinBox

        def ejecutar(dialog):
            self.assertIsNone(dialog.findChild(QDoubleSpinBox))
            return int(QDialog.DialogCode.Rejected)

        with patch.object(dialogos.QDialog, "exec", ejecutar):
            self.assertIsNone(dialogos.prompt_cliente_ficha(QWidget(), title="t", helper_text="h", tipos=self.TIPOS))

    def test_motivo_corto_no_habilita_aceptar(self) -> None:
        def ejecutar(dialog):
            campo = dialog.findChild(QLineEdit)
            boton = dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok)
            campo.setText("no")
            self.assertFalse(boton.isEnabled())
            campo.setText("Cliente duplicado")
            self.assertTrue(boton.isEnabled())
            return int(QDialog.DialogCode.Accepted)

        with patch.object(dialogos.QDialog, "exec", ejecutar):
            self.assertEqual(dialogos.prompt_motivo(QWidget(), title="t", helper_text="h"), "Cliente duplicado")


class PantallaTests(_Qt):
    """Los botones de Configuración usan la ficha nueva y piden motivo."""

    def _ctx(self):
        class _Ctx:
            def __enter__(self_inner):
                return SimpleNamespace(commit=lambda: None)

            def __exit__(self_inner, *a):
                return False

        return _Ctx()

    def test_crear_usa_la_ficha_nueva(self) -> None:
        falso = SimpleNamespace(current_role=RolUsuario.ADMIN)
        with patch("pos_uniformes.ui.main_window.get_session", return_value=self._ctx()), patch(
            "pos_uniformes.ui.main_window.tipos_para_combo", return_value=[("GENERAL", "General")]
        ), patch("pos_uniformes.ui.main_window.prompt_cliente_ficha", return_value=None) as prompt, patch(
            "pos_uniformes.ui.main_window.crear_cliente"
        ) as crear:
            MainWindow._handle_create_client(falso)
        self.assertEqual(prompt.call_args.kwargs["tipos"], [("GENERAL", "General")])
        crear.assert_not_called()

    def test_crear_con_telefono_repetido_da_error_y_no_reintenta(self) -> None:
        coincidencia = ids.ClienteEncontrado(id=1, codigo="CLI-000001", nombre="Ana", telefono_enmascarado="•••• 4567")
        crear = MagicMock(side_effect=ids.CoincidenciasPorConfirmarError([coincidencia]))
        falso = SimpleNamespace(current_role=RolUsuario.ADMIN, user_id=1, _render_client_card_safe=None,
                                refresh_all=MagicMock())
        with patch("pos_uniformes.ui.main_window.get_session", side_effect=lambda: self._ctx()), patch(
            "pos_uniformes.ui.main_window.tipos_para_combo", return_value=[]
        ), patch("pos_uniformes.ui.main_window.prompt_cliente_ficha", return_value={"nombre": "Ana"}), patch(
            "pos_uniformes.ui.main_window.crear_cliente", crear
        ), patch("pos_uniformes.ui.main_window.QMessageBox.warning") as aviso:
            MainWindow._handle_create_client(falso)
        crear.assert_called_once()
        self.assertNotIn("confirmar_telefono_compartido", crear.call_args.kwargs)
        aviso.assert_called_once()
        self.assertIn("CLI-000001", aviso.call_args.args[2])
        falso.refresh_all.assert_not_called()

    def test_cambiar_estado_sin_motivo_no_hace_nada(self) -> None:
        falso = SimpleNamespace(current_role=RolUsuario.ADMIN, _selected_settings_client_id=lambda: 5)
        with patch("pos_uniformes.ui.main_window.prompt_motivo", return_value=None), patch(
            "pos_uniformes.ui.main_window.alternar_estado"
        ) as alternar:
            MainWindow._handle_toggle_client(falso)
        alternar.assert_not_called()


if __name__ == "__main__":
    unittest.main()
