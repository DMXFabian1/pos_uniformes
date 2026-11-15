"""Limpieza de los valores sucios del catálogo (tanda 5 del alta, 2026-11-15).

Las altas nuevas ya entran con una sola forma (`catalogo_valores_service`);
esto junta lo que ya estaba en la caja con dos escrituras (perfil del
2026-11-13, `alta_datos.md`):

- **Tallas** a su forma oficial según `forma_oficial_talla`: Uni/NT →
  Unitalla, Ch → CH, M → MD, G → GD, XL → EXG… Solo cambia el texto de la
  talla: SKU, precio y existencia se quedan igual.
- **Taxonomías** (tipo de prenda, pieza, atributo, categoría, nivel) que solo
  difieren en acentos, mayúsculas o espacios («Basico» y «Básico»): sus
  prendas pasan a la forma con acento y la otra queda inactiva.
- **Nombres que repiten la escuela** («Pants 3pz Deportivo Estv 154 ESTV
  154», los 2 de ESTV de la tanda 1).

No se tocan (se listan aparte):

- **Choques**: dos tallas de la misma prenda y el mismo color que quedarían
  iguales (por ejemplo «XL» y «EXG» juntas): se arreglan a mano.
- **Colores**: decisión de Daniel (2026-11-13): una sola forma para lo nuevo,
  sin tocar todavía lo que ya existe. Se listan como informativo.
- Escuelas y marcas con dos escrituras, y valores parecidos pero no iguales
  («Deportiva» / «Deportivo»): informativo.

`planear_limpieza` solo lee. `aplicar_limpieza` escribe todo en una sola
transacción (savepoint), con bitácora en `cambio_catalogo` (observación
«LIMPIEZA-VALORES-2026-11 · …»), y es idempotente: la segunda vez el plan sale
vacío. Solo ADMIN.
"""

from __future__ import annotations

import difflib
import re
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    AtributoProducto,
    Categoria,
    Escuela,
    Marca,
    NivelEducativo,
    Producto,
    TipoCambioCatalogo,
    TipoEntidadCatalogo,
    TipoPieza,
    TipoPrenda,
    Usuario,
    Variante,
)
from pos_uniformes.services import catalogo_valores_service as valores
from pos_uniformes.services.catalog_audit_service import CatalogAuditService
from pos_uniformes.services.catalog_service import CatalogService

REFERENCIA = "LIMPIEZA-VALORES-2026-11"
SIN_COLOR = "Sin color"
#: Qué tan parecidos tienen que ser dos valores distintos para listarlos (informativo).
UMBRAL_PARECIDOS = 0.85

# Campo → (modelo, columna de Producto, relación de Producto).
TAXONOMIAS: dict[str, tuple[type, object, str]] = {
    valores.CAMPO_TIPO_PRENDA: (TipoPrenda, Producto.tipo_prenda_id, "tipo_prenda"),
    valores.CAMPO_TIPO_PIEZA: (TipoPieza, Producto.tipo_pieza_id, "tipo_pieza"),
    valores.CAMPO_ATRIBUTO: (AtributoProducto, Producto.atributo_id, "atributo"),
    valores.CAMPO_CATEGORIA: (Categoria, Producto.categoria_id, "categoria"),
    valores.CAMPO_NIVEL: (NivelEducativo, Producto.nivel_educativo_id, "nivel_educativo"),
}
SOLO_INFORMATIVO: dict[str, tuple[type, object]] = {
    valores.CAMPO_ESCUELA: (Escuela, Producto.escuela_id),
    "marca": (Marca, Producto.marca_id),
}


@dataclass
class CambioTalla:
    """Un renglón del plan: «Uni → Unitalla: 66 tallas de 64 prendas»."""

    antes: str
    despues: str
    variantes: list[int] = field(default_factory=list)
    productos: set[int] = field(default_factory=set)

    @property
    def texto(self) -> str:
        return (f"«{self.antes}» → «{self.despues}»: {_n(len(self.variantes), 'talla', 'tallas')} "
                f"de {_n(len(self.productos), 'prenda', 'prendas')}")


@dataclass(frozen=True)
class TallaEnChoque:
    variante_id: int
    sku: str
    talla: str


@dataclass
class Choque:
    """Tallas de una misma prenda y color que quedarían iguales: no se tocan."""

    producto_id: int
    producto: str
    color: str
    talla_final: str
    tallas: list[TallaEnChoque] = field(default_factory=list)

    @property
    def texto(self) -> str:
        lista = ", ".join(f"«{t.talla}» ({t.sku})" for t in self.tallas)
        return f"#{self.producto_id} {self.producto} · {self.color}: {lista} quedarían todas en «{self.talla_final}»"


