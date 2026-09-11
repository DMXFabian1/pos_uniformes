"""Estudio del arrastre entre ventanas "Up or Down".

La pregunta: al abrir una ventana nueva, el mercado no arranca en 0,50 sino sesgado por lo que
acaba de pasar. ¿Ese sesgo es información (el mercado sabe algo) o sobrerreacción (memoria de la
racha)? La respuesta decide si conviene ir a favor de la racha o en contra.

Método, sin nada de teoría:
1. Se toman las ventanas ya resueltas, con su strike y su cierre.
2. Para cada una se mide el precio del token "Up" a los `offset_seconds` de la apertura.
   En ese momento el precio de referencia y el strike son casi iguales, así que la probabilidad
   real es ~0,50: todo lo que se aparte de 0,50 es sesgo del mercado.
3. Se compara ese sesgo con el resultado real.
4. Se calcula lo que habrían dado las dos estrategias, con la comisión del 7 % incluida:
   ir a favor del sesgo o ir en contra.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from .fees import taker_fee
from .storage import scan

FEE_CRIPTO = 0.07


@dataclass
class Muestra:
    symbol: str
    slug: str
    start_ms: int
    p_up_mercado: float       # precio implícito de "Up" poco después de abrir
    up_won: bool
    return_bps: float
    prev_up_won: bool | None
    prev_return_bps: float | None


@dataclass
class Estudio:
    n: int = 0
    muestras: list[Muestra] = field(default_factory=list)
    por_racha: list[dict[str, Any]] = field(default_factory=list)
    estrategias: list[dict[str, Any]] = field(default_factory=list)
    sesgo_medio: float = 0.0
    aciertos_mercado: float = 0.0
    aviso: str = ""


def _up_token_por_condicion(data_dir: str | Path) -> dict[str, str]:
    mk = scan(data_dir, "markets")
    if mk is None:
        return {}
    df = mk.sort("ts_ms").group_by("condition_id").last().collect()
    out: dict[str, str] = {}
    for r in df.to_dicts():
        try:
            toks = json.loads(r["tokens"])
        except (json.JSONDecodeError, TypeError):
            continue
        for t in toks:
            if str(t.get("outcome", "")).lower() == "up":
                out[r["condition_id"]] = t["token_id"]
    return out


def recopilar(data_dir: str | Path, offset_seconds: float = 20, tolerancia_s: float = 40) -> Estudio:
    est = Estudio()
    w = scan(data_dir, "updown_windows")
    q = scan(data_dir, "quotes")
    if w is None or q is None:
        est.aviso = "faltan datos: hacen falta las tablas updown_windows y quotes"
        return est
    ventanas = (w.filter(pl.col("status") == "resuelta").sort("ts_ms")
                .group_by("condition_id").last().collect().sort("start_ms"))
    if not ventanas.height:
        est.aviso = "todavía no hay ventanas resueltas"
        return est
    up_tok = _up_token_por_condicion(data_dir)
    objetivo = int(offset_seconds * 1000)
    tol = int(tolerancia_s * 1000)
    quotes = q.select("token_id", "ts_ms", "mid").collect()
    por_token: dict[str, list[tuple[int, float]]] = {}
    for r in quotes.to_dicts():
        if r["mid"] is not None:
            por_token.setdefault(r["token_id"], []).append((r["ts_ms"], r["mid"]))
    for v in por_token.values():
        v.sort()

    anterior: dict[str, Muestra] = {}
    for r in ventanas.to_dicts():
        tok = up_tok.get(r["condition_id"])
        serie = por_token.get(tok or "")
        if not serie:
            continue
        blanco = r["start_ms"] + objetivo
        mejor = min(serie, key=lambda x: abs(x[0] - blanco))
        if abs(mejor[0] - blanco) > tol:
            continue
        strike, cierre = r["strike"], r["settle_price"]
        if not strike or not cierre:
            continue
        prev = anterior.get(r["symbol"])
        m = Muestra(symbol=r["symbol"], slug=r["slug"], start_ms=r["start_ms"], p_up_mercado=float(mejor[1]),
                    up_won=bool(r["up_won"]), return_bps=(cierre / strike - 1) * 10000,
                    prev_up_won=None if prev is None else prev.up_won,
                    prev_return_bps=None if prev is None else prev.return_bps)
        est.muestras.append(m)
        anterior[r["symbol"]] = m
    est.n = len(est.muestras)
    if est.n == 0:
        est.aviso = "hay ventanas resueltas pero sin cotizaciones cerca de la apertura"
    return est


def analizar(est: Estudio, size: float = 50) -> Estudio:
    ms = [m for m in est.muestras if m.prev_up_won is not None]
    if not ms:
        est.aviso = est.aviso or "aún no hay ventanas consecutivas del mismo símbolo"
        return est
    est.sesgo_medio = sum(m.p_up_mercado - 0.5 for m in ms) / len(ms)
    est.aciertos_mercado = sum(1 for m in ms if (m.p_up_mercado > 0.5) == m.up_won) / len(ms)

    for etiqueta, grupo in (("racha anterior: subió", [m for m in ms if m.prev_up_won]),
                            ("racha anterior: bajó", [m for m in ms if not m.prev_up_won])):
        if not grupo:
            continue
        sesgo = sum(m.p_up_mercado - 0.5 for m in grupo) / len(grupo)
        real = sum(1 for m in grupo if m.up_won) / len(grupo)
        est.por_racha.append({
            "grupo": etiqueta, "n": len(grupo),
            "p_up_apertura": round(sum(m.p_up_mercado for m in grupo) / len(grupo), 4),
            "sesgo": round(sesgo, 4), "acabaron_up": round(real, 4),
            "diferencia": round(real - (0.5 + sesgo), 4),
        })

    for nombre, a_favor in (("ir A FAVOR del sesgo del mercado", True), ("ir EN CONTRA del sesgo (fade)", False)):
        pnl = ganadas = 0.0
        operadas = 0
        for m in ms:
            sesgo = m.p_up_mercado - 0.5
            if abs(sesgo) < 1e-9:
                continue
            comprar_up = (sesgo > 0) if a_favor else (sesgo < 0)
            precio = m.p_up_mercado if comprar_up else 1 - m.p_up_mercado
            if not (0.01 < precio < 0.99):
                continue
            operadas += 1
            gano = m.up_won if comprar_up else not m.up_won
            coste = size * precio + taker_fee(size, precio, FEE_CRIPTO)
            pnl += (size if gano else 0.0) - coste
            ganadas += 1 if gano else 0
        if operadas:
            est.estrategias.append({
                "estrategia": nombre, "operaciones": operadas, "acierto": round(ganadas / operadas, 4),
                "pnl_usd": round(pnl, 2), "pnl_por_operacion": round(pnl / operadas, 4),
            })
    return est


def formatear(est: Estudio) -> str:
    if est.aviso and not est.por_racha:
        return f"Estudio del arrastre entre ventanas: {est.aviso}"
    ms = [m for m in est.muestras if m.prev_up_won is not None]
    lineas = [f"Ventanas resueltas con cotización de apertura: {est.n}  (con ventana previa del mismo símbolo: {len(ms)})",
              f"Sesgo medio del mercado al abrir: {est.sesgo_medio:+.4f}  (0 = arranca justo en 0,50)",
              f"El sesgo acertó la dirección en el {est.aciertos_mercado * 100:.1f} % de los casos", ""]
    lineas.append("Por cómo terminó la ventana anterior:")
    lineas.append(f"  {'grupo':26}{'n':>5}{'P(Up) al abrir':>16}{'acabaron Up':>14}{'diferencia':>12}")
    for g in est.por_racha:
        lineas.append(f"  {g['grupo']:26}{g['n']:>5}{g['p_up_apertura']:>16.4f}{g['acabaron_up']:>14.4f}{g['diferencia']:>+12.4f}")
    lineas += ["", "Qué habría dado cada estrategia (50 shares, comisión del 7 % incluida):",
               f"  {'estrategia':36}{'ops':>6}{'acierto':>10}{'PnL USD':>12}{'por op.':>10}"]
    for e in est.estrategias:
        lineas.append(f"  {e['estrategia']:36}{e['operaciones']:>6}{e['acierto']:>10.3f}{e['pnl_usd']:>12.2f}{e['pnl_por_operacion']:>10.4f}")
    n = len(ms)
    if n < 100:
        err = 0.5 / math.sqrt(max(n, 1))
        lineas += ["", f"AVISO: con {n} ventanas el margen de error de una tasa de acierto es de unos "
                       f"±{err * 100:.0f} puntos. Hacen falta varios cientos para concluir algo."]
    return "\n".join(lineas)


def estudiar(data_dir: str | Path, offset_seconds: float = 20, size: float = 50) -> Estudio:
    return analizar(recopilar(data_dir, offset_seconds), size)
