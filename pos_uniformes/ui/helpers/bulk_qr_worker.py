"""Worker QThread para generacion masiva de QR sin bloquear la UI."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from pos_uniformes.database.models import Variante
from pos_uniformes.database.connection import get_session
from pos_uniformes.utils.qr_generator import QrGenerator


class BulkQrWorker(QThread):
    """Genera QR en un hilo separado para no trabar la interfaz.

    Modos:
        "missing" — solo genera QR para variantes que no tienen archivo.
        "all"     — regenera todos los QR (sobreescribe existentes).
    """

    progress = pyqtSignal(int, int, str)
    finished_ok = pyqtSignal(int, int)
    failed = pyqtSignal(str)

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self._mode = mode
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            with get_session() as session:
                variantes = session.scalars(
                    select(Variante)
                    .where(Variante.activo.is_(True))
                    .options(joinedload(Variante.producto))
                    .order_by(Variante.sku)
                ).unique().all()

                total = len(variantes)
                generated = 0
                skipped = 0

                for i, variante in enumerate(variantes, start=1):
                    if self._cancelled:
                        break

                    sku = str(variante.sku or "").upper()

                    if self._mode == "missing" and QrGenerator.exists_for_variant(variante):
                        skipped += 1
                        if i % 50 == 0 or i == total:
                            self.progress.emit(i, total, f"Revisando {i}/{total} — {skipped} ya existentes")
                        continue

                    self.progress.emit(i, total, f"Generando {i}/{total}: {sku}")
                    QrGenerator.generate_for_variant(variante)
                    generated += 1

                self.finished_ok.emit(generated, skipped)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
