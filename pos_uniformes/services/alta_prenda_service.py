"""El motor del alta: plan → ensayo → aplicar, todo junto o nada.

Tanda 2 del rediseño de «Nueva prenda» (2026-11-13). El asistente viejo
guardaba la prenda en una transacción y sus tallas en otra (si se cancelaba
en medio quedaba una prenda sin tallas), no la ligaba al uniforme ni a las
recetas, copiaba la misma existencia a todas las tallas como un ajuste que
ya no dejaba borrarlas, y la bitácora decía siempre «Producto creado.».

Aquí, la pantalla nueva (tanda 3) y la skill `alta-productos` dan de alta
exactamente igual:

1. **Plan** (`planear_desde_modelo`, `planear`, `planear_varias_escuelas`):
   un objeto con el nombre que se va a guardar (`CatalogService.armar_nombre`),
   las tallas con su precio y de dónde salió, los SKU previstos, el uniforme
   al que se liga, lo que pasa con las recetas, avisos (ámbar, no frenan) y
   errores (frenan). Los valores de catálogo se revisan con
   `catalogo_valores_service`: nada se crea si no se confirmó.
2. **Ensayo** (`ensayar`): hace todo dentro de un savepoint y lo deshace;
   devuelve exactamente lo que se crearía (SKU reales incluidos).
3. **Aplicar** (`aplicar`): producto, tallas, liga al uniforme, receta y
   existencia inicial en un solo savepoint: si algo falla no queda nada.
   La existencia inicial entra como una ENTRADA normal por talla (corregible;
   la talla se puede borrar después). La bitácora dice el origen («Alta desde
   POS · modelo: Pants Suelto Miguel Hidalgo», «Claude», «Copia de escuela…»).

Reglas de Daniel: tallas y colores nuevos en una sola forma; el 5/9 solo se
sugiere; nunca se baja un precio (aquí solo se crean tallas nuevas; una
receta que ya existe no se toca); escuelas nuevas y altas solo ADMIN.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from types import SimpleNamespace
from typing import Iterable, Mapping, Sequence

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError, SQLAlchemyError
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    AtributoProducto,
    Categoria,
    ConjuntoComponente,
    Escuela,
    Marca,
    NivelEducativo,
    Producto,
    TipoPieza,
    TipoPrenda,
    Usuario,
    Variante,
)
from pos_uniformes.services import catalogo_valores_service as valores
from pos_uniformes.services import conjunto_service, hermanos_service, uniforme_service
from pos_uniformes.services import precio_sugerido_service as precios
from pos_uniformes.services.catalog_service import _MEILI_PENDIENTE, CatalogService
from pos_uniformes.services.inventario_service import InventarioService
from pos_uniformes.services.talla_orden_service import clave_talla

ORIGEN_POS = "Alta desde POS"
ORIGEN_CLAUDE = "Claude (skill alta-productos)"
REFERENCIA_ENTRADA = CatalogService.REFERENCIA_ALTA_ENTRADA
SIN_COLOR = "Sin color"


def origen_copia_escuela(origen: str, destino: str) -> str:
    return f"Copia de escuela: {origen} → {destino}"


class AltaNoValida(ValueError):
    """El plan tiene errores: no se guarda nada."""


# ── Plan ───────────────────────────────────────────────────────────────────

@dataclass
class TallaPlan:
    """Una talla del plan. Sus avisos viven aquí y no se repiten en
    `PlanPrenda.avisos` (que son los de toda la prenda)."""

    talla: str
    precio: Decimal | None
    origen_precio: str = precios.ORIGEN_A_MANO
    llegan: int = 0
    costo: Decimal | None = None
    #: El precio del modelo para esta talla (para recalcular «de dónde»).
    precio_modelo: Decimal | None = None
    # Calculado por `completar`:
    #: El que más se repite en la base y en cuántas prendas («volver al de
    #: las demás: $295, en 41 prendas»).
    moda: Decimal | None = None
    prendas_con_moda: int = 0
    sugerencia_5_9: Decimal | None = None
    #: Ámbar, no frena («Queda más bajo que en las demás escuelas ($295).»).
    aviso: str = ""
    #: Frena («Falta el precio.», «El precio no puede quedar en $0.»).
    error: str = ""
    sku: str = ""  # previsto (el real sale del ensayo)
    #: «la tienen 3 de 14» (cuántas hermanas tienen esta talla).
    texto_cobertura: str = ""


@dataclass
class PlanPrenda:
    nombre_sin_escuela: str
    escuela: str | None
    categoria: str
    marca: str
    tipo_prenda: str | None = None
    tipo_pieza: str | None = None
    nivel: str | None = None
    atributo: str | None = None
    genero: str | None = None
    escudo: str | None = None
    ubicacion: str | None = None
    descripcion: str | None = None
    color: str = SIN_COLOR
    tallas: list[TallaPlan] = field(default_factory=list)
    #: Tallas que tienen las hermanas pero no el modelo (o que se quitaron),
    #: desmarcadas, con su precio sugerido y «la tienen 3 de 14». Se pasan a
    #: `tallas` con `marcar_talla`.
    tallas_posibles: list[TallaPlan] = field(default_factory=list)
    ligar: bool = True
    grupo: str | None = None
    orden: int | None = None
    obligatoria: bool = True
    modelo_id: int | None = None
    modelo_nombre: str | None = None
    modelo_texto: str = ""
    #: Otros moldes para «Copiado de: ▾» (se elige con `modelo_id`).
    alternativas: tuple[hermanos_service.Modelo, ...] = ()
    #: Cuántos SKU reservan los planes anteriores del mismo lote.
    saltar_skus: int = 0
    #: Valores nuevos que el usuario confirmó crear («Es otro, crearlo»).
    confirmados: tuple[str, ...] = ()
    #: Origen propio para la bitácora (gana sobre el de `aplicar`).
    origen: str | None = None
    #: Avisos y errores que pone quien arma el plan (sin modelo, lote) y que
    #: `completar` conserva cada vez que se vuelve a llamar.
    avisos_fijos: list[str] = field(default_factory=list)
    errores_fijos: list[str] = field(default_factory=list)
    # Calculado por `completar`:
    escuela_id: int | None = None
    nombre: str = ""
    grupo_previsto: str | None = None
    receta_texto: str = ""
    #: De toda la prenda (los de cada talla están en `TallaPlan.aviso/error`).
    avisos: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)

    @property
    def puede_aplicar(self) -> bool:
        return not self.todos_los_errores

    @property
    def todos_los_errores(self) -> list[str]:
        """Los de la prenda y los de cada talla, en texto (para la skill)."""
        return list(self.errores) + [f"Talla {t.talla}: {_minuscula(t.error)}" for t in self.tallas if t.error]

    @property
    def todos_los_avisos(self) -> list[str]:
        return list(self.avisos) + [f"Talla {t.talla}: {_minuscula(t.aviso)}" for t in self.tallas if t.aviso]

    @property
    def es_conjunto(self) -> bool:
        return (self.tipo_pieza or "") in conjunto_service.TIPOS_CONJUNTO

    @property
    def skus_previstos(self) -> list[str]:
        return [t.sku for t in self.tallas]

    @property
    def texto_rango(self) -> str:
        """«10 tallas · $245 a $295»."""
        con_precio = [t.precio for t in self.tallas if t.precio is not None]
        n = len(self.tallas)
        tallas = f"{n} talla" if n == 1 else f"{n} tallas"
        if not con_precio:
            return tallas
        lo, hi = min(con_precio), max(con_precio)
        return f"{tallas} · " + (f"${lo:.0f}" if lo == hi else f"${lo:.0f} a ${hi:.0f}")

    @property
    def resumen(self) -> str:
        """La frase para confirmar: «Se crean 10 tallas de … de $245 a $295.
        Quedan en su uniforme Deportivo.»"""
        n = len(self.tallas)
        verbo = "Se crea 1 talla" if n == 1 else f"Se crean {n} tallas"
        texto = f"{verbo} de {self.nombre}"
        con_precio = [t.precio for t in self.tallas if t.precio is not None]
        if con_precio:
            lo, hi = min(con_precio), max(con_precio)
            texto += f", a ${lo:.0f}" if lo == hi else f", de ${lo:.0f} a ${hi:.0f}"
        texto += "."
        if self.escuela and self.ligar:
            texto += f" Quedan en su uniforme {self.grupo or self.grupo_previsto or ''}".rstrip() + "."
        return texto


def _minuscula(texto: str) -> str:
    return texto[:1].lower() + texto[1:]


def origen_bitacora(plan: PlanPrenda, origen: str | None = None) -> str:
    """«Alta desde POS · modelo: Pants Suelto Miguel Hidalgo»."""
    partes = [(plan.origen or origen or ORIGEN_POS).strip()]
    if plan.modelo_nombre:
        partes.append(f"modelo: {plan.modelo_nombre}")
    return " · ".join(partes)


def cambiar_color_en_nombre(nombre: str, color_viejo: str | None, color_nuevo: str | None) -> str:
    """«Suéter Botones M Rojo» → «Suéter Botones M Azul». Si el nombre no lleva
    el color, se queda igual (el color vive donde lo tenga el modelo)."""
    viejo = valores.normalizar(color_viejo)
    if not viejo or not color_nuevo or viejo == valores.normalizar(SIN_COLOR):
        return nombre
    if viejo == valores.normalizar(color_nuevo):
        return nombre
    palabras = str(nombre or "").split()
    claves = [valores.normalizar(p) for p in palabras]
    buscado = viejo.split()
    # «Blanca» en el nombre cuando el color guardado es «Blanco».
    alternas = {tuple(buscado)}
    if buscado and buscado[-1].endswith("o"):
        alternas.add(tuple(buscado[:-1] + [buscado[-1][:-1] + "a"]))
    if buscado and buscado[-1].endswith("a"):
        alternas.add(tuple(buscado[:-1] + [buscado[-1][:-1] + "o"]))
    n = len(buscado)
    for i in range(len(claves) - n + 1):
        if tuple(claves[i : i + n]) in alternas:
            return " ".join(palabras[:i] + [str(color_nuevo).strip()] + palabras[i + n :])
    return nombre


# ── Completar y revisar un plan ────────────────────────────────────────────

_CAMPOS = (
    (valores.CAMPO_ESCUELA, "escuela"),
    (valores.CAMPO_CATEGORIA, "categoria"),
    (valores.CAMPO_TIPO_PRENDA, "tipo_prenda"),
    (valores.CAMPO_TIPO_PIEZA, "tipo_pieza"),
    (valores.CAMPO_NIVEL, "nivel"),
    (valores.CAMPO_ATRIBUTO, "atributo"),
)


class _Usos:
    """Los valores que ya existen, leídos una vez por lote de planes."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self._cache: dict[str, dict[str, int]] = {}
        self._marcas: list[str] | None = None
        self._precios: dict[tuple, dict] = {}

    def de(self, campo: str) -> dict[str, int]:
        if campo not in self._cache:
            self._cache[campo] = valores.contar_usos(self.session, campo)
        return self._cache[campo]

    def marcas(self) -> list[str]:
        if self._marcas is None:
            self._marcas = [str(n) for n in self.session.scalars(select(Marca.nombre)).all()]
        return self._marcas

    def precios(self, pieza_id: int | None, nivel_id: int | None, excluir: int | None) -> dict:
        clave = (pieza_id, nivel_id, excluir)
        if clave not in self._precios:
            self._precios[clave] = (
                precios.precios_de_la_base(self.session, pieza_id, nivel_id, excluir_escuela_id=excluir)
                if pieza_id is not None
                else {}
            )
        return self._precios[clave]


