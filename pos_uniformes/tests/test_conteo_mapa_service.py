"""Mapa de conteos: qué está contado y qué no, por capas."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from pos_uniformes.database.connection import Base
from pos_uniformes.database.models import Variante
from pos_uniformes.services import conteo_mapa_service as m
from pos_uniformes.tests.test_conteo_jornada_service import _seed, _seed_basicos


class MapaTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.uno = _seed(self.s, "Uno", stock=3)     # 2 prendas × tallas 6 y 8
        self.dos = _seed(self.s, "Dos", stock=3)
        _seed_basicos(self.s, self.uno, "Pantalón")   # 2 prendas × 2 tallas
        vs = list(self.s.scalars(select(Variante).order_by(Variante.id)).all())
        uno = [v for v in vs if v.producto.escuela_id == self.uno.id]
        uno[0].ultimo_conteo_at = datetime.now() - timedelta(days=2)     # al día
        uno[1].ultimo_conteo_at = datetime.now() - timedelta(days=400)   # vieja
        # las otras dos de Uno: nunca; Dos: nunca; básicos: una al día
        basicos = [v for v in vs if v.producto.escuela_id is None]
        basicos[0].ultimo_conteo_at = datetime.now() - timedelta(days=1)
        self.s.commit()

    def test_resumen_por_escuela_y_basicos(self) -> None:
        r = m.resumen(self.s)
        uno = next(e for e in r["escuelas"] if e["nombre"] == "Uno")
        self.assertEqual((uno["tallas"], uno["al_dia"], uno["viejas"], uno["nunca"], uno["pct_al_dia"], uno["ultimo_dias"], uno["estado"]), (4, 1, 1, 2, 25, 2, "vieja"))
        dos = next(e for e in r["escuelas"] if e["nombre"] == "Dos")
        self.assertEqual((dos["nunca"], dos["estado"], dos["ultimo_dias"]), (4, "nunca", None))
        pant = next(b for b in r["basicos"] if b["tipo_pieza"] == "Pantalón")
        self.assertEqual((pant["tallas"], pant["al_dia"], pant["nunca"]), (4, 1, 3))
        self.assertEqual(r["total"]["tallas"], 12)

    def test_detalle_de_escuela_trae_prendas_y_tallas_con_semaforo(self) -> None:
        d = m.escuela(self.s, self.uno.id)
        self.assertEqual(d["titulo"], "Uno")
        self.assertEqual(len(d["prendas"]), 2)
        estados = {(p["nombre"], t["talla"]): t["estado"] for p in d["prendas"] for t in p["tallas_detalle"]}
        self.assertEqual(sorted(estados.values()), ["al_dia", "nunca", "nunca", "vieja"])
        self.assertTrue(all(t["dias"] is None for p in d["prendas"] for t in p["tallas_detalle"] if t["estado"] == "nunca"))

    def test_detalle_de_basicos_por_tipo(self) -> None:
        d = m.basicos(self.s, "Pantalón")
        self.assertEqual(d["titulo"], "Básicos · Pantalón")
        self.assertEqual([p["nombre"] for p in d["prendas"]], ["Pantalón Azul Escolar", "Pantalón Gris Escolar"])
        self.assertEqual(d["al_dia"] + d["nunca"], 4)


class HtmlYKioskoTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
        self.s = Session(engine)
        self.uno = _seed(self.s, "Uno", stock=3); _seed_basicos(self.s, self.uno, "Pantalón"); self.s.commit()

    def test_el_html_lleva_todas_las_capas_y_no_rompe_el_script(self) -> None:
        import json, re
        html = m.html(self.s)
        datos = json.loads(re.search(r"const D = (\{.*?\});\n", html, re.S).group(1).replace("<\\/", "</"))
        self.assertIn("e%d" % self.uno.id, datos["detalles"])
        self.assertIn("bPantalón", datos["detalles"])
        self.assertEqual(datos["total"]["tallas"], 8)
        self.assertNotIn("</script>", json.dumps(datos))   # nada dentro del JSON puede cerrar el script
        self.assertIn("Mapa de conteos", html)

    def test_el_dialogo_del_kiosko_pinta_lo_que_genera_el_hilo(self) -> None:
        import sys
        import time
        from PyQt6.QtWidgets import QApplication
        from pos_uniformes.ui.dialogs.conteo_mapa_dialog import ConteoMapaDialog

        app = QApplication.instance() or QApplication(sys.argv)
        datos = m.todo(self.s)
        d = ConteoMapaDialog(None, generar=lambda: datos)
        for _ in range(50):
            app.processEvents()
            if d.refrescar_btn.isEnabled():
                break
            time.sleep(0.02)
        self.assertTrue(d.refrescar_btn.isEnabled())
        self.assertIn("Toca una escuela", d.estado.text())
        d2 = ConteoMapaDialog(None, generar=lambda: (_ for _ in ()).throw(RuntimeError("sin red")))
        for _ in range(50):
            app.processEvents()
            if d2.refrescar_btn.isEnabled():
                break
            time.sleep(0.02)
        self.assertIn("No se pudo armar", d2.estado.text())
        d.close(); d2.close()


class SeccionConteosTests(unittest.TestCase):
    """El mapa vive dentro de la sección Conteos del kiosko; la tabla a un clic."""

    def test_el_widget_no_se_arma_dos_veces_seguidas_ni_antes_de_un_minuto(self) -> None:
        import sys, time
        from PyQt6.QtWidgets import QApplication
        from pos_uniformes.ui.dialogs.conteo_mapa_dialog import ConteoMapaWidget

        app = QApplication.instance() or QApplication(sys.argv)
        veces = []
        datos = {"total": {"tallas": 0, "al_dia": 0, "viejas": 0, "nunca": 0, "pct_al_dia": 0, "ultimo_dias": None, "estado": "nunca"}, "escuelas": [], "basicos": [], "detalles": {}}
        w = ConteoMapaWidget(None, generar=lambda: veces.append(1) or datos, auto=False)
        self.assertTrue(w.recargar())
        self.assertFalse(w.recargar())            # ya hay una en vuelo
        for _ in range(50):
            app.processEvents()
            if w.refrescar_btn.isEnabled():
                break
            time.sleep(0.02)
        self.assertEqual(veces, [1])
        self.assertFalse(w.recargar())            # recién armado: no antes de un minuto
        self.assertTrue(w.recargar(forzar=True))  # el botón ↻ sí
        w.close()

    def test_las_capas_se_navegan_con_los_enlaces(self) -> None:
        import sys, time
        from PyQt6.QtWidgets import QApplication, QLabel
        from pos_uniformes.ui.dialogs.conteo_mapa_dialog import ConteoMapaWidget

        app = QApplication.instance() or QApplication(sys.argv)
        engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
        s = Session(engine); uno = _seed(s, "Uno", stock=3); _seed_basicos(s, uno, "Pantalón"); s.commit()
        datos = m.todo(s)   # sqlite en memoria no se puede usar desde el hilo del widget
        w = ConteoMapaWidget(None, generar=lambda: datos, auto=True)
        for _ in range(50):
            app.processEvents()
            if w.refrescar_btn.isEnabled() and w._datos:
                break
            time.sleep(0.02)
        from pos_uniformes.ui.helpers.conteo_mapa_widgets import CapaDetalle, CapaMapa, Mosaico

        textos = lambda: " | ".join(l.text() for l in w.cuerpo.findChildren(QLabel))
        self.assertIsInstance(w._capa_widget, CapaMapa)
        self.assertIn("Uno", textos()); self.assertIn("BÁSICOS", textos())
        w._navegar(f"e{uno.id}")                      # capa 2: la escuela
        self.assertIsInstance(w._capa_widget, CapaDetalle)
        self.assertIn("Prenda 0 Uno", textos())
        prenda = w._capa_widget.prendas[0]
        self.assertFalse(prenda._tallas.isVisibleTo(prenda))
        self.assertTrue(prenda.alternar())            # capa 3: las tallas
        self.assertIn("3 pz", textos())
        w._navegar("mapa")
        self.assertIsInstance(w._capa_widget, CapaMapa)
        self.assertEqual(len(w.cuerpo.findChildren(Mosaico)), 2)   # Uno + Básicos·Pantalón
        w.busca.setText("zzz")
        self.assertIn("Ninguna escuela", textos())
        w.close()

    def test_la_seccion_tiene_mapa_y_boton_ver_tabla(self) -> None:
        import inspect
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        fuente = inspect.getsource(QuoteSatelliteWindow._conteos_alternar_tabla)
        self.assertIn("conteos_historial_table.setVisible(tabla)", fuente)
        self.assertIn("conteos_mapa.setVisible(not tabla)", fuente)
        # El refresco lee en un hilo y pinta al volver (2026-09-22): el mapa
        # se recarga cuando llegan los datos, no dentro del refresco.
        pintado = inspect.getsource(QuoteSatelliteWindow._on_conteos_datos_listos)
        self.assertIn("mapa.recargar()", pintado)

    def test_los_mosaicos_dicen_quien_la_esta_contando(self) -> None:
        from pos_uniformes.services import conteo_jornada_service as jn

        engine = create_engine("sqlite:///:memory:"); Base.metadata.create_all(engine)
        s = Session(engine)
        uno = _seed(s, "Uno", stock=3); s.commit()
        j, _ = jn.registrar_impresion(s, escuela_id=uno.id, empleada_code="VEND-5", empleada_nombre="Fanny"); s.commit()
        r = m.resumen(s)
        fila = next(e for e in r["escuelas"] if e["nombre"] == "Uno")
        self.assertTrue(fila["en_proceso"].startswith("Fanny · hoja impresa"))
        self.assertIn('"en_proceso": "Fanny · hoja impresa', m.html(s))   # el mosaico lo pinta el JS con ese dato
