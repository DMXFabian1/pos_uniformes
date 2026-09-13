"""Dibujar líneas de afluencia con el ratón y que el contador las tome sin reiniciar."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)

AFLUENCIA = Path(__file__).resolve().parents[1] / "afluencia"
if str(AFLUENCIA) not in sys.path:  # contador_afluencia importa `conteo` plano
    sys.path.insert(0, str(AFLUENCIA))

import contador_afluencia as contador  # noqa: E402
import dibujar_lineas as dl  # noqa: E402

CFG = {
    "camaras": [
        {"nombre": "ENTRADA1.1", "canal": 5, "modo": "linea", "linea": [0.3, 0.6, 0.6, 0.6], "lado_dentro": "abajo"},
        {"nombre": "ENTRADA2.2", "canal": 3, "modo": "linea", "linea": [0.5, 0.6, 0.7, 0.8], "lado_dentro": "abajo"},
        {"nombre": "ENTRADA1", "canal": 4, "modo": "paso"},
    ]
}


class SombraTests(unittest.TestCase):
    def test_lado_abajo_de_una_horizontal_es_la_mitad_inferior(self) -> None:
        pol = dl.sombra_dentro(0.2, 0.5, 0.8, 0.5, "abajo")
        self.assertEqual(sorted(pol), [(0.0, 0.5), (0.0, 1.0), (1.0, 0.5), (1.0, 1.0)])

    def test_lado_izquierda_de_una_vertical(self) -> None:
        pol = dl.sombra_dentro(0.5, 0.1, 0.5, 0.9, "izquierda")
        self.assertEqual(sorted(pol), [(0.0, 0.0), (0.0, 1.0), (0.5, 0.0), (0.5, 1.0)])

    def test_la_sombra_coincide_con_lo_que_el_contador_llama_dentro(self) -> None:
        from conteo import Linea

        linea = Linea(0.5, 0.6, 0.7, 0.8, lado_dentro="abajo")
        pol = dl.sombra_dentro(0.5, 0.6, 0.7, 0.8, "abajo")
        # El centroide de la sombra cae del lado que el contador cuenta como dentro.
        cx = sum(x for x, _ in pol) / len(pol)
        cy = sum(y for _, y in pol) / len(pol)
        self.assertEqual(linea.lado(cx, cy), 1)


class VentanaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        raiz = Path(self.tmp.name)
        self.config = raiz / "afluencia.json"
        self.config.write_text(json.dumps(CFG), encoding="utf-8")
        cuadros = raiz / "cuadros"
        cuadros.mkdir()
        pix = QPixmap(1280, 720)
        pix.fill(QColor("gray"))
        pix.save(str(cuadros / "ENTRADA2.2.jpg"))
        self.v = dl.VentanaLineas(config=self.config, cuadros=cuadros)
        self.v.show()
        app.processEvents()

    def tearDown(self) -> None:
        self.v.close()
        self.v.deleteLater()
        app.processEvents()
        self.tmp.cleanup()

    def _clic(self, x: float, y: float) -> None:
        r = self.v.lienzo._rect_imagen()
        QTest.mouseClick(self.v.lienzo, Qt.MouseButton.LeftButton, pos=QPointF(r.x() + x * r.width(), r.y() + y * r.height()).toPoint())

    def test_solo_lista_las_camaras_con_linea(self) -> None:
        nombres = [self.v.lista.item(i).text() for i in range(self.v.lista.count())]
        self.assertEqual(nombres, ["ENTRADA1.1", "ENTRADA2.2"])

    def test_dos_clics_hacen_la_linea_y_guardar_la_escribe(self) -> None:
        self.v.lista.setCurrentRow(1)
        app.processEvents()
        self.assertEqual(self.v.lienzo.linea(), [0.5, 0.6, 0.7, 0.8])
        self._clic(0.62, 0.48)
        self._clic(0.88, 0.58)
        self.v.radios["izquierda"].setChecked(True)
        dl.QMessageBox.information = staticmethod(lambda *a, **k: None)
        self.v._guardar()
        cfg = json.loads(self.config.read_text(encoding="utf-8"))
        cam = next(c for c in cfg["camaras"] if c["nombre"] == "ENTRADA2.2")
        self.assertEqual(cam["linea"], [0.62, 0.48, 0.88, 0.58])
        self.assertEqual(cam["lado_dentro"], "izquierda")
        # Lo demás del archivo se conserva tal cual.
        self.assertEqual(cfg["camaras"][2], CFG["camaras"][2])
        self.assertEqual(cfg["camaras"][0]["linea"], [0.3, 0.6, 0.6, 0.6])

    def test_sin_cuadro_no_se_puede_dibujar(self) -> None:
        self.v.lista.setCurrentRow(0)  # ENTRADA1.1 no tiene jpg
        app.processEvents()
        self.assertIsNone(self.v.lienzo.pix)
        self._clic(0.2, 0.2)
        self.assertEqual(self.v.lienzo.linea(), [0.3, 0.6, 0.6, 0.6])

    def test_un_tercer_clic_empieza_otra_linea(self) -> None:
        self.v.lista.setCurrentRow(1)
        app.processEvents()
        self._clic(0.1, 0.5)
        self.assertIsNone(self.v.lienzo.linea())
        self.assertFalse(self.v.guardar.isEnabled())
        self.assertIn("Falta el segundo clic", self.v.estado.text())
        self._clic(0.9, 0.5)
        self.assertEqual(self.v.lienzo.linea(), [0.1, 0.5, 0.9, 0.5])
        self.assertTrue(self.v.guardar.isEnabled())


class RecargaEnCalienteTests(unittest.TestCase):
    def _hilos(self):
        import threading

        return [
            contador.HiloCamara(dict(cam), "rtsp://x", {}, None, threading.Lock(), threading.Event(), None)
            for cam in CFG["camaras"]
        ]

    def test_cambia_la_linea_del_hilo_sin_reiniciar(self) -> None:
        hilos = self._hilos()
        nuevo = json.loads(json.dumps(CFG))
        nuevo["camaras"][1]["linea"] = [0.62, 0.48, 0.88, 0.58]
        nuevo["camaras"][1]["lado_dentro"] = "izquierda"
        self.assertEqual(contador.aplicar_cambios(nuevo, hilos), ["ENTRADA2.2"])
        linea = hilos[1].contador_linea.linea
        self.assertEqual((linea.x1, linea.y1, linea.x2, linea.y2, linea.lado_dentro), (0.62, 0.48, 0.88, 0.58, "izquierda"))
        # La que no cambió sigue con su contador (y su memoria de quién cruzó).
        self.assertEqual(contador.aplicar_cambios(nuevo, hilos), [])

    def test_linea_invalida_conserva_la_anterior(self) -> None:
        hilos = self._hilos()
        nuevo = json.loads(json.dumps(CFG))
        nuevo["camaras"][1]["linea"] = [0.5, 0.5, 0.5, 0.5]
        self.assertEqual(contador.aplicar_cambios(nuevo, hilos), [])
        self.assertEqual(hilos[1].contador_linea.linea.x2, 0.7)

    def test_camara_nueva_o_canal_distinto_esperan_reinicio(self) -> None:
        hilos = self._hilos()
        nuevo = json.loads(json.dumps(CFG))
        nuevo["camaras"][0]["canal"] = 9
        nuevo["camaras"].append({"nombre": "BODEGA", "canal": 7, "modo": "linea", "linea": [0, 0.5, 1, 0.5]})
        self.assertEqual(contador.aplicar_cambios(nuevo, hilos), [])
        self.assertEqual(hilos[0].cam["canal"], 5)


if __name__ == "__main__":
    unittest.main()