@dataclass
class FusionTaxonomia:
    campo: str
    de_id: int
    de_nombre: str
    a_id: int
    a_nombre: str
    productos: list[int] = field(default_factory=list)

    @property
    def texto(self) -> str:
        etiqueta = valores.ETIQUETA_CAMPO.get(self.campo, self.campo)
        return (f"{etiqueta}: «{self.de_nombre}» → «{self.a_nombre}» "
                f"({_n(len(self.productos), 'prenda', 'prendas')}; «{self.de_nombre}» queda inactivo)")


@dataclass(frozen=True)
class NombreRepetido:
    producto_id: int
    antes: str
    despues: str
    base: str

    @property
    def texto(self) -> str:
        return f"#{self.producto_id}: «{self.antes}» → «{self.despues}»"


@dataclass
class PlanLimpieza:
    tallas: list[CambioTalla] = field(default_factory=list)
    choques: list[Choque] = field(default_factory=list)
    taxonomias: list[FusionTaxonomia] = field(default_factory=list)
    nombres: list[NombreRepetido] = field(default_factory=list)
    #: variante_id → talla nueva (lo que se escribe).
    variantes: dict[int, str] = field(default_factory=dict)
    #: Informativo: (color, forma oficial, tallas que lo usan).
    colores: list[tuple[str, str, int]] = field(default_factory=list)
    #: Informativo: escuelas y marcas con dos escrituras, y valores parecidos.
    parecidos: list[str] = field(default_factory=list)

    @property
    def hay_cambios(self) -> bool:
        return bool(self.variantes or self.taxonomias or self.nombres)

    def texto(self) -> str:
        renglones: list[str] = []

        def seccion(titulo: str, lineas: list[str], vacio: str) -> None:
            renglones.append("")
            renglones.append(titulo)
            renglones.extend(f"  - {linea}" for linea in lineas) if lineas else renglones.append(f"  ({vacio})")

        productos = set().union(*(c.productos for c in self.tallas)) if self.tallas else set()
        seccion(f"TALLAS A JUNTAR ({_n(len(self.variantes), 'talla', 'tallas')} de "
                f"{_n(len(productos), 'prenda', 'prendas')}):",
                [c.texto for c in self.tallas], "nada")
        seccion(f"CHOQUES: NO SE TOCAN ({len(self.choques)}; arreglar a mano):",
                [c.texto for c in self.choques], "ninguno")
        seccion(f"TAXONOMÍAS CON DOS ESCRITURAS ({len(self.taxonomias)}):",
                [f.texto for f in self.taxonomias], "nada")
        seccion(f"NOMBRES QUE REPITEN LA ESCUELA ({len(self.nombres)}):",
                [n.texto for n in self.nombres], "ninguno")
        seccion("COLORES (INFORMATIVO, NO SE TOCAN: decisión 2026-11-13):",
                [f"«{c}» → sería «{o}» ({_n(n, 'talla', 'tallas')})" for c, o, n in self.colores], "nada")
        seccion("PARECIDOS (INFORMATIVO, NO SE TOCAN):", self.parecidos, "nada")
        renglones.append("")
        renglones.append("SKU, precios y existencias no cambian.")
        return "\n".join(renglones).strip("\n")


def _n(n: int, uno: str, varios: str) -> str:
    return f"1 {uno}" if n == 1 else f"{n} {varios}"


# ── Plan (solo lee) ────────────────────────────────────────────────────────

def _planear_tallas(session: Session, plan: PlanLimpieza) -> None:
    filas = session.execute(
        select(Variante.id, Variante.producto_id, Variante.sku, Variante.talla, Variante.color, Producto.nombre)
        .join(Producto, Variante.producto_id == Producto.id)
        .order_by(Variante.producto_id, Variante.id)
    ).all()
    grupos: dict[tuple[int, str], list] = defaultdict(list)
    for fila in filas:
        grupos[(int(fila.producto_id), str(fila.color or ""))].append(fila)
    por_cambio: dict[tuple[str, str], CambioTalla] = {}
    for (producto_id, color), variantes in grupos.items():
        finales: dict[str, list] = defaultdict(list)
        nueva_de: dict[int, str] = {}
        for v in variantes:
            nueva = valores.forma_oficial_talla(v.talla) or str(v.talla)
            nueva_de[int(v.id)] = nueva
            finales[nueva].append(v)
        for final, juntas in finales.items():
            cambian = [v for v in juntas if nueva_de[int(v.id)] != v.talla]
            if not cambian:
                continue
            if len(juntas) > 1:
                plan.choques.append(Choque(
                    producto_id, str(juntas[0].nombre), color or SIN_COLOR, final,
                    [TallaEnChoque(int(v.id), str(v.sku), str(v.talla)) for v in juntas],
                ))
                continue
            v = cambian[0]
            plan.variantes[int(v.id)] = final
            cambio = por_cambio.setdefault((str(v.talla), final), CambioTalla(str(v.talla), final))
            cambio.variantes.append(int(v.id))
            cambio.productos.add(producto_id)
    plan.tallas = sorted(por_cambio.values(), key=lambda c: (-len(c.variantes), c.antes))