def _id_de(session: Session, modelo, nombre: str | None) -> int | None:
    if not nombre:
        return None
    return session.scalar(select(modelo.id).where(modelo.nombre == nombre))


def _confirmado(plan: PlanPrenda, texto: str) -> bool:
    clave = valores.normalizar(texto)
    return any(valores.normalizar(c) == clave for c in plan.confirmados)


def _revisar_valores(plan: PlanPrenda, usos: _Usos) -> None:
    for campo, atributo in _CAMPOS:
        texto = valores.limpiar(getattr(plan, atributo))
        if not texto:
            setattr(plan, atributo, None)
            continue
        existentes = usos.de(campo)
        if texto in existentes:
            setattr(plan, atributo, texto)  # tal cual existe (copiado del modelo)
            continue
        rev = valores.revisar_valor(campo, texto, existentes)
        if rev.estado == valores.ESTADO_OK and rev.valor in existentes:
            setattr(plan, atributo, rev.valor)
        elif _confirmado(plan, texto):
            setattr(plan, atributo, texto)
            plan.avisos.append(f"Se crea «{texto}» como {valores.ETIQUETA_CAMPO[campo]} nueva.")
        else:
            plan.errores.append(rev.texto_pregunta())
    marca = valores.limpiar(plan.marca)
    if not marca:
        plan.errores.append("Falta la marca.")
    else:
        por_clave = {valores.normalizar(m): m for m in usos.marcas()}
        if marca in usos.marcas():
            pass
        elif valores.normalizar(marca) in por_clave:
            plan.marca = por_clave[valores.normalizar(marca)]
        elif _confirmado(plan, marca):
            plan.avisos.append(f"Se crea «{marca}» como marca nueva.")
        else:
            plan.errores.append(f"«{marca}» no existe como marca. Elígela de la lista o confirma que es nueva.")
    if not plan.categoria:
        plan.errores.append("Falta la categoría.")


