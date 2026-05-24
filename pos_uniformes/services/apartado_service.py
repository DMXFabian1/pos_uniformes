"""Reglas de negocio para apartados y abonos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from pos_uniformes.database.models import (
    Apartado,
    ApartadoAbono,
    ApartadoDetalle,
    Cliente,
    EstadoApartado,
    RolUsuario,
    Usuario,
    Variante,
)
from pos_uniformes.services.inventario_service import InventarioService
from pos_uniformes.services.layaway_pricing_service import (
    build_layaway_pricing,
    resolve_layaway_client_discount_percent,
    resolve_layaway_min_deposit,
    resolve_layaway_unit_price,
)


@dataclass(frozen=True)
class ApartadoItemInput:
    sku: str
    cantidad: int
    precio_unitario: Decimal | None = None
    pricing_rule_key: str = ""
    pricing_rule_label: str = ""


class ApartadoService:
    """Crea, abona, entrega y cancela apartados con reserva de stock."""

    @staticmethod
    def _validar_operador(usuario: Usuario) -> None:
        if not usuario.activo:
            raise PermissionError("El usuario no esta activo.")
        if usuario.rol not in {RolUsuario.ADMIN, RolUsuario.CAJERO}:
            raise PermissionError("El usuario no puede gestionar apartados.")

    @staticmethod
    def _validar_admin(usuario: Usuario) -> None:
        ApartadoService._validar_operador(usuario)
        if usuario.rol != RolUsuario.ADMIN:
            raise PermissionError("Solo ADMIN puede cancelar apartados.")

    @staticmethod
    def obtener_variante_por_sku(session: Session, sku: str) -> Variante | None:
        statement = select(Variante).where(Variante.sku == sku, Variante.activo.is_(True))
        return session.scalar(statement)

    @staticmethod
    def _recalcular_estado(apartado: Apartado) -> None:
        if apartado.estado == EstadoApartado.CANCELADO:
            return
        if apartado.estado == EstadoApartado.ENTREGADO:
            return
        if apartado.saldo_pendiente <= Decimal("0.00"):
            apartado.saldo_pendiente = Decimal("0.00")
            apartado.estado = EstadoApartado.LIQUIDADO
            if apartado.liquidado_at is None:
                apartado.liquidado_at = datetime.now(timezone.utc)
        else:
            apartado.estado = EstadoApartado.ACTIVO
            apartado.liquidado_at = None

    @classmethod
    def crear_apartado(
        cls,
        session: Session,
        usuario: Usuario,
        folio: str,
        cliente_nombre: str,
        cliente_telefono: str | None,
        items: list[ApartadoItemInput],
        anticipo: Decimal,
        fecha_compromiso: datetime | None = None,
        observacion: str | None = None,
        cliente: Cliente | None = None,
        seller_employee_code: str | None = None,
        seller_employee_display_name: str | None = None,
    ) -> Apartado:
        cls._validar_operador(usuario)
        if not cliente_nombre.strip():
            raise ValueError("Debes capturar el nombre del cliente.")
        if not items:
            raise ValueError("El apartado debe contener al menos una presentacion.")
        if anticipo <= Decimal("0.00"):
            raise ValueError("El apartado debe iniciar con un anticipo mayor a cero.")

        apartado = Apartado(
            usuario=usuario,
            cliente=cliente,
            folio=folio.strip(),
            cliente_nombre=cliente_nombre.strip(),
            cliente_telefono=(cliente_telefono or "").strip() or None,
            fecha_compromiso=fecha_compromiso,
            observacion=observacion,
            estado=EstadoApartado.ACTIVO,
            seller_employee_code=seller_employee_code or None,
            seller_employee_display_name=seller_employee_display_name or None,
        )

        total = Decimal("0.00")
        seen_skus: set[str] = set()
        client_discount_percent = resolve_layaway_client_discount_percent(
            session,
            selected_client_id=getattr(cliente, "id", None),
        )
        for item in items:
            sku = item.sku.strip().upper()
            if not sku:
                raise ValueError("Cada linea del apartado necesita SKU.")
            if sku in seen_skus:
                raise ValueError(f"El SKU '{sku}' esta repetido en el apartado.")
            seen_skus.add(sku)
            if item.cantidad <= 0:
                raise ValueError("La cantidad debe ser mayor a cero.")

            variante = cls.obtener_variante_por_sku(session, sku)
            if variante is None:
                raise ValueError(f"No existe una presentacion activa para el SKU '{sku}'.")

            InventarioService.validar_stock_disponible(variante, item.cantidad)
            precio_unitario = (
                Decimal(item.precio_unitario).quantize(Decimal("0.01"))
                if item.precio_unitario is not None
                else resolve_layaway_unit_price(
                    variante.precio_venta,
                    discount_percent=client_discount_percent,
                )
            )
            subtotal_linea = Decimal(item.cantidad) * precio_unitario
            detalle = ApartadoDetalle(
                variante=variante,
                cantidad=item.cantidad,
                precio_unitario=precio_unitario,
                subtotal_linea=subtotal_linea,
            )
            apartado.detalles.append(detalle)
            total += subtotal_linea

        pricing = build_layaway_pricing(total)
        minimum_deposit = resolve_layaway_min_deposit(pricing.total)
        if anticipo < minimum_deposit:
            raise ValueError(
                f"El anticipo minimo para este apartado es ${minimum_deposit} (20% del total)."
            )
        if anticipo > pricing.total:
            raise ValueError("El anticipo no puede ser mayor al total del apartado.")

        apartado.subtotal = pricing.subtotal
        apartado.total = pricing.total
        apartado.total_abonado = anticipo
        apartado.saldo_pendiente = pricing.total - anticipo

        session.add(apartado)
        session.flush()

        for detalle in apartado.detalles:
            InventarioService.registrar_reserva_apartado(
                session=session,
                variante=detalle.variante,
                cantidad=detalle.cantidad,
                referencia=apartado.folio,
                observacion=f"Apartado para {apartado.cliente_nombre}",
                creado_por=usuario.username,
            )

        if anticipo > Decimal("0.00"):
            session.add(
                ApartadoAbono(
                    apartado=apartado,
                    usuario=usuario,
                    monto=anticipo,
                    referencia="ANTICIPO",
                    observacion="Anticipo inicial del apartado.",
                    seller_employee_code=seller_employee_code or None,
                    seller_employee_display_name=seller_employee_display_name or None,
                )
            )

        cls._recalcular_estado(apartado)
        session.add(apartado)
        return apartado

    @classmethod
    def registrar_abono(
        cls,
        session: Session,
        apartado: Apartado,
        usuario: Usuario,
        monto: Decimal,
        metodo_pago: str = "Efectivo",
        monto_efectivo: Decimal | None = None,
        referencia: str | None = None,
        observacion: str | None = None,
        seller_employee_code: str | None = None,
        seller_employee_display_name: str | None = None,
    ) -> ApartadoAbono:
        cls._validar_operador(usuario)
        if apartado.estado in {EstadoApartado.CANCELADO, EstadoApartado.ENTREGADO}:
            raise ValueError("No puedes registrar abonos sobre un apartado cerrado.")
        if monto <= Decimal("0.00"):
            raise ValueError("El abono debe ser mayor a cero.")
        if monto > apartado.saldo_pendiente:
            raise ValueError("El abono no puede ser mayor al saldo pendiente.")
        metodo_pago_normalizado = metodo_pago.strip() or "Efectivo"
        if metodo_pago_normalizado not in {"Efectivo", "Transferencia", "Mixto"}:
            raise ValueError("Metodo de pago no valido para el abono.")

        if monto_efectivo is None:
            efectivo_real = monto if metodo_pago_normalizado == "Efectivo" else Decimal("0.00")
        else:
            efectivo_real = Decimal(monto_efectivo)
        if efectivo_real < Decimal("0.00"):
            raise ValueError("El efectivo del abono no puede ser negativo.")
        if metodo_pago_normalizado == "Efectivo" and efectivo_real != monto:
            raise ValueError("En abonos en efectivo, el monto en caja debe coincidir con el abono.")
        if metodo_pago_normalizado == "Transferencia" and efectivo_real != Decimal("0.00"):
            raise ValueError("En abonos por transferencia, el efectivo en caja debe ser cero.")
        if metodo_pago_normalizado == "Mixto" and efectivo_real > monto:
            raise ValueError("En abonos mixtos, el efectivo en caja no puede exceder el abono total.")

        abono = ApartadoAbono(
            apartado=apartado,
            usuario=usuario,
            monto=monto,
            metodo_pago=metodo_pago_normalizado,
            monto_efectivo=efectivo_real.quantize(Decimal("0.01")),
            referencia=(referencia or "").strip() or None,
            observacion=(observacion or "").strip() or None,
            seller_employee_code=seller_employee_code or None,
            seller_employee_display_name=seller_employee_display_name or None,
        )
        apartado.total_abonado = Decimal(apartado.total_abonado) + monto
        apartado.saldo_pendiente = Decimal(apartado.total) - Decimal(apartado.total_abonado)
        cls._recalcular_estado(apartado)
        session.add(abono)
        session.add(apartado)
        return abono

    @classmethod
    def entregar_apartado(
        cls,
        session: Session,
        apartado: Apartado,
        usuario: Usuario,
        delivery_employee_code: str | None = None,
        delivery_employee_display_name: str | None = None,
    ) -> Apartado:
        cls._validar_operador(usuario)
        if apartado.estado == EstadoApartado.CANCELADO:
            raise ValueError("No puedes entregar un apartado cancelado.")
        if apartado.estado == EstadoApartado.ENTREGADO:
            raise ValueError("El apartado ya fue entregado.")
        if apartado.saldo_pendiente > Decimal("0.00"):
            raise ValueError("No puedes entregar un apartado con saldo pendiente.")

        apartado.estado = EstadoApartado.ENTREGADO
        apartado.entregado_por = usuario
        apartado.entregado_at = datetime.now(timezone.utc)
        if delivery_employee_code:
            apartado.delivery_employee_code = delivery_employee_code
            apartado.delivery_employee_display_name = delivery_employee_display_name or None
        session.add(apartado)
        return apartado

    @classmethod
    def cancelar_apartado(
        cls,
        session: Session,
        apartado: Apartado,
        usuario: Usuario,
        observacion: str | None = None,
    ) -> Apartado:
        cls._validar_admin(usuario)
        if apartado.estado == EstadoApartado.CANCELADO:
            raise ValueError("El apartado ya esta cancelado.")
        if apartado.estado == EstadoApartado.ENTREGADO:
            raise ValueError("No puedes cancelar un apartado ya entregado.")

        for detalle in apartado.detalles:
            InventarioService.registrar_liberacion_apartado(
                session=session,
                variante=detalle.variante,
                cantidad=detalle.cantidad,
                referencia=apartado.folio,
                observacion=(observacion or "").strip() or f"Cancelacion de apartado {apartado.folio}",
                creado_por=usuario.username,
            )

        apartado.estado = EstadoApartado.CANCELADO
        apartado.cancelado_por = usuario
        apartado.cancelado_at = datetime.now(timezone.utc)
        if observacion:
            apartado.observacion = observacion
        session.add(apartado)
        return apartado

    @classmethod
    def anular_ultimo_abono(
        cls,
        session: Session,
        apartado: Apartado,
        usuario: Usuario,
        observacion: str | None = None,
    ) -> ApartadoAbono:
        """Anula el último abono registrado y recalcula saldos."""
        cls._validar_operador(usuario)
        if apartado.estado in {EstadoApartado.CANCELADO, EstadoApartado.ENTREGADO}:
            raise ValueError("No puedes anular abonos de un apartado cerrado.")
        abonos = sorted(apartado.abonos, key=lambda a: a.created_at)
        if not abonos:
            raise ValueError("El apartado no tiene abonos registrados.")
        ultimo = abonos[-1]
        apartado.total_abonado = Decimal(apartado.total_abonado) - Decimal(ultimo.monto)
        apartado.saldo_pendiente = Decimal(apartado.total) - Decimal(apartado.total_abonado)
        cls._recalcular_estado(apartado)
        session.delete(ultimo)
        session.add(apartado)
        return ultimo

    @classmethod
    def agregar_detalle(
        cls,
        session: Session,
        apartado: Apartado,
        usuario: Usuario,
        sku: str,
        cantidad: int,
        precio_unitario: Decimal | None = None,
    ) -> ApartadoDetalle:
        """Agrega un producto al apartado existente."""
        cls._validar_operador(usuario)
        if apartado.estado != EstadoApartado.ACTIVO:
            raise ValueError("Solo puedes editar apartados activos.")
        sku = sku.strip().upper()
        if not sku:
            raise ValueError("El SKU no puede estar vacio.")
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero.")
        for d in apartado.detalles:
            if d.variante.sku == sku:
                raise ValueError(f"El SKU '{sku}' ya existe en el apartado. Usa cambiar cantidad.")
        variante = cls.obtener_variante_por_sku(session, sku)
        if variante is None:
            raise ValueError(f"No existe una presentacion activa para el SKU '{sku}'.")
        InventarioService.validar_stock_disponible(variante, cantidad)
        if precio_unitario is None:
            client_discount = resolve_layaway_client_discount_percent(
                session, selected_client_id=getattr(apartado.cliente, "id", None),
            )
            precio_unitario = resolve_layaway_unit_price(variante.precio_venta, discount_percent=client_discount)
        else:
            precio_unitario = Decimal(precio_unitario).quantize(Decimal("0.01"))
        subtotal_linea = Decimal(cantidad) * precio_unitario
        detalle = ApartadoDetalle(
            apartado=apartado,
            variante=variante,
            cantidad=cantidad,
            precio_unitario=precio_unitario,
            subtotal_linea=subtotal_linea,
        )
        session.add(detalle)
        session.flush()
        InventarioService.registrar_reserva_apartado(
            session=session,
            variante=variante,
            cantidad=cantidad,
            referencia=apartado.folio,
            observacion=f"Agregado a apartado {apartado.folio}",
            creado_por=usuario.username,
        )
        cls._recalcular_totales(session, apartado)
        return detalle

    @classmethod
    def quitar_detalle(
        cls,
        session: Session,
        apartado: Apartado,
        usuario: Usuario,
        detalle_id: int,
    ) -> None:
        """Quita un producto del apartado y libera su inventario."""
        cls._validar_operador(usuario)
        if apartado.estado != EstadoApartado.ACTIVO:
            raise ValueError("Solo puedes editar apartados activos.")
        detalle = next((d for d in apartado.detalles if d.id == detalle_id), None)
        if detalle is None:
            raise ValueError("No se encontro el detalle en el apartado.")
        if len(apartado.detalles) <= 1:
            raise ValueError("No puedes quitar el ultimo producto. Cancela el apartado en su lugar.")
        InventarioService.registrar_liberacion_apartado(
            session=session,
            variante=detalle.variante,
            cantidad=detalle.cantidad,
            referencia=apartado.folio,
            observacion=f"Eliminado de apartado {apartado.folio}",
            creado_por=usuario.username,
        )
        session.delete(detalle)
        session.flush()
        cls._recalcular_totales(session, apartado)

    @classmethod
    def cambiar_cantidad_detalle(
        cls,
        session: Session,
        apartado: Apartado,
        usuario: Usuario,
        detalle_id: int,
        nueva_cantidad: int,
    ) -> ApartadoDetalle:
        """Cambia la cantidad de un producto en el apartado."""
        cls._validar_operador(usuario)
        if apartado.estado != EstadoApartado.ACTIVO:
            raise ValueError("Solo puedes editar apartados activos.")
        if nueva_cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero.")
        detalle = next((d for d in apartado.detalles if d.id == detalle_id), None)
        if detalle is None:
            raise ValueError("No se encontro el detalle en el apartado.")
        diferencia = nueva_cantidad - detalle.cantidad
        if diferencia > 0:
            InventarioService.validar_stock_disponible(detalle.variante, diferencia)
            InventarioService.registrar_reserva_apartado(
                session=session,
                variante=detalle.variante,
                cantidad=diferencia,
                referencia=apartado.folio,
                observacion=f"Aumento cantidad en apartado {apartado.folio}",
                creado_por=usuario.username,
            )
        elif diferencia < 0:
            InventarioService.registrar_liberacion_apartado(
                session=session,
                variante=detalle.variante,
                cantidad=abs(diferencia),
                referencia=apartado.folio,
                observacion=f"Reduccion cantidad en apartado {apartado.folio}",
                creado_por=usuario.username,
            )
        detalle.cantidad = nueva_cantidad
        detalle.subtotal_linea = Decimal(nueva_cantidad) * Decimal(detalle.precio_unitario)
        session.add(detalle)
        session.flush()
        cls._recalcular_totales(session, apartado)
        return detalle

    @classmethod
    def _recalcular_totales(cls, session: Session, apartado: Apartado) -> None:
        """Recalcula subtotal, total y saldo tras editar detalles."""
        session.refresh(apartado, ["detalles"])
        nuevo_subtotal = sum(Decimal(d.subtotal_linea) for d in apartado.detalles)
        pricing = build_layaway_pricing(nuevo_subtotal)
        if pricing.total < Decimal(apartado.total_abonado):
            raise ValueError(
                f"El nuevo total (${pricing.total}) no puede ser menor "
                f"a lo ya abonado (${apartado.total_abonado})."
            )
        apartado.subtotal = pricing.subtotal
        apartado.total = pricing.total
        apartado.saldo_pendiente = pricing.total - Decimal(apartado.total_abonado)
        cls._recalcular_estado(apartado)
        session.add(apartado)

    @staticmethod
    def listar_apartados(session: Session) -> list[Apartado]:
        statement = (
            select(Apartado)
            .options(
                joinedload(Apartado.usuario),
                joinedload(Apartado.cliente),
                joinedload(Apartado.detalles).joinedload(ApartadoDetalle.variante).joinedload(Variante.producto),
                joinedload(Apartado.abonos).joinedload(ApartadoAbono.usuario),
            )
            .order_by(desc(Apartado.created_at))
        )
        return list(session.scalars(statement).unique())

    @staticmethod
    def obtener_apartado(session: Session, apartado_id: int) -> Apartado | None:
        statement = (
            select(Apartado)
            .where(Apartado.id == apartado_id)
            .options(
                joinedload(Apartado.usuario),
                joinedload(Apartado.cliente),
                joinedload(Apartado.detalles).joinedload(ApartadoDetalle.variante).joinedload(Variante.producto),
                joinedload(Apartado.abonos).joinedload(ApartadoAbono.usuario),
            )
        )
        return session.scalar(statement)
