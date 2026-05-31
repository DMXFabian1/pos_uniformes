"""Flujo conversacional guiado para cotizar uniformes por WhatsApp.

Es una maquina de estados simple que acompaña al cliente paso a paso:

    1. Elegir escuela
    2. Elegir tipo de prenda (familia de producto)
    3. Elegir variante (talla / color) — muestra el precio
    4. Indicar cantidad
    5. Agregar otra prenda o finalizar
    6. (Opcional) dar un nombre
    7. Se genera un PRESUPUESTO en estado BORRADOR, atribuido a un
       usuario de servicio, con el telefono de WhatsApp del cliente.

Los precios y totales SIEMPRE provienen de la base de datos (tabla variante),
nunca se inventan. Una empleada revisa y emite el presupuesto desde el POS.

NOTA sobre el almacenamiento de sesiones: para este prototipo el estado de la
conversacion vive en memoria del proceso (`_SESSIONS`). Funciona porque la API
corre con un solo worker de uvicorn. Para produccion con varios workers,
mover este estado a Redis o a una tabla de la base de datos.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from pos_uniformes.api.services.whatsapp_client import WhatsAppClient
from pos_uniformes.database.models import (
    EstadoPresupuesto,
    Escuela,
    Presupuesto,
    PresupuestoDetalle,
    Producto,
    RolUsuario,
    TipoPieza,
    Usuario,
    Variante,
)

logger = logging.getLogger(__name__)

# ── Estados de la conversacion ──────────────────────────────────────────────
STEP_ASK_SCHOOL = "ask_school"
STEP_ASK_FAMILY = "ask_family"
STEP_ASK_VARIANT = "ask_variant"
STEP_ASK_QTY = "ask_qty"
STEP_ASK_MORE = "ask_more"
STEP_ASK_NAME = "ask_name"

SESSION_TTL_SECONDS = 60 * 60  # 1 hora de inactividad reinicia la conversacion
MAX_LIST_ROWS = 10


@dataclass
class CartItem:
    variante_id: int
    sku: str
    descripcion: str
    talla: str
    color: str
    precio: Decimal
    cantidad: int

    @property
    def subtotal(self) -> Decimal:
        return (self.precio * self.cantidad).quantize(Decimal("0.01"))


@dataclass
class Session_:
    step: str = STEP_ASK_SCHOOL
    escuela_id: int | None = None
    escuela_nombre: str | None = None
    families: list[dict] = field(default_factory=list)  # cache del paso de familias
    pending_variante_id: int | None = None
    pending_label: str | None = None
    cart: list[CartItem] = field(default_factory=list)
    cliente_nombre: str | None = None
    last_active: float = field(default_factory=time.time)


# Estado en memoria, indexado por numero de WhatsApp (wa_id).
_SESSIONS: dict[str, Session_] = {}


def _get_session(phone: str) -> Session_:
    sess = _SESSIONS.get(phone)
    if sess is not None and (time.time() - sess.last_active) > SESSION_TTL_SECONDS:
        sess = None
    if sess is None:
        sess = Session_()
        _SESSIONS[phone] = sess
    sess.last_active = time.time()
    return sess


def _reset_session(phone: str) -> None:
    _SESSIONS.pop(phone, None)


# ── Consultas a la base de datos ─────────────────────────────────────────────

def _buscar_escuelas(db: Session, filtro: str | None = None) -> list[Escuela]:
    """Escuelas activas que tienen al menos un producto/variante activos."""
    stmt = (
        select(Escuela)
        .join(Producto, Producto.escuela_id == Escuela.id)
        .join(Variante, Variante.producto_id == Producto.id)
        .where(
            Escuela.activo.is_(True),
            Producto.activo.is_(True),
            Variante.activo.is_(True),
        )
        .distinct()
        .order_by(Escuela.nombre)
    )
    if filtro:
        stmt = stmt.where(func.lower(Escuela.nombre).like(f"%{filtro.strip().lower()}%"))
    return list(db.scalars(stmt.limit(MAX_LIST_ROWS + 1)).all())


def _familias_de_escuela(db: Session, escuela_id: int, filtro: str | None = None) -> list[dict]:
    """
    Agrupa los productos de una escuela por familia (tipo_pieza + nombre_base),
    con su precio mas bajo. Mismo criterio de agrupacion que el catalogo guiado.
    """
    productos = db.scalars(
        select(Producto)
        .where(
            Producto.escuela_id == escuela_id,
            Producto.activo.is_(True),
        )
        .options(selectinload(Producto.variantes), selectinload(Producto.tipo_pieza))
    ).all()

    familias: dict[str, dict] = {}
    for p in productos:
        variantes_activas = [v for v in p.variantes if v.activo]
        if not variantes_activas:
            continue
        if filtro and filtro.strip().lower() not in p.nombre_base.lower():
            continue
        tipo_pieza = p.tipo_pieza.nombre if p.tipo_pieza else "Sin pieza"
        key = f"{tipo_pieza}||{p.nombre_base}"
        if key not in familias:
            familias[key] = {
                "key": key,
                "nombre_base": p.nombre_base,
                "tipo_pieza": tipo_pieza,
                "precio_desde": min(v.precio_venta for v in variantes_activas),
                "producto_ids": [],
            }
        familias[key]["producto_ids"].append(p.id)
        familias[key]["precio_desde"] = min(
            familias[key]["precio_desde"],
            min(v.precio_venta for v in variantes_activas),
        )

    return sorted(familias.values(), key=lambda f: f["nombre_base"])


def _variantes_de_familia(db: Session, producto_ids: list[int]) -> list[Variante]:
    if not producto_ids:
        return []
    variantes = db.scalars(
        select(Variante)
        .where(Variante.producto_id.in_(producto_ids), Variante.activo.is_(True))
        .options(selectinload(Variante.producto))
        .order_by(Variante.talla, Variante.color)
    ).all()
    return list(variantes)


def _resolver_usuario_servicio(db: Session) -> Usuario | None:
    """Primer CAJERO activo; si no hay, primer ADMIN activo (igual que la API de quotes)."""
    user = db.scalar(
        select(Usuario)
        .where(Usuario.activo.is_(True), Usuario.rol == RolUsuario.CAJERO)
        .order_by(Usuario.id.asc())
    )
    if user is None:
        user = db.scalar(
            select(Usuario)
            .where(Usuario.activo.is_(True), Usuario.rol == RolUsuario.ADMIN)
            .order_by(Usuario.id.asc())
        )
    return user


def _generar_folio() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"PRE-{ts}-{uuid4().hex[:4].upper()}"


# ── Servicio principal ────────────────────────────────────────────────────────

class WhatsAppFlowService:
    """Orquesta la conversacion. Recibe un mensaje normalizado y responde."""

    def __init__(self, db: Session, client: WhatsAppClient | None = None) -> None:
        self.db = db
        self.client = client or WhatsAppClient()

    # message: {"reply_id": str|None, "text": str|None}
    def handle(self, phone: str, message: dict) -> None:
        reply_id = (message.get("reply_id") or "").strip()
        text = (message.get("text") or "").strip()

        # Comandos globales en cualquier momento.
        lower = text.lower()
        if reply_id in {"menu:cancel", "more:cancel"} or lower in {"cancelar", "salir"}:
            _reset_session(phone)
            self.client.send_text(phone, "Listo, cancelé la cotización. Escríbeme cuando quieras empezar de nuevo. 👋")
            return
        if lower in {"hola", "buenas", "menu", "menú", "inicio", "empezar"} and not reply_id:
            _reset_session(phone)

        sess = _get_session(phone)

        try:
            if sess.step == STEP_ASK_SCHOOL:
                self._handle_school(phone, sess, reply_id, text)
            elif sess.step == STEP_ASK_FAMILY:
                self._handle_family(phone, sess, reply_id, text)
            elif sess.step == STEP_ASK_VARIANT:
                self._handle_variant(phone, sess, reply_id, text)
            elif sess.step == STEP_ASK_QTY:
                self._handle_qty(phone, sess, reply_id, text)
            elif sess.step == STEP_ASK_MORE:
                self._handle_more(phone, sess, reply_id, text)
            elif sess.step == STEP_ASK_NAME:
                self._handle_name(phone, sess, reply_id, text)
            else:
                self._send_school_list(phone, sess)
        except Exception:  # nunca dejamos al cliente sin respuesta
            logger.exception("Error procesando mensaje de WhatsApp")
            self.client.send_text(
                phone,
                "Ups, tuve un problema. Escribe *menu* para empezar de nuevo.",
            )

    # ── Paso 1: escuela ─────────────────────────────────────────────────────

    def _send_school_list(self, phone: str, sess: Session_, filtro: str | None = None) -> None:
        escuelas = _buscar_escuelas(self.db, filtro)
        sess.step = STEP_ASK_SCHOOL
        if not escuelas:
            self.client.send_text(
                phone,
                "No encontré escuelas con ese nombre. Escribe parte del nombre de tu escuela.",
            )
            return
        hay_mas = len(escuelas) > MAX_LIST_ROWS
        rows = [(f"school:{e.id}", e.nombre, None) for e in escuelas[:MAX_LIST_ROWS]]
        body = "👕 *Cotizador de uniformes*\n\nSelecciona tu escuela:"
        if hay_mas:
            body += "\n\n(Hay más escuelas; si no aparece la tuya, escribe su nombre.)"
        self.client.send_list(
            phone, body=body, button_label="Ver escuelas", rows=rows,
            header="Paso 1 de 3", section_title="Escuelas",
        )

    def _handle_school(self, phone: str, sess: Session_, reply_id: str, text: str) -> None:
        if reply_id.startswith("school:"):
            escuela_id = int(reply_id.split(":", 1)[1])
            escuela = self.db.get(Escuela, escuela_id)
            if escuela is None:
                self._send_school_list(phone, sess)
                return
            sess.escuela_id = escuela.id
            sess.escuela_nombre = escuela.nombre
            self._send_family_list(phone, sess)
            return
        if text:
            self._send_school_list(phone, sess, filtro=text)
            return
        self._send_school_list(phone, sess)

    # ── Paso 2: familia (tipo de prenda) ─────────────────────────────────────

    def _send_family_list(self, phone: str, sess: Session_, filtro: str | None = None) -> None:
        familias = _familias_de_escuela(self.db, sess.escuela_id, filtro)
        sess.families = familias
        sess.step = STEP_ASK_FAMILY
        if not familias:
            self.client.send_text(
                phone,
                f"No tengo prendas registradas para *{sess.escuela_nombre}* con ese filtro.\n"
                "Escribe parte del nombre de la prenda o *menu* para reiniciar.",
            )
            return
        hay_mas = len(familias) > MAX_LIST_ROWS
        rows = []
        for idx, fam in enumerate(familias[:MAX_LIST_ROWS]):
            titulo = f"{fam['tipo_pieza']}: {fam['nombre_base']}" if fam["tipo_pieza"] != "Sin pieza" else fam["nombre_base"]
            desc = f"Desde ${fam['precio_desde']:,.2f}"
            rows.append((f"fam:{idx}", titulo, desc))
        body = f"🏫 *{sess.escuela_nombre}*\n\n¿Qué prenda quieres cotizar?"
        if hay_mas:
            body += "\n\n(Si no aparece, escribe parte del nombre de la prenda.)"
        self.client.send_list(
            phone, body=body, button_label="Ver prendas", rows=rows,
            header="Paso 2 de 3", section_title="Prendas",
        )

    def _handle_family(self, phone: str, sess: Session_, reply_id: str, text: str) -> None:
        if reply_id.startswith("fam:"):
            idx = int(reply_id.split(":", 1)[1])
            if 0 <= idx < len(sess.families):
                self._send_variant_list(phone, sess, sess.families[idx])
                return
        if text:
            self._send_family_list(phone, sess, filtro=text)
            return
        self._send_family_list(phone, sess)

    # ── Paso 3: variante (talla / color) ─────────────────────────────────────

    def _send_variant_list(self, phone: str, sess: Session_, familia: dict) -> None:
        variantes = _variantes_de_familia(self.db, familia["producto_ids"])
        sess.step = STEP_ASK_VARIANT
        if not variantes:
            self.client.send_text(phone, "Esa prenda no tiene tallas disponibles ahora. Elige otra.")
            self._send_family_list(phone, sess)
            return
        rows = []
        for v in variantes[:MAX_LIST_ROWS]:
            titulo = f"{v.talla} · {v.color}".strip(" ·")
            desc = f"${v.precio_venta:,.2f}  ·  SKU {v.sku}"
            rows.append((f"var:{v.id}", titulo, desc))
        body = f"📦 *{familia['nombre_base']}*\n\nElige talla y color:"
        if len(variantes) > MAX_LIST_ROWS:
            body += "\n\n(Mostrando las primeras opciones.)"
        self.client.send_list(
            phone, body=body, button_label="Ver tallas", rows=rows,
            header="Paso 3 de 3", section_title="Tallas y colores",
        )

    def _handle_variant(self, phone: str, sess: Session_, reply_id: str, text: str) -> None:
        if reply_id.startswith("var:"):
            variante_id = int(reply_id.split(":", 1)[1])
            variante = self.db.scalar(
                select(Variante)
                .where(Variante.id == variante_id, Variante.activo.is_(True))
                .options(selectinload(Variante.producto))
            )
            if variante is None:
                self.client.send_text(phone, "Esa opción ya no está disponible. Elige otra.")
                return
            sess.pending_variante_id = variante.id
            nombre_prod = variante.producto.nombre if variante.producto else variante.sku
            sess.pending_label = f"{nombre_prod} · {variante.talla} · {variante.color}".strip(" ·")
            sess.step = STEP_ASK_QTY
            self.client.send_text(
                phone,
                f"Seleccionaste:\n*{sess.pending_label}*\n${variante.precio_venta:,.2f} c/u\n\n"
                "¿Cuántas piezas quieres? (escribe un número)",
            )
            return
        self.client.send_text(phone, "Selecciona una opción de la lista, por favor.")

    # ── Paso 4: cantidad ──────────────────────────────────────────────────────

    def _handle_qty(self, phone: str, sess: Session_, reply_id: str, text: str) -> None:
        try:
            cantidad = int(text)
        except (TypeError, ValueError):
            self.client.send_text(phone, "Escribe la cantidad como un número, por ejemplo: 3")
            return
        if cantidad <= 0:
            self.client.send_text(phone, "La cantidad debe ser mayor a 0. Intenta de nuevo.")
            return
        if cantidad > 999:
            self.client.send_text(phone, "Esa cantidad es muy grande. Para pedidos mayores te paso con una asesora. Escribe otra cantidad.")
            return

        variante = self.db.scalar(
            select(Variante)
            .where(Variante.id == sess.pending_variante_id)
            .options(selectinload(Variante.producto))
        )
        if variante is None:
            self.client.send_text(phone, "Hubo un problema con la prenda. Escribe *menu* para reiniciar.")
            return

        nombre_prod = variante.producto.nombre if variante.producto else variante.sku
        descripcion = f"{nombre_prod} {variante.talla} {variante.color}".strip()

        # Si ya estaba en el carrito (mismo SKU), sumamos cantidades.
        existente = next((i for i in sess.cart if i.variante_id == variante.id), None)
        if existente is not None:
            existente.cantidad += cantidad
        else:
            sess.cart.append(
                CartItem(
                    variante_id=variante.id,
                    sku=variante.sku,
                    descripcion=descripcion,
                    talla=variante.talla,
                    color=variante.color,
                    precio=variante.precio_venta,
                    cantidad=cantidad,
                )
            )
        sess.pending_variante_id = None
        sess.pending_label = None
        self._send_more_prompt(phone, sess)

    # ── Paso 5: agregar mas o finalizar ──────────────────────────────────────

    def _send_more_prompt(self, phone: str, sess: Session_) -> None:
        sess.step = STEP_ASK_MORE
        self.client.send_buttons(
            phone,
            body=self._resumen_carrito(sess) + "\n\n¿Agregar otra prenda o finalizar?",
            buttons=[
                ("more:add", "➕ Otra prenda"),
                ("more:done", "✅ Finalizar"),
                ("more:cancel", "❌ Cancelar"),
            ],
        )

    def _handle_more(self, phone: str, sess: Session_, reply_id: str, text: str) -> None:
        lower = text.lower()
        if reply_id == "more:add" or lower in {"otra", "agregar", "mas", "más"}:
            self._send_family_list(phone, sess)
            return
        if reply_id == "more:done" or lower in {"finalizar", "listo", "terminar"}:
            sess.step = STEP_ASK_NAME
            self.client.send_buttons(
                phone,
                body="¿A nombre de quién hago el presupuesto? Escribe el nombre, o toca *Omitir*.",
                buttons=[("name:skip", "Omitir")],
            )
            return
        self._send_more_prompt(phone, sess)

    # ── Paso 6: nombre y cierre ───────────────────────────────────────────────

    def _handle_name(self, phone: str, sess: Session_, reply_id: str, text: str) -> None:
        if reply_id == "name:skip":
            sess.cliente_nombre = None
        elif text:
            sess.cliente_nombre = text[:150]
        self._finalizar(phone, sess)

    def _finalizar(self, phone: str, sess: Session_) -> None:
        if not sess.cart:
            self.client.send_text(phone, "Tu cotización está vacía. Escribe *menu* para empezar.")
            _reset_session(phone)
            return

        usuario = _resolver_usuario_servicio(self.db)
        if usuario is None:
            self.client.send_text(
                phone,
                "No puedo generar el presupuesto en este momento. Una asesora te atenderá pronto. 🙏",
            )
            logger.error("No hay usuario de servicio activo para crear presupuestos por WhatsApp.")
            return

        total = sum((i.subtotal for i in sess.cart), Decimal("0.00")).quantize(Decimal("0.01"))
        detalles = [
            PresupuestoDetalle(
                variante_id=i.variante_id,
                sku_snapshot=i.sku,
                descripcion_snapshot=i.descripcion[:220],
                talla_snapshot=i.talla,
                color_snapshot=i.color,
                precio_unitario=i.precio,
                cantidad=i.cantidad,
                subtotal_linea=i.subtotal,
            )
            for i in sess.cart
        ]
        observacion = "Generado por chatbot de WhatsApp."
        if sess.escuela_nombre:
            observacion += f" Escuela: {sess.escuela_nombre}."

        presupuesto = Presupuesto(
            usuario_id=usuario.id,
            cliente_id=None,
            cliente_nombre=sess.cliente_nombre,
            cliente_telefono=phone,
            folio=_generar_folio(),
            estado=EstadoPresupuesto.BORRADOR,
            subtotal=total,
            total=total,
            observacion=observacion,
        )
        presupuesto.detalles = detalles
        self.db.add(presupuesto)
        self.db.flush()
        folio = presupuesto.folio
        self.db.commit()

        self.client.send_text(
            phone,
            f"✅ *Presupuesto generado*\nFolio: *{folio}*\n\n"
            f"{self._resumen_carrito(sess)}\n\n"
            "Una asesora lo revisará y te confirmará disponibilidad y entrega. "
            "Menciona tu folio cuando vengas a la tienda. ¡Gracias! 🙌",
        )
        _reset_session(phone)

    # ── Utilidades ────────────────────────────────────────────────────────────

    def _resumen_carrito(self, sess: Session_) -> str:
        if not sess.cart:
            return "Tu cotización está vacía."
        lineas = ["🧾 *Tu cotización:*"]
        total = Decimal("0.00")
        for i in sess.cart:
            total += i.subtotal
            lineas.append(f"• {i.cantidad}× {i.descripcion} — ${i.subtotal:,.2f}")
        lineas.append(f"\n*Total: ${total:,.2f}*")
        return "\n".join(lineas)