def _revisar_tallas_y_color(plan: PlanPrenda, usos: _Usos) -> None:
    color = valores.forma_oficial_color(plan.color) or SIN_COLOR
    if color != SIN_COLOR:
        colores = usos.de(valores.CAMPO_COLOR)
        rev = valores.revisar_valor(valores.CAMPO_COLOR, color, colores)
        if not (color in colores or rev.estado == valores.ESTADO_OK or _confirmado(plan, color)):
            plan.errores.append(rev.texto_pregunta())
        elif rev.estado == valores.ESTADO_OK:
            color = rev.valor
    if color != plan.color and plan.color:
        plan.avisos.append(f"El color «{plan.color}» se guarda como «{color}».")
    plan.color = color

    if not plan.tallas:
        plan.errores.append("Marca al menos una talla.")
    existentes = usos.de(valores.CAMPO_TALLA)
    vistas: set[str] = set()
    for t in plan.tallas:
        oficial = valores.forma_oficial_talla(t.talla)
        if not oficial:
            plan.errores.append("Hay una talla vacía.")
            continue
        if oficial != t.talla:
            plan.avisos.append(f"La talla «{t.talla}» se guarda como «{oficial}».")
            t.talla = oficial
        rev = valores.revisar_valor(valores.CAMPO_TALLA, oficial, existentes)
        if not (oficial in existentes or rev.estado == valores.ESTADO_OK or _confirmado(plan, oficial)):
            plan.errores.append(f"La talla «{oficial}» no existe todavía. Elige una de la lista o confirma que es nueva.")
        if valores.normalizar(oficial) in vistas:
            plan.errores.append(f"La talla «{oficial}» está dos veces.")
        vistas.add(valores.normalizar(oficial))
        if t.llegan < 0:
            plan.errores.append(f"Talla {oficial}: lo que llega no puede ser negativo.")
        if t.costo is not None and t.costo < 0:
            plan.errores.append(f"Talla {oficial}: el costo no puede ser negativo.")
    if plan.es_conjunto and any(t.llegan for t in plan.tallas):
        plan.errores.append(
            f"{plan.tipo_pieza} no tiene existencia propia: se arma de sus piezas. Da entrada a las piezas."
        )


def _revisar_precios(plan: PlanPrenda, usos: _Usos) -> None:
    """Cada talla: la moda de la base, de dónde sale su precio (se recalcula
    si se editó), su sugerencia 5/9, su aviso y su error. Nada se repite en
    `plan.avisos`."""
    pieza_id = _id_de(usos.session, TipoPieza, plan.tipo_pieza)
    nivel_id = _id_de(usos.session, NivelEducativo, plan.nivel)
    conteos = usos.precios(pieza_id, nivel_id, plan.escuela_id)
    for t in plan.tallas_posibles:  # desmarcadas: solo su precio y aviso
        t.precio = precios.dinero(t.precio)
        contador = conteos.get(t.talla)
        t.moda = precios.moda(contador) if contador else None
        t.prendas_con_moda = int(contador.get(t.moda, 0)) if contador and t.moda is not None else 0
        t.origen_precio = precios.origen_de(t.precio, t.moda, t.precio_modelo, t.origen_precio)
        t.sugerencia_5_9 = precios._sugerencia(t.precio, t.moda)
        t.aviso, t.error, t.sku = "", "", ""
    for t in plan.tallas:
        t.precio = precios.dinero(t.precio)
        contador = conteos.get(t.talla)
        t.moda = precios.moda(contador) if contador else None
        t.prendas_con_moda = int(contador.get(t.moda, 0)) if contador and t.moda is not None else 0
        t.origen_precio = precios.origen_de(t.precio, t.moda, t.precio_modelo, t.origen_precio)
        t.sugerencia_5_9 = precios._sugerencia(t.precio, t.moda)
        t.aviso, t.error = "", ""
        if t.precio is None:
            t.error = "Falta el precio."
        elif t.precio <= 0:
            t.error = "El precio no puede quedar en $0."
        else:
            t.aviso = precios.aviso_precio(t.precio, t.moda)


