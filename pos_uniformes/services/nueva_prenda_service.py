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

from pos_uniformes.database.models import Escuela, NivelEducativo, Producto, TipoPieza
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
    "UltimaAlta",
    "escuelas_para_elegir",
    "fecha_corta",
    "filtrar_escuelas",
    "frase_confirmar",
    "frase_listo",
    "nota_bloqueo",
    "texto_boton",
    "ultimas_altas",
]
