"""Ayuda de `test_higiene_dialogos`: NO se recolecta sola (no empieza con
`test_`). Esa prueba la corre en un pytest aparte, en un solo proceso y en
este orden: la primera deja un diálogo modal abierto A PROPÓSITO."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

_app = QApplication.instance() or QApplication([])
_vivos: list = []


def test_1_deja_un_modal_abierto() -> None:
    d = QDialog()
    d.setWindowTitle("Olvidado a propósito")
    d.setModal(True)
    d.show()
    _vivos.append(d)
    assert QApplication.activeModalWidget() is d


def test_2_deja_un_aviso_sin_boton_de_escape() -> None:
    caja = QMessageBox(QMessageBox.Icon.Warning, "Aviso olvidado", "texto")
    caja.setModal(True)
    caja.show()
    _vivos.append(caja)


def test_3_la_siguiente_arranca_limpia() -> None:
    assert QApplication.activeModalWidget() is None
    assert not [w for w in QApplication.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible()]


def test_4_la_que_cierra_lo_suyo_pasa() -> None:
    d = QDialog()
    d.setModal(True)
    d.show()
    d.close()
