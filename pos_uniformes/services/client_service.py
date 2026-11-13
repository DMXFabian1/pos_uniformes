"""Gestion de clientes para ventas, apartados y fidelizacion futura."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Cliente, ClienteTipo, RolUsuario, TipoCliente, Usuario
from pos_uniformes.services.clientes import identidad_service
from pos_uniformes.services.clientes.telefono import normalizar_telefono


class ClientService:
    """Reglas de negocio para administracion de clientes."""

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
            # 2026-11-12 (Daniel: «la caja antigua ya no es de utilidad»): el
            # tipo se busca en el catálogo (`ClienteTipo` por
            # `tipo_cliente_id`, el que manda), no en el enum viejo, que no
            # tiene «docente» ni «institución».
            tipo_coincide = select(ClienteTipo.id).where(
                or_(
                    func.lower(ClienteTipo.nombre).like(like_term),
                    func.lower(ClienteTipo.clave).like(like_term),
                )
            )
            statement = statement.where(
                or_(
                    func.lower(Cliente.codigo_cliente).like(like_term),
                    func.lower(Cliente.nombre).like(like_term),
                    func.lower(func.coalesce(Cliente.telefono, "")).like(like_term),
                    func.lower(func.coalesce(Cliente.notas, "")).like(like_term),
                    Cliente.tipo_cliente_id.in_(tipo_coincide),
                    # 2026-11-12: ya no se busca por el nivel viejo
                    # (`nivel_lealtad`), que se retiró.
                )
            )
        return session.scalars(statement).all()

    @staticmethod
    def _generate_client_code(session: Session) -> str:
        next_id = (session.scalar(select(func.coalesce(func.max(Cliente.id), 0))) or 0) + 1
        return f"CLI-{int(next_id):06d}"

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
        tipo_clave: str | None = None,
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
                tipo_cliente=identidad_service.enum_desde_clave(tipo_clave) if tipo_clave else tipo_cliente,
                tipo_clave=tipo_clave or None,
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
        tipo_clave: str | None = None,
    ) -> Cliente:
        cls._validar_admin(admin_user)
        normalized_name = nombre.strip()
        if not normalized_name:
            raise ValueError("El nombre del cliente no puede estar vacio.")
        # 2026-11-12: «el nivel viejo retíralo» (Daniel). Editar a un cliente
        # nunca toca su nivel viejo (`nivel_lealtad`), su `descuento_preferente`
        # ni los metadatos de asignación, tenga o no nivel. Antes, a un cliente
        # con nivel se le regresaba al nivel de su tipo.
        cls.normalize_discount(descuento_preferente)  # sigue validando el rango
        client.nombre = normalized_name
        # 2026-11-12 (Daniel: «la caja antigua ya no es de utilidad, todo lo
        # demás corre en libreta y kioskos»): el tipo que manda es
        # `tipo_cliente_id` (catálogo `ClienteTipo`). Antes aquí solo se
        # escribía el enum viejo y el tipo real no cambiaba. Se aplica con la
        # misma regla que el alta y la aprobación de programas: no da nivel,
        # descuento ni programa, deja su evento, y si el tipo llega del enum
        # viejo (que no tiene Institución), MAYORISTA respeta a Institución.
        clave = (tipo_clave or "").strip().upper() or identidad_service.clave_desde_enum(tipo_cliente)
        identidad_service.aplicar_tipo(
            session,
            client,
            clave,
            usuario_id=getattr(admin_user, "id", None),
            respetar_institucion=not tipo_clave,
            origen=identidad_service.ORIGEN_POS_ADMIN,
        )
        # El enum viejo queda coherente (nadie vivo lo lee; se retira en la etapa R).
        client.tipo_cliente = identidad_service.enum_desde_clave(clave) if tipo_clave else tipo_cliente
        client.telefono = telefono.strip() or None
        client.telefono_normalizado = normalizar_telefono(client.telefono)
        client.notas = notas.strip() or None
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
