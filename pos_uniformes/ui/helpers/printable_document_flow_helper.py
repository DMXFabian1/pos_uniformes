"""Orquesta apertura de documentos imprimibles sin cargar esa logica en MainWindow."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import TypeVar

from pos_uniformes.services.sale_document_view_service import PrintableDocumentView

SessionT = TypeVar("SessionT")
ParentT = TypeVar("ParentT")


def open_printable_document_flow(
    *,
    parent: ParentT,
    session_factory: Callable[[], AbstractContextManager[SessionT]],
    build_document_view: Callable[[SessionT], PrintableDocumentView],
    open_dialog: Callable[[ParentT, str, str], None],
) -> PrintableDocumentView:
    with session_factory() as session:
        document_view = build_document_view(session)
    open_dialog(parent, document_view.title, document_view.content)
    return document_view
