"""Radiografía del mercado con los datos propios.

Responde las preguntas que deciden la estrategia, y que no se pueden contestar leyendo foros:
¿cuánto de lo que seguimos se mueve de verdad? ¿qué tan ancho es el spread? ¿cuánto pesa la
comisión frente a ese spread? Todo sale de lo que el bot ya guardó.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import polars as pl

from .storage import latest_markets, scan


@dataclass
class Radiografia:
    minutos: float = 0.0
    categorias: list[dict[str, Any]] = field(default_factory=list)
    tokens_seguidos: int = 0
    tokens_con_trades: int = 0
    top: list[dict[str, Any]] = field(default_factory=list)
    aviso: str = ""

    @property
    def tokens_muertos(self) -> int:
        return max(0, self.tokens_seguidos - self.tokens_con_trades)


def _indice(data_dir: str | Path) -> dict[str, dict[str, Any]]:
    mk = latest_markets(data_dir)
    if mk is None:
        return {}
    idx: dict[str, dict[str, Any]] = {}
    for r in mk.to_dicts():
        try:
            toks = json.loads(r["tokens"])
        except (json.JSONDecodeError, TypeError):
            continue
        for t in toks:
            idx[t["token_id"]] = {"cat": r["category"], "tick": float(r["tick_size"] or 0.01),
                                  "fee": float(r["fee_rate"] or 0), "q": str(r["question"])[:60]}
    return idx


def radiografia(data_dir: str | Path) -> Radiografia:
    rx = Radiografia()
    idx = _indice(data_dir)
    q_lf, t_lf = scan(data_dir, "quotes"), scan(data_dir, "trades")
    if not idx or q_lf is None:
        rx.aviso = "faltan datos: deja el bot corriendo un rato"
        return rx
    campo = lambda c, d: (lambda t: idx.get(t, {}).get(c, d))  # noqa: E731

    q = q_lf.collect().filter(pl.col("spread").is_not_null() & (pl.col("mid") > 0.02) & (pl.col("mid") < 0.98))
    if not q.height:
        rx.aviso = "todavía no hay cotizaciones utilizables"
        return rx
    q = q.with_columns([
        pl.col("token_id").map_elements(campo("cat", "?"), return_dtype=pl.String).alias("cat"),
        pl.col("token_id").map_elements(campo("tick", 0.01), return_dtype=pl.Float64).alias("tick"),
        pl.col("token_id").map_elements(campo("fee", 0.0), return_dtype=pl.Float64).alias("fee"),
    ]).with_columns((pl.col("spread") / pl.col("tick")).round(0).alias("ticks"))

    tr = t_lf.collect() if t_lf is not None else None
    if tr is not None and tr.height:
        rx.minutos = (tr["ts_ms"].max() - tr["ts_ms"].min()) / 60000
        tr = tr.with_columns([
            pl.col("token_id").map_elements(campo("cat", "?"), return_dtype=pl.String).alias("cat"),
            (pl.col("size") * pl.col("price")).alias("usd"),
        ])
    rx.tokens_seguidos = len(idx)
    rx.tokens_con_trades = int(tr["token_id"].n_unique()) if tr is not None and tr.height else 0

    for cat in sorted(q["cat"].unique().to_list()):
        sq = q.filter(pl.col("cat") == cat)
        st = tr.filter(pl.col("cat") == cat) if tr is not None and tr.height else None
        n_tokens = len({t for t, v in idx.items() if v["cat"] == cat})
        activos = int(st["token_id"].n_unique()) if st is not None and st.height else 0
        fee = float(sq["fee"].median() or 0)
        tick = float(sq["tick"].median() or 0.01)
        # coste de cruzar el libro en un mercado a 0,50: medio spread más comisión
        coste = tick / 2 + fee * 0.25
        rx.categorias.append({
            "categoria": cat, "tokens": n_tokens, "activos": activos,
            "muertos_pct": round(100 * (1 - activos / n_tokens), 1) if n_tokens else 0.0,
            "spread_1_tick_pct": round(100 * sq.filter(pl.col("ticks") <= 1).height / sq.height, 1),
            "spread_3mas_pct": round(100 * sq.filter(pl.col("ticks") >= 3).height / sq.height, 1),
            "profundidad": round(float(sq["bid_size"].median() or 0)),
            "fee": fee, "tick": tick,
            "coste_entrar": round(coste, 4), "coste_entrar_pct": round(coste / 0.5 * 100, 1),
            "trades": int(st.height) if st is not None else 0,
            "usd": round(float(st["usd"].sum()), 0) if st is not None and st.height else 0.0,
            "trades_min_mercado": round(st.height / rx.minutos / activos, 2) if (st is not None and st.height
                                                                                and rx.minutos and activos) else 0.0,
        })
    rx.categorias.sort(key=lambda c: -c["trades"])

    if tr is not None and tr.height:
        top = tr.group_by("token_id").agg(pl.len().alias("n"), pl.col("usd").sum().round(0).alias("usd")) \
                .sort("usd", descending=True).head(10)
        rx.top = [{"mercado": idx.get(r["token_id"], {}).get("q", "?"), "trades": r["n"], "usd": r["usd"]}
                  for r in top.to_dicts()]
    return rx


def formatear(rx: Radiografia) -> str:
    if rx.aviso:
        return f"Radiografía del mercado: {rx.aviso}."
    L = [f"Ventana analizada: {rx.minutos:.0f} minutos de actividad", ""]
    L.append("DÓNDE HAY MOVIMIENTO DE VERDAD")
    L.append(f"  {'categoría':15}{'mercados':>10}{'con trades':>12}{'muertos':>9}{'trades/min':>12}{'USD movidos':>14}")
    for c in rx.categorias:
        L.append(f"  {c['categoria']:15}{c['tokens']:>10}{c['activos']:>12}{c['muertos_pct']:>8.0f}%"
                 f"{c['trades_min_mercado']:>12.2f}{c['usd']:>14,.0f}")
    L.append(f"\n  De {rx.tokens_seguidos} mercados seguidos, {rx.tokens_con_trades} se movieron y "
             f"{rx.tokens_muertos} no tuvieron ni un trade ({100 * rx.tokens_muertos / max(rx.tokens_seguidos, 1):.0f} %).")
    L += ["", "QUÉ TAN CARO ES OPERAR (en un mercado a 0,50, cruzando el libro)"]
    L.append(f"  {'categoría':15}{'spread 1 tick':>15}{'spread 3+':>11}{'comisión':>10}{'coste entrar':>14}{'sobre el precio':>17}")
    for c in rx.categorias:
        L.append(f"  {c['categoria']:15}{c['spread_1_tick_pct']:>14.0f}%{c['spread_3mas_pct']:>10.0f}%"
                 f"{c['fee'] * 100:>9.0f}%{c['coste_entrar']:>14.4f}{c['coste_entrar_pct']:>16.1f}%")
    L.append("\n  Esa última columna es el listón: una señal que cruza el libro tiene que ganar más que eso")
    L.append("  solo para empatar. Poniendo órdenes en vez de cruzarlas, la comisión es cero.")
    if rx.top:
        L += ["", "LOS MERCADOS QUE DE VERDAD MUEVEN DINERO"]
        for t in rx.top[:8]:
            L.append(f"  {t['usd']:>10,.0f} USD  {t['trades']:>5} trades   {t['mercado']}")
    return "\n".join(L)
