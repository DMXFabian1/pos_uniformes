"""La ventana del buzón, como WhatsApp: chats a la izquierda, lo escrito va al
chat abierto, Enter manda y cada mensaje se copia con un toque."""

from __future__ import annotations

import os
import unittest
from contextlib import contextmanager

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtGui import QKeyEvent, QTextCursor  # noqa: E402
from PyQt6.QtCore import QEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication, QLabel, QToolButton  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from pos_uniformes.database.connection import Base  # noqa: E402
from pos_uniformes.database.models import BuzonMensaje  # noqa: E402
from pos_uniformes.services import buzon_service as bz  # noqa: E402
from pos_uniformes.ui.dialogs.buzon_dialog import BuzonDialog  # noqa: E402

_app = QApplication.instance() or QApplication([])


class _ConBase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.abiertas: list[BuzonDialog] = []
        self.leidos: dict[str, dict[str, int]] = {}

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

    def _mandar(self, texto: str, de: str, para: str | None = None) -> None:
        with self._sesion() as s:
            bz.enviar(s, texto, de=de, para=para)
            s.commit()

    def _ventana(self, yo: str) -> BuzonDialog:
        propios = self.leidos.setdefault(yo, {})
        d = BuzonDialog(
            session_factory=self._sesion, yo=yo,
            leer_leidos=lambda: dict(propios),
            guardar_leido=lambda clave, i: propios.__setitem__(clave, i),
        )
        d._timer.stop()             # nada de esperas: se refresca a mano
        self.abiertas.append(d)
        return d

    @staticmethod
    def _textos(d: BuzonDialog) -> list[str]:
        return [w.text() for w in d._mensajes.findChildren(QLabel, "cuerpo") if w.isVisibleTo(d._mensajes)]

    @staticmethod
    def _claves(d: BuzonDialog) -> list[str]:
        return [c.clave for c in d._chats]


class ChatsTests(_ConBase):
    def test_abre_en_el_grupo_y_el_grupo_va_arriba(self) -> None:
        self._mandar("hola", de="Claude", para="Entrada")
        d = self._ventana("Entrada")
        self.assertEqual(self._claves(d), [bz.GRUPO, "Claude"])
        self.assertEqual(d._abierto, bz.GRUPO)

    def test_lo_escrito_va_al_chat_abierto(self) -> None:
        # Era el tropiezo de la versión con «Para:»: aquí no hay que escoger nada.
        self._mandar("hola", de="Claude", para="Entrada")
        d = self._ventana("Entrada")
        d.abrir_chat("Claude")
        d.editor.setPlainText("PC: DESKTOP-AT4V4QO\nTotal en cola: 2")
        d.enviar()
        with self._sesion() as s:
            ultimo = s.scalars(select(BuzonMensaje).order_by(BuzonMensaje.id.desc())).first()
        self.assertEqual((ultimo.de, ultimo.para), ("Entrada", "Claude"))
        self.assertEqual(d.editor.toPlainText(), "")

    def test_enter_manda_y_shift_enter_hace_otro_renglon(self) -> None:
        d = self._ventana("Entrada")
        d.editor.setPlainText("uno")
        d.editor.moveCursor(QTextCursor.MoveOperation.End)   # donde va escribiendo
        shift = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        d.editor.keyPressEvent(shift)
        self.assertEqual(d.editor.toPlainText(), "uno\n")    # salto normal, no U+2028
        enter = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        d.editor.keyPressEvent(enter)
        self.assertEqual(d.editor.toPlainText(), "")
        self.assertEqual(self._textos(d), ["uno"])     # al grupo, que era el abierto

    def test_lo_que_manda_una_pc_le_llega_a_la_otra(self) -> None:
        principal, entrada = self._ventana("Principal"), self._ventana("Entrada")
        principal.editor.setPlainText("ya actualicé")
        principal.enviar()
        entrada.refrescar()
        self.assertEqual(self._textos(entrada), ["ya actualicé"])

    def test_un_chat_privado_no_se_ve_desde_otra_pc(self) -> None:
        self._mandar("solo para caja", de="Claude", para="Caja")
        d = self._ventana("Entrada")
        d.abrir_chat("Claude")
        self.assertEqual(d._abierto, "Claude")
        self.assertEqual(self._textos(d), [])


class NoLeidosTests(_ConBase):
    def test_cuenta_lo_que_no_ha_visto_y_se_apaga_al_abrirlo(self) -> None:
        self._mandar("uno", de="Claude", para="Entrada")
        self._mandar("dos", de="Claude", para="Entrada")
        d = self._ventana("Entrada")
        claude = next(c for c in d._chats if c.clave == "Claude")
        self.assertEqual(claude.no_leidos, 2)
        d.abrir_chat("Claude")
        d.refrescar()
        claude = next(c for c in d._chats if c.clave == "Claude")
        self.assertEqual(claude.no_leidos, 0)

    def test_lo_que_mando_yo_no_cuenta_como_no_leido(self) -> None:
        self._mandar("mio", de="Entrada", para="Claude")
        d = self._ventana("Entrada")
        self.assertEqual(next(c for c in d._chats if c.clave == "Claude").no_leidos, 0)


class CopiarYNombreTests(_ConBase):
    def test_copiar_deja_el_texto_exacto(self) -> None:
        self._mandar("linea 1\n    linea 2", de="Claude")
        d = self._ventana("Entrada")
        boton = next(b for b in d._mensajes.findChildren(QToolButton) if "Copiar" in b.text())
        boton.click()
        self.assertEqual(QApplication.clipboard().text(), "linea 1\n    linea 2")
        self.assertIn("Copiado", boton.text())

    def test_cambiar_el_nombre_se_lleva_el_historial(self) -> None:
        self._mandar("hola", de="Claude", para="DESKTOP-AT4V4QO")
        d = self._ventana("DESKTOP-AT4V4QO")
        d.renombrar("Entrada")
        d.abrir_chat("Claude")
        self.assertEqual(self._textos(d), ["hola"])
        self.assertIn("Entrada", d.yo_label.text())

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


if __name__ == "__main__":
    unittest.main()
