"""«✏️ Corregir prenda»: nombre y color de toda la prenda a la vez (tanda 4, 2026-11-15).

Caso (e) de la propuesta de «Nueva prenda»: corregir el nombre o el color
abría el asistente completo (que además volvía a pegar la escuela) y el color
se cambiaba talla por talla, sin tocar el nombre y sin avisar de las
etiquetas. Aquí, en una ventanita:

- el nombre SIN la escuela (la escuela se pone sola con `armar_nombre`, igual
  que en el alta: lo que se ve es lo que se guarda);
- el color de toda la prenda (si tiene uno solo), con «¿Quisiste decir…?»;
- opcional, el precio de cada talla. Si alguno baja, la pantalla enseña el
  aviso rojo de Inventario (`inventario_precio_lote_service`) y aquí no se
  aplica sin `permitir_bajar=True`.

Se conserva todo lo demás: SKU, códigos, costo, mínimo y existencia. La
bitácora (`cambio_catalogo`) anota cada campo con «Corregir prenda · desde
la ficha». Solo ADMIN.

Al guardar se vuelven a leer los precios de la base (2026-11-15, revisión):
una talla cuyo precio no se tocó guarda el que tiene la base en ese
momento (si otra caja lo subió mientras la ventanita estaba abierta, no se
regresa); si se tocó y la base ya no tiene el precio que se vio, se detiene
con «Los precios cambiaron…». Al cambiar el color también se recolorean las
tallas desactivadas de ese color (sin tocar su precio), para que al
reactivarlas no vendan el color viejo con el nombre nuevo.

Las etiquetas impresas no se pueden saber todas (las que imprime la misma
caja no dejan rastro); se cuentan las que se mandaron al satélite
(`trabajo` ETIQUETA con el SKU) y siempre se avisa en genérico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Mapping

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Producto, TipoTrabajo, Trabajo, Usuario, Variante
from pos_uniformes.services import catalogo_valores_service as valores
from pos_uniformes.services import precio_sugerido_service as precios
from pos_uniformes.services.alta_prenda_service import SIN_COLOR, cambiar_color_en_nombre
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.services.inventario_precio_lote_service import BajaDePrecio, precios_que_bajan

ORIGEN_CORREGIR = "Corregir prenda · desde la ficha"
AVISO_ETIQUETAS = "Las etiquetas impresas siguen diciendo lo anterior: vuelve a imprimirlas si hace falta."


class CorreccionNoValida(ValueError):
    """El plan tiene errores: no se guarda nada."""


class HayPreciosQueBajan(ValueError):
    """Algún precio baja y no se confirmó (`permitir_bajar`)."""


PRECIOS_CAMBIARON = "Los precios cambiaron mientras corregías: revisa otra vez."


@dataclass(frozen=True)
class TallaACorregir:
    variante_id: int
    sku: str
    talla: str
    color: str
    precio: Decimal
    precio_nuevo: Decimal


@dataclass
class PlanCorreccion:
    producto_id: int
    escuela: str | None
    marca: str
    nombre_antes: str
    nombre_sin_escuela_antes: str
    nombre_sin_escuela: str
    nombre: str = ""
    colores_antes: tuple[str, ...] = ()
    color: str | None = None
    tallas: list[TallaACorregir] = field(default_factory=list)
    #: Tallas desactivadas del color de antes: se recolorean junto con las activas.
    desactivadas: list[TallaACorregir] = field(default_factory=list)
    confirmados: tuple[str, ...] = ()
    bajas: list[BajaDePrecio] = field(default_factory=list)
    etiquetas_enviadas: int = 0
    avisos: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def color_antes(self) -> str | None:
        return self.colores_antes[0] if len(self.colores_antes) == 1 else None

    @property
    def cambia_nombre(self) -> bool:
        return bool(self.nombre) and self.nombre != self.nombre_antes

    @property
    def cambia_color(self) -> bool:
        return self.color is not None and self.color_antes is not None and self.color != self.color_antes

    @property
    def precios_que_cambian(self) -> list[TallaACorregir]:
        return [t for t in self.tallas if t.precio_nuevo != t.precio]

    @property
    def hay_cambios(self) -> bool:
        return self.cambia_nombre or self.cambia_color or bool(self.precios_que_cambian)

    @property
    def puede_aplicar(self) -> bool:
        return not self.errores and self.hay_cambios

    @property
    def resumen(self) -> str:
        """«Pasa a llamarse … · sus 10 tallas pasan a Azul · 2 precios cambian.»"""
        if not self.hay_cambios:
            return "Sin cambios todavía."
        partes = []
        n = len(self.tallas)
        tallas = "su talla" if n == 1 else f"sus {n} tallas"
        if self.cambia_nombre:
            partes.append(f"Pasa a llamarse «{self.nombre}» (con {tallas}).")
        if self.cambia_color:
            partes.append(f"{tallas[:1].upper()}{tallas[1:]} pasan de {self.color_antes} a {self.color}."
                          if n != 1 else f"Su talla pasa de {self.color_antes} a {self.color}.")
            d = len(self.desactivadas)
            if d:
                partes.append("También su talla desactivada." if d == 1 else f"También sus {d} tallas desactivadas.")
        cambian = len(self.precios_que_cambian)
        if cambian:
            partes.append("Cambia 1 precio." if cambian == 1 else f"Cambian {cambian} precios.")
        partes.append("Los códigos, la existencia y lo demás se quedan igual.")
        return " ".join(partes)

    @property
    def texto_etiquetas(self) -> str:
        """El aviso de las etiquetas, solo si cambia lo que dicen (nombre o color)."""
        if not (self.cambia_nombre or self.cambia_color):
            return ""
        if self.etiquetas_enviadas:
            n = self.etiquetas_enviadas
            return (f"Se han mandado a imprimir {n} {'etiqueta' if n == 1 else 'etiquetas'} de esta prenda. "
                    + AVISO_ETIQUETAS)
        return AVISO_ETIQUETAS


def _variantes(session: Session, producto_id: int) -> list[Variante]:
    return list(session.scalars(
        select(Variante).where(Variante.producto_id == int(producto_id)).order_by(Variante.id)
    ).all())


def etiquetas_enviadas(session: Session, skus: Iterable[str]) -> int:
    """Cuántas etiquetas de esos SKU se mandaron a imprimir al satélite (una consulta)."""
    skus = sorted({s for s in skus if s})
    if not skus:
        return 0
    try:
        return int(session.scalar(
            select(func.count(Trabajo.id)).where(
                Trabajo.tipo == TipoTrabajo.ETIQUETA,
                Trabajo.contenido["sku"].as_string().in_(skus),
            )
        ) or 0)
    except Exception:  # noqa: BLE001 - un dato de cortesía: si la base no deja, se avisa en genérico
        return 0


def planear_correccion(
    session: Session,
    producto_id: int,
    *,
    nombre_sin_escuela: str | None = None,
    color: str | None = None,
    precios_nuevos: Mapping[int, object] | None = None,
    confirmados: Iterable[str] = (),
) -> PlanCorreccion:
    """Lo que cambiaría. No escribe nada; se vuelve a llamar en cada cambio."""
    producto = session.get(Producto, int(producto_id))
    if producto is None:
        raise ValueError("Esa prenda ya no existe.")
    escuela = producto.escuela.nombre if producto.escuela is not None else None
    todas = _variantes(session, producto.id)
    variantes = [v for v in todas if v.activo]
    colores = []
    for v in variantes:
        c = valores.limpiar(v.color) or SIN_COLOR
        if c not in colores:
            colores.append(c)
    base_antes = CatalogService.nombre_sin_escuela(producto.nombre_base or producto.nombre, escuela)
    plan = PlanCorreccion(
        producto_id=int(producto.id),
        escuela=escuela,
        marca=producto.marca.nombre if producto.marca is not None else "",
        nombre_antes=str(producto.nombre),
        nombre_sin_escuela_antes=base_antes,
        nombre_sin_escuela=valores.limpiar(nombre_sin_escuela if nombre_sin_escuela is not None else base_antes),
        colores_antes=tuple(colores),
        confirmados=tuple(confirmados),
    )
    if not plan.nombre_sin_escuela:
        plan.errores.append("Falta el nombre.")
    else:
        plan.nombre = CatalogService.armar_nombre(plan.nombre_sin_escuela, escuela)
        otro = session.scalar(select(Producto.id).where(
            Producto.id != producto.id, Producto.nombre == plan.nombre, Producto.marca_id == producto.marca_id))
        if otro is not None:
            plan.errores.append(f"Ya existe otra prenda que se llama «{plan.nombre}».")

    nuevo = valores.forma_oficial_color(color) if color is not None else None
    if nuevo is not None and plan.color_antes is None and nuevo not in colores:
        plan.errores.append("Esta prenda tiene tallas de varios colores: corrige el color talla por talla.")
        nuevo = None
    if nuevo is not None and nuevo != plan.color_antes:
        if not nuevo:
            plan.errores.append("Elige el color.")
        else:
            usos = valores.contar_usos(session, valores.CAMPO_COLOR)
            rev = valores.revisar_valor(valores.CAMPO_COLOR, nuevo, usos)
            if rev.estado == valores.ESTADO_OK and rev.valor:
                nuevo = rev.valor
            elif not (nuevo in usos or valores.normalizar(nuevo) in {valores.normalizar(c) for c in plan.confirmados}):
                plan.errores.append(rev.texto_pregunta())
    plan.color = nuevo if nuevo is not None else plan.color_antes
    if plan.cambia_color:
        for v in todas:
            if v.activo or (valores.limpiar(v.color) or SIN_COLOR) != plan.color_antes:
                continue
            p = precios.dinero(v.precio_venta) or Decimal("0.00")
            plan.desactivadas.append(TallaACorregir(int(v.id), str(v.sku), str(v.talla), str(v.color), p, p))
        destino = {valores.normalizar(v.talla) for v in todas
                   if valores.normalizar(v.color) == valores.normalizar(plan.color)}
        chocan = [v.talla for v in todas if v.activo or any(d.variante_id == v.id for d in plan.desactivadas)
                  if valores.normalizar(v.talla) in destino]
        if chocan:
            plan.errores.append(f"La talla {chocan[0]} ya existe en {plan.color} (desactivada): "
                                "actívala o corrige talla por talla.")

    nuevos = {int(k): precios.dinero(v) for k, v in (precios_nuevos or {}).items()}
    for v in variantes:
        antes = precios.dinero(v.precio_venta) or Decimal("0.00")
        despues = nuevos.get(int(v.id), antes)
        if int(v.id) in nuevos:
            if despues is None:
                plan.errores.append(f"Talla {v.talla}: falta el precio.")
                despues = antes
            elif despues <= 0:
                plan.errores.append(f"Talla {v.talla}: el precio no puede quedar en $0.")
                despues = antes
        plan.tallas.append(TallaACorregir(int(v.id), str(v.sku), str(v.talla), str(v.color), antes, despues))
    plan.bajas = precios_que_bajan(
        [(t.variante_id, t.precio_nuevo) for t in plan.tallas],
        [{"variante_id": t.variante_id, "sku": t.sku, "talla": t.talla, "precio_venta": t.precio,
          "producto_nombre": plan.nombre or plan.nombre_antes} for t in plan.tallas],
    )
    if plan.cambia_nombre or plan.cambia_color:
        plan.etiquetas_enviadas = etiquetas_enviadas(session, [t.sku for t in plan.tallas])
    return plan


def nombre_con_color_nuevo(nombre_sin_escuela: str, color_antes: str | None, color_nuevo: str | None) -> str:
    """Puro: al cambiar el color, el nombre lo cambia también si lo llevaba."""
    return cambiar_color_en_nombre(nombre_sin_escuela, color_antes, color_nuevo)


@dataclass(frozen=True)
class ResultadoCorreccion:
    producto_id: int
    nombre: str
    tallas_cambiadas: int


def aplicar_correccion(
    session: Session,
    plan: PlanCorreccion,
    usuario: Usuario,
    *,
    permitir_bajar: bool = False,
    commit: bool = False,
) -> ResultadoCorreccion:
    """Cambia nombre, color y precios de la prenda, todo o nada (savepoint)."""
    if plan.errores:
        raise CorreccionNoValida("\n".join(plan.errores))
    if not plan.hay_cambios:
        raise CorreccionNoValida("No hay nada que cambiar.")
    if plan.bajas and not permitir_bajar:
        raise HayPreciosQueBajan(f"{len(plan.bajas)} precio(s) bajan: confírmalo antes.")
    CatalogService._validar_admin(usuario)
    cambiadas = 0
    with session.begin_nested():
        producto = session.get(Producto, plan.producto_id)
        if producto is None:
            raise ValueError("Esa prenda ya no existe.")
        variantes = _variantes(session, producto.id)
        # Los precios se vuelven a leer aquí: el plan es una foto de cuando se
        # abrió o replaneó la ventanita, y otra caja pudo cambiarlos.
        precio_final: dict[int, Decimal] = {}
        por_id = {t.variante_id: t for t in plan.tallas}
        for v in variantes:
            t = por_id.get(int(v.id))
            if t is None:
                continue
            actual = precios.dinero(v.precio_venta) or Decimal("0.00")
            if t.precio_nuevo == t.precio:
                precio_final[t.variante_id] = actual  # no se tocó: se queda el de la base
            elif actual != t.precio:
                raise CorreccionNoValida(PRECIOS_CAMBIARON)
            else:
                precio_final[t.variante_id] = t.precio_nuevo
        if plan.cambia_nombre:
            CatalogService.actualizar_producto(
                session, usuario, producto,
                categoria=producto.categoria, marca=producto.marca, nombre=plan.nombre_sin_escuela,
                descripcion=producto.descripcion, escuela=producto.escuela, tipo_prenda=producto.tipo_prenda,
                tipo_pieza=producto.tipo_pieza, nivel_educativo=producto.nivel_educativo,
                atributo=producto.atributo, genero=producto.genero, escudo=producto.escudo,
                ubicacion=producto.ubicacion, observacion=ORIGEN_CORREGIR,
            )
        apagadas = {d.variante_id for d in plan.desactivadas} if plan.cambia_color else set()
        for v in variantes:
            t = por_id.get(int(v.id))
            if t is None and int(v.id) not in apagadas:
                continue
            antes = precios.dinero(v.precio_venta) or Decimal("0.00")
            precio = precio_final.get(int(v.id), antes)
            color = plan.color if plan.cambia_color else v.color
            if color == v.color and precio == antes:
                continue
            CatalogService.actualizar_variante(
                session, usuario, v, producto, v.sku, v.talla, color, precio,
                costo_referencia=v.costo_referencia, stock_minimo=v.stock_minimo, observacion=ORIGEN_CORREGIR,
            )
            cambiadas += 1
        session.flush()
        resultado = ResultadoCorreccion(int(producto.id), str(producto.nombre), cambiadas)
    if commit:
        session.commit()
    return resultado


__all__ = [
    "AVISO_ETIQUETAS",
    "CorreccionNoValida",
    "HayPreciosQueBajan",
    "ORIGEN_CORREGIR",
    "PRECIOS_CAMBIARON",
    "PlanCorreccion",
    "ResultadoCorreccion",
    "TallaACorregir",
    "aplicar_correccion",
    "etiquetas_enviadas",
    "nombre_con_color_nuevo",
    "planear_correccion",
]
