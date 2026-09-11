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


def bucket(freshness_ms: float | None) -> str:
    if freshness_ms is None:
        return "desconocida"
    for nombre, lo, hi in BUCKETS:
        if lo <= freshness_ms < hi:
            return nombre
    return "10s+"


@dataclass
class Salud:
    """Foto del estado del feed en un instante."""
    estado: str = SANO
    freshness_ms: int = 0            # retraso mediano reciente entre el reloj del exchange y el nuestro
    p95_ms: int = 0
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
