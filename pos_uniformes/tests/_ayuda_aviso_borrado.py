"""Ayuda de `test_kioskos_vivos`: NO se recolecta sola. Esa prueba la corre en
un pytest aparte, en un solo proceso y en este orden.

La primera muestra el aviso breve de la barra de escaneo y BORRA el kiosko
enseguida; la segunda corre el ciclo de eventos más de 1.8 s. Con la lambda
sin dueño de antes, el proceso moría aquí siempre («wrapped C/C++ object of
type QLabel has been deleted» → Fatal Python error: Aborted).
"""

from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QElapsedTimer, QEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget

_app = QApplication.instance() or QApplication([])


def test_1_avisa_y_borra_el_kiosko() -> None:
    w = QuickSaleWidget(SimpleNamespace(offline_mode=True, _kiosk_lookup_from_cache=None))
    w._flash_scan_hint("Agregado")
    w.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)


def test_2_el_ciclo_de_eventos_sigue_vivo() -> None:
    reloj = QElapsedTimer()
    reloj.start()
    while reloj.elapsed() < 2300:
        QTest.qWait(50)
