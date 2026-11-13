"""Valores del catálogo: una sola forma y «¿Quisiste decir…?».

Tanda 1 del rediseño de «Nueva prenda» (2026-11-13). El asistente creaba en
silencio escuelas, tipos de prenda, piezas, atributos y niveles con cualquier
escritura, y dejaba pasar tallas y colores escritos a mano. Así nacieron
«Uni»/«Unitalla», «Ch»/«CH», «Blanca»/«Blanco», «Basico»/«Básico»…

Este servicio es puro (salvo `contar_usos` y `resolver_o_crear`, que leen o
escriben con la sesión que les pasan):

- `normalizar` compara sin mayúsculas, acentos ni espacios de más.
- `forma_oficial_talla` / `forma_oficial_color` dan la forma que Daniel
  decidió el 2026-11-13 (tallas: Unitalla; CH, MD, GD, EXG; números;
  Infantil, Juvenil, Adulto. Colores: forma masculina, «Surtido» para
  mezclados). Solo rige para lo NUEVO: no cambia lo que ya está en la base.
- `revisar_valor` decide si un valor se usa tal cual, si se parece a uno que
  ya existe (y cuál proponer) o si es nuevo de verdad.
- `resolver_o_crear` es lo que usa el asistente al guardar: nunca crea un
  valor que el usuario no confirmó, y una escuela nueva solo la crea ADMIN.

Los sinónimos salen del perfil del catálogo de la caja (2026-11-13,
`alta_datos.md`) y de las decisiones de Daniel (`alta_historia.md`, D5).
"""

from __future__ import annotations

import difflib
import unicodedata
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    AtributoProducto,
    Categoria,
    Escuela,
    NivelEducativo,
    Producto,
    RolUsuario,
    TipoPieza,
    TipoPrenda,
    Usuario,
    Variante,
)

# ── Campos que revisa el asistente ─────────────────────────────────────────

CAMPO_ESCUELA = "escuela"
CAMPO_TIPO_PRENDA = "tipo_prenda"
CAMPO_TIPO_PIEZA = "tipo_pieza"
CAMPO_ATRIBUTO = "atributo"
CAMPO_NIVEL = "nivel_educativo"
CAMPO_CATEGORIA = "categoria"
CAMPO_TALLA = "talla"
CAMPO_COLOR = "color"

MODELO_POR_CAMPO = {
    CAMPO_ESCUELA: Escuela,
    CAMPO_TIPO_PRENDA: TipoPrenda,
    CAMPO_TIPO_PIEZA: TipoPieza,
    CAMPO_ATRIBUTO: AtributoProducto,
    CAMPO_NIVEL: NivelEducativo,
    CAMPO_CATEGORIA: Categoria,
}
CAMPO_POR_MODELO = {modelo: campo for campo, modelo in MODELO_POR_CAMPO.items()}

ETIQUETA_CAMPO = {
    CAMPO_ESCUELA: "escuela",
    CAMPO_TIPO_PRENDA: "tipo de prenda",
    CAMPO_TIPO_PIEZA: "pieza",
    CAMPO_ATRIBUTO: "atributo",
    CAMPO_NIVEL: "nivel",
    CAMPO_CATEGORIA: "categoría",
    CAMPO_TALLA: "talla",
    CAMPO_COLOR: "color",
}

# ── Formas oficiales (decisión de Daniel, 2026-11-13) ──────────────────────

TALLA_UNITALLA = "Unitalla"
TALLAS_LETRA = ("CH", "MD", "GD", "EXG")
TALLAS_TEMPORADA = ("Infantil", "Juvenil", "Adulto")
TALLAS_OFICIALES_TEXTO = (TALLA_UNITALLA, *TALLAS_LETRA, *TALLAS_TEMPORADA)
# Lista para los selectores: números de uniforme (2 a 20) y de adulto
# (22 a 48), las letras y las de temporada. Lo que ya existe en la base
# (rangos de calceta, «CH-MD», «Dama»…) se sigue ofreciendo aparte.
TALLAS_SUGERIDAS = (
    *[str(n) for n in range(2, 21, 2)],
    *[str(n) for n in range(22, 49)],
    *TALLAS_LETRA,
    *TALLAS_TEMPORADA,
    TALLA_UNITALLA,
)

COLOR_SURTIDO = "Surtido"
COLORES_SUGERIDOS = (
    "Negro",
    "Blanco",
    "Gris",
    "Azul",
    "Azul Marino",
    "Azul Rey",
    "Celeste",
    "Rojo",
    "Verde",
    "Olivo",
    "Amarillo",
    "Beige",
    "Café",
    "Camel",
    "Khaki",
    "Rosa",
    "Morado",
    "Naranja",
    "Vino",
    "Plateado",
    "Dorado",
    COLOR_SURTIDO,
)

