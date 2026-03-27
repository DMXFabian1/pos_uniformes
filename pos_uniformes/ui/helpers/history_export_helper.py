"""Helpers para exportar el historial filtrado actual."""

from __future__ import annotations

from datetime import datetime

from pos_uniformes.utils.date_format import format_display_datetime


def build_history_export_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    export_rows: list[dict[str, object]] = []
    for row in rows:
        export_rows.append(
            {
                "fecha": format_display_datetime(row.get("fecha"), empty=""),
                "origen": row.get("origen") or "",
                "entidad": row.get("entidad") or "",
                "registro": row.get("registro") or "",
                "tipo": row.get("tipo") or "",
                "cambio": row.get("cambio"),
                "resultado": row.get("resultado"),
                "usuario": row.get("usuario") or "",
                "detalle": row.get("detalle") or "",
            }
        )
    return export_rows


def build_history_export_dir_name(now: datetime | None = None) -> str:
    reference = now or datetime.now()
    return reference.strftime("%Y%m%d_%H%M%S")
