"""Ayuda de `test_kioskos_vivos`: NO se recolecta sola. Esa prueba la corre en
un pytest aparte, en un solo proceso, DESPUÉS de test_e4c_kiosko_programas.

Solo corre el ciclo de eventos más de 1.8 s. test_e4c borraba sus kioskos con
`deleteLater` justo después de que mostraran un aviso de 1.8 s en la barra de
escaneo; la lambda del aviso caía aquí sobre la etiqueta ya destruida y PyQt6
tumbaba el proceso («wrapped C/C++ object of type QLabel has been deleted» →
Fatal Python error: Aborted). Así se veía en la suite con -n 6 (2026-11-11).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QElapsedTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def test_el_ciclo_de_eventos_sigue_vivo() -> None:
    reloj = QElapsedTimer()
    reloj.start()
    while reloj.elapsed() < 2300:
        QTest.qWait(50)