def _filas_vivas(session: Session, modelo, columna) -> list[tuple[object, int]]:
    """(fila, prendas que la usan) de las activas o con alguna prenda."""
    usos = dict(session.execute(
        select(columna, func.count(Producto.id)).where(columna.is_not(None)).group_by(columna)
    ).all())
    filas = session.scalars(select(modelo).order_by(modelo.id)).all()
    return [(f, int(usos.get(f.id, 0))) for f in filas if f.activo or usos.get(f.id)]


def _destino(grupo: list[tuple[object, int]]):
    """La forma que se queda: la acentuada, luego la activa, luego la más usada."""
    return sorted(grupo, key=lambda fu: (not valores.lleva_acento(fu[0].nombre), not fu[0].activo,
                                         -fu[1], fu[0].id))[0][0]


def _planear_taxonomias(session: Session, plan: PlanLimpieza) -> None:
    for campo, (modelo, columna, _rel) in TAXONOMIAS.items():
        vivas = _filas_vivas(session, modelo, columna)
        grupos: dict[str, list] = defaultdict(list)
        for fila, usos in vivas:
            grupos[valores.normalizar(fila.nombre)].append((fila, usos))
        for grupo in grupos.values():
            if len(grupo) < 2:
                continue
            destino = _destino(grupo)
            for fila, _usos in grupo:
                if fila.id == destino.id:
                    continue
                productos = [int(i) for i in session.scalars(
                    select(Producto.id).where(columna == fila.id).order_by(Producto.id)).all()]
                plan.taxonomias.append(FusionTaxonomia(campo, int(fila.id), str(fila.nombre),
                                                       int(destino.id), str(destino.nombre), productos))
        _parecidos(campo, [f.nombre for f, _u in vivas], plan)
    for campo, (modelo, columna) in SOLO_INFORMATIVO.items():
        vivas = _filas_vivas(session, modelo, columna)
        grupos = defaultdict(list)
        for fila, usos in vivas:
            grupos[valores.normalizar(fila.nombre)].append(f"«{fila.nombre}» ({usos})")
        etiqueta = valores.ETIQUETA_CAMPO.get(campo, campo)
        for nombres in grupos.values():
            if len(nombres) > 1:
                plan.parecidos.append(f"{etiqueta}: {' / '.join(nombres)} (misma escritura sin acentos)")


def _parecidos(campo: str, nombres: list[str], plan: PlanLimpieza) -> None:
    etiqueta = valores.ETIQUETA_CAMPO.get(campo, campo)
    unicos = sorted({valores.normalizar(n): n for n in nombres}.items())
    for i, (na, a) in enumerate(unicos):
        for nb, b in unicos[i + 1:]:
            if re.sub(r"\d", "#", na) == re.sub(r"\d", "#", nb):
                continue  # «Pants 2pz» y «Pants 3pz» son otra cosa, no una mala escritura
            if difflib.SequenceMatcher(None, na, nb).ratio() >= UMBRAL_PARECIDOS:
                plan.parecidos.append(f"{etiqueta}: «{a}» / «{b}»")


def _planear_colores(session: Session, plan: PlanLimpieza) -> None:
    usos = valores.contar_usos(session, valores.CAMPO_COLOR)
    for color, n in sorted(usos.items(), key=lambda cu: (-cu[1], cu[0])):
        oficial = valores.forma_oficial_color(color)
        if oficial and oficial != color:
            plan.colores.append((color, oficial, n))


def _planear_nombres(session: Session, plan: PlanLimpieza) -> None:
    """Los que repiten la escuela (el mismo criterio de `arreglar_nombres_estv`)."""
    productos = session.scalars(
        select(Producto).join(Escuela, Producto.escuela_id == Escuela.id).order_by(Producto.id)).all()
    for p in productos:
        escuela = p.escuela.nombre
        base = CatalogService.nombre_sin_escuela(p.nombre_base or p.nombre, escuela)
        nuevo = CatalogService.armar_nombre(base, escuela)
        quitadas = len(p.nombre.split()) - len(CatalogService.nombre_sin_escuela(p.nombre, escuela).split())
        if nuevo != p.nombre and quitadas >= 2 * len(escuela.split()):
            plan.nombres.append(NombreRepetido(int(p.id), str(p.nombre), nuevo, base))


