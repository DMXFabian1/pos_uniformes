"""Tallas y colores que faltan, desde la ficha de la prenda (tanda 4, 2026-11-15).

Caso (d) de la propuesta de «Nueva prenda»: agregar una talla o un color a
una prenda que ya existe llevaba de 8 a 12 clics por talla (una lista de 580
prendas, talla y color escritos a mano, el precio en blanco). Aquí:

- `leer_ficha` arma la escalera de tallas de la prenda y, en gris, las que
  tienen sus hermanas (misma pieza y nivel; en ropa general, las demás
  generales de la pieza) y esta no, con su precio sugerido («EXG ＋ $305»).
- `planear_tallas_nuevas` / `aplicar_tallas_nuevas`: una o varias tallas
  nuevas en la MISMA prenda, todo junto o nada, con la bitácora «Desde la
  ficha», la existencia que llega como entrada normal y la receta al día
  (los conjuntos que usan la prenda recalculan esa talla).
- `planear_otro_color` / `aplicar_otro_color`: todas las tallas activas, con
  sus precios, en un color nuevo.

**Dónde vive el color (decisión de esta tanda).** En la caja, 577 de 581
prendas tienen un solo color y el color va en el nombre cuando la prenda lo
lleva («Moño Rojo», «Suéter Botones M Rojo Ignacio Allende»); la ropa normal
de varios colores es UN producto con variantes talla × color (Daniel,
2026-10-13, `nombre_con_color_service`). Por eso:

- si el nombre de la prenda lleva su color, el color nuevo es **otra prenda**
  (otro `Producto`, con el color cambiado en el nombre), dada de alta con el
  motor (`alta_prenda_service`: liga al uniforme y receta incluidas);
- si no lo lleva, el color nuevo son **tallas nuevas de la misma prenda**
  (el nombre visible ya dice el color cuando hay más de uno).

Precio: nunca se sugiere bajar. El de una talla nueva es el que más se
repite en sus hermanas, pero nunca menos que el de la talla más chica que la
prenda ya tiene (`piso`).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    ConjuntoComponente,
    Escuela,
    Marca,
    NivelEducativo,
    Producto,
    TipoPieza,
    UniformePieza,
    Usuario,
    Variante,
)
from pos_uniformes.services import alta_prenda_service as alta
from pos_uniformes.services import catalogo_valores_service as valores
from pos_uniformes.services import conjunto_service, hermanos_service, uniforme_service
from pos_uniformes.services import precio_sugerido_service as precios
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.services.inventario_service import InventarioService
from pos_uniformes.services.talla_orden_service import clave_talla

ORIGEN_FICHA = "Desde la ficha"
ORIGEN_TALLA = f"{ORIGEN_FICHA} · talla nueva"
ORIGEN_COLOR = f"{ORIGEN_FICHA} · otro color"
ORIGEN_COMO_TALLA_ANTERIOR = "no baja de la talla anterior"

MODO_PRENDA = "prenda"  # el color nuevo es otra prenda (el nombre lleva el color)
MODO_TALLAS = "tallas"  # el color nuevo son tallas de la misma prenda

SIN_COLOR = alta.SIN_COLOR

#: Infantil < Juvenil < Adulto (en `talla_orden_service` caen en orden alfabético).
_ORDEN_TEMPORADA = {"infantil": 0, "juvenil": 1, "adulto": 2}


def clave(talla: object) -> tuple:
    """`clave_talla` con Infantil, Juvenil y Adulto en su orden."""
    n = valores.normalizar(talla)
    if n in _ORDEN_TEMPORADA:
        return (1, 60 + _ORDEN_TEMPORADA[n], n)
    return clave_talla(talla)


def _dinero(valor: object) -> Decimal | None:
    return precios.dinero(valor)


def _pesos(valor: Decimal | None) -> str:
    return "" if valor is None else f"${valor:,.0f}"


# ── La ficha ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TallaDeLaPrenda:
    talla: str
    precio: Decimal
    colores: tuple[str, ...] = ()
    variante_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class TallaQueFalta:
    """Una talla que tienen las hermanas y esta prenda no (el chip gris)."""

    talla: str
    precio: Decimal | None
    origen: str
    tienen: int = 0
    total: int = 0

    @property
    def texto_chip(self) -> str:
        """«EXG ＋ $305» (sin precio: «EXG ＋»)."""
        return f"{self.talla} ＋ {_pesos(self.precio)}".rstrip()

    def texto_cobertura(self, tipo_pieza: str | None = None) -> str:
        """«la tienen 3 de las 14 prendas de Pants Suelto»."""
        if not self.total:
            return ""
        de = f"de {self.total} prenda" if self.total == 1 else f"de las {self.total} prendas"
        pieza = f" de {tipo_pieza}" if tipo_pieza else ""
        return f"la tienen {self.tienen} {de}{pieza}"


@dataclass(frozen=True)
class FichaPrenda:
    producto_id: int
    nombre: str
    nombre_sin_escuela: str
    escuela: str | None
    escuela_id: int | None
    nivel: str | None
    tipo_pieza: str | None
    marca: str
    colores: tuple[str, ...]
    tallas: tuple[TallaDeLaPrenda, ...]
    faltan: tuple[TallaQueFalta, ...] = ()
    #: La lista oficial menos las que tiene y las que faltan («＋ Otra talla…»).
    otras_tallas: tuple[str, ...] = ()
    hermanas: int = 0
    es_conjunto: bool = False
    activa: bool = True

    @property
    def color_unico(self) -> str | None:
        return self.colores[0] if len(self.colores) == 1 else None

    @property
    def texto_hermanas(self) -> str:
        """La nota bajo la escalera, solo si hay tallas en gris."""
        if not self.faltan:
            return ""
        pieza = self.tipo_pieza or "esta pieza"
        if self.escuela_id is None:
            de = f"las otras {pieza} generales"
        else:
            nivel = f" de {self.nivel.lower()}" if self.nivel else ""
            de = f"las {pieza} de otras escuelas{nivel}"
        return f"En gris: las tallas que tienen {de} y esta no. Toca una para agregarla."


def _hermanas(session: Session, producto: Producto) -> tuple[int, tuple[hermanos_service.TallaEnHermanas, ...]]:
    """Cuántas hermanas y qué tallas tienen (con cuántas la tienen).

    Hermanas: misma pieza y nivel en otras escuelas; para una prenda general,
    las demás generales (sin escuela ni nivel) de la misma pieza."""
    if producto.tipo_pieza_id is None:
        return 0, ()
    filas = hermanos_service._filas_hermanas(session, int(producto.tipo_pieza_id), producto.nivel_educativo_id)
    if producto.escuela_id is None:
        filas = [f for f in filas if f.escuela_id is None and f.nivel is None and int(f.id) != int(producto.id)]
    else:
        filas = [f for f in filas if f.escuela_id != producto.escuela_id]
    agrupadas = hermanos_service._agrupar(filas)
    return len(agrupadas), hermanos_service._tallas_en_hermanas(agrupadas)


def _propias(session: Session, producto_id: int) -> list[Variante]:
    return list(
        session.scalars(
            select(Variante).where(Variante.producto_id == int(producto_id)).order_by(Variante.id)
        ).all()
    )


def _tallas_activas(variantes: Iterable[Variante]) -> list[TallaDeLaPrenda]:
    por_talla: dict[str, dict] = {}
    for v in variantes:
        if not v.activo:
            continue
        talla = valores.limpiar(v.talla)
        d = por_talla.setdefault(talla, {"precio": Decimal("0"), "colores": [], "ids": []})
        d["precio"] = max(d["precio"], _dinero(v.precio_venta) or Decimal("0"))
        color = valores.limpiar(v.color) or SIN_COLOR
        if color not in d["colores"]:
            d["colores"].append(color)
        d["ids"].append(int(v.id))
    return [
        TallaDeLaPrenda(t, d["precio"], tuple(d["colores"]), tuple(d["ids"]))
        for t, d in sorted(por_talla.items(), key=lambda td: clave(td[0]))
    ]


def piso_de(talla: str, propias: Mapping[str, Decimal]) -> tuple[str, Decimal] | None:
    """Puro: la talla más cara de las que la prenda ya tiene y son más chicas
    que `talla` (una talla nueva nunca queda más barata que ella)."""
    k = clave(talla)
    chicas = [(t, p) for t, p in propias.items() if p is not None and clave(t) < k]
    if not chicas:
        return None
    return max(chicas, key=lambda tp: (tp[1], clave(tp[0])))


def precio_para(talla: str, moda: Decimal | None, propias: Mapping[str, Decimal]) -> tuple[Decimal | None, str]:
    """Puro: el precio sugerido para una talla nueva y de dónde sale.

    El que más se repite en sus hermanas; si queda debajo de una talla más
    chica de la misma prenda, el de esa talla (nunca se sugiere bajar). Sin
    hermanas, el de la talla anterior."""
    piso = piso_de(talla, propias)
    if moda is not None and (piso is None or moda >= piso[1]):
        return moda, precios.ORIGEN_COMO_LAS_DEMAS
    if piso is not None:
        return piso[1], ORIGEN_COMO_TALLA_ANTERIOR
    return None, precios.ORIGEN_FALTA


def _conteos(session: Session, producto: Producto) -> dict[str, Counter]:
    if producto.tipo_pieza_id is None:
        return {}
    return precios.precios_de_la_base(
        session, int(producto.tipo_pieza_id), producto.nivel_educativo_id,
        excluir_escuela_id=producto.escuela_id,
    )


def leer_ficha(session: Session, producto_id: int) -> FichaPrenda | None:
    """La escalera de la prenda con las tallas que le faltan. Solo lee (5 consultas)."""
    producto = session.get(Producto, int(producto_id))
    if producto is None:
        return None
    variantes = _propias(session, producto.id)
    tallas = _tallas_activas(variantes)
    tiene = {valores.normalizar(valores.forma_oficial_talla(v.talla)) for v in variantes}
    propias = {t.talla: t.precio for t in tallas}
    total, en_hermanas = _hermanas(session, producto)
    conteos = _conteos(session, producto) if en_hermanas else {}
    faltan = []
    for h in en_hermanas:
        if valores.normalizar(h.talla) in tiene:
            continue
        contador = conteos.get(h.talla)
        precio, origen = precio_para(h.talla, precios.moda(contador) if contador else None, propias)
        faltan.append(TallaQueFalta(h.talla, precio, origen, h.prendas, h.total))
    faltan.sort(key=lambda t: clave(t.talla))
    ocupadas = tiene | {valores.normalizar(t.talla) for t in faltan}
    otras = tuple(t for t in valores.TALLAS_SUGERIDAS if valores.normalizar(t) not in ocupadas)
    colores = []
    for t in tallas:
        for c in t.colores:
            if c not in colores:
                colores.append(c)
    escuela = producto.escuela.nombre if producto.escuela is not None else None
    return FichaPrenda(
        producto_id=int(producto.id),
        nombre=str(producto.nombre),
        nombre_sin_escuela=CatalogService.nombre_sin_escuela(producto.nombre_base or producto.nombre, escuela),
        escuela=escuela,
        escuela_id=int(producto.escuela_id) if producto.escuela_id is not None else None,
        nivel=producto.nivel_educativo.nombre if producto.nivel_educativo is not None else None,
        tipo_pieza=producto.tipo_pieza.nombre if producto.tipo_pieza is not None else None,
        marca=producto.marca.nombre if producto.marca is not None else "",
        colores=tuple(colores),
        tallas=tuple(tallas),
        faltan=tuple(faltan),
        otras_tallas=otras,
        hermanas=total,
        es_conjunto=conjunto_service.es_conjunto(producto),
        activa=bool(producto.activo),
    )


# ── Tallas nuevas en la misma prenda ───────────────────────────────────────

@dataclass
class PlanTallasNuevas:
    producto_id: int
    nombre: str
    escuela: str | None
    tipo_pieza: str | None
    colores: tuple[str, ...]
    tallas: list[alta.TallaPlan] = field(default_factory=list)
    origen: str = ORIGEN_TALLA
    confirmados: tuple[str, ...] = ()
    #: Las que la prenda ya tiene, con su precio (para el piso).
    propias: dict[str, Decimal] = field(default_factory=dict)
    avisos_fijos: list[str] = field(default_factory=list)
    errores_fijos: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)
    skus: list[str] = field(default_factory=list)

    @property
    def todos_los_errores(self) -> list[str]:
        return list(self.errores) + [f"Talla {t.talla}: {t.error[:1].lower()}{t.error[1:]}" for t in self.tallas if t.error]

    @property
    def todos_los_avisos(self) -> list[str]:
        return list(self.avisos) + [f"Talla {t.talla}: {t.aviso[:1].lower()}{t.aviso[1:]}" for t in self.tallas if t.aviso]

    @property
    def puede_aplicar(self) -> bool:
        return not self.todos_los_errores

    @property
    def cuantas(self) -> int:
        """Tallas que se crean (una por talla y color)."""
        return len(self.tallas) * max(1, len(self.colores))

    @property
    def texto_tallas(self) -> str:
        nombres = [t.talla for t in self.tallas]
        if len(nombres) == 1:
            return f"la talla {nombres[0]}"
        return "las tallas " + ", ".join(nombres[:-1]) + f" y {nombres[-1]}"

    @property
    def texto_colores(self) -> str:
        reales = [c for c in self.colores if c != SIN_COLOR]
        if len(self.colores) <= 1 or not reales:
            return ""
        return " en " + (", ".join(reales[:-1]) + f" y {reales[-1]}" if len(reales) > 1 else reales[0])

    @property
    def resumen(self) -> str:
        """«Se crea la talla EXG de Pants Suelto Benito Juárez, a $305.»"""
        if not self.tallas:
            return ""
        verbo = "Se crea" if len(self.tallas) == 1 else "Se crean"
        texto = f"{verbo} {self.texto_tallas}{self.texto_colores} de {self.nombre}"
        con_precio = [t.precio for t in self.tallas if t.precio is not None]
        if con_precio:
            lo, hi = min(con_precio), max(con_precio)
            texto += f", a {_pesos(lo)}" if lo == hi else f", de {_pesos(lo)} a {_pesos(hi)}"
        return texto + "."


def _talla_plan(talla: str, precio: Decimal | None, origen: str, llegan: int = 0) -> alta.TallaPlan:
    return alta.TallaPlan(talla=talla, precio=precio, origen_precio=origen, llegan=int(llegan or 0))


def planear_tallas_nuevas(
    session: Session,
    producto_id: int,
    tallas: Mapping[str, object] | Sequence[str],
    *,
    llegan: Mapping[str, int] | None = None,
    colores: Sequence[str] | None = None,
    confirmados: Iterable[str] = (),
    origen: str = ORIGEN_TALLA,
) -> PlanTallasNuevas:
    """Una o varias tallas nuevas para la prenda. `tallas` es una lista (precio
    sugerido) o {talla: precio} (None = el sugerido). Se crean en cada color
    que la prenda tiene (o en `colores`). No escribe nada."""
    producto = session.get(Producto, int(producto_id))
    if producto is None:
        raise ValueError("Esa prenda ya no existe.")
    variantes = _propias(session, producto.id)
    activas = _tallas_activas(variantes)
    propias = {t.talla: t.precio for t in activas}
    colores_prenda = []
    for t in activas:
        for c in t.colores:
            if c not in colores_prenda:
                colores_prenda.append(c)
    a_mano = dict(tallas) if isinstance(tallas, Mapping) else {t: None for t in tallas}
    llegan = {valores.forma_oficial_talla(k): int(v or 0) for k, v in (llegan or {}).items()}
    conteos = _conteos(session, producto)
    lista = []
    for cruda, precio in a_mano.items():
        talla = valores.forma_oficial_talla(cruda)
        contador = conteos.get(talla)
        sugerido, origen_precio = precio_para(talla, precios.moda(contador) if contador else None, propias)
        escrito = _dinero(precio)
        if escrito is not None:
            sugerido, origen_precio = escrito, precios.ORIGEN_A_MANO
        lista.append(_talla_plan(talla, sugerido, origen_precio, llegan.get(talla, 0)))
    lista.sort(key=lambda t: clave(t.talla))
    plan = PlanTallasNuevas(
        producto_id=int(producto.id),
        nombre=str(producto.nombre),
        escuela=producto.escuela.nombre if producto.escuela is not None else None,
        tipo_pieza=producto.tipo_pieza.nombre if producto.tipo_pieza is not None else None,
        colores=tuple(valores.limpiar(c) or SIN_COLOR for c in (colores or colores_prenda or [SIN_COLOR])),
        tallas=lista,
        origen=origen,
        confirmados=tuple(confirmados),
        propias=propias,
    )
    if not producto.activo:
        plan.errores_fijos.append("La prenda está desactivada: actívala antes de agregarle tallas.")
    return completar_tallas(session, plan)


def completar_tallas(session: Session, plan: PlanTallasNuevas, *, saltar_skus: int = 0) -> PlanTallasNuevas:
    """Revisa el plan (tallas repetidas o que ya existen, precio, avisos) y
    pone los SKU previstos. Se puede volver a llamar después de editarlo."""
    plan.avisos, plan.errores = list(plan.avisos_fijos), list(plan.errores_fijos)
    producto = session.get(Producto, plan.producto_id)
    existentes = {
        (valores.normalizar(v.talla), valores.normalizar(v.color or SIN_COLOR)): bool(v.activo)
        for v in _propias(session, plan.producto_id)
    }
    usos = valores.contar_usos(session, valores.CAMPO_TALLA)
    conteos = _conteos(session, producto) if producto is not None else {}
    vistas: set[str] = set()
    if not plan.tallas:
        plan.errores.append("Elige al menos una talla.")
    for t in plan.tallas:
        t.talla = valores.forma_oficial_talla(t.talla)
        clave_t = valores.normalizar(t.talla)
        t.aviso, t.error = "", ""
        if not clave_t:
            plan.errores.append("Hay una talla vacía.")
            continue
        if clave_t in vistas:
            plan.errores.append(f"La talla «{t.talla}» está dos veces.")
        vistas.add(clave_t)
        for color in plan.colores:
            ya = existentes.get((clave_t, valores.normalizar(color)))
            if ya is True:
                t.error = "Ya la tiene."
            elif ya is False:
                t.error = "Ya existe pero está desactivada: actívala desde la lista."
        rev = valores.revisar_valor(valores.CAMPO_TALLA, t.talla, usos)
        if not (t.talla in usos or rev.estado == valores.ESTADO_OK or alta._confirmado(plan, t.talla)):
            plan.errores.append(f"La talla «{t.talla}» no existe todavía. Elige una de la lista o confirma que es nueva.")
        t.precio = _dinero(t.precio)
        contador = conteos.get(t.talla)
        t.moda = precios.moda(contador) if contador else None
        t.prendas_con_moda = int(contador.get(t.moda, 0)) if contador and t.moda is not None else 0
        t.sugerencia_5_9 = precios._sugerencia(t.precio, t.moda)
        if t.llegan < 0:
            t.error = t.error or "Lo que llega no puede ser negativo."
        if t.error:
            continue
        if t.precio is None:
            t.error = "Falta el precio."
        elif t.precio <= 0:
            t.error = "El precio no puede quedar en $0."
        else:
            piso = piso_de(t.talla, plan.propias)
            if piso is not None and t.precio < piso[1]:
                t.aviso = f"Queda más barata que la talla {piso[0]} ({_pesos(piso[1])})."
            elif t.moda is not None and t.precio < t.moda:
                t.aviso = f"Queda más bajo que en las demás ({_pesos(t.moda)})."
    if producto is not None and conjunto_service.es_conjunto(producto) and any(t.llegan for t in plan.tallas):
        plan.errores.append(f"{plan.tipo_pieza} no tiene existencia propia: se arma de sus piezas.")
    n = plan.cuantas
    plan.skus = CatalogService.preview_next_skus(session, saltar_skus + n)[saltar_skus:] if n else []
    for i, t in enumerate(plan.tallas):
        t.sku = plan.skus[i * max(1, len(plan.colores))] if plan.skus else ""
    return plan


def _ligar_si_falta(session: Session, producto: Producto) -> str | None:
    """Una prenda de escuela que no está en su uniforme queda ligada (como en el motor)."""
    if producto.escuela_id is None:
        return None
    ya = session.scalar(select(UniformePieza.id).where(UniformePieza.producto_id == producto.id))
    if ya is not None:
        return None
    uni = uniforme_service.uniforme_de(session, int(producto.escuela_id), crear=True)
    return uniforme_service.agregar_pieza(session, uni.id, producto.id).grupo


def _recetas_al_dia(session: Session, producto: Producto, tallas: set[str]) -> tuple[list[str], list[str]]:
    """Los conjuntos que usan la prenda (y ella, si es conjunto) recalculan esas
    tallas. Avisa si un conjunto no puede armar una talla nueva."""
    hechas: list[str] = []
    avisos: list[str] = []
    norm = {conjunto_service._norm_talla(t) for t in tallas}
    ids = set(
        session.scalars(
            select(ConjuntoComponente.conjunto_id).where(ConjuntoComponente.componente_id == producto.id)
        ).all()
    )
    if conjunto_service.receta_de(session, producto.id):
        ids.add(int(producto.id))
    for cid in sorted(ids):
        conjunto_service.sincronizar_conjunto(session, cid, tallas=norm, creado_por="alta")
        conjunto = session.get(Producto, cid)
        sin_pieza = [t for t in conjunto_service.tallas_sin_pieza(session, cid)
                     if conjunto_service._norm_talla(t) in norm]
        if sin_pieza:
            avisos.append(
                f"La receta de {conjunto.nombre} no arma la talla {', '.join(sin_pieza)}: "
                "le falta esa talla a alguna de sus piezas."
            )
        else:
            hechas.append(conjunto.nombre)
    return hechas, avisos


def _errores(plan) -> str:
    return "\n".join(plan.todos_los_errores)


def aplicar_tallas_nuevas(
    session: Session, plan: PlanTallasNuevas, usuario: Usuario, *, commit: bool = False
) -> alta.ResultadoAlta:
    """Crea las tallas del plan, todas o ninguna (savepoint)."""
    errores = _errores(plan)
    if errores:
        raise alta.AltaNoValida(errores)
    CatalogService._validar_admin(usuario)
    with session.begin_nested():
        producto = session.get(Producto, plan.producto_id)
        if producto is None:
            raise ValueError("Esa prenda ya no existe.")
        creadas = []
        for t in plan.tallas:
            for color in plan.colores:
                v = CatalogService.crear_variante(
                    session, usuario, producto, None, t.talla, color, t.precio,
                    costo_referencia=t.costo, stock_inicial=0, observacion=plan.origen,
                )
                creadas.append((t, v))
        grupo = _ligar_si_falta(session, producto)
        recetas, avisos = _recetas_al_dia(session, producto, {t.talla for t in plan.tallas})
        for t, v in creadas:
            if t.llegan:
                InventarioService.registrar_ajuste_manual(
                    session, v, int(t.llegan), usuario,
                    referencia=alta.REFERENCIA_ENTRADA, observacion=f"Llegaron al agregar la talla · {plan.origen}",
                )
        session.flush()
        resultado = alta.ResultadoAlta(productos=(alta.ProductoCreado(
            producto_id=int(producto.id),
            nombre=str(producto.nombre),
            escuela=plan.escuela,
            tallas=tuple(
                alta.TallaCreada(int(v.id), str(v.sku), str(v.talla), str(v.color), Decimal(v.precio_venta),
                                 int(t.llegan))
                for t, v in creadas
            ),
            uniforme=grupo,
            recetas=tuple(recetas),
            avisos=tuple(avisos),
            bitacora=plan.origen,
        ),))
    if commit:
        session.commit()
    return resultado


# ── Otro color ─────────────────────────────────────────────────────────────

@dataclass
class PlanOtroColor:
    producto_id: int
    nombre_antes: str
    color_antes: str
    color: str
    modo: str
    plan_prenda: alta.PlanPrenda | None = None
    plan_tallas: PlanTallasNuevas | None = None
    avisos_extra: list[str] = field(default_factory=list)
    errores_extra: list[str] = field(default_factory=list)

    @property
    def _plan(self):
        return self.plan_prenda if self.modo == MODO_PRENDA else self.plan_tallas

    @property
    def tallas(self) -> list[alta.TallaPlan]:
        return list(self._plan.tallas) if self._plan is not None else []

    @property
    def todos_los_errores(self) -> list[str]:
        return list(self.errores_extra) + (self._plan.todos_los_errores if self._plan is not None else [])

    @property
    def todos_los_avisos(self) -> list[str]:
        return list(self.avisos_extra) + (self._plan.todos_los_avisos if self._plan is not None else [])

    @property
    def puede_aplicar(self) -> bool:
        return not self.todos_los_errores

    @property
    def nombre(self) -> str:
        """El nombre de la prenda nueva, o el de la misma prenda."""
        if self.modo == MODO_PRENDA and self.plan_prenda is not None:
            return self.plan_prenda.nombre
        return self.nombre_antes

    @property
    def texto_rango(self) -> str:
        con_precio = [t.precio for t in self.tallas if t.precio is not None]
        n = len(self.tallas)
        tallas = "1 talla" if n == 1 else f"{n} tallas"
        if not con_precio:
            return tallas
        lo, hi = min(con_precio), max(con_precio)
        return f"{tallas} · " + (_pesos(lo) if lo == hi else f"{_pesos(lo)} a {_pesos(hi)}")

    @property
    def resumen(self) -> str:
        """La frase de «Así queda» / confirmar."""
        if not self.tallas:
            return ""
        n = len(self.tallas)
        tallas = "1 talla" if n == 1 else f"{n} tallas"
        con_precio = [t.precio for t in self.tallas if t.precio is not None]
        cuanto = ""
        if con_precio:
            lo, hi = min(con_precio), max(con_precio)
            cuanto = f", a {_pesos(lo)}" if lo == hi else f", de {_pesos(lo)} a {_pesos(hi)}"
        if self.modo == MODO_PRENDA:
            return f"Se crea «{self.nombre}» con {tallas}{cuanto}. «{self.nombre_antes}» se queda igual."
        verbo = "Se agrega" if n == 1 else "Se agregan"
        return f"{verbo} {tallas} en {self.color} a «{self.nombre_antes}»{cuanto}."


def color_en_nombre(nombre: str, color: str | None) -> bool:
    """Puro: ¿el nombre lleva el color? («Moño Rojo», «Blanca» por «Blanco»)."""
    if not color or valores.normalizar(color) == valores.normalizar(SIN_COLOR):
        return False
    return alta.cambiar_color_en_nombre(nombre, color, "\x00") != nombre


def planear_otro_color(
    session: Session, producto_id: int, color: str, *, confirmados: Iterable[str] = ()
) -> PlanOtroColor:
    """Todas las tallas activas de la prenda, con sus precios, en `color`."""
    producto = session.get(Producto, int(producto_id))
    if producto is None:
        raise ValueError("Esa prenda ya no existe.")
    variantes = _propias(session, producto.id)
    activas = _tallas_activas(variantes)
    colores = Counter(valores.limpiar(v.color) or SIN_COLOR for v in variantes if v.activo)
    color_antes = colores.most_common(1)[0][0] if colores else SIN_COLOR
    nuevo = valores.forma_oficial_color(color) or ""
    escuela = producto.escuela.nombre if producto.escuela is not None else None
    base = CatalogService.nombre_sin_escuela(producto.nombre_base or producto.nombre, escuela)
    modo = MODO_PRENDA if color_en_nombre(base, color_antes) else MODO_TALLAS
    plan = PlanOtroColor(int(producto.id), str(producto.nombre), color_antes, nuevo, modo)
    confirmados = tuple(confirmados)
    if not nuevo:
        plan.errores_extra.append("Elige el color nuevo.")
    elif valores.normalizar(nuevo) in {valores.normalizar(c) for c in colores}:
        plan.errores_extra.append(f"La prenda ya está en {nuevo}.")
    if not activas:
        plan.errores_extra.append("La prenda no tiene tallas activas que copiar.")
    if nuevo:
        usos = valores.contar_usos(session, valores.CAMPO_COLOR)
        rev = valores.revisar_valor(valores.CAMPO_COLOR, nuevo, usos)
        if not (nuevo in usos or rev.estado == valores.ESTADO_OK
                or valores.normalizar(nuevo) in {valores.normalizar(c) for c in confirmados}):
            plan.errores_extra.append(rev.texto_pregunta())
    if modo == MODO_PRENDA:
        liga = session.execute(
            select(UniformePieza.grupo, UniformePieza.orden, UniformePieza.obligatoria)
            .where(UniformePieza.producto_id == producto.id, UniformePieza.activo.is_(True))
            .order_by(UniformePieza.id)
        ).first()
        spec = {
            "producto": {
                "nombre": alta.cambiar_color_en_nombre(base, color_antes, nuevo) if nuevo else base,
                "categoria": producto.categoria.nombre if producto.categoria is not None else "",
                "marca": producto.marca.nombre if producto.marca is not None else "",
                "escuela": escuela,
                "tipo_prenda": producto.tipo_prenda.nombre if producto.tipo_prenda is not None else None,
                "tipo_pieza": producto.tipo_pieza.nombre if producto.tipo_pieza is not None else None,
                "nivel_educativo": producto.nivel_educativo.nombre if producto.nivel_educativo is not None else None,
                "atributo": producto.atributo.nombre if producto.atributo is not None else None,
                "genero": producto.genero, "escudo": producto.escudo, "ubicacion": producto.ubicacion,
                "descripcion": producto.descripcion,
            },
            "color": nuevo or SIN_COLOR,
            "variantes": [{"talla": t.talla, "precio": t.precio, "origen_precio": "como la prenda"} for t in activas],
            "uniforme": ({"grupo": liga[0], "obligatoria": bool(liga[2])} if liga else
                         ({} if escuela else False)),
            "modelo": producto.nombre,
            "modelo_id": int(producto.id),
            "origen": ORIGEN_COLOR,
            "confirmados": confirmados,
        }
        plan.plan_prenda = alta.planear(session, spec)
        # Lo que avisa el motor de una escuela que «ya tiene» la pieza es
        # justo la prenda de la que se copia: no hace falta decirlo.
        plan.plan_prenda.avisos = [a for a in plan.plan_prenda.avisos if not a.startswith("La escuela ya tiene")]
    else:
        plan.plan_tallas = planear_tallas_nuevas(
            session, producto.id, {t.talla: t.precio for t in activas},
            colores=[nuevo or SIN_COLOR], confirmados=confirmados, origen=ORIGEN_COLOR,
        )
        for t in plan.plan_tallas.tallas:
            t.origen_precio = "como la prenda"
        if color_antes == SIN_COLOR:
            plan.avisos_extra.append(
                "Hoy sus tallas dicen «Sin color». Si en realidad son de un color, mejor corrígelo con "
                "«Corregir prenda»."
            )
    return plan


def aplicar_otro_color(
    session: Session, plan: PlanOtroColor, usuario: Usuario, *, commit: bool = False
) -> alta.ResultadoAlta:
    if not plan.puede_aplicar:
        raise alta.AltaNoValida("\n".join(plan.todos_los_errores))
    if plan.modo == MODO_PRENDA:
        return alta.aplicar(session, plan.plan_prenda, usuario, ORIGEN_COLOR, commit=commit)
    return aplicar_tallas_nuevas(session, plan.plan_tallas, usuario, commit=commit)


__all__ = [
    "FichaPrenda",
    "MODO_PRENDA",
    "MODO_TALLAS",
    "ORIGEN_COLOR",
    "ORIGEN_FICHA",
    "ORIGEN_TALLA",
    "PlanOtroColor",
    "PlanTallasNuevas",
    "TallaDeLaPrenda",
    "TallaQueFalta",
    "aplicar_otro_color",
    "aplicar_tallas_nuevas",
    "clave",
    "color_en_nombre",
    "completar_tallas",
    "leer_ficha",
    "piso_de",
    "planear_otro_color",
    "planear_tallas_nuevas",
    "precio_para",
]