@dataclass(frozen=True)
class RecetasDeLaEscuela:
    """Qué pasa con los conjuntos (Pants 3pz, Chamarra) de la escuela al dar
    de alta una de sus piezas. Una sola regla para el plan y para `aplicar`."""

    #: Sin receta y sin existencia propia: su receta se completa.
    completar: tuple[Producto, ...] = ()
    #: Sin receta pero con existencia propia: NO se tocan (armar su receta
    #: pondría su existencia en la calculada de sus piezas y se perdería lo
    #: contado). Se avisa.
    con_existencia: tuple[tuple[Producto, int], ...] = ()

    def avisos(self) -> list[str]:
        return [
            f"«{c.nombre}» tiene {n} en existencia propia: su receta no se arma sola para no perderla. "
            "Ármala en Uniformes por escuela."
            for c, n in self.con_existencia
        ]


def recetas_de_la_escuela(session: Session, escuela_id: int | None, tipo_pieza: str | None) -> RecetasDeLaEscuela:
    """Los conjuntos activos de la escuela cuya receta lleva `tipo_pieza` y
    todavía no tienen receta (una receta que ya existe no se pisa). Tres
    consultas, nada por fila."""
    if escuela_id is None or not tipo_pieza:
        return RecetasDeLaEscuela()
    candidatos = [
        c for c in _conjuntos_de_la_escuela(session, escuela_id)
        if tipo_pieza in {t for t, _ in conjunto_service.RECETAS_POR_TIPO.get(conjunto_service.tipo_pieza(c), ())}
    ]
    if not candidatos:
        return RecetasDeLaEscuela()
    ids = [int(c.id) for c in candidatos]
    con_receta = set(
        session.scalars(
            select(ConjuntoComponente.conjunto_id).where(ConjuntoComponente.conjunto_id.in_(ids)).distinct()
        ).all()
    )
    existencia: dict[int, list[int]] = {}
    for pid, stock in session.execute(
        select(Variante.producto_id, Variante.stock_actual).where(
            Variante.producto_id.in_(ids), Variante.activo.is_(True)
        )
    ).all():
        existencia.setdefault(int(pid), []).append(int(stock or 0))
    completar, con_existencia = [], []
    for c in candidatos:
        if c.id in con_receta:
            continue  # ajustada a mano o ya armada: no se pisa
        stocks = existencia.get(int(c.id), [])
        if any(stocks):
            con_existencia.append((c, sum(x for x in stocks if x > 0)))
        else:
            completar.append(c)
    return RecetasDeLaEscuela(tuple(completar), tuple(con_existencia))


def _receta_prevista(session: Session, plan: PlanPrenda) -> str:
    if plan.es_conjunto:
        faltan = conjunto_service.piezas_que_faltan(session, plan.escuela_id, plan.tipo_pieza or "", plan.nombre)
        if faltan:
            return (
                f"Receta {plan.tipo_pieza}: no se puede armar todavía, falta {', '.join(faltan)} "
                "en la escuela (la prenda sí se crea)."
            )
        return f"Receta {plan.tipo_pieza}: se propone con las piezas de la escuela."
    recetas = recetas_de_la_escuela(session, plan.escuela_id, plan.tipo_pieza)
    plan.avisos.extend(recetas.avisos())
    if not recetas.completar:
        return ""
    tipos = sorted({conjunto_service.tipo_pieza(c) for c in recetas.completar})
    return "Receta " + " y ".join(tipos) + ": se completa."


def _conjuntos_de_la_escuela(session: Session, escuela_id: int) -> list[Producto]:
    return list(
        session.scalars(
            select(Producto)
            .join(TipoPieza, TipoPieza.id == Producto.tipo_pieza_id)
            .where(
                Producto.escuela_id == int(escuela_id),
                Producto.activo.is_(True),
                TipoPieza.nombre.in_(conjunto_service.TIPOS_CONJUNTO),
            )
            .order_by(Producto.id)
        ).all()
    )


def completar(
    session: Session, plan: PlanPrenda, *, saltar_skus: int | None = None, usos: _Usos | None = None
) -> PlanPrenda:
    """Revisa el plan y le pone nombre, SKU previstos, uniforme, receta,
    avisos y errores. No escribe nada; se puede volver a llamar después de
    editar el plan. `saltar_skus`: cuántos SKU ya se reservaron los planes
    anteriores del mismo lote (se guarda en el plan)."""
    if saltar_skus is not None:
        plan.saltar_skus = int(saltar_skus)
    saltar_skus = plan.saltar_skus
    usos = usos or _Usos(session)
    plan.avisos, plan.errores = list(plan.avisos_fijos), list(plan.errores_fijos)
    _revisar_valores(plan, usos)
    plan.escuela_id = _id_de(session, Escuela, plan.escuela)
    _revisar_tallas_y_color(plan, usos)
    _revisar_precios(plan, usos)

    base = valores.limpiar(plan.nombre_sin_escuela)
    if not base:
        plan.errores.append("Falta el nombre de la prenda.")
    plan.nombre = CatalogService.armar_nombre(base, plan.escuela) if base else ""
    plan.nombre_sin_escuela = CatalogService.nombre_sin_escuela(plan.nombre, plan.escuela) if base else ""
    marca_id = _id_de(session, Marca, plan.marca)
    if plan.nombre and marca_id is not None:
        if session.scalar(select(Producto.id).where(Producto.nombre == plan.nombre, Producto.marca_id == marca_id)):
            plan.errores.append(f"Ya existe «{plan.nombre}».")
    if plan.escuela_id is not None and plan.tipo_pieza:
        ya = session.scalars(
            select(Producto.nombre)
            .join(TipoPieza, TipoPieza.id == Producto.tipo_pieza_id)
            .where(
                Producto.escuela_id == plan.escuela_id,
                Producto.activo.is_(True),
                TipoPieza.nombre == plan.tipo_pieza,
                Producto.nombre != plan.nombre,
            )
        ).all()
        if ya:
            plan.avisos.append(f"La escuela ya tiene {', '.join(f'«{n}»' for n in ya)}.")

    if plan.escuela and plan.ligar:
        stub = SimpleNamespace(
            tipo_prenda=SimpleNamespace(nombre=plan.tipo_prenda or "") if plan.tipo_prenda else None,
            tipo_pieza=SimpleNamespace(nombre=plan.tipo_pieza or "") if plan.tipo_pieza else None,
        )
        plan.grupo_previsto = plan.grupo or uniforme_service.grupo_para(stub)
        if plan.grupo and plan.grupo not in uniforme_service.GRUPOS:
            plan.errores.append(f"El grupo «{plan.grupo}» no existe en el uniforme.")
    else:
        plan.grupo_previsto = None
    plan.receta_texto = _receta_prevista(session, plan)

    skus = CatalogService.preview_next_skus(session, saltar_skus + len(plan.tallas))[saltar_skus:]
    for t, sku in zip(plan.tallas, skus):
        t.sku = sku
    return plan


