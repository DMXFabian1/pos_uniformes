"""Detalle lateral visible para el tab de Historial."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HistoryDetailView:
    summary_label: str
    meta_label: str
    change_label: str
    notes_label: str


def build_history_detail_view(row: dict[str, object] | None) -> HistoryDetailView:
    if row is None:
        return HistoryDetailView(
            summary_label="Selecciona un movimiento para ver el detalle.",
            meta_label="Sin movimiento seleccionado.",
            change_label="Cambio y resultado visibles aqui cuando elijas una fila.",
            notes_label="El detalle extendido aparecera aqui para revisar la trazabilidad.",
        )

    fecha = row.get("fecha_label") or ""
    origen = row.get("origen") or ""
    registro = row.get("registro") or ""
    entidad = row.get("entidad") or ""
    tipo = row.get("tipo") or ""
    usuario = row.get("usuario") or ""
    cambio = row.get("cambio_label") or row.get("cambio") or "—"
    resultado = row.get("resultado_label") or row.get("resultado") or "—"
    detalle = str(row.get("detalle") or "Sin observacion adicional.")

    return HistoryDetailView(
        summary_label=f"{tipo} | {registro}",
        meta_label=" | ".join(
            part
            for part in (
                fecha,
                origen,
                entidad,
                f"Usuario: {usuario}" if usuario else "",
            )
            if part
        ),
        change_label=f"Cambio: {cambio} | Resultado: {resultado}",
        notes_label=detalle,
    )
