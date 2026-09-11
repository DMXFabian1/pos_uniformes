"""Salud del feed: cuatro estados explícitos, para poder separar el dato bueno del sucio.

La medición anterior dejó claro que el feed del CLOB no es constante: la mediana de retraso ronda
el medio segundo, pero hay tramos de decenas de segundos y momentos en que deja de llegar nada.
Operar en esos tramos no es lo mismo que operar con el libro al día, y mezclarlo en las
estadísticas invalida las dos mitades.

Estados:

- **SANO**: el libro que vemos describe el mercado de ahora.
- **DEGRADADO**: llega con retraso apreciable pero sigue llegando. Se puede mirar, con reservas.
- **VIEJO**: el retraso es tal que el libro ya no describe el mercado. No se abre nada.
- **CONGELADO**: ha dejado de llegar. Ni siquiera sabemos si el mercado se movió.

Los umbrales son una hipótesis, no una verdad: se registran junto a cada decisión precisamente
para poder comprobar después a partir de qué antigüedad desaparece la ventaja.

**Sobre el signo de la frescura.** La frescura se mide como `recv - ts`: la diferencia entre
nuestro reloj y el que estampó el mensaje. Esa resta lleva dentro el desfase entre los dos relojes,
que no conocemos. Si nuestro reloj va atrasado, la resta sale negativa, y una frescura negativa no
significa que el libro llegue del futuro: significa que el número absoluto no se puede leer como un
retraso. Lo que sí es válido es la comparación entre momentos, una vez descontado el suelo.

El suelo se estima como el mínimo observado (`desfase_reloj`): el mensaje que menos tardó es el que
menos contaminado está por el transporte, así que su retraso aparente es la mejor estimación del
desfase. Es el mismo truco de filtro de mínimo que usa NTP, y como NTP solo sirve para medidas
relativas: sin relojes sincronizados no hay retraso absoluto.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SANO = "SANO"
DEGRADADO = "DEGRADADO"
VIEJO = "VIEJO"
CONGELADO = "CONGELADO"

# Estados en los que un dato no puede mezclarse con el resto sin contaminarlo.
CONTAMINADOS = {VIEJO, CONGELADO}

# Tramos de antigüedad para el análisis. No son umbrales de decisión: son cajones para medir
# cómo cambian llenado, ganancia y selección adversa según la frescura del libro.
BUCKETS: tuple[tuple[str, float, float], ...] = (
    ("0-250ms", 0, 250),
    ("250-500ms", 250, 500),
    ("500ms-1s", 500, 1_000),
    ("1-2s", 1_000, 2_000),
    ("2-5s", 2_000, 5_000),
    ("5-10s", 5_000, 10_000),
    ("10s+", 10_000, float("inf")),
)


def desfase_reloj(valores) -> float:
    """Desfase estimado entre el reloj del exchange y el nuestro, en ms.

    Filtro de mínimo: de todos los retrasos aparentes observados, el más pequeño es el que menos
    transporte lleva dentro, así que se acerca al desfase puro. Solo se corrige cuando sale
    negativo; un mínimo positivo es retraso de verdad y no hay nada que descontar.
    """
    xs = [float(v) for v in valores if v is not None]
    if not xs:
        return 0.0
    return min(min(xs), 0.0)


def corregir(freshness_ms: float | None, desfase_ms: float = 0.0) -> float | None:
    """Frescura descontado el desfase de reloj. Nunca negativa: el suelo es cero."""
    if freshness_ms is None:
        return None
    return max(float(freshness_ms) - desfase_ms, 0.0)


def freshness_score(freshness_ms: float | None, media_vida_ms: float = 1_000.0,
                    desfase_ms: float = 0.0) -> float | None:
    """Frescura como número entre 0 y 1, para poder cruzarla con llenado y resultado.

    Decae a la mitad cada `media_vida_ms`: 0 ms vale 1, un segundo 0,5, dos segundos 0,25. Es una
    escala de análisis, no un umbral de decisión: no se usa para bloquear nada.
    """
    v = corregir(freshness_ms, desfase_ms)
    if v is None:
        return None
    return round(0.5 ** (v / media_vida_ms), 4)


def bucket(freshness_ms: float | None, desfase_ms: float = 0.0) -> str:
    """Cajón de antigüedad. Por debajo del suelo cae en el primero, no en el último.

    Antes, una frescura negativa no encajaba en ningún tramo y terminaba en `10s+`: el dato más
    fresco posible se contaba como el más viejo, y con el reloj desfasado eso afectaba a la mayoría
    de las decisiones. El cajón de lo que llega antes de tiempo es el de lo que acaba de llegar.
    """
    v = corregir(freshness_ms, desfase_ms)
    if v is None:
        return "desconocida"
    for nombre, lo, hi in BUCKETS:
        if lo <= v < hi:
            return nombre
    return "10s+"


@dataclass
class Salud:
    """Foto del estado del feed en un instante."""
    estado: str = SANO
    freshness_ms: int = 0            # retraso mediano reciente entre el reloj del exchange y el nuestro
    p95_ms: int = 0
    min_ms: int = 0                  # el menor retraso aparente de la ventana: estima el desfase de reloj
    mensajes_por_segundo: float = 0.0
    ultimo_mensaje_hace_ms: int = 0
    libros_validos: int = 0
    libros_totales: int = 0
    reconexiones: int = 0
    trade_feed_lag_s: int = -1
    paginas_llenas: int = 0
    motivo: str = ""

    @property
    def contaminado(self) -> bool:
        return self.estado in CONTAMINADOS

    @property
    def puede_operar(self) -> bool:
        return self.estado in (SANO, DEGRADADO)

    def to_row(self, ts_ms: int, run_id: str, experiment: str) -> dict[str, Any]:
        return {"ts_ms": ts_ms, "run_id": run_id, "experiment": experiment, "estado": self.estado,
                "freshness_ms": int(self.freshness_ms), "p95_ms": int(self.p95_ms),
                "min_ms": int(self.min_ms),
                "mensajes_por_segundo": round(self.mensajes_por_segundo, 2),
                "ultimo_mensaje_hace_ms": int(self.ultimo_mensaje_hace_ms),
                "libros_validos": int(self.libros_validos), "libros_totales": int(self.libros_totales),
                "reconexiones": int(self.reconexiones), "trade_feed_lag_s": int(self.trade_feed_lag_s),
                "paginas_llenas": int(self.paginas_llenas)}


@dataclass
class Umbrales:
    """Hipótesis sobre cuándo un libro deja de servir. Se miden, no se dan por buenas."""
    sano_ms: int = 1_000
    degradado_ms: int = 5_000
    sin_mensajes_viejo_s: float = 15
    sin_mensajes_congelado_s: float = 60
    campos: dict[str, Any] = field(default_factory=dict)


def evaluar(freshness_ms: float, ultimo_mensaje_hace_ms: float, u: Umbrales | None = None,
            **extra: Any) -> Salud:
    """Decide el estado a partir del retraso medido y de cuánto hace que no llega nada."""
    u = u or Umbrales()
    s = Salud(freshness_ms=int(freshness_ms), ultimo_mensaje_hace_ms=int(ultimo_mensaje_hace_ms))
    for k, v in extra.items():
        if hasattr(s, k) and v is not None:
            setattr(s, k, v)
    if ultimo_mensaje_hace_ms >= u.sin_mensajes_congelado_s * 1000:
        s.estado, s.motivo = CONGELADO, f"sin mensajes desde hace {ultimo_mensaje_hace_ms / 1000:.0f} s"
    elif ultimo_mensaje_hace_ms >= u.sin_mensajes_viejo_s * 1000:
        s.estado, s.motivo = VIEJO, f"sin mensajes desde hace {ultimo_mensaje_hace_ms / 1000:.0f} s"
    elif freshness_ms > u.degradado_ms:
        s.estado, s.motivo = VIEJO, f"el feed llega {freshness_ms / 1000:.1f} s tarde"
    elif freshness_ms > u.sano_ms:
        s.estado, s.motivo = DEGRADADO, f"el feed llega {freshness_ms / 1000:.1f} s tarde"
    else:
        s.estado, s.motivo = SANO, ""
    return s
