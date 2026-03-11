"""Gestion de configuracion del negocio e impresion."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import ConfiguracionNegocio, RolUsuario, Usuario


@dataclass(frozen=True)
class BusinessSettingsInput:
    nombre_negocio: str
    telefono: str | None
    direccion: str | None
    pie_ticket: str | None
    transferencia_banco: str | None
    transferencia_beneficiario: str | None
    transferencia_clabe: str | None
    transferencia_instrucciones: str | None
    whatsapp_apartado_recordatorio: str | None
    whatsapp_apartado_liquidado: str | None
    whatsapp_cliente_promocion: str | None
    whatsapp_cliente_seguimiento: str | None
    whatsapp_cliente_saludo: str | None
    impresora_preferida: str | None
    copias_ticket: int


class BusinessSettingsService:
    """Administra la configuracion general del negocio."""

    @staticmethod
    def _validate_admin(admin_user: Usuario) -> None:
        if not admin_user.activo:
            raise PermissionError("El usuario administrador no esta activo.")
        if admin_user.rol != RolUsuario.ADMIN:
            raise PermissionError("Solo ADMIN puede actualizar la configuracion del negocio.")

    @staticmethod
    def get_or_create(session: Session) -> ConfiguracionNegocio:
        config = session.scalar(select(ConfiguracionNegocio).limit(1))
        if config is None:
            config = ConfiguracionNegocio(
                nombre_negocio="POS Uniformes",
                pie_ticket="Gracias por tu compra.",
                whatsapp_apartado_recordatorio=(
                    "Hola {cliente}, te recordamos tu apartado {folio}. "
                    "Saldo pendiente: ${saldo}. Estado de vencimiento: {vencimiento}. "
                    "Fecha compromiso: {fecha_compromiso}."
                ),
                whatsapp_apartado_liquidado=(
                    "Hola {cliente}, tu apartado {folio} ya esta liquidado y listo para entrega. "
                    "Fecha compromiso: {fecha_compromiso}."
                ),
                whatsapp_cliente_promocion=(
                    "Hola {cliente}, queremos compartirte una promocion especial disponible en tienda."
                ),
                whatsapp_cliente_seguimiento=(
                    "Hola {cliente}, te escribimos para dar seguimiento y ponernos a tus ordenes."
                ),
                whatsapp_cliente_saludo=(
                    "Hola {cliente}, gracias por seguir en contacto con nosotros."
                ),
                copias_ticket=1,
            )
            session.add(config)
            session.flush()
        return config

    @classmethod
    def update_settings(
        cls,
        session: Session,
        admin_user: Usuario,
        payload: BusinessSettingsInput,
    ) -> ConfiguracionNegocio:
        cls._validate_admin(admin_user)
        if not payload.nombre_negocio.strip():
            raise ValueError("El nombre del negocio no puede estar vacio.")
        if payload.copias_ticket < 1 or payload.copias_ticket > 5:
            raise ValueError("Las copias de ticket deben estar entre 1 y 5.")

        config = cls.get_or_create(session)
        config.nombre_negocio = payload.nombre_negocio.strip()
        config.telefono = payload.telefono.strip() if payload.telefono else None
        config.direccion = payload.direccion.strip() if payload.direccion else None
        config.pie_ticket = payload.pie_ticket.strip() if payload.pie_ticket else None
        config.transferencia_banco = payload.transferencia_banco.strip() if payload.transferencia_banco else None
        config.transferencia_beneficiario = (
            payload.transferencia_beneficiario.strip() if payload.transferencia_beneficiario else None
        )
        config.transferencia_clabe = payload.transferencia_clabe.strip() if payload.transferencia_clabe else None
        config.transferencia_instrucciones = (
            payload.transferencia_instrucciones.strip() if payload.transferencia_instrucciones else None
        )
        config.whatsapp_apartado_recordatorio = (
            payload.whatsapp_apartado_recordatorio.strip() if payload.whatsapp_apartado_recordatorio else None
        )
        config.whatsapp_apartado_liquidado = (
            payload.whatsapp_apartado_liquidado.strip() if payload.whatsapp_apartado_liquidado else None
        )
        config.whatsapp_cliente_promocion = (
            payload.whatsapp_cliente_promocion.strip() if payload.whatsapp_cliente_promocion else None
        )
        config.whatsapp_cliente_seguimiento = (
            payload.whatsapp_cliente_seguimiento.strip() if payload.whatsapp_cliente_seguimiento else None
        )
        config.whatsapp_cliente_saludo = (
            payload.whatsapp_cliente_saludo.strip() if payload.whatsapp_cliente_saludo else None
        )
        config.impresora_preferida = payload.impresora_preferida.strip() if payload.impresora_preferida else None
        config.copias_ticket = payload.copias_ticket
        session.add(config)
        return config
