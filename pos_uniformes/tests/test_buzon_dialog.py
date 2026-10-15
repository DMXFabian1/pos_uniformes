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

    def _ventana(self, yo: str, **extra) -> BuzonDialog:
        propios = self.leidos.setdefault(yo, {})
        d = BuzonDialog(
            session_factory=self._sesion, yo=yo,
            leer_leidos=lambda: dict(propios),
            guardar_leido=lambda clave, i: propios.__setitem__(clave, i),
            en_hilo=False,
            guardar_nombre_local=extra.pop("guardar_nombre_local", lambda n: None),
            identificador=extra.pop("identificador", "id-" + yo),
            **extra,
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



class EjecutarTests(_ConBase):
    def _botones(self, d: BuzonDialog, texto: str) -> list[QToolButton]:
        return [b for b in d._mensajes.findChildren(QToolButton) if texto in b.text()]

    def test_el_boton_sale_solo_en_lo_que_manda_alguien_de_confianza(self) -> None:
        self._mandar("Get-ChildItem $env:APPDATA", de="Claude", para="Entrada")
        self._mandar("Get-ChildItem $env:APPDATA", de="Caja", para="Entrada")
        d = self._ventana("Entrada")
        d.abrir_chat("Claude")
        self.assertEqual(len(self._botones(d, "Ejecutar")), 1)
        d.abrir_chat("Caja")
        self.assertEqual(self._botones(d, "Ejecutar"), [])

    def test_un_mensaje_de_texto_normal_no_se_ofrece_para_ejecutar(self) -> None:
        self._mandar("Dale Ejecutar al de abajo, por favor.", de="Claude", para="Entrada")
        d = self._ventana("Entrada")
        d.abrir_chat("Claude")
        self.assertEqual(self._botones(d, "Ejecutar"), [])

    def test_con_pin_corre_y_el_resultado_regresa_a_quien_lo_pidio(self) -> None:
        from pos_uniformes.services.buzon_ejecutar_service import Resultado

        corridos = []
        self._mandar("Get-Date | Out-String", de="Claude", para="Entrada")
        d = self._ventana(
            "Entrada",
            confirmar=lambda *_: True,
            ejecutar=lambda t: corridos.append(t) or Resultado("15/10/2026\n", 0, 0.4),
        )
        d.abrir_chat("Claude")
        self._botones(d, "Ejecutar")[0].click()
        self.assertEqual(corridos, ["Get-Date | Out-String"])
        with self._sesion() as s:
            ultimos = s.scalars(select(BuzonMensaje).order_by(BuzonMensaje.id.desc()).limit(2)).all()
        resultado, recibido = ultimos
        self.assertEqual((resultado.de, resultado.para), ("Entrada", "Claude"))
        self.assertIn("15/10/2026", resultado.texto)
        # Antes de correr avisa que lo recibió: si se traba, se sabe que arrancó.
        self.assertIn("Recibido", recibido.texto)

    def test_si_la_ejecucion_truena_igual_llega_el_error(self) -> None:
        def _truena(_):
            raise RuntimeError("se cayó")

        self._mandar("Get-Date | Out-String", de="Claude", para="Entrada")
        d = self._ventana("Entrada", confirmar=lambda *_: True, ejecutar=_truena)
        d.abrir_chat("Claude")
        self._botones(d, "Ejecutar")[0].click()
        with self._sesion() as s:
            ultimo = s.scalars(select(BuzonMensaje).order_by(BuzonMensaje.id.desc())).first()
        self.assertIn("se cayó", ultimo.texto)

    def test_con_pin_equivocado_no_corre_nada(self) -> None:
        corridos = []
        self._mandar("Get-Date | Out-String", de="Claude", para="Entrada")
        d = self._ventana("Entrada", confirmar=lambda *_: False, ejecutar=corridos.append)
        d.abrir_chat("Claude")
        self._botones(d, "Ejecutar")[0].click()
        self.assertEqual(corridos, [])
        self.assertIn("PIN", d.estado.text())

    def test_si_se_arrepiente_no_pasa_nada(self) -> None:
        corridos = []
        self._mandar("Get-Date | Out-String", de="Claude", para="Entrada")
        d = self._ventana("Entrada", confirmar=lambda *_: None, ejecutar=corridos.append)
        d.abrir_chat("Claude")
        self._botones(d, "Ejecutar")[0].click()
        self.assertEqual(corridos, [])
        self.assertTrue(d.estado.isHidden())


class AvisoTests(unittest.TestCase):
    def setUp(self) -> None:
        from PyQt6.QtWidgets import QWidget

        from pos_uniformes.ui.helpers.buzon_aviso import BuzonAviso

        self.ventana = QWidget()
        self.ventana.resize(800, 600)
        self.n = 0
        self.abiertos = []
        self.aviso = BuzonAviso(
            self.ventana, contar=lambda: self.n,
            abrir=lambda v: self.abiertos.append(v), en_hilo=False,
        )
        self.aviso._timer.stop()
        self.aviso._primera.stop()

    def tearDown(self) -> None:
        self.ventana.deleteLater()

    def test_sin_mensajes_no_se_ve(self) -> None:
        self.aviso.revisar()
        self.assertTrue(self.aviso.isHidden())

    def test_con_mensajes_dice_cuantos(self) -> None:
        self.n = 2
        self.aviso.revisar()
        self.assertFalse(self.aviso.isHidden())
        self.assertIn("2 mensajes nuevos", self.aviso.text())

    def test_uno_en_singular(self) -> None:
        self.n = 1
        self.aviso.revisar()
        self.assertIn("1 mensaje nuevo", self.aviso.text())

    def test_tocarlo_abre_el_buzon_y_vuelve_a_contar(self) -> None:
        self.n = 3
        self.aviso.revisar()
        self.n = 0                      # lo leyó en el buzón
        self.aviso.click()
        self.assertEqual(self.abiertos, [self.ventana])
        self.assertTrue(self.aviso.isHidden())

    def test_va_en_la_esquina_de_abajo_a_la_derecha(self) -> None:
        self.n = 1
        self.aviso.revisar()
        self.assertGreater(self.aviso.x(), 800 / 2)
        self.assertGreater(self.aviso.y(), 600 / 2)

    def test_si_no_se_puede_contar_no_truena(self) -> None:
        def _falla():
            raise OSError("sin red")

        self.aviso._contar = _falla
        self.aviso.revisar()
        self.assertTrue(self.aviso.isHidden())



class NombreDeLaPcTests(_ConBase):
    def _pc(self, ident: str, nombre: str) -> None:
        from pos_uniformes.database.models import Satelite

        with self._sesion() as s:
            s.add(Satelite(identificador=ident, nombre=nombre))
            s.commit()

    def test_no_se_puede_llamar_igual_que_otra_pc(self) -> None:
        self._pc("id-caja", "Caja")
        guardados = []
        d = self._ventana("DESKTOP-AT4V4QO", identificador="id-entrada",
                          guardar_nombre_local=guardados.append)
        d.renombrar("caja")
        self.assertIn("otra PC", d.estado.text())
        self.assertEqual(guardados, [])                      # no cambió nada
        self.assertEqual(d._yo, "DESKTOP-AT4V4QO")

    def test_claude_y_el_grupo_estan_reservados(self) -> None:
        d = self._ventana("Entrada")
        for nombre in ("Claude", "todas las pcs"):
            d.renombrar(nombre)
            self.assertIn("reservado", d.estado.text())
        self.assertEqual(d._yo, "Entrada")

    def test_renombrar_guarda_el_nombre_local_y_el_registro_por_identificador(self) -> None:
        from pos_uniformes.database.models import Satelite

        self._pc("id-entrada", "DESKTOP-AT4V4QO")
        guardados = []
        d = self._ventana("DESKTOP-AT4V4QO", identificador="id-entrada",
                          guardar_nombre_local=guardados.append)
        d.renombrar("  Entrada  ")
        self.assertEqual(guardados, ["Entrada"])
        with self._sesion() as s:
            self.assertEqual(s.get(Satelite, 1).nombre, "Entrada")


if __name__ == "__main__":
    unittest.main()