def planear_limpieza(session: Session) -> PlanLimpieza:
    """Lo que haría la limpieza. Solo lee."""
    plan = PlanLimpieza()
    _planear_tallas(session, plan)
    _planear_taxonomias(session, plan)
    _planear_nombres(session, plan)
    _planear_colores(session, plan)
    return plan


# ── Aplicar ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ResultadoLimpieza:
    tallas: int
    prendas_movidas: int
    taxonomias_apagadas: int
    nombres: int

    def texto(self) -> str:
        return (f"Aplicado: {_n(self.tallas, 'talla', 'tallas')} a su forma oficial, "
                f"{_n(self.prendas_movidas, 'prenda', 'prendas')} a la taxonomía con acento "
                f"({self.taxonomias_apagadas} inactivas), {_n(self.nombres, 'nombre', 'nombres')} sin la escuela repetida.")


class PlanDesactualizado(ValueError):
    """La base cambió entre el plan y aplicar: hay que volver a planear."""


def aplicar_limpieza(session: Session, plan: PlanLimpieza, usuario: Usuario, *, commit: bool = False
                     ) -> ResultadoLimpieza:
    """Escribe el plan, todo o nada. No cambia SKU, precios ni existencias."""
    CatalogService._validar_admin(usuario)
    antes_de = {vid: c.antes for c in plan.tallas for vid in c.variantes}
    movidas = apagadas = 0
    with session.begin_nested():
        for vid, nueva in plan.variantes.items():
            v = session.get(Variante, vid)
            if v is None or v.talla != antes_de.get(vid):
                raise PlanDesactualizado(f"La talla #{vid} cambió desde el plan: vuelve a correr sin --aplicar.")
            CatalogAuditService.registrar_cambio(
                session=session, usuario=usuario, entidad_tipo=TipoEntidadCatalogo.PRESENTACION,
                entidad_id=int(v.id), accion=TipoCambioCatalogo.ACTUALIZACION, campo="talla",
                valor_anterior=v.talla, valor_nuevo=nueva,
                descripcion_entidad=CatalogService._descripcion_presentacion(v),
                observacion=f"{REFERENCIA} · talla «{v.talla}» → «{nueva}»",
            )
            v.talla = nueva
        session.flush()
        for fusion in plan.taxonomias:
            modelo, columna, relacion = TAXONOMIAS[fusion.campo]
            de, a = session.get(modelo, fusion.de_id), session.get(modelo, fusion.a_id)
            if de is None or a is None:
                raise PlanDesactualizado("Una taxonomía cambió desde el plan: vuelve a correr sin --aplicar.")
            for p in session.scalars(select(Producto).where(columna == de.id).order_by(Producto.id)).all():
                CatalogAuditService.registrar_cambio(
                    session=session, usuario=usuario, entidad_tipo=TipoEntidadCatalogo.PRODUCTO,
                    entidad_id=int(p.id), accion=TipoCambioCatalogo.ACTUALIZACION, campo=relacion,
                    valor_anterior=de.nombre, valor_nuevo=a.nombre,
                    descripcion_entidad=CatalogService._descripcion_producto(p),
                    observacion=f"{REFERENCIA} · {relacion} «{de.nombre}» → «{a.nombre}»",
                )
                setattr(p, relacion, a)
                movidas += 1
            if de.activo:
                de.activo = False
                apagadas += 1
        session.flush()
        for nombre in plan.nombres:
            p = session.get(Producto, nombre.producto_id)
            if p is None or p.nombre != nombre.antes:
                raise PlanDesactualizado(f"El nombre de #{nombre.producto_id} cambió desde el plan.")
            CatalogService.actualizar_producto(
                session, usuario, p,
                categoria=p.categoria, marca=p.marca, nombre=nombre.base, descripcion=p.descripcion,
                escuela=p.escuela, tipo_prenda=p.tipo_prenda, tipo_pieza=p.tipo_pieza,
                nivel_educativo=p.nivel_educativo, atributo=p.atributo, genero=p.genero,
                escudo=p.escudo, ubicacion=p.ubicacion, observacion=f"{REFERENCIA} · nombre sin la escuela repetida",
            )
            if p.nombre != nombre.despues:
                raise PlanDesactualizado(f"#{p.id} quedó «{p.nombre}», se esperaba «{nombre.despues}».")
        session.flush()
        if plan.hay_cambios:
            CatalogService._notify_meili(session)
        resultado = ResultadoLimpieza(len(plan.variantes), movidas, apagadas, len(plan.nombres))
    if commit:
        session.commit()
    return resultado


__all__ = [
    "CambioTalla",
    "Choque",
    "FusionTaxonomia",
    "NombreRepetido",
    "PlanDesactualizado",
    "PlanLimpieza",
    "REFERENCIA",
    "ResultadoLimpieza",
    "aplicar_limpieza",
    "planear_limpieza",
]