# ── Armar planes ───────────────────────────────────────────────────────────

def _niveles_de_la_escuela(session: Session, escuela_id: int | None) -> list[str]:
    """Los niveles de las prendas activas de la escuela, del que más tiene al que menos."""
    if escuela_id is None:
        return []
    filas = session.execute(
        select(NivelEducativo.nombre, func.count(Producto.id))
        .join(Producto, Producto.nivel_educativo_id == NivelEducativo.id)
        .where(Producto.escuela_id == int(escuela_id), Producto.activo.is_(True))
        .group_by(NivelEducativo.nombre)
        .order_by(func.count(Producto.id).desc(), NivelEducativo.nombre)
    ).all()
    return [str(n) for n, _c in filas]


def _texto(valor: object) -> str | None:
    texto = valores.limpiar(valor)
    return texto or None


def planear(
    session: Session,
    spec: Mapping,
    *,
    confirmados: Iterable[str] = (),
    saltar_skus: int = 0,
    usos: _Usos | None = None,
) -> PlanPrenda:
    """Un plan desde una especificación (la de la skill `alta-productos`):

        {"producto": {"nombre": "Pants 2pz Deportivo", "categoria": …, "marca": …,
                      "escuela": …|None, "tipo_prenda", "tipo_pieza", "nivel_educativo",
                      "atributo", "genero", "escudo", "ubicacion", "descripcion"},
         "color": "Sin color",
         "variantes": [{"talla": "10", "precio": 650, "costo": 400, "llegan": 3}, …],
         "uniforme": {"grupo": "Deportivo", "orden": 2, "obligatoria": true} | false,
         "modelo": "nombre del modelo", "modelo_id": 12, "origen": "…"}

    Sin «uniforme», una prenda de escuela se liga a su uniforme con el grupo
    que le toca; con `"uniforme": false`, no se liga."""
    prod = dict(spec.get("producto") or {})
    uniforme = spec.get("uniforme", {})
    tallas = [
        TallaPlan(
            talla=valores.limpiar(v.get("talla")),
            precio=precios.dinero(v.get("precio")),
            origen_precio=str(v.get("origen_precio") or precios.ORIGEN_A_MANO),
            llegan=int(v.get("llegan", v.get("stock", 0)) or 0),
            costo=precios.dinero(v.get("costo")),
        )
        for v in (spec.get("variantes") or [])
    ]
    plan = PlanPrenda(
        nombre_sin_escuela=valores.limpiar(prod.get("nombre")),
        escuela=_texto(prod.get("escuela") or spec.get("escuela")),
        categoria=valores.limpiar(prod.get("categoria")),
        marca=valores.limpiar(prod.get("marca")),
        tipo_prenda=_texto(prod.get("tipo_prenda")),
        tipo_pieza=_texto(prod.get("tipo_pieza")),
        nivel=_texto(prod.get("nivel_educativo") or prod.get("nivel")),
        atributo=_texto(prod.get("atributo")),
        genero=_texto(prod.get("genero")),
        escudo=_texto(prod.get("escudo")),
        ubicacion=_texto(prod.get("ubicacion")),
        descripcion=_texto(prod.get("descripcion")),
        color=valores.limpiar(spec.get("color")) or SIN_COLOR,
        tallas=tallas,
        ligar=uniforme is not False,
        grupo=(uniforme or {}).get("grupo") if isinstance(uniforme, Mapping) else None,
        orden=(uniforme or {}).get("orden") if isinstance(uniforme, Mapping) else None,
        obligatoria=bool((uniforme or {}).get("obligatoria", True)) if isinstance(uniforme, Mapping) else True,
        modelo_id=spec.get("modelo_id"),
        modelo_nombre=_texto(spec.get("modelo")),
        confirmados=tuple(confirmados) + tuple(spec.get("confirmados") or ()),
        origen=_texto(spec.get("origen")),
    )
    return completar(session, plan, saltar_skus=saltar_skus, usos=usos)


def _talla_sugerida(s, m, hermanas, llegan: Mapping, costos: Mapping) -> TallaPlan:
    cobertura = hermanas.cobertura(s.talla)
    return TallaPlan(
        talla=s.talla, precio=s.precio, origen_precio=s.origen,
        llegan=int(llegan.get(s.talla, 0)), costo=costos.get(s.talla),
        precio_modelo=(m.precios.get(s.talla) if m else None),
        texto_cobertura=cobertura.texto if cobertura else "",
    )


def _ordenar(tallas: list[TallaPlan]) -> None:
    tallas.sort(key=lambda t: clave_talla(t.talla))


def marcar_talla(session: Session, plan: PlanPrenda, talla: str, *, usos: _Usos | None = None) -> PlanPrenda:
    """Pasa una talla de `tallas_posibles` a `tallas` (la fila gris «EXG $305,
    la tienen 1 de 4» que se marca) y vuelve a completar el plan."""
    clave = valores.normalizar(valores.forma_oficial_talla(talla))
    t = next((t for t in plan.tallas_posibles if valores.normalizar(t.talla) == clave), None)
    if t is None:
        raise ValueError(f"La talla «{talla}» no está entre las que se pueden agregar.")
    plan.tallas_posibles.remove(t)
    plan.tallas.append(t)
    _ordenar(plan.tallas)
    return completar(session, plan, usos=usos)


