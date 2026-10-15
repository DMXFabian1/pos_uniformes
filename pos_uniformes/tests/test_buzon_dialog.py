"""La ventana del buzón: se manda, se ve en la otra PC y se copia."""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QPlainTextEdit, QPushButton  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from pos_uniformes.database.connection import Base  # noqa: E402
from pos_uniformes.services import buzon_service as bz  # noqa: E402
from pos_uniformes.ui.dialogs.buzon_dialog import TODAS, BuzonDialog  # noqa: E402

_app = QApplication.instance() or QApplication([])


class _ConBase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.abiertas: list[BuzonDialog] = []

    def tearDown(self) -> None:
        for d in self.abiertas:
            d._timer.stop()
            d.deleteLater()

    @contextmanager
    def _sesion(self):
        s = Session(self.engine)
        try:
            yield s
        finally:
            s.close()

    def _ventana(self, yo: str) -> BuzonDialog:
        d = BuzonDialog(session_factory=self._sesion, yo=yo)
        d._timer.stop()             # nada de esperas: se refresca a mano
        self.abiertas.append(d)
        return d

    @staticmethod
    def _textos(d: BuzonDialog) -> list[str]:
        return [w.toPlainText() for w in d._lista.findChildren(QPlainTextEdit)]


class BuzonTests(_ConBase):
    def test_lo_que_manda_la_principal_lo_ve_entrada(self) -> None:
        principal, entrada = self._ventana("Principal"), self._ventana("Entrada")
        principal.editor.setPlainText('Get-Content "$env:APPDATA\\x.json"')
        principal.enviar()
        entrada.refrescar()
        self.assertEqual(self._textos(entrada), ['Get-Content "$env:APPDATA\\x.json"'])
        self.assertEqual(principal.editor.toPlainText(), "")   # se vació al mandar

    def test_un_mensaje_para_otra_pc_no_le_llega_a_esta(self) -> None:
        with self._sesion() as s:
            bz.enviar(s, "solo para caja", de="Claude", para="Caja")
            s.commit()
        self.assertEqual(self._textos(self._ventana("Entrada")), [])

    def test_copiar_deja_el_texto_exacto_en_el_portapapeles(self) -> None:
        with self._sesion() as s:
            bz.enviar(s, "linea 1\n    linea 2", de="Claude")
            s.commit()
        d = self._ventana("Entrada")
        boton = next(b for b in d._lista.findChildren(QPushButton) if "Copiar" in b.text())
        boton.click()
        self.assertEqual(QApplication.clipboard().text(), "linea 1\n    linea 2")
        self.assertIn("Copiado", boton.text())

    def test_se_puede_escoger_a_quien(self) -> None:
        with self._sesion() as s:
            bz.enviar(s, "hola", de="Claude")
            s.commit()
        d = self._ventana("Entrada")
        opciones = [d.destino.itemText(i) for i in range(d.destino.count())]
        self.assertEqual(opciones, [TODAS, "Claude"])

    def test_sin_conexion_se_dice_y_lo_escrito_no_se_pierde(self) -> None:
        d = self._ventana("Entrada")

        @contextmanager
        def _caida():
            raise OSError("No route to host")
            yield  # pragma: no cover

        d._session_factory = _caida
        d.editor.setPlainText("algo importante")
        d.enviar()
        self.assertFalse(d.estado.isHidden())
        self.assertEqual(d.editor.toPlainText(), "algo importante")

    def test_vacio_no_se_manda(self) -> None:
        d = self._ventana("Entrada")
        d.editor.setPlainText("   ")
        d.enviar()
        self.assertIn("vacío", d.estado.text())


if __name__ == "__main__":
    unittest.main()