# Sinónimos conocidos (clave ya normalizada → forma oficial).
# Tallas: «Uni» 66 y «NT» contra «Unitalla» 23; «Ch» 1 contra «CH» 256;
# G, M y XL sueltas (1 cada una) contra GD, MD y EXG (perfil de la caja).
# «XXL» NO va a EXG: es otra talla (más grande); queda como valor aparte hasta
# que Daniel decida (si se escribe, pregunta como nueva).
SINONIMOS_TALLA = {
    "uni": TALLA_UNITALLA,
    "nt": TALLA_UNITALLA,
    "unica": TALLA_UNITALLA,
    "talla unica": TALLA_UNITALLA,
    "unitalla": TALLA_UNITALLA,
    "ch": "CH",
    "chica": "CH",
    "chico": "CH",
    "m": "MD",
    "md": "MD",
    "mediana": "MD",
    "mediano": "MD",
    "g": "GD",
    "gd": "GD",
    "grande": "GD",
    "xl": "EXG",
    "xg": "EXG",
    "exg": "EXG",
    "extra grande": "EXG",
    "extragrande": "EXG",
    "infantil": "Infantil",
    "juvenil": "Juvenil",
    "adulto": "Adulto",
}

# Colores: una sola forma, la masculina («Blanca» 306 contra «Blanco» 125),
# como ya hace `armar_recetas`; «Surtido» para mezclados (no «Multicolor»).
SINONIMOS_COLOR = {
    "blanca": "Blanco",
    "negra": "Negro",
    "roja": "Rojo",
    "amarilla": "Amarillo",
    "morada": "Morado",
    "multicolor": COLOR_SURTIDO,
    "surtida": COLOR_SURTIDO,
    "surtidos": COLOR_SURTIDO,
    "marino": "Azul Marino",
}

# Taxonomías: solo se proponen si la forma oficial ya existe en la base.
# «Deportiva» 75 contra «Deportivo» 101; «Basico» contra «Básico».
SINONIMOS_POR_CAMPO = {
    CAMPO_TALLA: SINONIMOS_TALLA,
    CAMPO_COLOR: SINONIMOS_COLOR,
    CAMPO_ATRIBUTO: {"deportiva": "Deportivo", "basico": "Básico"},
    CAMPO_TIPO_PRENDA: {"basico": "Básico"},
}

# Tallas de letra del config.json del Gestor que NO son oficiales: no se
# ofrecen en las listas del asistente (salvo que ya existan en la base).
TALLAS_NO_OFICIALES = frozenset({"xs", "s", "l", "xxl", "xxxl", "xxxxl", "esp"})

UMBRAL_PARECIDO = 0.78
MAX_SUGERENCIAS = 3

_PUNTUACION = str.maketrans({c: " " for c in "().,;:\"'«»"})


# ── Normalización ──────────────────────────────────────────────────────────

def limpiar(texto: object) -> str:
    """Quita espacios de más (incluidos los de en medio)."""
    return " ".join(str(texto or "").split())


