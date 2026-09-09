"""Descubrimiento de mercados vía Gamma API (eventos por tag: deportes, política)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Any

import httpx

from .config import Config
from .fees import fee_rate_from_market

log = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    token_id: str
    outcome: str
    index: int


@dataclass
class MarketInfo:
    condition_id: str
    gamma_id: str
    question: str
    slug: str
    event_id: str
    event_slug: str
    event_title: str
    category: str
    tokens: list[TokenInfo]
    neg_risk: bool
    event_neg_risk: bool
    tick_size: float
    min_order_size: float
    fee_rate: float
    fee_type: str
    volume_24h: float
    liquidity: float
    end_date: str
    accepting_orders: bool
    sports_market_type: str
    game_start_time: str
    tags: list[str] = field(default_factory=list)
    event_market_count: int = 0          # mercados abiertos del evento (cobertura para multi-outcome)
    event_neg_risk_augmented: bool = False
    event_game_id: str = ""              # enlaza con el feed en vivo de deportes
    event_start_time: str = ""

    @property
    def is_binary(self) -> bool:
        return len(self.tokens) == 2

    @property
    def token_ids(self) -> list[str]:
        return [t.token_id for t in self.tokens]

    def token_for_outcome(self, outcome: str) -> TokenInfo | None:
        for t in self.tokens:
            if t.outcome.lower() == outcome.lower():
                return t
        return None

    @property
    def yes_token(self) -> TokenInfo:
        """Token 'Yes' (o el primer outcome en mercados deportivos A vs B)."""
        return self.token_for_outcome("Yes") or self.tokens[0]

    @property
    def no_token(self) -> TokenInfo:
        return self.token_for_outcome("No") or self.tokens[1]

    def to_row(self, ts_ms: int, status: str = "active") -> dict[str, Any]:
        d = asdict(self)
        d["tokens"] = json.dumps([asdict(t) for t in self.tokens])
        d["tags"] = json.dumps(self.tags)
        d["ts_ms"] = ts_ms
        d["status"] = status
        return d

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "MarketInfo":
        toks = [TokenInfo(**t) for t in json.loads(row["tokens"])]
        tags = json.loads(row["tags"]) if row.get("tags") else []
        kwargs = {k: row[k] for k in cls.__dataclass_fields__
              if k in row and row[k] is not None and k not in ("tokens", "tags")}
        return cls(tokens=toks, tags=tags, **kwargs)


def _f(x: Any, default: float = 0.0) -> float:
    try:
        return float(x) if x is not None else default
    except (TypeError, ValueError):
        return default


def parse_market(m: dict[str, Any], event: dict[str, Any], category: str, default_fee: float) -> MarketInfo | None:
    try:
        token_ids = json.loads(m.get("clobTokenIds") or "[]")
        outcomes = json.loads(m.get("outcomes") or "[]")
    except json.JSONDecodeError:
        return None
    if len(token_ids) < 2 or len(token_ids) != len(outcomes):
        return None
    tokens = [TokenInfo(str(t), str(o), i) for i, (t, o) in enumerate(zip(token_ids, outcomes))]
    sched = m.get("feeSchedule")
    return MarketInfo(
        condition_id=str(m.get("conditionId") or ""),
        gamma_id=str(m.get("id") or ""),
        question=str(m.get("question") or ""),
        slug=str(m.get("slug") or ""),
        event_id=str(event.get("id") or ""),
        event_slug=str(event.get("slug") or ""),
        event_title=str(event.get("title") or ""),
        category=category,
        tokens=tokens,
        neg_risk=bool(m.get("negRisk")),
        event_neg_risk=bool(event.get("negRisk")),
        tick_size=_f(m.get("orderPriceMinTickSize"), 0.01),
        min_order_size=_f(m.get("orderMinSize"), 5),
        fee_rate=fee_rate_from_market(m, default_fee),
        fee_type=str(m.get("feeType") or ("none" if m.get("feesEnabled") is False else "")),
        volume_24h=_f(m.get("volume24hr")),
        liquidity=_f(m.get("liquidityNum"), _f(m.get("liquidity"))),
        end_date=str(m.get("endDate") or ""),
        accepting_orders=bool(m.get("acceptingOrders")),
        sports_market_type=str(m.get("sportsMarketType") or ""),
        game_start_time=str(m.get("gameStartTime") or ""),
        tags=[str(t.get("slug")) for t in (event.get("tags") or []) if t.get("slug")],
        event_market_count=sum(1 for x in (event.get("markets") or []) if not x.get("closed")),
        event_neg_risk_augmented=bool(event.get("negRiskAugmented")),
        event_game_id=str(event.get("gameId") or ""),
        event_start_time=str(event.get("startTime") or ""),
    )


class GammaClient:
    def __init__(self, base_url: str, timeout: float = 20.0):
        self._c = httpx.AsyncClient(base_url=base_url, timeout=timeout, headers={"User-Agent": "polymarket-scalper/0.1"})

    async def close(self) -> None:
        await self._c.aclose()

    async def events_by_tag(self, tag_id: int, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        r = await self._c.get("/events", params={
            "closed": "false", "active": "true", "limit": limit, "offset": offset,
            "order": "volume24hr", "ascending": "false", "tag_id": tag_id,
        })
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else []

    async def market_by_condition(self, condition_id: str) -> dict[str, Any] | None:
        r = await self._c.get("/markets", params={"condition_ids": condition_id})
        r.raise_for_status()
        data = r.json()
        return data[0] if isinstance(data, list) and data else None


async def discover_markets(cfg: Config, gamma: GammaClient) -> list[MarketInfo]:
    """Devuelve los mercados activos con libro de órdenes de las categorías configuradas."""
    found: dict[str, MarketInfo] = {}
    dcfg = cfg.discovery
    for cat, ccfg in cfg.categories.items():
        seen_events = 0
        offset = 0
        page = 100
        while seen_events < dcfg.events_per_category:
            try:
                events = await gamma.events_by_tag(ccfg.tag_id, limit=page, offset=offset)
            except httpx.HTTPError as e:
                log.warning("gamma events tag=%s offset=%s falló: %s", ccfg.tag_id, offset, e)
                break
            if not events:
                break
            for ev in events:
                # en eventos negRisk hacen falta TODOS los mercados abiertos para cubrir el espacio de
                # resultados; el filtro de volumen se aplica al evento, no a cada mercado
                whole_event = bool(ev.get("negRisk")) and _f(ev.get("volume24hr")) >= dcfg.min_volume_24h
                for m in ev.get("markets") or []:
                    if not m.get("enableOrderBook") or m.get("closed") or not m.get("acceptingOrders"):
                        continue
                    if not whole_event and _f(m.get("volume24hr")) < dcfg.min_volume_24h:
                        continue
                    smt = str(m.get("sportsMarketType") or "")
                    if smt and smt in dcfg.exclude_sports_market_types:
                        continue
                    mi = parse_market(m, ev, cat, ccfg.default_fee_rate)
                    if mi is None or not mi.condition_id:
                        continue
                    if mi.condition_id not in found:      # un evento puede tener varios tags
                        found[mi.condition_id] = mi
            seen_events += len(events)
            offset += page
            if len(events) < page:
                break
    markets = sorted(found.values(), key=lambda m: m.volume_24h, reverse=True)[: dcfg.max_markets]
    log.info("discovery: %d mercados (%s)", len(markets),
             ", ".join(f"{c}={sum(1 for m in markets if m.category == c)}" for c in cfg.categories))
    return markets
