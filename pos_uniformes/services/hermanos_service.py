"""El «modelo» de una prenda nueva y lo que le falta a una escuela.

Tanda 2 del rediseño de «Nueva prenda» (2026-11-13). En la caja, 72 de las
73 altas de escuela desde mayo ya tenían una prenda hermana (la misma pieza
en otra escuela del mismo nivel) y 44 salieron idénticas en tallas y precio
(`alta_datos.md` §8). Por eso el alta empieza buscando a qué se parece:

- `buscar_modelo` encuentra la prenda que sirve de molde: de las hermanas
  (misma pieza y nivel, otras escuelas) la que tiene el juego de tallas y
  precios que más se repite, con «igual en N escuelas». Si en ese nivel no
  hay ninguna, busca en los demás niveles y lo dice (`relajado`).
- `comparar_escuela` dice qué piezas «ya tiene» una escuela y cuáles «le
  faltan» comparada con las de su nivel («lo tienen 41 de 44»).
- `escuelas_sin_pieza` dice a qué escuelas del nivel les falta una pieza,
  para «hacer la misma para otras escuelas».

Solo lee, con pocas consultas (nada por fila). Es la lógica que antes vivía
en `buscar_hermanos.py` de la skill `alta-productos`.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

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
    Variante,
)
from pos_uniformes.services.catalog_service import CatalogService
from pos_uniformes.services.catalogo_valores_service import forma_oficial_talla, normalizar
from pos_uniformes.services.talla_orden_service import clave_talla

#: Cuántos moldes distintos se ofrecen además del elegido («Copiado de: ▾»).
MAX_ALTERNATIVAS = 3

_CENTAVO = Decimal("0.01")


def _dinero(valor: object) -> Decimal:
    return Decimal(str(valor)).quantize(_CENTAVO)


# ── Resultados ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TallaModelo:
    talla: str
    precio: Decimal


@dataclass(frozen=True)
class Modelo:
    """Una prenda que ya existe y sirve de molde."""

    producto_id: int
    nombre: str
    nombre_sin_escuela: str
    escuela_id: int | None
    escuela: str | None
    nivel: str | None
    tipo_pieza: str | None
    tipo_prenda: str | None
    atributo: str | None
    marca: str
    categoria: str
    genero: str | None
    escudo: str | None
    ubicacion: str | None
    color: str
    tallas: tuple[TallaModelo, ...]
    #: Cuántas escuelas (o prendas generales) tienen exactamente estas tallas y precios.
    iguales: int = 1
    #: El grupo y el orden que ocupa en el uniforme de su escuela, si está ligado.
    grupo_uniforme: str | None = None
    orden_uniforme: int | None = None

    @property
    def precios(self) -> dict[str, Decimal]:
        return {t.talla: t.precio for t in self.tallas}

    @property
    def texto_iguales(self) -> str:
        """«igual en 14 escuelas de primaria» / «igual en 1 escuela»."""
        sujeto = "escuela" if self.iguales == 1 else "escuelas"
        if self.escuela_id is None:
            sujeto = "prenda" if self.iguales == 1 else "prendas"
        nivel = f" de {self.nivel.lower()}" if self.nivel else ""
        return f"igual en {self.iguales} {sujeto}{nivel}"

    @property
    def texto_rango(self) -> str:
        """«10 tallas · $245 a $295»."""
        if not self.tallas:
            return "sin tallas"
        precios = [t.precio for t in self.tallas]
        n = len(self.tallas)
        tallas = f"{n} talla" if n == 1 else f"{n} tallas"
        lo, hi = min(precios), max(precios)
        rango = f"${lo:.0f}" if lo == hi else f"${lo:.0f} a ${hi:.0f}"
        return f"{tallas} · {rango}"


@dataclass(frozen=True)
class TallaEnHermanas:
    """Una talla y cuántas de las hermanas la tienen («la tienen 3 de 14»)."""

    talla: str
    prendas: int
    total: int

    @property
    def texto(self) -> str:
        return f"la tienen {self.prendas} de {self.total}"


@dataclass(frozen=True)
class Hermanas:
    tipo_pieza: str
    nivel: str | None
    modelo: Modelo | None
    alternativas: tuple[Modelo, ...] = ()
    #: Cuántas prendas hermanas hay (con al menos una talla activa).
    total: int = 0
    #: No había en el nivel pedido y se buscó en todos.
    relajado: bool = False
    #: Todas las tallas que tienen las hermanas, en orden, con cuántas la tienen.
    tallas: tuple[TallaEnHermanas, ...] = ()

    def cobertura(self, talla: str) -> TallaEnHermanas | None:
        clave = normalizar(forma_oficial_talla(talla))
        return next((t for t in self.tallas if normalizar(t.talla) == clave), None)

    @property
    def texto(self) -> str:
        if self.modelo is None:
            return f"No hay otra {self.tipo_pieza} para copiar: hay que poner tallas y precios."
        texto = f"Copiado de: {self.modelo.nombre} ({self.modelo.texto_iguales})"
        if self.relajado and self.nivel:
            texto += f". No hay en {self.nivel.lower()}; se tomó de otro nivel"
        return texto


@dataclass(frozen=True)
class PiezaComparada:
    tipo_pieza: str
    escuelas_con_ella: int
    escuelas_del_nivel: int
    #: Las prendas de la escuela de esa pieza (solo en «ya tiene»).
    productos: tuple[str, ...] = ()

    @property
    def texto(self) -> str:
        """«lo tienen 41 de 44»."""
        return f"lo tienen {self.escuelas_con_ella} de {self.escuelas_del_nivel}"


@dataclass(frozen=True)
class Comparacion:
    escuela_id: int
    escuela: str
    nivel: str
    ya_tiene: tuple[PiezaComparada, ...] = ()
    le_falta: tuple[PiezaComparada, ...] = ()
    escuelas_del_nivel: int = 0


@dataclass(frozen=True)
class EscuelaSinPieza:
    escuela_id: int
    escuela: str


@dataclass(frozen=True)
class SinPieza:
    tipo_pieza: str
    nivel: str
    escuelas: tuple[EscuelaSinPieza, ...] = ()
    escuelas_del_nivel: int = 0

    @property
    def texto(self) -> str:
        """«le falta a 13 de primaria»."""
        return f"le falta a {len(self.escuelas)} de {self.nivel.lower()}"


# ── Resolución de nombres ──────────────────────────────────────────────────

def _id_por_nombre(session: Session, modelo, valor: object) -> int | None:
    """Id de `modelo` por id o por nombre (sin mayúsculas ni acentos)."""
    if valor is None or valor == "":
        return None
    if isinstance(valor, int):
        return valor
    clave = normalizar(valor)
    filas = session.execute(select(modelo.id, modelo.nombre)).all()
    exactas = [i for i, n in filas if n == str(valor).strip()]
    if exactas:
        return int(exactas[0])
    parecidas = sorted((int(i) for i, n in filas if normalizar(n) == clave))
    return parecidas[0] if parecidas else None


# ── Modelo ─────────────────────────────────────────────────────────────────

def _filas_hermanas(session: Session, tipo_pieza_id: int, nivel_id: int | None):
    tpr = aliased(TipoPrenda)
    tpi = aliased(TipoPieza)
    stmt = (
        select(
            Producto.id, Producto.nombre, Producto.nombre_base, Producto.escuela_id,
            Escuela.nombre.label("escuela"), NivelEducativo.nombre.label("nivel"),
            tpr.nombre.label("prenda"), tpi.nombre.label("pieza"),
            AtributoProducto.nombre.label("atributo"), Marca.nombre.label("marca"),
            Categoria.nombre.label("categoria"), Producto.genero, Producto.escudo, Producto.ubicacion,
            Variante.talla, Variante.color, Variante.precio_venta,
        )
        .join(Variante, (Variante.producto_id == Producto.id) & Variante.activo.is_(True))
        .join(Marca, Marca.id == Producto.marca_id)
        .join(Categoria, Categoria.id == Producto.categoria_id)
        .outerjoin(Escuela, Escuela.id == Producto.escuela_id)
        .outerjoin(NivelEducativo, NivelEducativo.id == Producto.nivel_educativo_id)
        .outerjoin(tpr, tpr.id == Producto.tipo_prenda_id)
        .outerjoin(tpi, tpi.id == Producto.tipo_pieza_id)
        .outerjoin(AtributoProducto, AtributoProducto.id == Producto.atributo_id)
        .where(Producto.activo.is_(True), Producto.tipo_pieza_id == tipo_pieza_id)
    )
    if nivel_id is not None:
        stmt = stmt.where(Producto.nivel_educativo_id == nivel_id)
    return session.execute(stmt).all()


def _agrupar(filas) -> dict[int, dict]:
    productos: dict[int, dict] = {}
    for f in filas:
        p = productos.setdefault(int(f.id), {
            "fila": f, "precios": {}, "colores": Counter(),
        })
        talla = forma_oficial_talla(f.talla)
        precio = _dinero(f.precio_venta)
        # Si una talla está en dos colores con dos precios, cuenta el más alto
        # (nunca se sugiere bajar).
        if talla not in p["precios"] or precio > p["precios"][talla]:
            p["precios"][talla] = precio
        p["colores"][str(f.color or "Sin color")] += 1
    return productos


def _firma(p: dict) -> tuple:
    return tuple(sorted(p["precios"].items(), key=lambda tp: clave_talla(tp[0])))


def _modelo_de(pid: int, p: dict, iguales: int, ligas: dict[int, tuple[str, int]]) -> Modelo:
    f = p["fila"]
    nombre_guardado = f.nombre_base or f.nombre
    grupo, orden = ligas.get(pid, (None, None))
    return Modelo(
        producto_id=pid,
        nombre=str(f.nombre),
        nombre_sin_escuela=CatalogService.nombre_sin_escuela(nombre_guardado, f.escuela),
        escuela_id=int(f.escuela_id) if f.escuela_id is not None else None,
        escuela=f.escuela,
        nivel=f.nivel,
        tipo_pieza=f.pieza,
        tipo_prenda=f.prenda,
        atributo=f.atributo,
        marca=str(f.marca),
        categoria=str(f.categoria),
        genero=f.genero,
        escudo=f.escudo,
        ubicacion=f.ubicacion,
        color=p["colores"].most_common(1)[0][0] if p["colores"] else "Sin color",
        tallas=tuple(TallaModelo(t, precio) for t, precio in _firma(p)),
        iguales=iguales,
        grupo_uniforme=grupo,
        orden_uniforme=orden,
    )


def _ligas_al_uniforme(session: Session, producto_ids: list[int]) -> dict[int, tuple[str, int]]:
    if not producto_ids:
        return {}
    filas = session.execute(
        select(UniformePieza.producto_id, UniformePieza.grupo, UniformePieza.orden)
        .join(Uniforme, Uniforme.id == UniformePieza.uniforme_id)
        .where(
            UniformePieza.producto_id.in_(producto_ids),
            UniformePieza.activo.is_(True),
            Uniforme.activo.is_(True),
        )
        .order_by(UniformePieza.id)
    ).all()
    ligas: dict[int, tuple[str, int]] = {}
    for pid, grupo, orden in filas:
        ligas.setdefault(int(pid), (str(grupo), int(orden)))
    return ligas


def elegir_modelo(productos: dict[int, dict]) -> tuple[list[tuple[int, int]], dict[tuple, list[int]]]:
    """Puro: ordena los moldes. Devuelve [(producto_id representante, iguales)]
    del más repetido al menos, y los productos de cada firma.

    El más repetido es el juego de tallas y precios que más escuelas tienen
    igual; a empate, el de más tallas y luego el más reciente. El representante
    de cada juego es la prenda más reciente que lo tiene."""
    por_firma: dict[tuple, list[int]] = defaultdict(list)
    for pid, p in productos.items():
        por_firma[_firma(p)].append(pid)

    def dueños(pids: list[int]) -> int:
        return len({productos[pid]["fila"].escuela_id or -pid for pid in pids})

    orden = sorted(
        por_firma.items(),
        key=lambda kv: (dueños(kv[1]), len(kv[0]), max(kv[1])),
        reverse=True,
    )
    return [(max(pids), dueños(pids)) for _, pids in orden], dict(por_firma)


def buscar_modelo(
    session: Session,
    tipo_pieza: str | int,
    nivel: str | int | None = None,
    *,
    escuela_id: int | None = None,
    modelo_id: int | None = None,
) -> Hermanas:
    """El molde para una `tipo_pieza` nueva de `nivel` (sin contar la escuela
    `escuela_id`, que es la que la va a recibir).

    `modelo_id` fuerza el molde (el «Copiado de: ▾» de la pantalla); si no es
    de las hermanas, igual se usa. Son 2 o 3 consultas."""
    pieza_id = _id_por_nombre(session, TipoPieza, tipo_pieza)
    nivel_id = _id_por_nombre(session, NivelEducativo, nivel)
    nombre_pieza = str(tipo_pieza) if not isinstance(tipo_pieza, int) else ""
    nombre_nivel = str(nivel) if nivel not in (None, "") and not isinstance(nivel, int) else None
    if pieza_id is None:
        return Hermanas(tipo_pieza=nombre_pieza, nivel=nombre_nivel, modelo=None)

    def candidatas(nid: int | None) -> dict[int, dict]:
        productos = _agrupar(_filas_hermanas(session, pieza_id, nid))
        if escuela_id is not None:
            productos = {pid: p for pid, p in productos.items() if p["fila"].escuela_id != escuela_id}
        return productos

    relajado = False
    productos = candidatas(nivel_id)
    if not productos and nivel_id is not None:
        productos = candidatas(None)
        relajado = bool(productos)

    forzado: dict[int, dict] = {}
    if modelo_id is not None and int(modelo_id) not in productos:
        forzado = {
            pid: p
            for pid, p in _agrupar(_filas_hermanas(session, pieza_id, None)).items()
            if pid == int(modelo_id)
        }
        if not forzado:
            # Otra pieza («igual que esta, otro modelo»): se lee por id.
            pieza_del_forzado = session.scalar(select(Producto.tipo_pieza_id).where(Producto.id == int(modelo_id)))
            if pieza_del_forzado is not None:
                forzado = {
                    pid: p
                    for pid, p in _agrupar(_filas_hermanas(session, int(pieza_del_forzado), None)).items()
                    if pid == int(modelo_id)
                }

    if productos:
        any_fila = next(iter(productos.values()))["fila"]
        nombre_pieza = any_fila.pieza or nombre_pieza
        if not relajado and nivel_id is not None:
            nombre_nivel = any_fila.nivel or nombre_nivel
    elif not forzado:
        return Hermanas(tipo_pieza=nombre_pieza, nivel=nombre_nivel, modelo=None)

    ranking, por_firma = elegir_modelo(productos) if productos else ([], {})
    ligas = _ligas_al_uniforme(session, [pid for pid, _ in ranking] + list(forzado))
    moldes = [_modelo_de(pid, productos[pid], iguales, ligas) for pid, iguales in ranking]

    elegido: Modelo | None = moldes[0] if moldes else None
    if modelo_id is not None:
        mid = int(modelo_id)
        if mid in forzado:
            elegido = _modelo_de(mid, forzado[mid], 1, ligas)
        elif mid in productos:
            firma = _firma(productos[mid])
            iguales = len({productos[p]["fila"].escuela_id or -p for p in por_firma[firma]})
            elegido = _modelo_de(mid, productos[mid], iguales, ligas)
    alternativas = tuple(m for m in moldes if elegido is None or m.producto_id != elegido.producto_id)
    return Hermanas(
        tallas=_tallas_en_hermanas(productos),
        tipo_pieza=nombre_pieza,
        nivel=nombre_nivel,
        modelo=elegido,
        alternativas=alternativas[:MAX_ALTERNATIVAS],
        total=len(productos),
        relajado=relajado,
    )


def _tallas_en_hermanas(productos: dict[int, dict]) -> tuple[TallaEnHermanas, ...]:
    """Puro: cada talla de las hermanas y en cuántas está."""
    cuenta = Counter(t for p in productos.values() for t in p["precios"])
    total = len(productos)
    return tuple(
        TallaEnHermanas(t, n, total) for t, n in sorted(cuenta.items(), key=lambda tn: clave_talla(tn[0]))
    )


# ── Ya tiene / Le falta ────────────────────────────────────────────────────

def _reparto(session: Session):
    """(filas (escuela_id, producto_id, nivel_id, nivel), {producto_id: (nombre, pieza)})."""
    from pos_uniformes.services import escuela_piezas_service

    filas = escuela_piezas_service.productos_por_escuela(session)
    piezas = {
        int(pid): (str(nombre), str(pieza))
        for pid, nombre, pieza in session.execute(
            select(Producto.id, Producto.nombre, TipoPieza.nombre)
            .join(TipoPieza, TipoPieza.id == Producto.tipo_pieza_id)
            .where(Producto.activo.is_(True))
        ).all()
    }
    return filas, piezas


def _nivel_de(filas, escuela_id: int, nivel: str | None) -> str:
    niveles = sorted({str(n) for e, _p, _nid, n in filas if e == escuela_id})
    if nivel:
        for n in niveles + sorted({str(n) for *_x, n in filas}):
            if normalizar(n) == normalizar(nivel):
                return n
        return str(nivel)
    if len(niveles) == 1:
        return niveles[0]
    if not niveles:
        raise ValueError("La escuela todavía no tiene prendas: di de qué nivel es.")
    raise ValueError(f"La escuela tiene varios niveles ({', '.join(niveles)}): di cuál.")


def _piezas_por_escuela(filas, piezas, nivel: str) -> dict[int, dict[str, list[str]]]:
    por_escuela: dict[int, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for escuela_id, producto_id, _nid, nivel_nombre in filas:
        if normalizar(nivel_nombre) != normalizar(nivel):
            continue
        dato = piezas.get(int(producto_id))
        if dato is None:
            continue
        nombre, pieza = dato
        por_escuela[int(escuela_id)][pieza].append(nombre)
    return por_escuela


def comparar_escuela(session: Session, escuela_id: int, nivel: str | None = None) -> Comparacion:
    """Lo que la escuela ya tiene y lo que le falta, contra las demás de su nivel.

    Cuenta las prendas propias y las generales de su uniforme (igual que la
    matriz de Piezas). Si la escuela aún no tiene prendas, hay que decir el
    nivel."""
    filas, piezas = _reparto(session)
    nombre = session.scalar(select(Escuela.nombre).where(Escuela.id == int(escuela_id)))
    if nombre is None:
        raise ValueError("No existe la escuela.")
    nivel_nombre = _nivel_de(filas, int(escuela_id), nivel)
    por_escuela = _piezas_por_escuela(filas, piezas, nivel_nombre)
    propias = por_escuela.get(int(escuela_id), {})
    otras = {e: ps for e, ps in por_escuela.items() if e != int(escuela_id)}
    total = len(otras)
    cuenta = Counter(p for ps in otras.values() for p in ps)

    ya_tiene = tuple(
        PiezaComparada(p, cuenta.get(p, 0), total, tuple(sorted(propias[p])))
        for p in sorted(propias, key=lambda p: (-cuenta.get(p, 0), normalizar(p)))
    )
    le_falta = tuple(
        PiezaComparada(p, n, total)
        for p, n in sorted(cuenta.items(), key=lambda pn: (-pn[1], normalizar(pn[0])))
        if p not in propias
    )
    return Comparacion(
        escuela_id=int(escuela_id), escuela=str(nombre), nivel=nivel_nombre,
        ya_tiene=ya_tiene, le_falta=le_falta, escuelas_del_nivel=total,
    )


def escuelas_sin_pieza(session: Session, tipo_pieza: str, nivel: str) -> SinPieza:
    """Las escuelas del nivel que no tienen esa pieza («le falta a 13 de primaria»)."""
    filas, piezas = _reparto(session)
    por_escuela = _piezas_por_escuela(filas, piezas, nivel)
    clave = normalizar(tipo_pieza)
    faltan = [e for e, ps in por_escuela.items() if not any(normalizar(p) == clave for p in ps)]
    nombres = dict(
        session.execute(select(Escuela.id, Escuela.nombre).where(Escuela.id.in_(faltan))).all()
    ) if faltan else {}
    nivel_nombre = next(
        (str(n) for *_x, n in filas if normalizar(n) == normalizar(nivel)), str(nivel)
    )
    escuelas = tuple(
        EscuelaSinPieza(int(e), str(nombres.get(e, "")))
        for e in sorted(faltan, key=lambda e: normalizar(nombres.get(e, "")))
    )
    return SinPieza(tipo_pieza=str(tipo_pieza), nivel=nivel_nombre, escuelas=escuelas,
                    escuelas_del_nivel=len(por_escuela))