def sin_acentos(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def normalizar(texto: object) -> str:
    """Forma para comparar: sin mayúsculas, acentos, signos ni espacios de más.

    El guion se conserva: «3-5» (calceta) no es la talla «35»."""
    return " ".join(sin_acentos(str(texto or "")).casefold().translate(_PUNTUACION).split())


def lleva_acento(texto: str) -> bool:
    return any(unicodedata.category(c) == "Mn" for c in unicodedata.normalize("NFD", texto))


def es_talla_oficial(talla: str) -> bool:
    limpio = limpiar(talla)
    return limpio.isdigit() or limpio in TALLAS_OFICIALES_TEXTO


def forma_oficial(campo: str, texto: object) -> str | None:
    """La forma oficial que corresponde a lo escrito, o None si no hay sinónimo."""
    return SINONIMOS_POR_CAMPO.get(campo, {}).get(normalizar(texto))


def forma_oficial_talla(talla: object) -> str:
    limpio = limpiar(talla)
    return forma_oficial(CAMPO_TALLA, limpio) or limpio


def forma_oficial_color(color: object) -> str:
    limpio = limpiar(color)
    return forma_oficial(CAMPO_COLOR, limpio) or limpio


def depurar_opciones(campo: str, *grupos: list[str]) -> list[str]:
    """Une listas de opciones dejando una sola forma de cada valor.

    Pasa los sinónimos a su forma oficial (para tallas y colores siempre;
    para lo demás solo si la oficial está en la lista) y, entre dos escrituras
    que solo difieren en acentos o mayúsculas, se queda con la acentuada."""
    todos = [limpiar(v) for grupo in grupos for v in grupo if limpiar(v)]
    presentes = {normalizar(v) for v in todos}
    elegido: dict[str, str] = {}
    orden: list[str] = []
    for valor in todos:
        oficial = forma_oficial(campo, valor)
        if oficial and (campo in (CAMPO_TALLA, CAMPO_COLOR) or normalizar(oficial) in presentes):
            valor = oficial
        clave = normalizar(valor)
        actual = elegido.get(clave)
        if actual is None:
            elegido[clave] = valor
            orden.append(clave)
        elif lleva_acento(valor) and not lleva_acento(actual):
            elegido[clave] = valor
    return [elegido[clave] for clave in orden]


def tallas_para_ofrecer(valores: list[str]) -> list[str]:
    """Quita de una lista de sugerencias (la del Gestor) las tallas de letra
    que no son oficiales (XS, S, L, XXL, XXXL, ESP…). Las que ya existen en
    la base se ofrecen aparte, así que no se pierden."""
    return [v for v in valores if normalizar(v) not in TALLAS_NO_OFICIALES]


# ── Revisión de un valor ───────────────────────────────────────────────────

ESTADO_OK = "ok"
ESTADO_PARECIDO = "parecido"
ESTADO_NUEVO = "nuevo"

# De dónde sale la propuesta: una forma oficial (sinónimo conocido), la misma
# palabra con otra escritura (acentos/mayúsculas) o solo un parecido de letras.
ORIGEN_FORMA_OFICIAL = "forma_oficial"
ORIGEN_ESCRITURA = "escritura"
ORIGEN_PARECIDO = "parecido"


@dataclass(frozen=True)
class Parecido:
    valor: str
    usos: int = 0


@dataclass(frozen=True)
class Revision:
    campo: str
    escrito: str
    estado: str
    valor: str
    sugerencias: tuple[Parecido, ...] = field(default_factory=tuple)
    existe: bool = False
    origen: str = ""
    usos_escrito: int = 0

    @property
    def necesita_pregunta(self) -> bool:
        return self.estado != ESTADO_OK

    @property
    def sugerencia_segura(self) -> bool:
        """La propuesta es la misma cosa escrita de otra forma (sinónimo o
        acentos), no solo letras parecidas: «Usar…» puede ir por defecto."""
        return bool(self.sugerencias) and self.origen in (ORIGEN_FORMA_OFICIAL, ORIGEN_ESCRITURA)

    @property
    def unidad(self) -> str:
        return "tallas" if self.campo in (CAMPO_TALLA, CAMPO_COLOR) else "prendas"

    def texto_pregunta(self, puede_crear: bool = True) -> str:
        etiqueta = ETIQUETA_CAMPO.get(self.campo, self.campo)
        if self.campo == CAMPO_ESCUELA and not self.existe:
            if self.sugerencias:
                primera = self.sugerencias[0]
                return (
                    f"«{self.escrito}» no está en la lista de escuelas.\n"
                    f"¿Es la misma que «{primera.valor}» ({primera.usos} prendas)?"
                )
            if not puede_crear:
                return (
                    f"«{self.escrito}» no está en la lista de escuelas.\n"
                    "Elige una de la lista o pide a un ADMIN que la dé de alta."
                )
            return (
                f"«{self.escrito}» no está en la lista de escuelas.\n"
                "¿Crear una escuela nueva con ese nombre?"
            )
        if self.sugerencias:
            primera = self.sugerencias[0]
            return f"«{self.escrito}» se parece a «{primera.valor}» ({primera.usos} {self.unidad})."
        return f"«{self.escrito}» no existe todavía como {etiqueta}."

    def texto_motivo(self) -> str:
        """Por qué se propone, cuando la propuesta es una forma oficial."""
        if self.origen != ORIGEN_FORMA_OFICIAL or not self.sugerencias:
            return ""
        texto = f"Para lo nuevo se usa una sola forma: «{self.sugerencias[0].valor}»."
        if self.existe and self.usos_escrito:
            texto += f" «{self.escrito}» ya está en {self.usos_escrito} {self.unidad}; esas no cambian."
        return texto


def _mejor_de(grupo: list[str], usos: dict[str, int]) -> str:
    return sorted(grupo, key=lambda v: (not lleva_acento(v), -usos.get(v, 0), v))[0]


def _solo_error_de_dedo(na: str, nb: str) -> bool:
    """Mismas palabras, con letras cambiadas en alguna («Chamara»/«Chamarra»,
    «Blnaco»/«Blanco»). Una palabra de más o de menos («Gris claro»/«Gris»,
    «Verde Bandera»/«Verde») o un número distinto («Pants 3pz»/«Pants 2pz»,
    «13-18»/«13-16») ya es otra cosa."""
    pa, pb = na.split(), nb.split()
    if len(pa) != len(pb):
        return False
    for wa, wb in zip(pa, pb):
        if wa == wb:
            continue
        if any(c.isdigit() for c in wa + wb):
            return False
        if difflib.SequenceMatcher(None, wa, wb).ratio() < 0.7:
            return False
    return True


def _similitud(a: str, b: str, campo: str = CAMPO_ESCUELA) -> float:
    na, nb = normalizar(a), normalizar(b)
    if not na or not nb:
        return 0.0
    if campo == CAMPO_TALLA:
        # Tallas: solo sinónimos. «2-4» no es «24» ni «13-18» es «13-16».
        return 0.0
    if campo != CAMPO_ESCUELA:
        if not _solo_error_de_dedo(na, nb):
            return 0.0
        return difflib.SequenceMatcher(None, na, nb).ratio()
    ratio = difflib.SequenceMatcher(None, na, nb).ratio()
    # Solo escuelas: «Ignacio Allende» dentro de «Ignacio Allende (Jaral)»
    # (todas las palabras de uno están en el otro).
    pa, pb = set(na.split()), set(nb.split())
    if pa and pb and (pa <= pb or pb <= pa) and min(len(na), len(nb)) >= 3:
        ratio = max(ratio, 0.9)
    return ratio


def _parecidos(campo: str, escrito: str, usos: dict[str, int]) -> tuple[Parecido, ...]:
    puntuados = []
    for valor, n in usos.items():
        if valor == escrito:
            continue
        score = _similitud(escrito, valor, campo)
        if score >= UMBRAL_PARECIDO:
            puntuados.append((score, n, valor))
    puntuados.sort(key=lambda t: (-t[0], -t[1], t[2]))
    return tuple(Parecido(valor, n) for _, n, valor in puntuados[:MAX_SUGERENCIAS])


def revisar_valor(campo: str, texto: object, usos: dict[str, int] | None = None) -> Revision:
    """Decide qué hacer con lo que se escribió en `campo`.

    `usos` son los valores que ya existen con cuántas prendas (o tallas) los
    usan. Devuelve `ok` (se usa `valor` sin preguntar), `parecido` (hay que
    preguntar «¿Quisiste decir…?») o `nuevo` (no existe nada parecido; crearlo
    pide que el usuario lo elija)."""
    usos = dict(usos or {})
    escrito = limpiar(texto)
    if not escrito:
        return Revision(campo, "", ESTADO_OK, "")
    existe = escrito in usos
    clave = normalizar(escrito)
    por_clave: dict[str, list[str]] = {}
    for valor in usos:
        por_clave.setdefault(normalizar(valor), []).append(valor)

    oficial = forma_oficial(campo, escrito)
    if oficial is not None:
        existentes_oficial = por_clave.get(normalizar(oficial), [])
        es_libre = campo in (CAMPO_TALLA, CAMPO_COLOR)
        if existentes_oficial or es_libre:
            destino = oficial if (es_libre or oficial in existentes_oficial) else _mejor_de(existentes_oficial, usos)
            if destino == escrito:
                return Revision(campo, escrito, ESTADO_OK, escrito, existe=existe)
            if normalizar(destino) == normalizar(escrito):
                # «ch» → «CH», o «Básico» cuando en la base solo está «Basico»:
                # es la misma palabra, se usa la que hay sin preguntar (el
                # renombrado de lo viejo es de la tanda 5).
                return Revision(campo, escrito, ESTADO_OK, destino, existe=existe)
            return Revision(
                campo, escrito, ESTADO_PARECIDO, destino,
                sugerencias=(Parecido(destino, usos.get(destino, 0)),), existe=existe,
                origen=ORIGEN_FORMA_OFICIAL, usos_escrito=usos.get(escrito, 0),
            )

    grupo = por_clave.get(clave, [])
    if grupo:
        mejor = _mejor_de(grupo, usos)
        if mejor == escrito:
            return Revision(campo, escrito, ESTADO_OK, escrito, existe=True)
        if not existe:
            # Solo cambian mayúsculas, espacios o acentos y lo escrito no
            # existe tal cual: se usa el que ya está («sueter» → «Suéter»).
            return Revision(campo, escrito, ESTADO_OK, mejor, existe=False)
        # Existen las dos escrituras («Basico» y «Básico»): se propone la buena.
        return Revision(
            campo, escrito, ESTADO_PARECIDO, mejor,
            sugerencias=(Parecido(mejor, usos.get(mejor, 0)),), existe=existe,
            origen=ORIGEN_ESCRITURA, usos_escrito=usos.get(escrito, 0),
        )

    if campo == CAMPO_TALLA and es_talla_oficial(escrito):
        return Revision(campo, escrito, ESTADO_OK, escrito, existe=existe)
    if campo == CAMPO_COLOR and escrito in COLORES_SUGERIDOS:
        return Revision(campo, escrito, ESTADO_OK, escrito, existe=existe)

    parecidos = _parecidos(campo, escrito, usos)
    if parecidos:
        return Revision(
            campo, escrito, ESTADO_PARECIDO, parecidos[0].valor, sugerencias=parecidos, existe=existe,
            origen=ORIGEN_PARECIDO, usos_escrito=usos.get(escrito, 0),
        )
    return Revision(campo, escrito, ESTADO_NUEVO, escrito, existe=existe, usos_escrito=usos.get(escrito, 0))


# ── Base de datos ──────────────────────────────────────────────────────────

def contar_usos(session: Session, campo: str) -> dict[str, int]:
    """Valores activos de `campo` con cuántas prendas activas (o tallas activas
    para talla y color) los usan."""
    if campo in (CAMPO_TALLA, CAMPO_COLOR):
        columna = Variante.talla if campo == CAMPO_TALLA else Variante.color
        filas = session.execute(
            select(columna, func.count(Variante.id))
            .where(Variante.activo.is_(True))
            .group_by(columna)
        ).all()
        return {limpiar(v): int(n) for v, n in filas if limpiar(v)}
    modelo = MODELO_POR_CAMPO[campo]
    fk = {
        CAMPO_ESCUELA: Producto.escuela_id,
        CAMPO_TIPO_PRENDA: Producto.tipo_prenda_id,
        CAMPO_TIPO_PIEZA: Producto.tipo_pieza_id,
        CAMPO_ATRIBUTO: Producto.atributo_id,
        CAMPO_NIVEL: Producto.nivel_educativo_id,
        CAMPO_CATEGORIA: Producto.categoria_id,
    }[campo]
    filas = session.execute(
        select(modelo.nombre, func.count(Producto.id))
        .select_from(modelo)
        .outerjoin(Producto, (fk == modelo.id) & Producto.activo.is_(True))
        .where(modelo.activo.is_(True))
        .group_by(modelo.id, modelo.nombre)
    ).all()
    return {limpiar(v): int(n) for v, n in filas if limpiar(v)}


class ValorNoConfirmado(ValueError):
    """Se quiso guardar un valor que no existe y que nadie confirmó."""


def resolver_o_crear(
    session: Session,
    modelo,
    texto: object,
    *,
    confirmados: object = (),
    usuario: Usuario | None = None,
):
    """La fila de `modelo` que corresponde a `texto`, sin crear en silencio.

    1. Igual letra por letra → esa.
    2. Igual sin mayúsculas, acentos ni espacios → la que lleva acento.
    3. Si el usuario confirmó crearlo (`confirmados`, nombres tal como los
       eligió) → se crea; una escuela, solo si `usuario` es ADMIN.
    4. Si no → `ValorNoConfirmado`."""
    nombre = limpiar(texto)
    if not nombre:
        return None
    exacta = session.scalar(select(modelo).where(modelo.nombre == nombre))
    if exacta is not None:
        return exacta
    clave = normalizar(nombre)
    parecidas = [f for f in session.scalars(select(modelo)).all() if normalizar(f.nombre) == clave]
    if parecidas:
        parecidas.sort(key=lambda f: (not bool(getattr(f, "activo", True)), not lleva_acento(f.nombre), f.id))
        return parecidas[0]
    campo = CAMPO_POR_MODELO.get(modelo, "")
    etiqueta = ETIQUETA_CAMPO.get(campo, "catálogo")
    if clave not in {normalizar(c) for c in (confirmados or ())}:
        raise ValorNoConfirmado(
            f"«{nombre}» no existe como {etiqueta}. Elígelo de la lista o confirma que es nuevo."
        )
    if modelo is Escuela and (usuario is None or usuario.rol != RolUsuario.ADMIN or not usuario.activo):
        raise PermissionError("Solo ADMIN puede crear una escuela nueva.")
    nueva = modelo(nombre=nombre)
    session.add(nueva)
    session.flush()
    return nueva
