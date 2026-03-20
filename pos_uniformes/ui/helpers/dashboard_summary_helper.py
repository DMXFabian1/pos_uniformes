"""Resumen visible del dashboard principal."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class DashboardStatusView:
    metrics_text: str


@dataclass(frozen=True)
class DashboardOperationsView:
    primary_text: str
    secondary_text: str


@dataclass(frozen=True)
class DashboardFutureAlertsView:
    title_text: str
    body_text: str


@dataclass(frozen=True)
class DashboardKpiCardView:
    subtitle_text: str
    detail_text: str
    tone: str


@dataclass(frozen=True)
class DashboardKpiCardsView:
    users: DashboardKpiCardView
    products: DashboardKpiCardView
    stock: DashboardKpiCardView
    sales: DashboardKpiCardView


@dataclass(frozen=True)
class DashboardOperationalAlertsView:
    text: str
    tone: str


def build_dashboard_status_view(
    *,
    usuarios: int,
    proveedores: int,
    productos: int,
    variantes: int,
    stock_total: int,
    compras: int,
    ventas: int,
    is_admin: bool,
) -> DashboardStatusView:
    if is_admin:
        metrics_parts = (
            f"Usuarios: {usuarios}",
            f"Proveedores: {proveedores}",
            f"Productos: {productos}",
            f"Presentaciones: {variantes}",
            f"Stock total: {stock_total}",
            f"Compras: {compras}",
            f"Ventas: {ventas}",
        )
    else:
        metrics_parts = (
            f"Productos: {productos}",
            f"Presentaciones: {variantes}",
            f"Stock total: {stock_total}",
            f"Ventas: {ventas}",
        )
    return DashboardStatusView(metrics_text=" | ".join(metrics_parts))


def build_dashboard_operations_view(
    *,
    ventas_confirmadas: int,
    ingresos: Decimal,
    compras_confirmadas: Decimal,
    stock_bajo: int,
    is_admin: bool,
) -> DashboardOperationsView:
    primary_text = f"Ventas confirmadas: {ventas_confirmadas} | Ingreso confirmado: ${ingresos}"
    if is_admin:
        secondary_text = (
            f"Compras confirmadas: ${compras_confirmadas} | "
            f"Presentaciones con stock bajo (<=3): {stock_bajo}"
        )
    else:
        secondary_text = "Snapshot rapido del periodo actual listo para revision."
    return DashboardOperationsView(primary_text=primary_text, secondary_text=secondary_text)


def build_dashboard_future_alerts_view(*, is_admin: bool) -> DashboardFutureAlertsView:
    if is_admin:
        return DashboardFutureAlertsView(
            title_text="Zona reservada para futuras notificaciones del negocio.",
            body_text=(
                "Aqui podran aparecer avisos de stock critico, respaldos automaticos, "
                "caja abierta demasiado tiempo y otras incidencias operativas."
            ),
        )
    return DashboardFutureAlertsView(
        title_text="Zona reservada para futuras notificaciones de operacion.",
        body_text=(
            "Aqui podran aparecer avisos de apartados por atender, movimientos pendientes "
            "y recordatorios relevantes del turno."
        ),
    )


def build_dashboard_kpi_cards_view(
    *,
    usuarios: int,
    productos: int,
    variantes: int,
    stock_total: int,
    ventas: int,
    ventas_confirmadas: int,
    stock_bajo: int,
    is_admin: bool,
) -> DashboardKpiCardsView:
    users_tone = "positive" if usuarios > 0 else "danger"
    products_tone = "positive" if variantes > 0 else "warning"
    if stock_bajo >= 100:
        stock_tone = "danger"
    elif stock_bajo > 0:
        stock_tone = "warning"
    else:
        stock_tone = "positive"
    sales_tone = "positive" if ventas_confirmadas > 0 else "neutral"

    return DashboardKpiCardsView(
        users=DashboardKpiCardView(
            subtitle_text="Cuentas con acceso al POS",
            detail_text="Operacion lista para acceso administrativo." if is_admin else "Usuarios listos para operar.",
            tone=users_tone,
        ),
        products=DashboardKpiCardView(
            subtitle_text="Catalogo visible para caja",
            detail_text=f"{variantes} presentaciones activas para consulta.",
            tone=products_tone,
        ),
        stock=DashboardKpiCardView(
            subtitle_text="Unidades disponibles",
            detail_text=(
                "Sin alertas de stock bajo."
                if stock_bajo <= 0
                else f"{stock_bajo} presentaciones con stock bajo dentro del catalogo."
            ),
            tone=stock_tone,
        ),
        sales=DashboardKpiCardView(
            subtitle_text="Documentos registrados",
            detail_text=f"{ventas_confirmadas} ventas confirmadas dentro de {ventas} documentos.",
            tone=sales_tone,
        ),
    )


def build_dashboard_operational_alerts_view(alerts: tuple[str, ...]) -> DashboardOperationalAlertsView:
    if not alerts:
        return DashboardOperationalAlertsView(
            text="Sin microalertas operativas relevantes en este momento.",
            tone="positive",
        )
    if len(alerts) == 1:
        return DashboardOperationalAlertsView(text=alerts[0], tone="warning")
    return DashboardOperationalAlertsView(
        text=f"{alerts[0]} | {alerts[1]}",
        tone="danger" if len(alerts) >= 3 else "warning",
    )
