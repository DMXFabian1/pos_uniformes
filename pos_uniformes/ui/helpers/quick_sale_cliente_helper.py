"""Venta Rápida: el botón «Cliente» abre el buscador y alta de E1-B.

Mixin para `QuickSaleWidget`. Elegir o registrar termina SIEMPRE en
`_identificar_cliente` (del Monedero), que no se modifica: la venta, el total,
la cola sin conexión y el Monedero siguen igual. Sin conexión no se busca ni
se registra.
"""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import QDialog, QMessageBox

from pos_uniformes.services.clientes import identidad_service
from pos_uniformes.services.clientes.identidad_service import ClienteEncontrado
from pos_uniformes.ui.dialogs.cliente_rapido_dialog import ClienteRapidoDialog
from pos_uniformes.ui.helpers.quick_sale_monedero_helper import _es_error_de_red

_logger = logging.getLogger(__name__)

SIN_CONEXION_MENSAJE = "Sin conexión: cobra sin cliente o intenta después."


class ClienteRapidoMixin:
    def _on_cliente_rapido(self) -> None:
        if not self._en_linea():
            QMessageBox.information(self, "Cliente", SIN_CONEXION_MENSAJE)
            return
        dialogo = ClienteRapidoDialog(
            self,
            buscar=self._buscar_clientes_identidad,
            registrar=self._registrar_cliente_identidad,
        )
        if dialogo.exec() != int(QDialog.DialogCode.Accepted) or dialogo.elegido is None:
            return
        elegido = dialogo.elegido
        self._identificar_cliente(elegido.codigo, por_qr=False, cliente_id=elegido.id)
        if getattr(dialogo, "es_nuevo", False):
            self._ofrecer_credencial_whatsapp(int(elegido.id))

    def _ofrecer_credencial_whatsapp(self, cliente_id: int) -> None:
        """Recién registrado: credencial lista para mandarla por WhatsApp.

        Si algo falla (sin teléfono, sin conexión, la imagen), se dice y ya:
        el cliente ya quedó registrado y ligado a la venta."""
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.services.clientes import credencial_whatsapp_service as cws
        from pos_uniformes.ui.dialogs.credencial_whatsapp_dialog import CredencialWhatsappDialog

        try:
            with get_session() as session:
                envio = cws.preparar(session, cliente_id)
        except cws.SinTelefonoParaWhatsappError as exc:
            QMessageBox.information(self, "Credencial", f"{exc}\n\nSe puede mandar después desde el POS.")
            return
        except Exception as exc:  # noqa: BLE001
            _logger.exception("Credencial de bienvenida: no se pudo preparar la del cliente %s", cliente_id)
            if _es_error_de_red(exc):
                self._avisar_sin_conexion()
                return
            QMessageBox.warning(self, "Credencial", f"No se pudo generar la credencial.\n\n{exc}")
            return
        # «Proponer programa…» también aquí, al momento del alta (Daniel,
        # 2026-11-10). Para entonces el cliente ya está ligado a la venta.
        CredencialWhatsappDialog(self, envio, proponer=self._on_proponer_programa).exec()

    def _buscar_clientes_identidad(self, texto: str) -> list[ClienteEncontrado]:
        from pos_uniformes.database.connection import get_session

        try:
            with get_session() as session:
                return identidad_service.buscar_clientes(session, texto)
        except Exception as exc:
            if _es_error_de_red(exc):
                self._avisar_sin_conexion()
            raise

    def _registrar_cliente_identidad(self, nombre: str, telefono: str, confirmar: bool) -> ClienteEncontrado:
        from pos_uniformes.database.connection import get_session

        try:
            with get_session() as session:
                cliente = identidad_service.dar_de_alta(
                    session,
                    nombre=nombre,
                    telefono=telefono,
                    origen=identidad_service.ORIGEN_VENTA_RAPIDA,
                    employee_code=str(self._employee_code or "") or None,
                    exigir_telefono_valido=True,
                    revisar_duplicados=True,
                    confirmar_telefono_compartido=confirmar,
                )
                # Entra directo a Maximoda Club (Daniel, 2026-11-10). Si no se
                # puede, el alta sigue sin programa.
                from pos_uniformes.services.fidelizacion import membresia_service

                membresia_service.inscribir_al_club_al_registrar(
                    session, cliente_id=int(cliente.id), employee_code=str(self._employee_code or "") or None
                )
                session.commit()
                return identidad_service._a_encontrado(cliente)
        except Exception as exc:
            if _es_error_de_red(exc):
                self._avisar_sin_conexion()
            raise
