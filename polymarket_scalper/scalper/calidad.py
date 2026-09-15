"""Comprobaciones que hacen fallar una corrida en vez de dejarla producir dato inservible.

La fase anterior encontró siete defectos de medición, y ninguno se anunció: todos se descubrieron
mirando un número que no cuadraba. Un reloj que da frescuras negativas, un filtro que tira las
órdenes sin llenar, un modelo que se promociona a mitad de corrida — todos escribieron datos con
buena pinta durante horas.

Este módulo convierte cada uno de esos fallos en una comprobación que corta. La regla de fondo es
que **es mejor no tener dato que tener dato que parece bueno y no lo es**: una corrida abortada
cuesta unas horas; una corrida silenciosamente contaminada cuesta las conclusiones.

Cada comprobación devuelve una lista de problemas. `verificar` las junta y decide si la corrida
puede darse por válida.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from .storage import scan

# Un timestamp fuera de esta ventana no es un reloj con deriva: es un reloj roto o una columna mal
# rellenada. 2020-01-01 y 2100-01-01 en milisegundos.
TS_MIN = 1_577_836_800_000
TS_MAX = 4_102_444_800_000


@dataclass
class Problema:
    """Algo que invalida la corrida, o parte de ella."""
    comprobacion: str
    detalle: str
    filas: int = 0
    grave: bool = True          # grave corta la corrida; no grave solo se avisa

    def __str__(self) -> str:
        n = f" ({self.filas} filas)" if self.filas else ""
        return f"{'FALLO' if self.grave else 'AVISO'} · {self.comprobacion}: {self.detalle}{n}"


@dataclass
class Informe:
    problemas: list[Problema] = field(default_factory=list)
    comprobadas: list[str] = field(default_factory=list)

    @property
    def graves(self) -> list[Problema]:
        return [p for p in self.problemas if p.grave]

    @property
    def valida(self) -> bool:
        return not self.graves

    def __str__(self) -> str:
        if not self.problemas:
            return f"Calidad del dato: {len(self.comprobadas)} comprobaciones, ningún problema."
        cab = (f"Calidad del dato: {len(self.graves)} fallo(s) y "
               f"{len(self.problemas) - len(self.graves)} aviso(s) en {len(self.comprobadas)} comprobaciones.")
        return "\n".join([cab] + [f"  {p}" for p in self.problemas])


def _filas(data_dir: str | Path, tabla: str, experiment: str | None = None) -> pl.DataFrame:
    lf = scan(data_dir, tabla)
    if lf is None:
        return pl.DataFrame()
    if experiment and "experiment" in lf.collect_schema().names():
        lf = lf.filter(pl.col("experiment") == experiment)
    return lf.collect()


def _tiene(df: pl.DataFrame, *cols: str) -> bool:
    return not df.is_empty() and all(c in df.columns for c in cols)


def timestamps_posibles(data_dir: str | Path, experiment: str | None = None) -> list[Problema]:
    """Ningún instante puede caer fuera de un rango que tenga sentido, ni ir hacia atrás.

    Un `ts_exit` anterior al `ts_fill` significa que se restaron dos relojes distintos, que fue
    exactamente el fallo de las esperas negativas y de los retrasos de reacción negativos.

    El cero no es un instante imposible: es el centinela de "esto no ocurrió". Una orden que nunca
    se llenó tiene `ts_fill = 0` y tiene que seguir en el dataset — es justo la mitad de la muestra
    que esta fase exige conservar para que exista una tasa de llenado.
    """
    out: list[Problema] = []
    for tabla in ("ledger", "decisions", "partial_legs", "partial_leg_track", "fill_observations"):
        df = _filas(data_dir, tabla, experiment)
        if df.is_empty():
            continue
        for col in ("ts_ms", "ts_signal", "ts_fill", "ts_exit", "t0_ms"):
            if col not in df.columns:
                continue
            malos = df.filter(pl.col(col).is_not_null() & (pl.col(col) != 0) &
                              ((pl.col(col) < TS_MIN) | (pl.col(col) > TS_MAX)))
            if malos.height:
                out.append(Problema("timestamps_posibles",
                                    f"{tabla}.{col} fuera de rango razonable", malos.height))
    df = _filas(data_dir, "ledger", experiment)
    if _tiene(df, "ts_fill", "ts_exit"):
        alreves = df.filter(pl.col("ts_fill").is_not_null() & pl.col("ts_exit").is_not_null() &
                            (pl.col("ts_fill") > 0) & (pl.col("ts_exit") > 0) &
                            (pl.col("ts_exit") < pl.col("ts_fill")))
        if alreves.height:
            out.append(Problema("timestamps_posibles",
                                "ledger: se cierra antes de llenarse (dos relojes restados)",
                                alreves.height))
    return out


def un_solo_motor(data_dir: str | Path, run_id: str) -> list[Problema]:
    """Una corrida, un experiment_id. Si hay dos, el motor cambió y la muestra está mezclada."""
    df = _filas(data_dir, "ledger")
    if not _tiene(df, "run_id", "experiment"):
        return []
    suyas = df.filter(pl.col("run_id") == run_id)
    if suyas.is_empty():
        return []
    exps = sorted({e for e in suyas["experiment"].to_list() if e})
    if len(exps) > 1:
        return [Problema("un_solo_motor",
                         f"la corrida {run_id} tiene {len(exps)} experimentos: {', '.join(exps)}",
                         suyas.height)]
    return []


def modelo_inmutable(data_dir: str | Path, run_id: str) -> list[Problema]:
    """Dentro de una corrida no puede cambiar la versión del modelo que decide."""
    df = _filas(data_dir, "ledger")
    if not _tiene(df, "run_id", "model_version"):
        return []
    suyas = df.filter(pl.col("run_id") == run_id)
    if suyas.is_empty():
        return []
    # Hay que mirar **por estrategia**. Que la captura de spread tenga modelo y el dinero
    # inteligente no lo tenga es lo normal: son detectores distintos y cada uno lleva el suyo. Lo
    # que delata una promoción a mitad es que UNA MISMA estrategia cambie de versión con el tiempo,
    # que es lo que pasó en `muestra-3` con TENNIS_SPREAD_CAPTURE: 494 filas sin modelo y 186 con la
    # v2. Comparar entre estrategias daba fallo en cualquier corrida honesta.
    #
    # El nulo cuenta como una versión: "sin modelo" y "con modelo v2" son dos motores distintos, y
    # pasar de uno al otro es justo lo que hay que detectar.
    if "strategy" not in suyas.columns:
        return []
    out: list[Problema] = []
    for est in sorted({e for e in suyas["strategy"].to_list() if e}):
        filas = suyas.filter(pl.col("strategy") == est)
        versiones = sorted({("sin modelo" if v is None else f"v{v}")
                            for v in filas["model_version"].to_list()})
        if len(versiones) > 1:
            out.append(Problema("modelo_inmutable",
                                f"la corrida {run_id} decidió {est} con {', '.join(versiones)}: se "
                                f"promocionó un modelo a mitad", filas.height))
    return out


def ordenes_conservadas(data_dir: str | Path, experiment: str | None = None) -> list[Problema]:
    """Las órdenes que no se llenan son parte de la medida, no ruido que se pueda tirar.

    Sin ellas no existe una tasa de llenado: el denominador desaparece y todo parece llenarse
    siempre. Si no queda ni una sin llenar, o es un mercado irreal o alguien las está filtrando.
    """
    df = _filas(data_dir, "fill_observations", experiment)
    if df.is_empty():
        return [Problema("ordenes_conservadas", "no hay ninguna observación de orden registrada")]
    if "llenada" not in df.columns:
        return [Problema("ordenes_conservadas", "fill_observations no trae la columna `llenada`")]
    sin_llenar = df.filter(~pl.col("llenada").fill_null(False)).height
    if sin_llenar == 0:
        return [Problema("ordenes_conservadas",
                         "todas las órdenes aparecen llenadas: falta el denominador de la tasa "
                         "de llenado", df.height)]
    return []


def patas_completas(data_dir: str | Path, experiment: str | None = None) -> list[Problema]:
    """Toda pata suelta necesita su T0 y su desenlace; sin eso no se puede situar nada en el tiempo."""
    out: list[Problema] = []
    df = _filas(data_dir, "partial_legs", experiment)
    if df.is_empty():
        return out
    if "t0_ms" in df.columns:
        sin_t0 = df.filter(pl.col("t0_ms").is_null() | (pl.col("t0_ms") <= 0))
        if sin_t0.height:
            out.append(Problema("patas_completas", "hay patas sueltas sin T0", sin_t0.height))
    if "partial_leg_id" in df.columns:
        repes = df.group_by("partial_leg_id").len().filter(pl.col("len") > 1)
        if repes.height:
            out.append(Problema("patas_completas",
                                "hay partial_leg_id repetidos: el identificador no es único",
                                repes.height))
    if "desenlace" in df.columns:
        abiertas = df.filter(pl.col("desenlace") == "abierta")
        if abiertas.height:
            out.append(Problema("patas_completas",
                                "patas sin desenlace al cerrar la corrida (no invalida, pero no "
                                "entran en el punto de no retorno)", abiertas.height, grave=False))
    return out


def precio_ejecutable(data_dir: str | Path, experiment: str | None = None) -> list[Problema]:
    """El precio de salida tiene que venir del libro, y cuando no se puede hay que decirlo.

    Dos formas de hacer trampa sin querer: guardar el mid como si fuera ejecutable, o dejar el hueco
    en blanco sin marcar por qué. Un punto con P&L contrafactual pero sin precio de salida solo
    puede haber salido del mid.
    """
    out: list[Problema] = []
    df = _filas(data_dir, "partial_leg_track", experiment)
    if df.is_empty():
        return out
    if _tiene(df, "contrafactual_pnl", "salida_precio"):
        del_aire = df.filter(pl.col("contrafactual_pnl").is_not_null() & pl.col("salida_precio").is_null())
        if del_aire.height:
            out.append(Problema("precio_ejecutable",
                                "hay P&L contrafactual sin precio de salida: solo puede venir del mid",
                                del_aire.height))
    if _tiene(df, "contrafactual_pnl", "mid", "salida_precio"):
        # el VWAP de salida nunca puede ser mejor que el mid: se sale por el lado malo del libro
        iguales = df.filter(pl.col("salida_precio").is_not_null() & pl.col("mid").is_not_null() &
                            ((pl.col("salida_precio") - pl.col("mid")).abs() < 1e-12))
        if iguales.height > max(3, int(df.height * 0.02)):
            out.append(Problema("precio_ejecutable",
                                "el precio de salida coincide exactamente con el mid demasiadas "
                                "veces: ¿se está usando el mid como sustituto?", iguales.height))
    if "desfase_medicion_ms" in df.columns:
        # Un horizonte medido mucho más tarde de lo que dice no mide ese horizonte. No invalida la
        # corrida —el dato sigue siendo cierto, solo que de otro instante— pero hay que verlo.
        tarde = df.filter(pl.col("desfase_medicion_ms") > 5_000)
        if tarde.height > max(3, int(df.height * 0.05)):
            out.append(Problema("precio_ejecutable",
                                "muchos puntos se midieron más de 5 s tarde: los horizontes cortos "
                                "no describen lo que dicen", tarde.height, grave=False))
    if "incompleto" in df.columns and "contrafactual_pnl" in df.columns:
        mudos = df.filter(pl.col("contrafactual_pnl").is_null() & pl.col("incompleto").is_null())
        if mudos.height:
            out.append(Problema("precio_ejecutable",
                                "hay puntos sin P&L y sin motivo: un hueco tiene que decir por qué",
                                mudos.height))
    return out


def pnl_separado(data_dir: str | Path, experiment: str | None = None) -> list[Problema]:
    """El resultado hipotético no puede acabar en ninguna columna de resultado realizado."""
    out: list[Problema] = []
    led = _filas(data_dir, "ledger", experiment)
    if not led.is_empty():
        contaminadas = [c for c in led.columns if "contrafactual" in c]
        if contaminadas:
            out.append(Problema("pnl_separado",
                                f"el ledger tiene columnas contrafactuales: {contaminadas}"))
        if {"sombra", "realized_pnl", "experiment"} <= set(led.columns):
            # Las sombras nunca tocan el efectivo, así que la marca tiene que estar. Solo se exige
            # en datos con experimento: las corridas anteriores a que existieran las sombras traen
            # la columna vacía por edad, no por un fallo.
            sin_marca = led.filter(pl.col("experiment").is_not_null() & (pl.col("experiment") != "")
                                   & pl.col("sombra").is_null())
            if sin_marca.height:
                out.append(Problema("pnl_separado",
                                    "hay filas del ledger sin marcar si son sombra o reales",
                                    sin_marca.height))
    trk = _filas(data_dir, "partial_leg_track", experiment)
    if not trk.is_empty():
        reales = [c for c in trk.columns if c in ("realized_pnl", "pnl_realizado")]
        if reales:
            out.append(Problema("pnl_separado",
                                f"la trayectoria hipotética trae resultado realizado: {reales}"))
    return out


COMPROBACIONES = ("timestamps_posibles", "un_solo_motor", "modelo_inmutable", "ordenes_conservadas",
                  "patas_completas", "precio_ejecutable", "pnl_separado")


def verificar(data_dir: str | Path, run_id: str | None = None,
              experiment: str | None = None) -> Informe:
    """Pasa todas las comprobaciones. Si alguna grave falla, la corrida no vale."""
    inf = Informe(comprobadas=list(COMPROBACIONES))
    inf.problemas += timestamps_posibles(data_dir, experiment)
    if run_id:
        inf.problemas += un_solo_motor(data_dir, run_id)
        inf.problemas += modelo_inmutable(data_dir, run_id)
    inf.problemas += ordenes_conservadas(data_dir, experiment)
    inf.problemas += patas_completas(data_dir, experiment)
    inf.problemas += precio_ejecutable(data_dir, experiment)
    inf.problemas += pnl_separado(data_dir, experiment)
    return inf
