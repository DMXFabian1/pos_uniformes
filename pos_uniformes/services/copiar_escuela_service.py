"""«Escuela igual a otra»: copiar el uniforme de una escuela a otra (tanda 5, 2026-11-15).

Caso (b) de la propuesta de «Nueva prenda». Hoy, para Rancho Nuevo o Jaral
había que repetir el alta de 7 a 15 veces (más de 300 clics) o pedírselo a
Claude. Aquí se elige de qué escuela se copia y para cuál (una que existe o
una nueva), y cada prenda del origen sale con su estado:

- **NUEVA**: el destino no la tiene. Se da de alta con el motor del alta
  (`alta_prenda_service.planear_desde_modelo` con la prenda del origen de
  modelo y `preferir="modelo"`): **mismos precios que el origen**, existencia
  0, el mismo lugar en el uniforme y la receta propuesta como en el origen.
- **YA ESTÁ**: el destino ya la tiene (misma pieza y mismo nombre sin color).
  No se toca; si no estaba en su uniforme, se liga.
- **CAMBIA COLOR**: el destino ya la tiene, pero en otro color del que se
  eligió. Se le cambia el color (y el nombre, si lo lleva) a toda la prenda
  con `corregir_prenda_service`: SKU, precios y existencia se quedan igual.
- **SE LIGA**: una pieza general del uniforme del origen (falda, pantalón de
  vestir, sin escuela) que falta en el uniforme del destino.

Las prendas se emparejan por tipo de pieza y nombre sin escuela y sin color
(«Suéter Botones M Rojo» del origen = «Suéter Botones M Gris» del destino).
El color se cambia para todas (`colores`: color del origen → color nuevo) o
prenda por prenda (`color_de`: producto del origen → color); el de una prenda
gana. Una prenda que ya está solo cambia de color si se eligió uno para ella
(o para su color del origen): si no, se queda como está.

Todo va en una transacción (todo o nada) y la bitácora dice «Copia de escuela:
<origen> → <destino> · modelo: <prenda del origen>». Nunca se baja un precio:
las prendas nuevas copian los del origen y las que ya están no cambian de
precio. Una escuela nueva solo la crea un ADMIN, después de contestar «¿Es la
misma que…?» (las parecidas por nombre, sin acentos). Lo mismo usa la skill
`alta-productos` (`scripts/copiar_escuela.py`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, InvalidRequestError, SQLAlchemyError
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    AtributoProducto,
    Categoria,
    Escuela,
    Marca,
    NivelEducativo,
    Producto,
    TipoPieza,
    TipoPrenda,
    Uniforme,
    UniformePieza,
    Usuario,
    Variante,
)
from pos_uniformes.services import alta_prenda_service as alta
from pos_uniformes.services import catalogo_valores_service as valores
from pos_uniformes.services import conjunto_service, uniforme_service
from pos_uniformes.services import corregir_prenda_service as corregir
from pos_uniformes.services import precio_sugerido_service as precios
from pos_uniformes.services.catalog_service import _MEILI_PENDIENTE, CatalogService
from pos_uniformes.services.talla_orden_service import clave_talla

ESTADO_NUEVA = "NUEVA"
ESTADO_YA_ESTA = "YA ESTÁ"
ESTADO_CAMBIA_COLOR = "CAMBIA COLOR"
ESTADO_SE_LIGA = "SE LIGA"

SIN_COLOR = alta.SIN_COLOR
_ORDEN_GRUPO = {g: i for i, g in enumerate(uniforme_service.GRUPOS)}


class CopiaNoValida(ValueError):
    """El plan de la copia tiene errores: no se guarda nada."""


# ── Lo que tiene una escuela ───────────────────────────────────────────────

@dataclass(frozen=True)
class PiezaOrigen:
    """Una prenda activa de la escuela (o una general de su uniforme)."""

    producto_id: int
    nombre: str
    nombre_sin_escuela: str
    tipo_pieza: str | None
    nivel: str | None
    color: str
    tallas: tuple[tuple[str, Decimal], ...] = ()
    costos: tuple[tuple[str, Decimal], ...] = ()
    #: Su lugar en el uniforme de su escuela (None si no está).
    grupo: str | None = None
    orden: int | None = None
    obligatoria: bool = True
    color_uniforme: str | None = None
    #: Pieza general (sin escuela) del uniforme: falda, pantalón de vestir…
    general: bool = False
    # Para armar el alta cuando la prenda no tiene tipo de pieza.
    categoria: str = ""
    marca: str = ""
    tipo_prenda: str | None = None
    atributo: str | None = None
    genero: str | None = None
    escudo: str | None = None
    ubicacion: str | None = None

    @property
    def es_conjunto(self) -> bool:
        return (self.tipo_pieza or "") in conjunto_service.TIPOS_CONJUNTO

    @property
    def precios(self) -> dict[str, Decimal]:
        return dict(self.tallas)

    @property
    def texto_rango(self) -> str:
        """«10 tallas · $245 a $295»."""
        n = len(self.tallas)
        texto = "1 talla" if n == 1 else f"{n} tallas"
        if self.tallas:
            lo, hi = min(p for _t, p in self.tallas), max(p for _t, p in self.tallas)
            texto += f" · ${lo:.0f}" if lo == hi else f" · ${lo:.0f} a ${hi:.0f}"
        return texto


@dataclass(frozen=True)
class EscuelaParaCopiar:
    """Un renglón del buscador «¿De qué escuela copias?»."""

    escuela_id: int
    nombre: str
    niveles: tuple[str, ...] = ()
    prendas: int = 0

    @property
    def detalle(self) -> str:
        """«Primaria · 7 prendas»."""
        if not self.prendas:
            return "sin prendas todavía"
        prendas = "1 prenda" if self.prendas == 1 else f"{self.prendas} prendas"
        return " · ".join([*self.niveles, prendas])


def escuelas_para_copiar(session: Session) -> list[EscuelaParaCopiar]:
    """Las escuelas activas con sus niveles y cuántas prendas activas tienen
    (una escuela con primaria y secundaria sale una vez). Una consulta."""
    filas = session.execute(
        select(Escuela.id, Escuela.nombre, NivelEducativo.nombre, Producto.id)
        .select_from(Escuela)
        .outerjoin(Producto, (Producto.escuela_id == Escuela.id) & Producto.activo.is_(True))
        .outerjoin(NivelEducativo, NivelEducativo.id == Producto.nivel_educativo_id)
        .where(Escuela.activo.is_(True))
    ).all()
    datos: dict[int, dict] = {}
    for eid, nombre, nivel, pid in filas:
        d = datos.setdefault(int(eid), {"nombre": str(nombre), "niveles": {}, "prendas": 0})
        if pid is not None:
            d["prendas"] += 1
            if nivel:
                d["niveles"][str(nivel)] = d["niveles"].get(str(nivel), 0) + 1
    salida = [
        EscuelaParaCopiar(eid, d["nombre"], tuple(sorted(d["niveles"], key=lambda n: -d["niveles"][n])),
                          d["prendas"])
        for eid, d in datos.items()
    ]
    salida.sort(key=lambda e: valores.normalizar(e.nombre))
    return salida


def filtrar_escuelas(escuelas: Iterable[EscuelaParaCopiar], texto: str) -> list[EscuelaParaCopiar]:
    """Puro: las que llevan todas las palabras escritas, sin acentos ni mayúsculas."""
    palabras = valores.normalizar(texto).split()
    if not palabras:
        return list(escuelas)
    return [e for e in escuelas
            if all(p in valores.normalizar(f"{e.nombre} {' '.join(e.niveles)}") for p in palabras)]


def _escuela(session: Session, escuela: str | int) -> Escuela | None:
    if isinstance(escuela, int):
        return session.get(Escuela, escuela)
    nombre = valores.limpiar(escuela)
    exacta = session.scalar(select(Escuela).where(Escuela.nombre == nombre))
    if exacta is not None:
        return exacta
    clave = valores.normalizar(nombre)
    parecidas = [e for e in session.scalars(select(Escuela)).all() if valores.normalizar(e.nombre) == clave]
    parecidas.sort(key=lambda e: (not e.activo, not valores.lleva_acento(e.nombre), e.id))
    return parecidas[0] if parecidas else None


def _uniforme_de(session: Session, escuela_id: int | None) -> dict[int, UniformePieza]:
    """Las piezas activas del uniforme de la escuela, por producto."""
    if escuela_id is None:
        return {}
    filas = session.scalars(
        select(UniformePieza)
        .join(Uniforme, Uniforme.id == UniformePieza.uniforme_id)
        .where(Uniforme.escuela_id == int(escuela_id), Uniforme.activo.is_(True), UniformePieza.activo.is_(True))
        .order_by(Uniforme.id, UniformePieza.orden, UniformePieza.id)
    ).all()
    piezas: dict[int, UniformePieza] = {}
    for p in filas:
        piezas.setdefault(int(p.producto_id), p)
    return piezas


def piezas_de_escuela(session: Session, escuela_id: int) -> list[PiezaOrigen]:
    """Las prendas activas de la escuela con sus tallas y precios (el más alto
    si una talla está dos veces: nunca se copia para abajo), su lugar en el
    uniforme y las piezas generales que lleva su uniforme. Tres consultas."""
    uniforme = _uniforme_de(session, escuela_id)
    filas = session.execute(
        select(Producto.id, Producto.nombre, Producto.nombre_base, Producto.escuela_id, Escuela.nombre,
               TipoPieza.nombre, NivelEducativo.nombre, Categoria.nombre, Marca.nombre, TipoPrenda.nombre,
               AtributoProducto.nombre, Producto.genero, Producto.escudo, Producto.ubicacion,
               Variante.talla, Variante.color, Variante.precio_venta, Variante.costo_referencia)
        .join(Variante, (Variante.producto_id == Producto.id) & Variante.activo.is_(True))
        .join(Categoria, Categoria.id == Producto.categoria_id)
        .join(Marca, Marca.id == Producto.marca_id)
        .outerjoin(Escuela, Escuela.id == Producto.escuela_id)
        .outerjoin(TipoPieza, TipoPieza.id == Producto.tipo_pieza_id)
        .outerjoin(NivelEducativo, NivelEducativo.id == Producto.nivel_educativo_id)
        .outerjoin(TipoPrenda, TipoPrenda.id == Producto.tipo_prenda_id)
        .outerjoin(AtributoProducto, AtributoProducto.id == Producto.atributo_id)
        .where(
            Producto.activo.is_(True),
            (Producto.escuela_id == int(escuela_id)) | Producto.id.in_(list(uniforme) or [-1]),
        )
        .order_by(Producto.id, Variante.id)
    ).all()
    datos: dict[int, dict] = {}
    for (pid, nombre, base, esc_id, esc, pieza, nivel, cat, marca, prenda, atributo, genero, escudo, ubic,
         talla, color, precio, costo) in filas:
        if esc_id is not None and int(esc_id) != int(escuela_id):
            continue  # de otra escuela aunque esté en el uniforme: no se copia
        d = datos.setdefault(int(pid), {
            "base": (str(nombre), CatalogService.nombre_sin_escuela(base or nombre, esc), pieza, nivel,
                     str(cat), str(marca), prenda, atributo, genero, escudo, ubic, esc_id is None),
            "precios": {}, "costos": {}, "colores": {},
        })
        t = valores.forma_oficial_talla(talla)
        p = precios.dinero(precio) or Decimal("0.00")
        if t not in d["precios"] or p > d["precios"][t]:
            d["precios"][t] = p
        if costo is not None:
            d["costos"][t] = precios.dinero(costo)
        c = valores.limpiar(color) or SIN_COLOR
        d["colores"][c] = d["colores"].get(c, 0) + 1
    salida = []
    for pid, d in datos.items():
        (nombre, base, pieza, nivel, cat, marca, prenda, atributo, genero, escudo, ubic, general) = d["base"]
        liga = uniforme.get(pid)
        color = max(d["colores"], key=lambda c: (d["colores"][c], c)) if d["colores"] else SIN_COLOR
        salida.append(PiezaOrigen(
            producto_id=pid, nombre=nombre, nombre_sin_escuela=base, tipo_pieza=pieza, nivel=nivel, color=color,
            tallas=tuple(sorted(d["precios"].items(), key=lambda tp: clave_talla(tp[0]))),
            costos=tuple(d["costos"].items()),
            grupo=liga.grupo if liga is not None else None,
            orden=int(liga.orden) if liga is not None else None,
            obligatoria=bool(liga.obligatoria) if liga is not None else True,
            color_uniforme=liga.color if liga is not None else None,
            general=bool(general), categoria=cat, marca=marca, tipo_prenda=prenda, atributo=atributo,
            genero=genero, escudo=escudo, ubicacion=ubic,
        ))
    salida.sort(key=_orden_lista)
    return salida


def _orden_lista(p: PiezaOrigen) -> tuple:
    """Como en el uniforme: por grupo y orden; lo que no está en él, al final."""
    return (p.grupo is None, _ORDEN_GRUPO.get(p.grupo or "", 99), p.orden or 0, p.general,
            valores.normalizar(p.nombre_sin_escuela))


# ── Emparejar ──────────────────────────────────────────────────────────────

def _colores_conocidos(session: Session) -> list[list[str]]:
    """Los colores de la base y los sugeridos, en palabras normalizadas, los
    más largos primero («Azul Marino» antes que «Azul»)."""
    todos = set(valores.contar_usos(session, valores.CAMPO_COLOR)) | set(valores.COLORES_SUGERIDOS)
    claves = {valores.normalizar(c) for c in todos} - {valores.normalizar(SIN_COLOR), ""}
    return sorted((c.split() for c in claves), key=len, reverse=True)


def nombre_sin_color(nombre: str, colores: Iterable[Iterable[str]]) -> str:
    """Puro: el nombre normalizado sin las palabras de color («Suéter Botones
    M Rojo» → «sueter botones m»). Cuenta «Blanca» como «Blanco»."""
    palabras = valores.normalizar(nombre).split()
    for color in colores:
        color = list(color)
        n = len(color)
        if not n:
            continue
        alternas = {tuple(color)}
        if color[-1].endswith("o"):
            alternas.add(tuple(color[:-1] + [color[-1][:-1] + "a"]))
        i = 0
        while i <= len(palabras) - n:
            if tuple(palabras[i:i + n]) in alternas:
                del palabras[i:i + n]
            else:
                i += 1
    return " ".join(palabras)


def clave_pieza(tipo_pieza: str | None, nombre_sin_escuela: str, colores: Iterable[Iterable[str]]) -> str:
    """Puro: con qué se emparejan las prendas del origen y del destino."""
    return f"{valores.normalizar(tipo_pieza)}|{nombre_sin_color(nombre_sin_escuela, colores)}"


# ── El plan ────────────────────────────────────────────────────────────────

@dataclass
class PiezaACopiar:
    origen: PiezaOrigen
    estado: str
    marcada: bool = True
    #: El color con el que queda (el del destino si ya está y no se eligió otro).
    color: str = SIN_COLOR
    #: Se eligió un color para ella (o para su color del origen).
    color_elegido: bool = False
    destino_id: int | None = None
    destino_nombre: str | None = None
    destino_color: str | None = None
    #: Ya existe en el destino pero falta en su uniforme (o es general): se liga.
    ligar: bool = False
    plan: alta.PlanPrenda | None = None
    correccion: corregir.PlanCorreccion | None = None
    avisos: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def nombre(self) -> str:
        """El nombre con el que queda en el destino."""
        if self.plan is not None and self.plan.nombre:
            return self.plan.nombre
        if self.correccion is not None and self.correccion.nombre:
            return self.correccion.nombre
        return self.destino_nombre or self.origen.nombre

    @property
    def texto_estado(self) -> str:
        """«NUEVA», «YA ESTÁ», «CAMBIA COLOR: Gris → Azul», «SE LIGA»."""
        if self.estado == ESTADO_CAMBIA_COLOR:
            return f"{ESTADO_CAMBIA_COLOR}: {self.destino_color} → {self.color}"
        if self.estado == ESTADO_YA_ESTA and self.ligar:
            return f"{ESTADO_YA_ESTA} · se liga al uniforme"
        return self.estado

    @property
    def todos_los_errores(self) -> list[str]:
        errores = list(self.errores)
        if self.plan is not None:
            errores += [e for e in self.plan.todos_los_errores if e not in errores]
        if self.correccion is not None:
            errores += [e for e in self.correccion.errores if e not in errores]
        return errores


@dataclass
class PlanCopia:
    origen: str
    origen_id: int
    destino: str
    destino_id: int | None
    es_nueva: bool = False
    #: Ya se contestó «¿Es la misma que…?»: es otra escuela y se crea.
    nueva_confirmada: bool = False
    piezas: list[PiezaACopiar] = field(default_factory=list)
    colores: dict[str, str] = field(default_factory=dict)
    color_de: dict[int, str] = field(default_factory=dict)
    confirmados: tuple[str, ...] = ()
    #: Los colores que ya usa el destino para cada color del origen («Sin
    #: color» → «Gris» en Jaral): las prendas nuevas los toman si no se eligió otro.
    colores_del_destino: dict[str, str] = field(default_factory=dict)
    #: Escuelas que se parecen al destino nuevo («¿Es la misma que…?»).
    parecidas: tuple[valores.Parecido, ...] = ()
    #: Prendas que solo tiene el destino (no se tocan).
    solo_en_destino: tuple[str, ...] = ()
    avisos: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def marcadas(self) -> list[PiezaACopiar]:
        return [p for p in self.piezas if p.marcada]

    def _de(self, estado: str) -> list[PiezaACopiar]:
        return [p for p in self.marcadas if p.estado == estado]

    @property
    def nuevas(self) -> list[PiezaACopiar]:
        return self._de(ESTADO_NUEVA)

    @property
    def cambian(self) -> list[PiezaACopiar]:
        return self._de(ESTADO_CAMBIA_COLOR)

    @property
    def ligan(self) -> list[PiezaACopiar]:
        return [p for p in self.marcadas if p.ligar]

    @property
    def planes(self) -> list[alta.PlanPrenda]:
        """Los planes de alta en el orden en que se guardan (los conjuntos al final)."""
        return [p.plan for p in sorted(self.nuevas, key=_orden_aplicar) if p.plan is not None]

    @property
    def tallas_nuevas(self) -> int:
        """Las tallas que se crean. Mientras no hay plan (escuela nueva sin
        confirmar) cuentan las del origen, que son las que se copiarán."""
        return sum(len(p.plan.tallas) if p.plan is not None else len(p.origen.tallas)
                   for p in self.nuevas)

    def _precios_nuevos(self) -> list[Decimal]:
        precios: list[Decimal] = []
        for p in self.nuevas:
            if p.plan is not None:
                precios.extend(t.precio for t in p.plan.tallas if t.precio is not None)
            else:
                precios.extend(precio for _t, precio in p.origen.tallas if precio is not None)
        return precios

    @property
    def hay_cambios(self) -> bool:
        return bool(self.nuevas or self.cambian or self.ligan)

    @property
    def todos_los_errores(self) -> list[str]:
        errores = list(self.errores)
        for p in self.marcadas:
            for e in p.todos_los_errores:
                errores.append(f"{p.origen.nombre_sin_escuela}: {e}")
        return errores

    @property
    def puede_aplicar(self) -> bool:
        return self.hay_cambios and not self.todos_los_errores

    @property
    def origen_bitacora(self) -> str:
        return alta.origen_copia_escuela(self.origen, self.destino)

    @property
    def colores_del_origen(self) -> list[tuple[str, int]]:
        """Los colores de las prendas del origen con cuántas lo llevan
        («Rojo, 2 prendas»), para «Color para todas»."""
        cuenta: dict[str, int] = {}
        for p in self.piezas:
            if not p.origen.general:
                cuenta[p.origen.color] = cuenta.get(p.origen.color, 0) + 1
        return sorted(cuenta.items(), key=lambda cn: (cn[0] == SIN_COLOR, -cn[1], cn[0]))

    def color_para_todas(self, color_origen: str) -> str:
        """El color con el que quedan las prendas de `color_origen`: el que se
        eligió, si no el que ya usa el destino, si no el mismo."""
        clave = valores.normalizar(color_origen)
        for k, v in self.colores.items():
            if valores.normalizar(k) == clave and valores.limpiar(v):
                return _color(v)
        return self.colores_del_destino.get(color_origen, color_origen)

    # ── Textos (los usa la pantalla y la skill) ───────────────────────────
    def texto_boton(self) -> str:
        """«Copiar 3 prendas (24 tallas)» / «Cambiar color de 1 prenda»."""
        n = len(self.nuevas)
        if n:
            prendas = "1 prenda" if n == 1 else f"{n} prendas"
            tallas = self.tallas_nuevas
            return f"Copiar {prendas} ({tallas} {'talla' if tallas == 1 else 'tallas'})"
        if self.cambian:
            c = len(self.cambian)
            return f"Cambiar color de {c} {'prenda' if c == 1 else 'prendas'}"
        if self.ligan:
            return "Ligar al uniforme"
        return "Copiar"

    def nota_bloqueo(self) -> str:
        """Por qué no deja copiar, en una línea. Vacío si se puede."""
        if self.errores:
            return self.errores[0].split("\n")[0]
        if not self.marcadas:
            return "Marca al menos una prenda."
        for p in self.marcadas:
            errores = p.todos_los_errores
            if errores:
                return f"{p.origen.nombre_sin_escuela}: {errores[0].split(chr(10))[0]}"
        if not self.hay_cambios:
            return "El destino ya tiene todo lo marcado."
        return ""

    def _partes(self, pasado: bool = False) -> list[str]:
        partes = []
        n = len(self.nuevas)
        if n:
            tallas = self.tallas_nuevas
            verbo = ("se creó" if n == 1 else "se crearon") if pasado else ("se crea" if n == 1 else "se crean")
            texto = f"{verbo} {'1 prenda' if n == 1 else f'{n} prendas'} ({tallas} {'talla' if tallas == 1 else 'tallas'}"
            todos = self._precios_nuevos()
            if todos:
                lo, hi = min(todos), max(todos)
                texto += f", a ${lo:.0f}" if lo == hi else f", de ${lo:.0f} a ${hi:.0f}"
            partes.append(texto + ")")
        c = len(self.cambian)
        if c:
            verbo = ("cambió" if c == 1 else "cambiaron") if pasado else ("cambia" if c == 1 else "cambian")
            partes.append(f"{c} {verbo} de color")
        sueltas = [p for p in self.ligan if p.estado != ESTADO_NUEVA]
        if sueltas:
            s = len(sueltas)
            verbo = ("se ligó" if s == 1 else "se ligaron") if pasado else ("se liga" if s == 1 else "se ligan")
            partes.append(f"{s} {'pieza que ya existe' if s == 1 else 'piezas que ya existen'} {verbo} a su uniforme")
        return partes

    def resumen(self) -> str:
        """La frase para confirmar, en una sola oración."""
        inicio = (f"Se crea la escuela {self.destino}, igual que {self.origen}" if self.es_nueva
                  else f"{self.destino} queda igual que {self.origen}")
        partes = self._partes()
        texto = inicio + (": " + _lista(partes) if partes else "") + "."
        if self.nuevas:
            texto += f" Mismos precios que {self.origen}, sin existencia."
        return texto

    def texto_listo(self) -> str:
        inicio = (f"Se creó la escuela {self.destino}, igual que {self.origen}" if self.es_nueva
                  else f"{self.destino} quedó igual que {self.origen}")
        partes = self._partes(pasado=True)
        return inicio + (": " + _lista(partes) if partes else "") + "."


def _lista(partes: list[str]) -> str:
    if len(partes) <= 1:
        return "".join(partes)
    return ", ".join(partes[:-1]) + " y " + partes[-1]


def _orden_aplicar(p: PiezaACopiar) -> tuple:
    """Primero las piezas sueltas, al final los conjuntos (su receta se arma
    con las piezas que se acaban de crear)."""
    return (p.origen.es_conjunto, _orden_lista(p.origen))


def escuelas_parecidas(session: Session, nombre: str, *, excluir: Iterable[str] = ()) -> tuple[valores.Parecido, ...]:
    """Las escuelas que se parecen a `nombre` sin acentos ni mayúsculas, para
    «¿Es la misma que…?»: las de letras parecidas y las del mismo nombre con
    otro lugar («Ignacio Allende Rancho Nuevo» ~ «Ignacio Allende» e «Ignacio
    Allende (Jaral)»). Vacío si ya existe tal cual. `excluir`: nombres que no
    se ofrecen (la escuela de la que se copia)."""
    usos = valores.contar_usos(session, valores.CAMPO_ESCUELA)
    fuera = {valores.normalizar(x) for x in excluir}
    usos = {v: n for v, n in usos.items() if valores.normalizar(v) not in fuera}
    escrito = valores.limpiar(nombre)
    if not escrito or escrito in usos:
        return ()
    rev = valores.revisar_valor(valores.CAMPO_ESCUELA, escrito, usos)
    if rev.estado == valores.ESTADO_OK and rev.valor in usos:
        return (valores.Parecido(rev.valor, usos.get(rev.valor, 0)),)
    escritas = _sin_lugar(escrito).split()
    mismas = sorted(((n, valor) for valor, n in usos.items() if _mismo_nombre(escritas, _sin_lugar(valor).split())),
                    key=lambda nv: (-nv[0], nv[1]))
    salida = list(rev.sugerencias)
    for n, valor in mismas:
        if all(p.valor != valor for p in salida):
            salida.append(valores.Parecido(valor, n))
    return tuple(salida[: valores.MAX_SUGERENCIAS + 2])


def _mismo_nombre(a: list[str], b: list[str]) -> bool:
    """Puro: uno empieza con todas las palabras del otro (al menos dos, o una
    larga): «ignacio allende rancho nuevo» y «ignacio allende»."""
    if not a or not b:
        return False
    corto, largo = (a, b) if len(a) <= len(b) else (b, a)
    if len(corto) < 2 and len(corto[0]) < 6:
        return False
    return largo[: len(corto)] == corto


def _sin_lugar(nombre: str) -> str:
    return valores.normalizar(re.sub(r"\([^)]*\)", " ", str(nombre or "")))


def _color(texto: object) -> str:
    return valores.forma_oficial_color(texto) or SIN_COLOR


def _color_elegido(o: PiezaOrigen, colores: Mapping[str, str], color_de: Mapping[int, str]) -> str | None:
    if o.producto_id in color_de and valores.limpiar(color_de[o.producto_id]):
        return _color(color_de[o.producto_id])
    por_clave = {valores.normalizar(k): v for k, v in colores.items() if valores.limpiar(v)}
    elegido = por_clave.get(valores.normalizar(o.color))
    return _color(elegido) if elegido else None


def planear_copia(
    session: Session,
    origen: str | int,
    destino: str | int,
    *,
    colores: Mapping[str, str] | None = None,
    color_de: Mapping[int, str] | None = None,
    quitar: Iterable[int] = (),
    confirmados: Iterable[str] = (),
    escuela_nueva: bool = False,
) -> PlanCopia:
    """Lo que pasaría al dejar `destino` igual que `origen`. No escribe nada;
    se vuelve a llamar con cada cambio (color, desmarcar).

    - `colores`: color del origen → color nuevo, para todas las de ese color.
    - `color_de`: producto del origen → color, prenda por prenda (gana).
    - `quitar`: productos del origen que el destino no lleva (desmarcados).
    - `escuela_nueva=True`: confirma que `destino` es una escuela nueva (ya se
      contestó «¿Es la misma que…?»). Sin eso, un destino que no existe frena.
    - `confirmados`: colores nuevos que se confirmaron («Es otro, crearlo»)."""
    colores = dict(colores or {})
    color_de = {int(k): v for k, v in (color_de or {}).items()}
    fuera = {int(x) for x in quitar}
    esc_origen = _escuela(session, origen)
    if esc_origen is None:
        raise ValueError("No existe la escuela de la que se copia.")
    esc_destino = _escuela(session, destino)
    destino_nombre = esc_destino.nombre if esc_destino is not None else valores.limpiar(destino)
    plan = PlanCopia(
        origen=str(esc_origen.nombre), origen_id=int(esc_origen.id),
        destino=destino_nombre, destino_id=int(esc_destino.id) if esc_destino is not None else None,
        es_nueva=esc_destino is None, nueva_confirmada=esc_destino is None and bool(escuela_nueva),
        colores=colores, color_de=color_de, confirmados=tuple(confirmados),
    )
    if not destino_nombre:
        plan.errores.append("Escribe el nombre de la escuela nueva.")
        return plan
    if esc_destino is not None and esc_destino.id == esc_origen.id:
        plan.errores.append("Elige otra escuela: es la misma de la que se copia.")
        return plan
    confirmados_alta = tuple(plan.confirmados)
    if plan.es_nueva:
        plan.parecidas = escuelas_parecidas(session, destino_nombre, excluir=(plan.origen,))
        if not escuela_nueva:
            primera = plan.parecidas[0].valor if plan.parecidas else None
            plan.errores.append(
                f"¿«{destino_nombre}» es la misma que «{primera}»? Elígela o confirma que es nueva."
                if primera else f"Confirma que «{destino_nombre}» es una escuela nueva."
            )
        else:
            plan.avisos.append(f"Se crea la escuela nueva «{destino_nombre}».")
            confirmados_alta += (destino_nombre,)

    lista_colores = _colores_conocidos(session)
    del_origen = piezas_de_escuela(session, esc_origen.id)
    del_destino = piezas_de_escuela(session, esc_destino.id) if esc_destino is not None else []
    uniforme_destino = set(_uniforme_de(session, esc_destino.id)) if esc_destino is not None else set()
    por_clave = {}
    for d in del_destino:
        if not d.general:
            por_clave.setdefault(clave_pieza(d.tipo_pieza, d.nombre_sin_escuela, lista_colores), d)
    usados: set[int] = set()

    for o in del_origen:
        pieza = PiezaACopiar(origen=o, estado=ESTADO_NUEVA, marcada=o.producto_id not in fuera)
        elegido = _color_elegido(o, colores, color_de)
        pieza.color_elegido = elegido is not None
        if o.general:
            pieza.estado = ESTADO_YA_ESTA if o.producto_id in uniforme_destino else ESTADO_SE_LIGA
            pieza.ligar = pieza.estado == ESTADO_SE_LIGA
            pieza.destino_id, pieza.destino_nombre, pieza.color = o.producto_id, o.nombre, o.color
            pieza.destino_color = o.color
            plan.piezas.append(pieza)
            continue
        d = por_clave.get(clave_pieza(o.tipo_pieza, o.nombre_sin_escuela, lista_colores))
        if d is None:
            pieza.color = elegido or _color(o.color)
            plan.piezas.append(pieza)
            continue
        usados.add(d.producto_id)
        pieza.destino_id, pieza.destino_nombre, pieza.destino_color = d.producto_id, d.nombre, d.color
        pieza.ligar = o.grupo is not None and d.producto_id not in uniforme_destino
        faltan = sorted(set(o.precios) - set(d.precios), key=clave_talla)
        if faltan:
            pieza.avisos.append(f"No tiene las tallas {', '.join(faltan)} del origen (no se agregan solas).")
        if elegido is not None and valores.normalizar(elegido) != valores.normalizar(d.color):
            pieza.estado, pieza.color = ESTADO_CAMBIA_COLOR, elegido
        else:
            pieza.estado, pieza.color = ESTADO_YA_ESTA, d.color
        plan.piezas.append(pieza)
    plan.solo_en_destino = tuple(d.nombre for d in del_destino if not d.general and d.producto_id not in usados)
    plan.colores_del_destino = _colores_del_destino(plan.piezas)
    for p in plan.piezas:
        if p.estado == ESTADO_NUEVA and not p.color_elegido:
            p.color = plan.colores_del_destino.get(p.origen.color, p.color)

    if plan.errores:
        return plan  # sin escuela confirmada: solo la lista, sin planes
    _planear_altas(session, plan, confirmados_alta)
    for p in plan.cambian:
        nombre = alta.cambiar_color_en_nombre(
            CatalogService.nombre_sin_escuela(p.destino_nombre or "", plan.destino), p.destino_color, p.color)
        p.correccion = corregir.planear_correccion(
            session, p.destino_id, nombre_sin_escuela=nombre, color=p.color, confirmados=plan.confirmados)
    if not plan.marcadas:
        plan.errores.append("Marca al menos una prenda.")
    return plan


def _colores_del_destino(piezas: Iterable[PiezaACopiar]) -> dict[str, str]:
    """Puro: para cada color del origen, el color que el destino usa en TODAS
    las prendas que ya tiene de ese color (si no es uno solo, no se adivina)."""
    vistos: dict[str, set[str]] = {}
    for p in piezas:
        if p.origen.general or p.destino_color is None or p.estado == ESTADO_NUEVA:
            continue
        vistos.setdefault(p.origen.color, set()).add(p.destino_color)
    return {o: next(iter(d)) for o, d in vistos.items() if len(d) == 1 and next(iter(d)) != o}


def _planear_altas(session: Session, plan: PlanCopia, confirmados: tuple[str, ...]) -> None:
    usos = alta._Usos(session)
    saltar = 0
    destino: str | int = plan.destino_id if plan.destino_id is not None else plan.destino
    for p in sorted(plan.nuevas, key=_orden_aplicar):
        o = p.origen
        if o.tipo_pieza:
            nuevo = alta.planear_desde_modelo(
                session, destino, o.tipo_pieza, nivel=o.nivel, modelo_id=o.producto_id, color=p.color,
                tallas=[t for t, _p in o.tallas], costos=dict(o.costos), preferir=precios.PREFERIR_MODELO,
                confirmados=confirmados, saltar_skus=saltar, usos=usos,
            )
        else:
            nuevo = alta.planear(session, _spec(o, plan.destino, p.color), confirmados=confirmados,
                                 saltar_skus=saltar, usos=usos)
        nuevo.origen = plan.origen_bitacora
        nuevo.modelo_nombre = o.nombre
        nuevo.alternativas = ()
        # El mismo lugar en el uniforme que en el origen (si no estaba, no se liga).
        nuevo.grupo, nuevo.orden, nuevo.obligatoria = o.grupo, o.orden, o.obligatoria
        nuevo.ligar = o.grupo is not None
        alta.completar(session, nuevo, usos=usos)
        nuevo.avisos = [a for a in nuevo.avisos if "escuela nueva" not in a]
        p.plan = nuevo
        saltar += len(nuevo.tallas)
    nombres = [p.plan.nombre for p in plan.nuevas if p.plan is not None]
    for p in plan.nuevas:
        if p.plan is not None and p.plan.nombre and nombres.count(p.plan.nombre) > 1:
            p.errores.append(f"«{p.plan.nombre}» saldría dos veces: cámbiale el color o desmárcala.")


def _spec(o: PiezaOrigen, destino: str, color: str) -> dict:
    """Una prenda sin tipo de pieza: se copia tal cual con `alta.planear`."""
    return {
        "producto": {
            "nombre": alta.cambiar_color_en_nombre(o.nombre_sin_escuela, o.color, color),
            "categoria": o.categoria, "marca": o.marca, "escuela": destino,
            "tipo_prenda": o.tipo_prenda, "tipo_pieza": o.tipo_pieza, "nivel_educativo": o.nivel,
            "atributo": o.atributo, "genero": o.genero, "escudo": o.escudo, "ubicacion": o.ubicacion,
        },
        "color": color,
        "variantes": [
            {"talla": t, "precio": p, "origen_precio": precios.ORIGEN_DEL_MODELO, "costo": dict(o.costos).get(t)}
            for t, p in o.tallas
        ],
        "modelo": o.nombre,
    }


def marcar(session: Session, plan: PlanCopia, producto_id: int, valor: bool = True, **kwargs) -> PlanCopia:
    """Marca o desmarca una prenda del origen y vuelve a planear."""
    quitar = {p.origen.producto_id for p in plan.piezas if not p.marcada}
    if valor:
        quitar.discard(int(producto_id))
    else:
        quitar.add(int(producto_id))
    return replanear(session, plan, quitar=quitar, **kwargs)


def replanear(session: Session, plan: PlanCopia, **cambios) -> PlanCopia:
    """El mismo plan con lo que cambió (colores, color_de, quitar, confirmados)."""
    datos = {
        "colores": plan.colores,
        "color_de": plan.color_de,
        "quitar": {p.origen.producto_id for p in plan.piezas if not p.marcada},
        "confirmados": plan.confirmados,
        "escuela_nueva": plan.nueva_confirmada,
    }
    datos.update(cambios)
    destino = plan.destino_id if plan.destino_id is not None else plan.destino
    return planear_copia(session, plan.origen_id, destino, **datos)


# ── Guardar ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ResultadoCopia:
    alta: alta.ResultadoAlta = field(default_factory=alta.ResultadoAlta)
    #: «Chaleco Rojo X → Chaleco Azul X».
    cambiados: tuple[str, ...] = ()
    #: Las tallas de las prendas que cambiaron de color (para sus etiquetas).
    variantes_cambiadas: tuple[int, ...] = ()
    ligados: tuple[str, ...] = ()
    escuela: str = ""
    escuela_creada: bool = False
    ensayo: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    @property
    def productos(self) -> tuple[alta.ProductoCreado, ...]:
        return self.alta.productos

    @property
    def variantes_para_etiquetas(self) -> list[int]:
        return [t.variante_id for p in self.alta.productos for t in p.tallas] + list(self.variantes_cambiadas)

    def texto(self) -> str:
        if self.error:
            return f"No se guardó nada: {self.error}"
        lineas = [self.alta.texto()] if self.alta.productos else []
        lineas += [f"Cambia color: {c}" for c in self.cambiados]
        lineas += [f"Se liga al uniforme: {nombre}" for nombre in self.ligados]
        return "\n".join(lineas)


def _hacer(session: Session, plan: PlanCopia, usuario: Usuario, *, ensayo: bool) -> ResultadoCopia:
    resultado_alta = alta.ResultadoAlta(ensayo=ensayo)
    if plan.planes:
        resultado_alta = alta.aplicar(session, plan.planes, usuario, plan.origen_bitacora)
        resultado_alta = alta.ResultadoAlta(productos=resultado_alta.productos, ensayo=ensayo)
    escuela = _escuela(session, plan.destino)
    if escuela is None:
        raise ValueError(f"No existe la escuela «{plan.destino}».")
    cambiados, variantes = [], []
    for p in plan.cambian:
        r = corregir.aplicar_correccion(session, p.correccion, usuario, observacion=plan.origen_bitacora)
        cambiados.append(f"{p.destino_nombre} → {r.nombre}" if r.nombre != p.destino_nombre
                         else f"{r.nombre}: {p.destino_color} → {p.color}")
        variantes += [t.variante_id for t in p.correccion.tallas]
    ligados = []
    sueltas = [p for p in plan.ligan if p.estado != ESTADO_NUEVA]
    if sueltas:
        uni = uniforme_service.uniforme_de(session, escuela.id, crear=True)
        for p in sueltas:
            o = p.origen
            uniforme_service.agregar_pieza(
                session, uni.id, p.destino_id, grupo=o.grupo, obligatoria=o.obligatoria, orden=o.orden,
                color=o.color_uniforme,
            )
            ligados.append(p.nombre)
    session.flush()
    return ResultadoCopia(
        alta=resultado_alta, cambiados=tuple(cambiados), variantes_cambiadas=tuple(variantes),
        ligados=tuple(ligados), escuela=str(escuela.nombre), escuela_creada=plan.es_nueva, ensayo=ensayo,
    )


def aplicar_copia(session: Session, plan: PlanCopia, usuario: Usuario, *, commit: bool = False) -> ResultadoCopia:
    """Guarda la copia entera o nada (savepoint): altas, cambios de color,
    ligas al uniforme y recetas. Con `commit=True` hace commit al terminar."""
    errores = plan.todos_los_errores
    if errores:
        raise CopiaNoValida("\n".join(errores))
    if not plan.hay_cambios:
        raise CopiaNoValida("No hay nada que copiar.")
    CatalogService._validar_admin(usuario)
    with session.begin_nested():
        resultado = _hacer(session, plan, usuario, ensayo=False)
    if commit:
        session.commit()
    return resultado


def ensayar_copia(session: Session, plan: PlanCopia, usuario: Usuario) -> ResultadoCopia:
    """Hace la copia dentro de un savepoint y la deshace: devuelve exactamente
    lo que quedaría (SKU reales incluidos). Los errores van en `error`."""
    errores = plan.todos_los_errores
    if errores:
        return ResultadoCopia(ensayo=True, error="\n".join(errores))
    pendiente_antes = session.info.get(_MEILI_PENDIENTE)
    punto = session.begin_nested()
    try:
        CatalogService._validar_admin(usuario)
        resultado = _hacer(session, plan, usuario, ensayo=True)
    except (ValueError, PermissionError) as exc:
        resultado = ResultadoCopia(ensayo=True, error=str(exc))
    except IntegrityError:
        resultado = ResultadoCopia(ensayo=True, error="Ya hay algo guardado igual: vuelve a revisar la copia.")
    except SQLAlchemyError as exc:
        resultado = ResultadoCopia(ensayo=True, error=f"La base no dejó hacer el ensayo: {exc.__class__.__name__}.")
    finally:
        try:
            punto.rollback()
        except InvalidRequestError:
            pass
        if pendiente_antes is None:
            session.info.pop(_MEILI_PENDIENTE, None)
    return resultado


__all__ = [
    "CopiaNoValida",
    "ESTADO_CAMBIA_COLOR",
    "ESTADO_NUEVA",
    "ESTADO_SE_LIGA",
    "ESTADO_YA_ESTA",
    "EscuelaParaCopiar",
    "PiezaACopiar",
    "PiezaOrigen",
    "PlanCopia",
    "ResultadoCopia",
    "aplicar_copia",
    "clave_pieza",
    "ensayar_copia",
    "escuelas_parecidas",
    "escuelas_para_copiar",
    "filtrar_escuelas",
    "marcar",
    "nombre_sin_color",
    "piezas_de_escuela",
    "planear_copia",
    "replanear",
]