def desmarcar_talla(session: Session, plan: PlanPrenda, talla: str, *, usos: _Usos | None = None) -> PlanPrenda:
    """Lo contrario de `marcar_talla`: la talla queda gris, con su precio."""
    clave = valores.normalizar(valores.forma_oficial_talla(talla))
    t = next((t for t in plan.tallas if valores.normalizar(t.talla) == clave), None)
    if t is None:
        raise ValueError(f"La talla «{talla}» no está marcada.")
    plan.tallas.remove(t)
    t.llegan = 0
    plan.tallas_posibles.append(t)
    _ordenar(plan.tallas_posibles)
    return completar(session, plan, usos=usos)


def planear_desde_modelo(
    session: Session,
    escuela: str | int,
    tipo_pieza: str,
    *,
    nivel: str | None = None,
    modelo_id: int | None = None,
    color: str | None = None,
    nombre: str | None = None,
    tallas: Sequence[str] | None = None,
    quitar_tallas: Iterable[str] = (),
    precios_a_mano: Mapping[str, object] | None = None,
    llegan: Mapping[str, int] | None = None,
    costos: Mapping[str, object] | None = None,
    preferir: str = precios.PREFERIR_BASE,
    confirmados: Iterable[str] = (),
    saltar_skus: int = 0,
    usos: _Usos | None = None,
) -> PlanPrenda:
    """(a) Una prenda para una escuela, copiada de su modelo.

    Las tallas son las del modelo (o `tallas`, menos `quitar_tallas`); el
    precio de cada una, el que más se repite en la base para la pieza y el
    nivel («como las demás»), si no el del modelo, o `precios_a_mano`.
    `preferir="modelo"` copia los precios del modelo (escuela igual a otra)."""
    if isinstance(escuela, int):
        escuela_id = escuela
        escuela_nombre = session.scalar(select(Escuela.nombre).where(Escuela.id == escuela))
        if escuela_nombre is None:
            raise ValueError("No existe la escuela.")
    else:
        escuela_nombre = valores.limpiar(escuela)
        escuela_id = _id_de(session, Escuela, escuela_nombre)
    errores_fijos: list[str] = []
    if not nivel:
        # Sin nivel se toma el de la escuela; si tiene varios no se adivina
        # (copiaría el modelo y los precios de otro nivel sin avisar).
        niveles = _niveles_de_la_escuela(session, escuela_id)
        if len(niveles) == 1:
            nivel = niveles[0]
        elif len(niveles) > 1:
            errores_fijos.append(f"La escuela tiene {' y '.join(sorted(niveles))}: di de qué nivel es la prenda.")
    hermanas = hermanos_service.buscar_modelo(
        session, tipo_pieza, nivel, escuela_id=escuela_id, modelo_id=modelo_id
    )
    m = hermanas.modelo
    nivel = nivel or (m.nivel if m else None)
    lista = [valores.forma_oficial_talla(t) for t in (tallas if tallas is not None else (
        [t.talla for t in m.tallas] if m else []
    ))]
    fuera = {valores.normalizar(valores.forma_oficial_talla(t)) for t in quitar_tallas}
    lista = [t for t in lista if valores.normalizar(t) not in fuera]

    marcadas = {valores.normalizar(t) for t in lista}
    posibles = [t.talla for t in hermanas.tallas if valores.normalizar(t.talla) not in marcadas]
    posibles += [t.talla for t in (m.tallas if m else ()) if valores.normalizar(t.talla) not in marcadas
                 and t.talla not in posibles]
    posibles.sort(key=clave_talla)

    pieza_id = _id_de(session, TipoPieza, hermanas.tipo_pieza or tipo_pieza)
    nivel_id = _id_de(session, NivelEducativo, nivel)
    todas = precios.sugerir(
        session, pieza_id, nivel_id, lista + posibles,
        modelo=m.precios if m else None, a_mano=precios_a_mano, preferir=preferir,
        excluir_escuela_id=escuela_id,
    )
    sugeridos, sugeridos_posibles = todas[: len(lista)], todas[len(lista):]
    llegan = {valores.forma_oficial_talla(k): int(v or 0) for k, v in (llegan or {}).items()}
    costos = {valores.forma_oficial_talla(k): precios.dinero(v) for k, v in (costos or {}).items()}
    color_final = valores.limpiar(color) or (m.color if m else SIN_COLOR)
    if nombre:
        base = nombre
    elif m:
        base = cambiar_color_en_nombre(m.nombre_sin_escuela, m.color, color_final)
    else:
        base = hermanas.tipo_pieza or tipo_pieza
    plan = PlanPrenda(
        nombre_sin_escuela=base,
        escuela=escuela_nombre,
        categoria=m.categoria if m else "",
        marca=m.marca if m else "",
        tipo_prenda=m.tipo_prenda if m else None,
        tipo_pieza=hermanas.tipo_pieza or tipo_pieza,
        nivel=nivel,
        atributo=m.atributo if m else None,
        genero=m.genero if m else None,
        escudo=m.escudo if m else None,
        ubicacion=m.ubicacion if m else None,
        color=color_final,
        tallas=[_talla_sugerida(s, m, hermanas, llegan, costos) for s in sugeridos],
        tallas_posibles=[_talla_sugerida(s, m, hermanas, {}, {}) for s in sugeridos_posibles],
        alternativas=hermanas.alternativas,
        grupo=m.grupo_uniforme if m else None,
        modelo_id=m.producto_id if m else None,
        modelo_nombre=m.nombre if m else None,
        modelo_texto=hermanas.texto,
        confirmados=tuple(confirmados),
        avisos_fijos=([hermanas.texto] if m is None else []) + (
            [f"Esta pieza tiene dos escaleras de precio en {(nivel or 'la base').lower()}: "
             "se tomó la del modelo para no mezclarlas."]
            if any(s.escalera_del_modelo for s in sugeridos) else []
        ),
        errores_fijos=errores_fijos,
    )
    return completar(session, plan, saltar_skus=saltar_skus, usos=usos)


