"""Resumen, comparativos y alertas visibles para Analytics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from pos_uniformes.services.backup_service import AutomaticBackupStatus
from pos_uniformes.services.analytics_snapshot_service import AnalyticsSalesSnapshot


@dataclass(frozen=True)
class AnalyticsKpiTrendView:
    text: str
    tone: str


@dataclass(frozen=True)
class AnalyticsSummaryTrendView:
    sales: AnalyticsKpiTrendView
    tickets: AnalyticsKpiTrendView
    average: AnalyticsKpiTrendView
    units: AnalyticsKpiTrendView


def _format_percent_change(current: Decimal, previous: Decimal) -> tuple[str, str]:
    if previous == Decimal("0.00") and current == Decimal("0.00"):
        return "Sin cambio vs periodo anterior", "neutral"
    if previous == Decimal("0.00"):
        return "Nuevo movimiento vs periodo anterior", "positive"
    delta_percent = ((current - previous) / previous * Decimal("100")).quantize(Decimal("0.1"))
    if delta_percent == Decimal("0.0"):
        return "Sin cambio vs periodo anterior", "neutral"
    direction = "Subio" if delta_percent > 0 else "Bajo"
    tone = "positive" if delta_percent > 0 else "warning"
    return f"{direction} {abs(delta_percent)}% vs periodo anterior", tone


def _format_count_change(current: int, previous: int) -> tuple[str, str]:
    if current == previous:
        return "Sin cambio vs periodo anterior", "neutral"
    if previous == 0:
        return "Nuevo movimiento vs periodo anterior", "positive"
    delta_percent = (Decimal(current - previous) / Decimal(previous) * Decimal("100")).quantize(Decimal("0.1"))
    direction = "Subio" if delta_percent > 0 else "Bajo"
    tone = "positive" if delta_percent > 0 else "warning"
    return f"{direction} {abs(delta_percent)}% vs periodo anterior", tone


def build_analytics_summary_trend_view(
    current: AnalyticsSalesSnapshot,
    previous: AnalyticsSalesSnapshot,
) -> AnalyticsSummaryTrendView:
    sales_text, sales_tone = _format_percent_change(Decimal(current.total_sales), Decimal(previous.total_sales))
    tickets_text, tickets_tone = _format_count_change(current.total_tickets, previous.total_tickets)
    average_text, average_tone = _format_percent_change(
        Decimal(current.average_ticket),
        Decimal(previous.average_ticket),
    )
    units_text, units_tone = _format_count_change(current.total_units, previous.total_units)
    return AnalyticsSummaryTrendView(
        sales=AnalyticsKpiTrendView(sales_text, sales_tone),
        tickets=AnalyticsKpiTrendView(tickets_text, tickets_tone),
        average=AnalyticsKpiTrendView(average_text, average_tone),
        units=AnalyticsKpiTrendView(units_text, units_tone),
    )


def build_analytics_operational_alerts(
    *,
    stock_critical_count: int,
    overdue_layaways: int,
    automatic_backup_status: AutomaticBackupStatus | None,
    now: datetime,
    stale_backup_hours: int = 36,
) -> tuple[str, ...]:
    alerts: list[str] = []
    if stock_critical_count >= 10:
        alerts.append(f"Stock critico alto: {stock_critical_count} presentaciones.")
    if overdue_layaways > 0:
        alerts.append(f"Apartados vencidos: {overdue_layaways}.")
    if automatic_backup_status is None or automatic_backup_status.last_success_at is None:
        alerts.append("Respaldo automatico pendiente o sin primer respaldo correcto.")
    else:
        age_hours = max((now - automatic_backup_status.last_success_at).total_seconds() / 3600, 0)
        if automatic_backup_status.last_error:
            alerts.append("Ultimo respaldo automatico fallo; revisa Configuracion.")
        elif age_hours > stale_backup_hours:
            alerts.append("Ultimo respaldo automatico ya esta viejo.")
    return tuple(alerts)


def build_analytics_alerts_text(alerts: tuple[str, ...]) -> str:
    if not alerts:
        return "Sin alertas operativas relevantes en este momento."
    return " | ".join(alerts)
