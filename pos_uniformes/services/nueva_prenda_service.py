"""Lo que la pantalla «Nueva prenda» lee y los textos que enseña.

Tanda 3 del rediseño de «Nueva prenda» (2026-11-13). La pantalla no arma
consultas ni frases por su cuenta: aquí están

- las escuelas para el buscador del paso 1, cada una con su nivel y cuántas
  prendas tiene (para no confundir «Ignacio Allende» con «Ignacio Allende
  (Jaral)»), y el filtro sin acentos ni mayúsculas;
- «Últimas altas · Hacer otra igual» de la puerta (las ráfagas del 8-nov);
- el texto del botón vino, la nota de por qué no deja guardar, la frase de
  confirmación y la de «✓ Listo».

El alta en sí la hace `alta_prenda_service` (plan → aplicar, todo junto o nada).
Solo lee; nada aquí escribe en la base.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import Escuela, Marca, NivelEducativo, Producto, TipoPieza
from pos_uniformes.services import catalogo_valores_service as valores
from pos_uniformes.services.catalogo_valores_service import normalizar

MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
#: Cuántas «Últimas altas» se enseñan en la puerta.
ULTIMAS_ALTAS = 4


# ── Escuelas para el buscador ──────────────────────────────────────────────

@dataclass(frozen=True)
class EscuelaParaElegir:
    """Un renglón del buscador: una escuela en un nivel (una escuela con
    primaria y secundaria sale dos veces)."""

    escuela_id: int
    nombre: str
    nivel: str | None
    prendas: int = 0

    @property
    def detalle(self) -> str:
        """«Primaria · 9 prendas» / «sin prendas todavía»."""
        if not self.prendas:
            return "sin prendas todavía"
        prendas = "1 prenda" if self.prendas == 1 else f"{self.prendas} prendas"
        return f"{self.nivel} · {prendas}" if self.nivel else prendas

    @property
    def texto(self) -> str:
        return f"{self.nombre} · {self.detalle}"


def escuelas_para_elegir(session: Session) -> list[EscuelaParaElegir]:
    """Las escuelas activas con su nivel y cuántas prendas activas tienen en
    él. Una sola consulta."""
    filas = session.execute(
        select(Escuela.id, Escuela.nombre, NivelEducativo.nombre, func.count(Producto.id))
        .select_from(Escuela)
        .outerjoin(Producto, (Producto.escuela_id == Escuela.id) & Producto.activo.is_(True))
        .outerjoin(NivelEducativo, NivelEducativo.id == Producto.nivel_educativo_id)
        .where(Escuela.activo.is_(True))
        .group_by(Escuela.id, Escuela.nombre, NivelEducativo.nombre)
    ).all()
    con_nivel = {int(eid) for eid, _n, nivel, cuantas in filas if nivel is not None and cuantas}
    salida = []
    for eid, nombre, nivel, cuantas in filas:
        if nivel is None and int(eid) in con_nivel:
            continue  # prendas sin nivel de una escuela que sí tiene: no se enseña aparte
        salida.append(EscuelaParaElegir(int(eid), str(nombre), str(nivel) if nivel else None, int(cuantas or 0)))
    salida.sort(key=lambda e: (normalizar(e.nombre), normalizar(e.nivel or "")))
    return salida


def filtrar_escuelas(escuelas: Iterable[EscuelaParaElegir], texto: str) -> list[EscuelaParaElegir]:
    """Puro: las que llevan todas las palabras escritas, sin importar acentos
    ni mayúsculas («ignacio jaral», «tecnica 18», «primaria allende»)."""
    palabras = normalizar(texto).split()
    if not palabras:
        return list(escuelas)
    return [e for e in escuelas if all(p in normalizar(f"{e.nombre} {e.nivel or ''}") for p in palabras)]


# ── Últimas altas ──────────────────────────────────────────────────────────

def fecha_corta(fecha: datetime | None) -> str:
    """«13-nov»."""
    if fecha is None:
        return ""
    return f"{fecha.day}-{MESES[fecha.month - 1]}"


@dataclass(frozen=True)
class UltimaAlta:
    producto_id: int
    nombre: str
    escuela_id: int
    escuela: str
    tipo_pieza: str
    nivel: str | None
    fecha: datetime | None = None

    @property
    def detalle(self) -> str:
        """«Pants Suelto · 13-nov»."""
        return " · ".join(p for p in (self.tipo_pieza, fecha_corta(self.fecha)) if p)


def ultimas_altas(session: Session, limite: int = ULTIMAS_ALTAS) -> list[UltimaAlta]:
    """Las últimas prendas de escuela que se dieron de alta (activas), para
    «Hacer otra igual»: la misma pieza, copiada de esa, para otra escuela."""
    filas = session.execute(
        select(Producto.id, Producto.nombre, Escuela.id, Escuela.nombre, TipoPieza.nombre,
               NivelEducativo.nombre, Producto.created_at)
        .join(Escuela, Escuela.id == Producto.escuela_id)
        .join(TipoPieza, TipoPieza.id == Producto.tipo_pieza_id)
        .outerjoin(NivelEducativo, NivelEducativo.id == Producto.nivel_educativo_id)
        .where(Producto.activo.is_(True), Escuela.activo.is_(True))
        .order_by(Producto.created_at.desc(), Producto.id.desc())
        .limit(int(limite))
    ).all()
    return [
        UltimaAlta(int(pid), str(nombre), int(eid), str(escuela), str(pieza), str(nivel) if nivel else None,
                   creado if isinstance(creado, datetime) else None)
        for pid, nombre, eid, escuela, pieza, nivel, creado in filas
    ]


# ── Listas cerradas de la pantalla ─────────────────────────────────────────

SIN_COLOR = "Sin color"


@dataclass(frozen=True)
class Opciones:
    """Lo que ofrecen los combos (listas cerradas, una forma por valor)."""

    colores: tuple[str, ...] = ()
    #: Cuántas tallas usan cada color (para «¿Quisiste decir…?»).
    usos_color: dict = None  # type: ignore[assignment]
    marcas: tuple[str, ...] = ()
    generos: tuple[str, ...] = ()
    escudos: tuple[str, ...] = ()
    niveles: tuple[str, ...] = ()
    piezas: tuple[str, ...] = ()


def _distintos(session: Session, columna) -> list[str]:
    filas = session.execute(
        select(columna, func.count(Producto.id))
        .where(Producto.activo.is_(True), columna.is_not(None))
        .group_by(columna)
        .order_by(func.count(Producto.id).desc(), columna)
    ).all()
    return [valores.limpiar(v) for v, _n in filas if valores.limpiar(v)]


def opciones(session: Session) -> Opciones:
    """Colores (los sugeridos y los que ya existen, en su forma oficial, del
    más usado al menos), marcas, géneros, escudos, niveles y piezas."""
    usos_color = valores.contar_usos(session, valores.CAMPO_COLOR)
    por_uso = sorted(usos_color, key=lambda c: (-usos_color[c], normalizar(c)))
    colores = valores.depurar_opciones(valores.CAMPO_COLOR, [SIN_COLOR], list(valores.COLORES_SUGERIDOS), por_uso)
    return Opciones(
        colores=tuple(colores),
        usos_color=usos_color,
        marcas=tuple(sorted((str(m) for m in session.scalars(select(Marca.nombre).where(Marca.activo.is_(True)))),
                            key=normalizar)),
        generos=tuple(_distintos(session, Producto.genero)),
        escudos=tuple(_distintos(session, Producto.escudo)),
        niveles=tuple(str(n) for n in session.scalars(
            select(NivelEducativo.nombre).where(NivelEducativo.activo.is_(True)).order_by(NivelEducativo.id))),
        piezas=tuple(sorted((str(n) for n in session.scalars(
            select(TipoPieza.nombre).where(TipoPieza.activo.is_(True)))), key=normalizar)),
    )


# ── Textos de la pantalla (puros) ──────────────────────────────────────────

def _tallas(n: int) -> str:
    return "1 talla" if n == 1 else f"{n} tallas"


def _lista(nombres: Sequence[str]) -> str:
    """«A», «A y B», «A, B y C»."""
    nombres = [n for n in nombres if n]
    if len(nombres) <= 1:
        return "".join(nombres)
    return ", ".join(nombres[:-1]) + " y " + nombres[-1]


def _rango(precios: Sequence) -> str:
    precios = [p for p in precios if p is not None]
    if not precios:
        return ""
    lo, hi = min(precios), max(precios)
    return f"a ${lo:.0f}" if lo == hi else f"de ${lo:.0f} a ${hi:.0f}"


def _de_cuantas(total: int, singular: str, plural: str) -> str:
    """«de las 10 escuelas» / «de 1 escuela»."""
    return f"de {total} {singular}" if total == 1 else f"de las {total} {plural}"


def texto_pieza_comparada(con_ella: int, del_nivel: int) -> str:
    """«Le falta»: cuántas escuelas del nivel tienen la pieza, diciendo de
    qué es el total («la tienen 4 de las 10 escuelas»)."""
    return f"la tienen {con_ella} {_de_cuantas(del_nivel, 'escuela', 'escuelas')}"


def texto_cobertura_talla(talla, tipo_pieza: str | None) -> str:
    """La fila gris de una talla que no trae el modelo: cuántas de las prendas
    hermanas la tienen, nombrando el total («la tienen 1 de las 4 prendas de
    Pants Suelto»). Así no se confunde con «la tienen 4 de las 10 escuelas»."""
    total = int(getattr(talla, "cobertura_total", 0) or 0)
    if not total:
        return getattr(talla, "texto_cobertura", "") or ""
    tienen = int(getattr(talla, "cobertura_tienen", 0) or 0)
    de = _de_cuantas(total, "prenda", "prendas")
    return f"la tienen {tienen} {de} de {tipo_pieza}" if tipo_pieza else f"la tienen {tienen} {de}"


def texto_le_falta_a(escuelas: int, nivel: str | None) -> str:
    """«le falta a 6 escuelas de primaria»."""
    sujeto = "escuela" if escuelas == 1 else "escuelas"
    nivel = f" de {nivel.lower()}" if nivel else ""
    return f"le falta a {escuelas} {sujeto}{nivel}"


def texto_boton(planes: Sequence) -> str:
    """«Dar de alta 10 tallas» / «Dar de alta 3 prendas (30 tallas)»."""
    total = sum(len(p.tallas) for p in planes)
    if not planes or not total:
        return "Dar de alta"
    if len(planes) == 1:
        return f"Dar de alta {_tallas(total)}"
    return f"Dar de alta {len(planes)} prendas ({_tallas(total)})"


def nota_bloqueo(planes: Sequence) -> str:
    """Por qué el botón está apagado, en una línea («Falta precio en 2
    tallas»). Vacío si se puede dar de alta."""
    if not planes:
        return "Elige la escuela y la pieza."
    principal = planes[0]
    if not principal.tallas:
        return "Marca al menos una talla."
    sin_precio = [t for t in principal.tallas if t.error and t.precio is None]
    en_cero = [t for t in principal.tallas if t.error and t.precio is not None]
    if sin_precio:
        return f"Falta precio en {_tallas(len(sin_precio))}."
    if en_cero:
        return "Ningún precio puede quedar en $0." if len(en_cero) > 1 else f"La talla {en_cero[0].talla} está en $0."
    for plan in planes:
        if plan.errores:
            prefijo = "" if plan is principal else f"{plan.escuela}: "
            return prefijo + plan.errores[0].split("\n")[0]
        for t in plan.tallas:
            if t.error:
                return f"{plan.escuela}: talla {t.talla}, {t.error[:1].lower()}{t.error[1:]}"
    return ""


def frase_confirmar(planes: Sequence) -> str:
    """La frase del paso 4. Con una escuela es `PlanPrenda.resumen`; con
    varias, una sola frase con todas."""
    if not planes:
        return ""
    if len(planes) == 1:
        return planes[0].resumen
    total = sum(len(p.tallas) for p in planes)
    escuelas = [p.escuela or "" for p in planes]
    pieza = planes[0].tipo_pieza or planes[0].nombre_sin_escuela
    texto = (
        f"Se crean {len(planes)} prendas de {pieza} ({_tallas(total)}), una para cada escuela: "
        f"{_lista(escuelas)}"
    )
    rango = _rango([t.precio for p in planes for t in p.tallas])
    texto += f", {rango}." if rango else "."
    grupos = sorted({p.grupo or p.grupo_previsto for p in planes if p.ligar and (p.grupo or p.grupo_previsto)})
    if grupos:
        texto += f" Quedan en su uniforme {_lista(grupos)}."
    return texto


def detalle_confirmar(planes: Sequence) -> str:
    """Lo que acompaña a la frase: la receta y lo que llega («Llegan 6
    piezas: entran como entrada normal.»). Vacío si no hay nada."""
    if not planes:
        return ""
    lineas = [t for t in dict.fromkeys(p.receta_texto for p in planes) if t]
    llegan = sum(int(t.llegan or 0) for t in planes[0].tallas)
    if llegan:
        lineas.append(f"Llega{'' if llegan == 1 else 'n'} {llegan} {'pieza' if llegan == 1 else 'piezas'} "
                      f"de {planes[0].escuela}: {'entra' if llegan == 1 else 'entran'} como entrada normal.")
    return "\n".join(lineas)


def frase_listo(resultado) -> str:
    """«10 tallas de Pants Suelto Ignacio Allende (Jaral), de $245 a $295.
    Quedó en su uniforme Deportivo y en la receta de Chamarra.»"""
    productos = list(getattr(resultado, "productos", ()) or ())
    if not productos:
        return ""
    total = sum(len(p.tallas) for p in productos)
    precios = [t.precio for p in productos for t in p.tallas]
    if len(productos) == 1:
        p = productos[0]
        texto = f"{_tallas(total)} de {p.nombre}"
    else:
        texto = f"{len(productos)} prendas ({_tallas(total)}): {_lista([p.nombre for p in productos])}"
    rango = _rango(precios)
    texto += f", {rango}." if rango else "."
    grupos = sorted({p.uniforme for p in productos if p.uniforme})
    recetas = []
    for p in productos:
        for r in p.recetas:
            nombre = r.split(":")[0].strip()
            if nombre not in recetas:
                recetas.append(nombre)
    partes = []
    if grupos:
        partes.append(f"en su uniforme {_lista(grupos)}")
    if recetas:
        partes.append(("en la receta de " if len(recetas) == 1 else "en las recetas de ") + _lista(recetas))
    if partes:
        verbo = "Quedó" if len(productos) == 1 else "Quedaron"
        texto += f" {verbo} {' y '.join(partes)}."
    return texto


__all__ = [
    "EscuelaParaElegir",
    "Opciones",
    "UltimaAlta",
    "escuelas_para_elegir",
    "fecha_corta",
    "filtrar_escuelas",
    "detalle_confirmar",
    "frase_confirmar",
    "frase_listo",
    "nota_bloqueo",
    "opciones",
    "texto_boton",
    "texto_cobertura_talla",
    "texto_le_falta_a",
    "texto_pieza_comparada",
    "ultimas_altas",
]