def planear_varias_escuelas(
    session: Session, escuelas: Iterable[str | int], tipo_pieza: str, **kwargs
) -> list[PlanPrenda]:
    """«La misma pieza para varias escuelas»: un plan por escuela, con SKU
    previstos seguidos. Se aplican juntos en una sola transacción."""
    usos = kwargs.pop("usos", None) or _Usos(session)
    planes: list[PlanPrenda] = []
    saltar = int(kwargs.pop("saltar_skus", 0))
    for escuela in escuelas:
        plan = planear_desde_modelo(session, escuela, tipo_pieza, saltar_skus=saltar, usos=usos, **kwargs)
        saltar += len(plan.tallas)
        planes.append(plan)
    nombres = [p.nombre for p in planes]
    for p in planes:
        if p.nombre and nombres.count(p.nombre) > 1:
            p.errores_fijos.append(f"«{p.nombre}» está dos veces en el lote.")
            p.errores.append(p.errores_fijos[-1])
    return planes


# ── Ensayar y aplicar ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class TallaCreada:
    variante_id: int
    sku: str
    talla: str
    color: str
    precio: Decimal
    llegan: int = 0


@dataclass(frozen=True)
class ProductoCreado:
    producto_id: int
    nombre: str
    escuela: str | None
    tallas: tuple[TallaCreada, ...]
    uniforme: str | None = None          # «Deportivo» (el grupo), si se ligó
    recetas: tuple[str, ...] = ()        # «Chamarra Deportiva X: sale de … (nueva)»
    avisos: tuple[str, ...] = ()
    bitacora: str = ""


@dataclass(frozen=True)
class ResultadoAlta:
    productos: tuple[ProductoCreado, ...] = ()
    ensayo: bool = False
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error

    @property
    def skus(self) -> list[str]:
        return [t.sku for p in self.productos for t in p.tallas]

    def texto(self) -> str:
        if self.error:
            return f"No se guardó nada: {self.error}"
        lineas = []
        for p in self.productos:
            lineas.append(f"«{p.nombre}»")
            for t in p.tallas:
                llegan = f" · llegan {t.llegan}" if t.llegan else ""
                lineas.append(f"  {t.sku:<12} {t.talla:<9} {t.color:<12} ${t.precio:.0f}{llegan}")
            if p.uniforme:
                lineas.append(f"  uniforme: {p.uniforme}")
            for r in p.recetas:
                lineas.append(f"  receta: {r}")
            for a in p.avisos:
                lineas.append(f"  ⚠ {a}")
        return "\n".join(lineas)


def _resolver(session: Session, modelo, nombre: str | None, plan: PlanPrenda, usuario: Usuario):
    if not nombre:
        return None
    return valores.resolver_o_crear(session, modelo, nombre, confirmados=plan.confirmados, usuario=usuario)


def _marca(session: Session, plan: PlanPrenda, usuario: Usuario) -> Marca:
    marca = session.scalar(select(Marca).where(Marca.nombre == plan.marca))
    if marca is None:
        clave = valores.normalizar(plan.marca)
        marca = next((m for m in session.scalars(select(Marca)).all() if valores.normalizar(m.nombre) == clave), None)
    if marca is None:
        if not _confirmado(plan, plan.marca):
            raise valores.ValorNoConfirmado(f"«{plan.marca}» no existe como marca.")
        marca = CatalogService.crear_marca(session, usuario, plan.marca)
    return marca


def _recetas(session: Session, producto: Producto, plan: PlanPrenda, avisos: list[str]) -> list[str]:
    """Propone la receta del conjunto nuevo, o completa las de los conjuntos de
    la escuela que no tenían (`recetas_de_la_escuela`). Una receta que ya
    existe no se toca, ni la de un conjunto con existencia propia."""
    hechas: list[str] = []
    if conjunto_service.es_conjunto(producto):
        candidatos = [producto]
    else:
        recetas = recetas_de_la_escuela(session, producto.escuela_id, plan.tipo_pieza)
        candidatos = list(recetas.completar)
        avisos.extend(recetas.avisos())
    for c in candidatos:
        prop = conjunto_service.proponer_receta(session, c)
        if prop["componentes"]:
            conjunto_service.definir_receta(session, c.id, prop["componentes"], creado_por="alta")
            texto = conjunto_service.receta_texto(session, c.id)
            hechas.append(f"{c.nombre}: {texto}" + (" (nueva)" if c.id == producto.id else " (se completó)"))
        elif c.id == producto.id:
            partes = []
            if prop["faltan"]:
                partes.append("falta " + ", ".join(prop["faltan"]))
            if prop["ambiguas"]:
                partes.append("hay varias de " + ", ".join(prop["ambiguas"]))
            avisos.append(
                f"La receta de {c.nombre} no se armó ({'; '.join(partes)}): arréglala en Uniformes por escuela."
            )
    return hechas


