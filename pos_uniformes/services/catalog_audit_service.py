"""Servicios para auditar cambios administrativos del catalogo."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from pos_uniformes.database.models import CambioCatalogo, TipoCambioCatalogo, TipoEntidadCatalogo, Usuario


class CatalogAuditService:
    """Registra cambios relevantes de catalogo para consulta posterior."""

    @staticmethod
    def _stringify(value: object | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return "ACTIVO" if value else "INACTIVO"
        if isinstance(value, Decimal):
            return format(value, ".2f")
        return str(value)

    @classmethod
    def registrar_cambio(
        cls,
        session: Session,
        usuario: Usuario,
        entidad_tipo: TipoEntidadCatalogo,
        entidad_id: int,
        accion: TipoCambioCatalogo,
        campo: str,
        valor_anterior: object | None,
        valor_nuevo: object | None,
        descripcion_entidad: str,
        observacion: str | None = None,
    ) -> CambioCatalogo:
        cambio = CambioCatalogo(
            usuario=usuario,
            entidad_tipo=entidad_tipo,
            entidad_id=entidad_id,
            accion=accion,
            campo=campo,
            valor_anterior=cls._stringify(valor_anterior),
            valor_nuevo=cls._stringify(valor_nuevo),
            descripcion_entidad=descripcion_entidad[:200],
            observacion=observacion,
        )
        session.add(cambio)
        return cambio
