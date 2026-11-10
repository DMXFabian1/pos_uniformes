"""Gestion de clientes para ventas, apartados y fidelizacion futura."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Cliente, RolUsuario, TipoCliente, Usuario
from pos_uniformes.services.clientes import identidad_service
from pos_uniformes.services.clientes.telefono import normalizar_telefono
from pos_uniformes.services.loyalty_service import LoyaltyService


class ClientService:
    """Reglas de negocio para administracion de clientes."""

    DEFAULT_DISCOUNT_BY_TYPE = {
        TipoCliente.GENERAL: Decimal("5.00"),
        TipoCliente.PROFESOR: Decimal("15.00"),
        TipoCliente.MAYORISTA: Decimal("20.00"),
    }

    @staticmethod
    def _validar_admin(admin_user: Usuario) -> None:
        if not admin_user.activo:
            raise PermissionError("El usuario administrador no esta activo.")
        if admin_user.rol != RolUsuario.ADMIN:
            raise PermissionError("Solo ADMIN puede gestionar clientes.")

    @staticmethod
    def list_clients(session: Session, search_text: str = "") -> list[Cliente]:
        statement = select(Cliente).order_by(Cliente.nombre.asc())
        normalized_search = search_text.strip().lower()
        if normalized_search:
            like_term = f"%{normalized_search}%"
            statement = statement.where(
                or_(
                    func.lower(Cliente.codigo_cliente).like(like_term),
                    func.lower(Cliente.nombre).like(like_term),
                    func.lower(func.coalesce(Cliente.telefono, "")).like(like_term),
                    func.lower(func.coalesce(Cliente.notas, "")).like(like_term),
                    func.lower(cast(Cliente.tipo_cliente, String)).like(like_term),
                    func.lower(cast(Cliente.nivel_lealtad, String)).like(like_term),
                )
            )
        return session.scalars(statement).all()

    @staticmethod
    def _generate_client_code(session: Session) -> str:
        next_id = (session.scalar(select(func.coalesce(func.max(Cliente.id), 0))) or 0) + 1
        return f"CLI-{int(next_id):06d}"

    @classmethod
    def default_discount_for_type(cls, tipo_cliente: TipoCliente) -> Decimal:
        default_level = LoyaltyService.default_level_for_client_type(tipo_cliente)
        return LoyaltyService.discount_for_level(default_level)

    @classmethod
    def normalize_discount(cls, discount_value: Decimal | str | float | int) -> Decimal:
        normalized = Decimal(str(discount_value)).quantize(Decimal("0.01"))
        if normalized < Decimal("0.00") or normalized > Decimal("100.00"):
            raise ValueError("El descuento preferente debe estar entre 0 y 100.")
        return normalized

    @classmethod
    def create_client(
        cls,
        session: Session,
        admin_user: Usuario,
        nombre: str,
        tipo_cliente: TipoCliente = TipoCliente.GENERAL,
        descuento_preferente: Decimal = Decimal("0.00"),
        telefono: str = "",
        notas: str = "",
    ) -> Cliente:
        cls._validar_admin(admin_user)
        # E1-B (R1, K1): el alta del ADMIN nace sin nivel y con descuento 0.
        # `descuento_preferente` se ignora a propósito: asignar nivel o
        # descuento es una acción explícita aparte (E1-C).
        cls.normalize_discount(descuento_preferente)  # sigue validando el rango
        # Teléfono de 10 dígitos y único (Daniel, 2026-11-10).
        try:
            return identidad_service.dar_de_alta(
                session,
                nombre=nombre,
                telefono=telefono,
                origen=identidad_service.ORIGEN_POS_ADMIN,
                tipo_cliente=tipo_cliente,
                notas=notas,
                usuario_id=getattr(admin_user, "id", None),
                exigir_telefono_valido=True,
                revisar_duplicados=True,
            )
        except identidad_service.CoincidenciasPorConfirmarError as exc:
            raise ValueError(identidad_service.mensaje_telefono_ya_registrado(exc.coincidencias)) from exc

    @classmethod
    def create_client_quick(
        cls,
        session: Session,
        usuario: Usuario,
        nombre: str,
        telefono: str = "",
    ) -> Cliente:
        if not usuario.activo:
            raise PermissionError("El usuario no esta activo.")
        if usuario.rol not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            raise PermissionError("El usuario no puede registrar clientes desde operacion.")
        normalized_name = nombre.strip()
        normalized_phone = telefono.strip()
        if not normalized_name:
            raise ValueError("El nombre del cliente no puede estar vacio.")
        if not normalized_phone:
            raise ValueError("El telefono del cliente no puede estar vacio.")
        # E1-B (K1): el alta rápida de Presupuesto nace sin nivel ni descuento.
        # Teléfono de 10 dígitos y único, como en Venta Rápida (Daniel, 2026-11-10).
        try:
            return identidad_service.dar_de_alta(
                session,
                nombre=normalized_name,
                telefono=normalized_phone,
                origen=identidad_service.ORIGEN_PRESUPUESTO_KIOSKO,
                usuario_id=getattr(usuario, "id", None),
                exigir_telefono_valido=True,
                revisar_duplicados=True,
            )
        except identidad_service.CoincidenciasPorConfirmarError as exc:
            raise ValueError(identidad_service.mensaje_telefono_ya_registrado(exc.coincidencias)) from exc

    @classmethod
    def update_client(
        cls,
        session: Session,
        admin_user: Usuario,
        client: Cliente,
        nombre: str,
        tipo_cliente: TipoCliente = TipoCliente.GENERAL,
        descuento_preferente: Decimal = Decimal("0.00"),
        telefono: str = "",
        notas: str = "",
    ) -> Cliente:
        cls._validar_admin(admin_user)
        normalized_name = nombre.strip()
        if not normalized_name:
            raise ValueError("El nombre del cliente no puede estar vacio.")
        if client.nivel_lealtad is None:
            # E1-B (R1, R3): editar a un cliente SIN nivel nunca le asigna
            # nivel ni toca su descuento ni los metadatos de asignación.
            cls.normalize_discount(descuento_preferente)  # sigue validando el rango
            client.nombre = normalized_name
            client.tipo_cliente = tipo_cliente
            client.telefono = telefono.strip() or None
            client.telefono_normalizado = normalizar_telefono(client.telefono)
            client.notas = notas.strip() or None
            session.add(client)
            return client
        client.nombre = normalized_name
        client.tipo_cliente = tipo_cliente
        client.descuento_preferente = cls.normalize_discount(descuento_preferente)
        client.telefono = telefono.strip() or None
        client.telefono_normalizado = normalizar_telefono(client.telefono)
        client.notas = notas.strip() or None
        LoyaltyService.assign_level(
            client,
            level=LoyaltyService.default_level_for_client_type(tipo_cliente),
            actor_user=admin_user,
            reason="actualizacion_cliente",
        )
        session.add(client)
        return client

    @classmethod
    def toggle_active(
        cls,
        session: Session,
        admin_user: Usuario,
        client: Cliente,
    ) -> Cliente:
        cls._validar_admin(admin_user)
        client.activo = not client.activo
        session.add(client)
        return client