def _crear(session: Session, plan: PlanPrenda, usuario: Usuario, origen: str | None) -> ProductoCreado:
    nota = origen_bitacora(plan, origen)
    escuela = _resolver(session, Escuela, plan.escuela, plan, usuario)
    categoria = _resolver(session, Categoria, plan.categoria, plan, usuario)
    producto = CatalogService.crear_producto(
        session, usuario, categoria, _marca(session, plan, usuario), plan.nombre_sin_escuela,
        descripcion=plan.descripcion,
        escuela=escuela,
        tipo_prenda=_resolver(session, TipoPrenda, plan.tipo_prenda, plan, usuario),
        tipo_pieza=_resolver(session, TipoPieza, plan.tipo_pieza, plan, usuario),
        nivel_educativo=_resolver(session, NivelEducativo, plan.nivel, plan, usuario),
        atributo=_resolver(session, AtributoProducto, plan.atributo, plan, usuario),
        genero=plan.genero, escudo=plan.escudo, ubicacion=plan.ubicacion,
        observacion=nota,
    )
    variantes = []
    for t in plan.tallas:
        v = CatalogService.crear_variante(
            session, usuario, producto, None, t.talla, plan.color, t.precio,
            costo_referencia=t.costo, stock_inicial=0, observacion=nota,
        )
        variantes.append((t, v))

    grupo = None
    if escuela is not None and plan.ligar:
        uni = uniforme_service.uniforme_de(session, escuela.id, crear=True)
        pieza = uniforme_service.agregar_pieza(
            session, uni.id, producto.id, grupo=plan.grupo, obligatoria=plan.obligatoria, orden=plan.orden,
        )
        grupo = pieza.grupo

    avisos: list[str] = []
    recetas = _recetas(session, producto, plan, avisos)

    # La existencia inicial, como una entrada normal por talla (se corrige
    # como cualquier otra y la talla se puede borrar después).
    for t, v in variantes:
        if t.llegan:
            InventarioService.registrar_ajuste_manual(
                session, v, int(t.llegan), usuario,
                referencia=REFERENCIA_ENTRADA, observacion=f"Llegaron al dar de alta · {nota}",
            )
    session.flush()
    return ProductoCreado(
        producto_id=int(producto.id),
        nombre=str(producto.nombre),
        escuela=escuela.nombre if escuela is not None else None,
        tallas=tuple(
            TallaCreada(int(v.id), str(v.sku), str(v.talla), str(v.color), Decimal(v.precio_venta), int(t.llegan))
            for t, v in variantes
        ),
        uniforme=grupo,
        recetas=tuple(recetas),
        avisos=tuple(avisos),
        bitacora=nota,
    )


def _errores(planes: Sequence[PlanPrenda]) -> str:
    errores = []
    for p in planes:
        for e in p.todos_los_errores:
            errores.append(f"{p.nombre or p.nombre_sin_escuela}: {e}" if len(planes) > 1 else e)
    return "\n".join(errores)


def _como_lista(planes: PlanPrenda | Sequence[PlanPrenda]) -> list[PlanPrenda]:
    return [planes] if isinstance(planes, PlanPrenda) else list(planes)


def aplicar(
    session: Session,
    planes: PlanPrenda | Sequence[PlanPrenda],
    usuario: Usuario,
    origen: str = ORIGEN_POS,
    *,
    commit: bool = False,
) -> ResultadoAlta:
    """Guarda todos los planes juntos o ninguno.

    Corre dentro de un savepoint: si algo falla (una receta, un SKU, un valor
    sin confirmar) se deshace todo lo de este alta y se vuelve a lanzar el
    error; lo demás de la sesión queda como estaba. Con `commit=True` hace
    commit al terminar; si no, lo hace quien llama (la skill junta varias
    cosas en una sola transacción)."""
    planes = _como_lista(planes)
    errores = _errores(planes)
    if errores:
        raise AltaNoValida(errores)
    CatalogService._validar_admin(usuario)
    with session.begin_nested():
        creados = tuple(_crear(session, p, usuario, origen) for p in planes)
    if commit:
        session.commit()
    return ResultadoAlta(productos=creados)


def ensayar(
    session: Session,
    planes: PlanPrenda | Sequence[PlanPrenda],
    usuario: Usuario,
    origen: str = ORIGEN_POS,
) -> ResultadoAlta:
    """Hace el alta dentro de un savepoint y la deshace: devuelve exactamente
    lo que se crearía (SKU, recetas, grupo del uniforme). No lanza errores
    de datos ni de la base (valor sin confirmar, permiso, duplicado porque
    otra caja guardó lo mismo): los devuelve en `error`.

    Toma el contador de SKU con candado mientras dura la transacción de quien
    llama: hay que cerrar (rollback/commit) la sesión después."""
    planes = _como_lista(planes)
    errores = _errores(planes)
    if errores:
        return ResultadoAlta(ensayo=True, error=errores)
    pendiente_antes = session.info.get(_MEILI_PENDIENTE)
    punto = session.begin_nested()
    try:
        CatalogService._validar_admin(usuario)
        creados = tuple(_crear(session, p, usuario, origen) for p in planes)
        resultado = ResultadoAlta(productos=creados, ensayo=True)
    except (ValueError, PermissionError) as exc:
        resultado = ResultadoAlta(ensayo=True, error=str(exc))
    except IntegrityError:
        resultado = ResultadoAlta(
            ensayo=True,
            error="Ya hay algo guardado igual (otra caja lo dio de alta mientras tanto): vuelve a revisar la prenda.",
        )
    except SQLAlchemyError as exc:
        resultado = ResultadoAlta(ensayo=True, error=f"La base no dejó hacer el ensayo: {exc.__class__.__name__}.")
    finally:
        # También tras un error de flush (savepoint DEACTIVE, is_active=False):
        # si no se deshace aquí, la sesión queda inservible para quien llama.
        try:
            punto.rollback()
        except InvalidRequestError:
            pass  # ya estaba cerrado
        if pendiente_antes is None:
            session.info.pop(_MEILI_PENDIENTE, None)
    return resultado


__all__ = [
    "ORIGEN_CLAUDE",
    "ORIGEN_POS",
    "REFERENCIA_ENTRADA",
    "AltaNoValida",
    "PlanPrenda",
    "ProductoCreado",
    "RecetasDeLaEscuela",
    "ResultadoAlta",
    "TallaCreada",
    "TallaPlan",
    "aplicar",
    "cambiar_color_en_nombre",
    "completar",
    "desmarcar_talla",
    "marcar_talla",
    "ensayar",
    "origen_bitacora",
    "origen_copia_escuela",
    "planear",
    "planear_desde_modelo",
    "planear_varias_escuelas",
    "recetas_de_la_escuela",
]
