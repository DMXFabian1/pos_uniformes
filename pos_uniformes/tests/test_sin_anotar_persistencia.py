"""Operaciones cobradas sin anotar: respaldo en disco y recuperación (A2/A3 · C1).

Antes la foto de una operación cobrada que no se pudo anotar solo vivía en
memoria: cerrar o reiniciar el kiosko la perdía sin rastro. Ahora:
- se guarda en `data/sin_anotar/<uuid>.json` (aparte de la cola);
- al abrir el programa se recupera (sin cobrar ni imprimir);
- en un fallo parcial solo queda pendiente lo que de verdad faltó;
- el respaldo se conserva hasta que PostgreSQL confirma TODAS las entradas
  (no basta con que entren a la cola local);
- la cola local se escribe de forma durable (fsync + reemplazo atómico);
- cerrar con pendientes pregunta (Cancelar / Cerrar de todos modos);
- el log del kiosko va a un archivo aunque no haya consola.

«Reiniciar» se simula creando otro QuickSaleWidget sobre la misma carpeta.
La cola real corre en una carpeta temporal; la falla se simula en la
escritura (como cuando Windows o el antivirus tienen tomado el archivo).

Las pruebas de conciliación usan PostgreSQL DE VERDAD (solo la base local
127.0.0.1/pos_uniformes_test, que fija conftest), con una empleada temporal y
fechas de 2001 para no aparecer en reportes de «hoy» de otras pruebas.

Cada prueba cierra los avisos que abrió y procesa sus `deleteLater`: un
aviso modal que sobrevive a su prueba tumba a las siguientes (la cartelera
no se muestra mientras hay un modal abierto).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid as _uuid
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication, QMessageBox

from pos_uniformes.services import libreta_local_queue_service as cola
from pos_uniformes.services import libreta_sin_anotar_service as sin_anotar
from pos_uniformes.ui.views.quick_sale_view import QuickSaleWidget
from pos_uniformes.utils import archivo_durable

_MOD = "pos_uniformes.ui.views.quick_sale_view"
_GUARDAR_REAL = cola._save_raw


def _items():
    return [
        {"sku": "SKU1", "nombre": "Pants 3pz", "talla": "8", "color": "", "precio": Decimal("590.00"), "cantidad": 2},
        {"sku": "SKU2", "nombre": "Playera", "talla": "8", "color": "", "precio": Decimal("200.00"), "cantidad": 1},
    ]


def _falla_siempre(entries):
    raise PermissionError("el archivo está en uso por otro proceso")


def _modales_visibles() -> set[int]:
    return {id(w) for w in QApplication.topLevelWidgets() if isinstance(w, QMessageBox) and w.isVisible()}


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        # Se registra PRIMERO → corre AL FINAL: la prueba no deja avisos.
        self._modales_antes = _modales_visibles()
        self.addCleanup(self._sin_avisos_abiertos)
        self._widgets: list[QuickSaleWidget] = []
        self.addCleanup(self._cerrar_widgets)

        self.raiz = Path(tempfile.mkdtemp(prefix="sin_anotar_"))
        for p in (
            patch.object(cola, "satellite_data_dir", return_value=self.raiz),
            patch.object(cola, "_ESPERA_ARCHIVO_OCUPADO", 0),
        ):
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(shutil.rmtree, self.raiz, True)
        self.w = self._kiosko()

    # ── higiene Qt ────────────────────────────────────────────────────
    def _cerrar_widgets(self) -> None:
        """Cierra los avisos de ESTA prueba y destruye sus widgets."""
        for w in self._widgets:
            try:
                for box in w.findChildren(QMessageBox):
                    box.done(0)
                w.close()
                w.deleteLater()
            except RuntimeError:  # ya destruido
                pass
        self._widgets.clear()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        QApplication.processEvents()

    def _sin_avisos_abiertos(self) -> None:
        nuevos = _modales_visibles() - self._modales_antes
        self.assertEqual(nuevos, set(), "la prueba dejó avisos abiertos")

    def _kiosko(self, empleada=("VEND-3", "Evelyn Ruiz")) -> QuickSaleWidget:
        """Un kiosko recién abierto (o reabierto) sobre la misma carpeta."""
        w = QuickSaleWidget(SimpleNamespace(offline_mode=True, _kiosk_lookup_from_cache=None))
        self._widgets.append(w)
        w._employee_code, w._employee_name = empleada
        w._items = _items()
        for nombre in ("_drenar_libreta_en_background", "_flash_scan_hint", "_avisar_sin_ticket"):
            p = patch.object(w, nombre)
            p.start()
            self.addCleanup(p.stop)
        return w

    # ── utilidades ────────────────────────────────────────────────────
    def _cola(self) -> list[dict]:
        path = self.raiz / "data" / "libreta_pendiente.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []

    def _archivos(self) -> list[Path]:
        carpeta = self.raiz / "data" / "sin_anotar"
        return sorted(carpeta.glob("*.json")) if carpeta.exists() else []

    def _respaldo(self) -> dict:
        [archivo] = self._archivos()
        return json.loads(archivo.read_text(encoding="utf-8"))

    def _anotar_fallando(self, w=None, tipo="venta", **kw) -> bool:
        w = w or self.w
        with patch.object(cola, "_save_raw", side_effect=_falla_siempre):
            return w._registrar_y_vaciar(tipo, **kw)

    def _apartado_falla_solo_el_anticipo(self, w=None) -> None:
        w = w or self.w
        llamadas = {"n": 0}

        def segunda_falla(entries):
            llamadas["n"] += 1
            if llamadas["n"] == 2:
                raise PermissionError("tomado")
            return _GUARDAR_REAL(entries)

        with patch.object(cola, "_save_raw", side_effect=segunda_falla):
            self.assertFalse(w._registrar_y_vaciar(
                "apartado", cliente="Blanca", anticipo=Decimal("300"), anticipo_tarjeta=False,
            ))


class PersistenciaTests(_Base):
    # 1
    def test_anotacion_fallida_se_guarda_en_disco_completa(self) -> None:
        self.w._discount_active = True
        self.assertFalse(self._anotar_fallando(pago_tarjeta=True))
        [archivo] = self._archivos()
        [foto] = self.w._anotaciones_pendientes
        self.assertEqual(archivo.name, f"{foto['operacion_uuid']}.json")
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        self.assertEqual(datos["version"], 1)
        self.assertEqual(datos["entradas"], [foto])  # foto exacta
        self.assertEqual((datos["en_cola"], datos["en_base"]), ([], []))
        for campo in ("operacion_uuid", "tipo", "created_at", "employee_code", "monto_total",
                      "monto_neto", "descuento_empleada", "pago_tarjeta", "items"):
            self.assertIn(campo, datos["entradas"][0])
        self.assertTrue(datos["entradas"][0]["descuento_empleada"])
        texto = archivo.read_text(encoding="utf-8").lower()
        for secreto in ("pin", "password", "contrase", "token"):
            self.assertNotIn(secreto, texto)
        self.assertNotIn("SE PIERDE", self.w._aviso_anotacion.text())
        self.assertIn("volverá a aparecer", self.w._aviso_anotacion.text())

    def test_no_se_sobrescribe_un_pendiente_con_otra_foto(self) -> None:
        self._anotar_fallando()
        [archivo] = self._archivos()
        antes = archivo.read_bytes()
        [foto] = self.w._anotaciones_pendientes
        otra = dict(foto, monto_total="1.00")
        with self.assertRaises(sin_anotar.PendienteEnConflicto):
            sin_anotar.guardar([otra])
        self.assertEqual(archivo.read_bytes(), antes)
        sin_anotar.guardar([dict(foto)])  # la misma foto: sin conflicto
        self.assertEqual(self._respaldo()["entradas"], [foto])

    def test_escritura_atomica_no_deja_temporales(self) -> None:
        self._anotar_fallando()
        carpeta = self.raiz / "data" / "sin_anotar"
        self.assertEqual([p.name for p in carpeta.iterdir() if p.suffix == ".tmp"], [])

    # 9
    def test_si_falla_tambien_el_respaldo_pide_apuntarlo_en_papel(self) -> None:
        with patch.object(sin_anotar, "_escribir_atomico", side_effect=OSError("disco lleno")):
            self.assertFalse(self._anotar_fallando())
        self.assertEqual(self._archivos(), [])
        texto = self.w._aviso_anotacion.text()
        self.assertIn("YA PAGÓ", texto)
        self.assertIn("TAMPOCO se pudo guardar el respaldo", texto)
        self.assertIn("SE PIERDE", texto)
        self.assertIn("papel", texto)
        self.assertEqual(len(self.w._anotaciones_pendientes), 1)  # sigue en memoria
        self.assertEqual(len(self.w._sin_respaldo), 1)

    def test_sin_respaldo_al_anotar_se_crea_el_respaldo_ya_en_cola(self) -> None:
        """El disco falló al retener; al reintentar con éxito se crea el
        respaldo (marcado «en cola») para que dure hasta PostgreSQL."""
        with patch.object(sin_anotar, "_escribir_atomico", side_effect=OSError("disco lleno")):
            self._anotar_fallando()
        [foto] = self.w._anotaciones_pendientes
        self.assertTrue(self.w._reintentar_anotacion())
        self.assertEqual(self.w._sin_respaldo, {})
        self.assertEqual(self._cola(), [foto])
        self.assertEqual(self._respaldo()["en_cola"], [foto["operacion_uuid"]])


class RecuperacionTests(_Base):
    # 2, 3, 11
    def test_se_recupera_al_reiniciar_con_el_mismo_uuid_y_se_ve(self) -> None:
        self._anotar_fallando(pago_tarjeta=True)
        [foto] = self.w._anotaciones_pendientes

        w2 = self._kiosko(empleada=("VEND-5", "Nayeli Herrera"))  # abre OTRA empleada
        [recuperada] = w2._anotaciones_pendientes
        self.assertEqual(recuperada, foto)
        self.assertEqual(recuperada["operacion_uuid"], foto["operacion_uuid"])
        self.assertEqual(recuperada["employee_code"], "VEND-3")  # no la de quien abrió
        self.assertEqual(recuperada["created_at"], foto["created_at"])
        self.assertFalse(w2._btn_reintentar_anotar.isHidden())
        self.assertIn("(1)", w2._btn_reintentar_anotar.text())

        w2._avisar_pendientes_recuperados()
        texto = w2._aviso_anotacion.text()
        self.assertIn("Al abrir el programa", texto)
        self.assertIn("1 operación", texto)
        self.assertIn("vendió Evelyn Ruiz", texto)
        self.assertIn("NO le vuelvas a cobrar", texto)

    # 4, 5
    def test_reintento_tras_reiniciar_no_cobra_ni_imprime(self) -> None:
        self._anotar_fallando()
        [foto] = self.w._anotaciones_pendientes
        w2 = self._kiosko()
        with patch(f"{_MOD}.route_tickets") as imprimir, \
                patch.object(w2, "_cobrar_con_monedero") as cobrar:
            self.assertTrue(w2._reintentar_anotacion())
        imprimir.assert_not_called()
        cobrar.assert_not_called()
        self.assertEqual(self._cola(), [foto])
        self.assertEqual(w2._anotaciones_pendientes, [])
        self.assertTrue(w2._btn_reintentar_anotar.isHidden())

    def test_respaldo_se_conserva_mientras_postgresql_no_confirma(self) -> None:
        """Entrar a la cola local NO borra el respaldo; solo lo marca."""
        self._anotar_fallando()
        [foto] = self.w._anotaciones_pendientes
        self.assertTrue(self.w._reintentar_anotacion())
        datos = self._respaldo()
        self.assertEqual(datos["en_cola"], [foto["operacion_uuid"]])
        self.assertEqual(datos["en_base"], [])
        # Reinicio antes de que suba: nada que anotar (ya está en la cola),
        # y el respaldo sigue en disco.
        w2 = self._kiosko()
        self.assertEqual(w2._anotaciones_pendientes, [])
        self.assertEqual(len(self._archivos()), 1)
        self.assertEqual(w2.claves_pendientes(), set())  # el cierre no pregunta por ella

    def test_si_la_cola_se_pierde_el_respaldo_la_vuelve_a_pedir(self) -> None:
        """La bitácora dice «en cola», pero la cola real ya no la tiene (se
        dañó o se vació): al arrancar vuelve a quedar pendiente."""
        self._anotar_fallando()
        [foto] = self.w._anotaciones_pendientes
        self.w._reintentar_anotacion()
        _GUARDAR_REAL([])  # la cola se perdió
        w2 = self._kiosko()
        self.assertEqual(w2._anotaciones_pendientes, [foto])
        self.assertTrue(w2._reintentar_anotacion())
        self.assertEqual(self._cola(), [foto])

    def test_si_la_cola_no_se_puede_leer_se_usa_la_bitacora(self) -> None:
        self._anotar_fallando()
        self.w._reintentar_anotacion()
        with patch.object(cola, "uuids_en_cola", side_effect=PermissionError("tomado")):
            w2 = self._kiosko()
        self.assertEqual(w2._anotaciones_pendientes, [])  # la bitácora dice «en cola»

    # 7
    def test_si_el_reintento_falla_el_pendiente_sigue_en_disco(self) -> None:
        self._anotar_fallando()
        [archivo] = self._archivos()
        antes = json.loads(archivo.read_text())
        with patch.object(cola, "_save_raw", side_effect=_falla_siempre):
            self.assertFalse(self.w._reintentar_anotacion())
        self.assertEqual(json.loads(archivo.read_text()), antes)
        self.assertEqual(len(self.w._anotaciones_pendientes), 1)
        w2 = self._kiosko()
        self.assertEqual(len(w2._anotaciones_pendientes), 1)

    # 10
    def test_archivo_corrupto_no_bloquea_el_arranque_y_se_reporta(self) -> None:
        self._anotar_fallando()
        carpeta = self.raiz / "data" / "sin_anotar"
        (carpeta / "dañado.json").write_bytes(b"{ esto no es json")
        (carpeta / "sin-entradas.json").write_text(json.dumps({"version": 1, "entradas": []}))
        w2 = self._kiosko()
        self.assertEqual(len(w2._anotaciones_pendientes), 1)  # el bueno sí se carga
        self.assertEqual(sorted(w2._sin_anotar_revisar), ["dañado.json", "sin-entradas.json"])
        with patch.object(w2, "_avisar_no_se_anoto") as aviso:
            w2._avisar_pendientes_recuperados()
        self.assertIn("revisarlos a mano", aviso.call_args.args[0])
        self.assertTrue((carpeta / "dañado.json").exists())  # no se borra

    def test_recuperar_dos_veces_no_duplica_en_memoria(self) -> None:
        self._anotar_fallando()
        self.w._recuperar_pendientes_persistidos()
        self.w._recuperar_pendientes_persistidos()
        self.assertEqual(len(self.w._anotaciones_pendientes), 1)

    def test_dos_operaciones_fallidas_dos_archivos_y_ambas_se_recuperan(self) -> None:
        self._anotar_fallando()
        self.w._items = _items()
        self._anotar_fallando()
        self.assertEqual(len(self._archivos()), 2)
        w2 = self._kiosko()
        self.assertEqual(len(w2._anotaciones_pendientes), 2)
        self.assertTrue(w2._reintentar_anotacion())
        self.assertEqual(len(self._cola()), 2)
        self.assertEqual(len(self._archivos()), 2)  # siguen hasta que suban


class FalloParcialTests(_Base):
    # 8
    def test_fallo_parcial_solo_queda_pendiente_lo_que_falto(self) -> None:
        self._apartado_falla_solo_el_anticipo()
        [apartado] = self._cola()
        [pendiente] = self.w._anotaciones_pendientes
        self.assertEqual((apartado["tipo"], pendiente["tipo"]), ("apartado", "abono"))
        datos = self._respaldo()
        self.assertEqual([e["tipo"] for e in datos["entradas"]], ["apartado", "abono"])  # foto completa
        self.assertEqual(datos["en_cola"], [apartado["operacion_uuid"]])  # qué sí se guardó
        texto = self.w._aviso_anotacion.text()
        ya, falta = texto.split("Falta anotar:")
        self.assertIn("Apartado", ya.split("Ya quedó anotado:")[1])
        self.assertNotIn("Apartado", falta)
        self.assertIn("Abono", falta)

    # 17
    def test_apartado_con_anticipo_parcial_no_se_duplica_tras_reiniciar(self) -> None:
        self._apartado_falla_solo_el_anticipo()
        w2 = self._kiosko()
        self.assertEqual([e["tipo"] for e in w2._anotaciones_pendientes], ["abono"])
        self.assertTrue(w2._reintentar_anotacion())
        self.assertEqual([e["tipo"] for e in self._cola()], ["apartado", "abono"])  # el apartado UNA vez
        w3 = self._kiosko()
        self.assertEqual(w3._anotaciones_pendientes, [])

    def test_sin_uuid_no_se_separa_y_se_conserva_completo(self) -> None:
        entradas = [{"tipo": "abono", "monto_total": "1"}, {"tipo": "abono", "monto_total": "2"}]
        with patch.object(self.w, "_mostrar_aviso_anotacion"):
            self.w._retener_anotacion(entradas, hechas=[entradas[0]])
        self.assertEqual(len(self.w._anotaciones_pendientes), 2)
        self.assertEqual(len(self.w._sin_respaldo), 1)  # no hay uuid para archivo


class ColaDurableTests(_Base):
    def test_la_cola_hace_fsync_antes_del_reemplazo(self) -> None:
        orden: list[str] = []
        fsync_real, replace_real = os.fsync, os.replace

        def fsync(fd):
            orden.append("fsync")
            return fsync_real(fd)

        def replace(a, b):
            orden.append(f"replace:{Path(b).name}")
            return replace_real(a, b)

        with patch.object(archivo_durable.os, "fsync", side_effect=fsync), \
                patch.object(archivo_durable.os, "replace", side_effect=replace):
            cola.encolar_operacion({"employee_code": "X", "tipo": "venta", "items": [],
                                    "monto_total": "1", "operacion_uuid": "u-dur-1"})
        i = orden.index("replace:libreta_pendiente.json")
        self.assertIn("fsync", orden[:i])  # los bytes al disco ANTES de reemplazar
        if os.name != "nt":
            self.assertIn("fsync", orden[i + 1:])  # y la carpeta, después
        self.assertEqual([e["operacion_uuid"] for e in self._cola()], ["u-dur-1"])
        self.assertFalse((self.raiz / "data" / "libreta_pendiente.tmp").exists())

    def test_si_falla_la_escritura_la_cola_anterior_queda_intacta(self) -> None:
        cola.encolar_operacion({"employee_code": "X", "tipo": "venta", "items": [],
                                "monto_total": "1", "operacion_uuid": "u-dur-1"})
        antes = (self.raiz / "data" / "libreta_pendiente.json").read_bytes()
        with patch.object(archivo_durable.os, "fsync", side_effect=OSError("disco")):
            with self.assertRaises(OSError):
                cola.encolar_operacion({"employee_code": "X", "tipo": "venta", "items": [],
                                        "monto_total": "2", "operacion_uuid": "u-dur-2"})
        self.assertEqual((self.raiz / "data" / "libreta_pendiente.json").read_bytes(), antes)
        self.assertFalse((self.raiz / "data" / "libreta_pendiente.tmp").exists())

    def test_el_respaldo_tambien_es_durable(self) -> None:
        with patch.object(archivo_durable.os, "fsync", wraps=os.fsync) as fsync:
            self._anotar_fallando()
        self.assertGreaterEqual(fsync.call_count, 1)


# ── Conciliación con PostgreSQL de verdad ────────────────────────────────


def _base_local_postgres():
    from pos_uniformes.database.connection import get_session

    with get_session() as s:
        url = s.get_bind().url
        if url.host not in {"127.0.0.1", "localhost", "::1"} or url.database != "pos_uniformes_test":
            raise unittest.SkipTest("Solo corre contra la base local pos_uniformes_test")
        if s.get_bind().dialect.name != "postgresql":
            raise unittest.SkipTest("requiere PostgreSQL")


class ConciliacionPostgresTests(_Base):
    """El respaldo se borra SOLO cuando PostgreSQL tiene todas las entradas."""

    def setUp(self) -> None:
        super().setUp()
        _base_local_postgres()
        from pos_uniformes.database.connection import get_session
        from pos_uniformes.database.models import Empleada

        self.code = f"TSTC1-{_uuid.uuid4().hex[:6].upper()}"
        with get_session() as s:
            s.add(Empleada(codigo=self.code, nombre_completo="Prueba C1", activo=True))
            s.commit()
        self.addCleanup(self._limpiar_base)

    def _limpiar_base(self) -> None:
        from sqlalchemy import delete

        from pos_uniformes.database.connection import get_session
        from pos_uniformes.database.models import Empleada, LibretaVenta

        with get_session() as s:
            s.execute(delete(LibretaVenta).where(LibretaVenta.employee_code == self.code))
            s.execute(delete(Empleada).where(Empleada.codigo == self.code))
            s.commit()

    def _foto(self, tipo="venta", monto="1180.00", minuto=0) -> dict:
        items = [] if tipo == "abono" else [
            {"sku": "SKU1", "nombre": "Pants 3pz", "talla": "8", "cantidad": 2, "precio": "590.00"}
        ]
        return {
            "employee_code": self.code, "employee_name": "Prueba C1", "tipo": tipo,
            "cliente": "Blanca" if tipo != "venta" else None, "items": items,
            "monto_total": monto, "monto_neto": monto, "pago_tarjeta": False,
            "descuento_empleada": False, "origen": "pc-prueba-c1",
            **({"comisiones": 0} if tipo == "abono" else {}),
            # 2001: fuera de cualquier reporte de «hoy» de otras pruebas.
            "created_at": f"2001-02-03T10:{minuto:02d}:00.123456-06:00",
            "operacion_uuid": str(_uuid.uuid4()),
        }

    def _retener(self, entradas: list[dict], hechas: list[dict] | None = None) -> None:
        """Lo mismo que hace `_anotar` cuando falla la cola."""
        for e in hechas or []:
            cola.encolar_operacion(e)
        self.w._retener_anotacion(entradas, hechas=hechas or [])

    def _drenar(self) -> int:
        from pos_uniformes.database.connection import get_session

        with get_session() as s:
            return cola.drenar_pendientes(s)

    def _en_base(self) -> list[tuple[str, str]]:
        from sqlalchemy import select

        from pos_uniformes.database.connection import get_session
        from pos_uniformes.database.models import LibretaVenta

        with get_session() as s:
            return sorted(
                (str(r.operacion_uuid), r.tipo)
                for r in s.scalars(select(LibretaVenta).where(LibretaVenta.employee_code == self.code))
            )

    # Respaldo eliminado tras confirmación completa
    def test_se_borra_solo_cuando_postgresql_confirma(self) -> None:
        venta = self._foto()
        self._retener([venta])
        self.assertTrue(self.w._reintentar_anotacion())
        self.assertEqual(len(self._archivos()), 1)  # en cola, aún no en la base
        self.assertEqual(self._drenar(), 1)
        self.assertEqual(self._en_base(), [(venta["operacion_uuid"], "venta")])
        self.assertEqual(self._archivos(), [])
        self.assertEqual(self._cola(), [])

    def test_si_postgresql_no_contesta_el_respaldo_se_queda(self) -> None:
        from sqlalchemy import exc as sa_exc

        venta = self._foto()
        self._retener([venta])
        self.w._reintentar_anotacion()
        caida = sa_exc.OperationalError("INSERT", {}, Exception("No route to host"))
        with patch.object(cola, "_subir", side_effect=caida):
            with self.assertRaises(sa_exc.OperationalError):
                self._drenar()
        self.assertEqual(len(self._archivos()), 1)
        self.assertEqual(self._en_base(), [])
        # Reinicio con la cola intacta: nada que anotar; luego sube y se borra.
        w2 = self._kiosko()
        self.assertEqual(w2._anotaciones_pendientes, [])
        self._drenar()
        self.assertEqual(self._archivos(), [])

    # Recuperación después de confirmación pero antes del borrado
    def test_confirmada_pero_sin_borrar_no_se_reanota_ni_duplica(self) -> None:
        venta = self._foto()
        self._retener([venta])
        self.w._reintentar_anotacion()
        real_unlink = Path.unlink

        def unlink_tomado(p, *a, **k):
            if "sin_anotar" in str(p) and p.suffix == ".json":
                raise PermissionError("tomado")
            return real_unlink(p, *a, **k)

        with patch.object(Path, "unlink", unlink_tomado), \
                patch(f"{_MOD}.route_tickets") as imprimir:
            self._drenar()
        imprimir.assert_not_called()
        self.assertEqual(self._respaldo()["en_base"], [venta["operacion_uuid"]])  # sabe que ya subió
        w2 = self._kiosko()
        self.assertEqual(w2._anotaciones_pendientes, [])  # no se reanota
        self.assertEqual(w2.claves_pendientes(), set())
        self._drenar()  # siguiente drenado: ahora sí se borra
        self.assertEqual(self._archivos(), [])
        self.assertEqual(self._en_base(), [(venta["operacion_uuid"], "venta")])  # UNA

    # Recuperación tras reiniciar antes de confirmación, con la cola perdida
    def test_drenado_sin_conciliar_y_cola_perdida_no_duplica(self) -> None:
        """Se cae justo entre el commit en PostgreSQL y la conciliación: la
        cola quedó vacía y el respaldo no sabe que ya subió. Al arrancar la
        vuelve a pedir; reencolarla NO duplica (el drenado la reconoce por
        uuid) y entonces sí se borra el respaldo."""
        venta = self._foto()
        self._retener([venta])
        self.w._reintentar_anotacion()
        with patch.object(cola, "_conciliar_respaldos"):
            self._drenar()
        self.assertEqual(len(self._archivos()), 1)
        w2 = self._kiosko()
        self.assertEqual([e["operacion_uuid"] for e in w2._anotaciones_pendientes], [venta["operacion_uuid"]])
        w2._reintentar_anotacion()
        self._drenar()
        self.assertEqual(self._en_base(), [(venta["operacion_uuid"], "venta")])  # UNA sola
        self.assertEqual(self._archivos(), [])

    # Fallo parcial: apartado confirmado, anticipo pendiente
    def test_apartado_confirmado_anticipo_pendiente(self) -> None:
        apartado, abono = self._foto("apartado"), self._foto("abono", "300.00", 1)
        self._retener([apartado, abono], hechas=[apartado])
        self._drenar()
        self.assertEqual(self._en_base(), [(apartado["operacion_uuid"], "apartado")])
        datos = self._respaldo()  # se conserva: falta el anticipo
        self.assertEqual(datos["en_base"], [apartado["operacion_uuid"]])
        w2 = self._kiosko()
        self.assertEqual([e["tipo"] for e in w2._anotaciones_pendientes], ["abono"])
        self.assertTrue(w2._reintentar_anotacion())
        self._drenar()
        self.assertEqual(
            self._en_base(),
            sorted([(apartado["operacion_uuid"], "apartado"), (abono["operacion_uuid"], "abono")]),
        )
        self.assertEqual(self._archivos(), [])

    # Fallo parcial: anticipo confirmado, apartado pendiente (la base rechaza el apartado)
    def test_anticipo_confirmado_apartado_rechazado(self) -> None:
        apartado, abono = self._foto("apartado"), self._foto("abono", "300.00", 1)
        self._retener([apartado, abono])
        self.w._reintentar_anotacion()
        subir_real = cola._subir

        def rechaza_apartado(session, entry):
            if entry["tipo"] == "apartado":
                raise ValueError("rechazada por la base")
            return subir_real(session, entry)

        with patch.object(cola, "_subir", side_effect=rechaza_apartado):
            self._drenar()
        self.assertEqual(self._en_base(), [(abono["operacion_uuid"], "abono")])
        self.assertEqual(self._respaldo()["en_base"], [abono["operacion_uuid"]])  # se conserva
        w2 = self._kiosko()
        self.assertEqual(w2._anotaciones_pendientes, [])  # el apartado sigue en la cola
        self._drenar()  # ya no lo rechaza
        self.assertEqual(len(self._en_base()), 2)
        self.assertEqual(self._archivos(), [])

    def test_muchos_drenados_no_duplican(self) -> None:
        venta = self._foto()
        self._retener([venta])
        self.w._reintentar_anotacion()
        for _ in range(3):
            self._drenar()
            cola.encolar_operacion(dict(venta))  # aunque reaparezca en la cola
        self._drenar()
        self.assertEqual(self._en_base(), [(venta["operacion_uuid"], "venta")])


class CierreTests(_Base):
    # 12
    def test_cerrar_con_pendientes_permite_cancelar(self) -> None:
        self._anotar_fallando()
        with patch.object(self.w, "_preguntar_cierre", return_value=False) as preguntar:
            self.assertFalse(self.w.confirmar_cierre())
        self.assertIn("1 operación", preguntar.call_args.args[0])
        self.assertIn("NO las borra", preguntar.call_args.args[0])
        self.assertEqual(len(self._archivos()), 1)

    # 13
    def test_cerrar_con_pendientes_permite_continuar_y_no_borra(self) -> None:
        self._anotar_fallando()
        with patch.object(self.w, "_preguntar_cierre", return_value=True):
            self.assertTrue(self.w.confirmar_cierre())
        self.assertEqual(len(self._archivos()), 1)

    def test_sin_pendientes_cierra_sin_preguntar(self) -> None:
        with patch.object(self.w, "_preguntar_cierre") as preguntar:
            self.assertTrue(self.w.confirmar_cierre())
        preguntar.assert_not_called()

    # 14
    def test_no_cuenta_dos_veces_memoria_y_disco(self) -> None:
        self._apartado_falla_solo_el_anticipo()  # 1 operación (apartado+abono)
        self.w._items = _items()
        self._anotar_fallando()  # otra operación
        self.assertEqual(len(self._archivos()), 2)
        self.assertEqual(len(self.w.claves_pendientes()), 2)
        # Un archivo que solo está en disco (de otra sesión) sí suma.
        otra = dict(self.w._anotaciones_pendientes[-1], operacion_uuid="0000aaaa-0000-0000-0000-000000000001")
        sin_anotar.guardar([otra])
        self.assertEqual(len(self.w.claves_pendientes()), 3)

    def test_sin_respaldo_el_cierre_advierte_que_se_pierde(self) -> None:
        with patch.object(sin_anotar, "_escribir_atomico", side_effect=OSError("disco lleno")):
            self._anotar_fallando()
            with patch.object(self.w, "_preguntar_cierre", return_value=False) as preguntar:
                self.w.confirmar_cierre()
        self.assertIn("SE PIERDEN", preguntar.call_args.args[0])

    def test_el_dialogo_de_cierre_no_bloquea_indefinidamente(self) -> None:
        self._anotar_fallando()
        with patch.object(QuickSaleWidget, "_CIERRE_TIMEOUT_MS", 50):
            self.assertTrue(self.w.confirmar_cierre())  # nadie contestó: cierra
        self.assertEqual(len(self._archivos()), 1)

    def test_la_ventana_principal_ignora_el_cierre_si_se_cancela(self) -> None:
        from pos_uniformes.ui.quote_satellite_window import QuoteSatelliteWindow

        falsa = SimpleNamespace(quick_sale_widget=SimpleNamespace(confirmar_cierre=lambda: False))
        evento = MagicMock()
        QuoteSatelliteWindow.closeEvent(falsa, evento)
        evento.ignore.assert_called_once()


class AvisosTests(_Base):
    """Prueba en tienda 2026-11-09: botones cortados y «Reintentar» en bucle."""

    def _botones(self, box) -> dict[str, object]:
        return {b.text(): b for b in box.buttons()}

    def _reintentar_fallando(self, veces: int) -> None:
        with patch.object(cola, "_save_raw", side_effect=_falla_siempre):
            for _ in range(veces):
                self.assertFalse(self.w._reintentar_anotacion())

    def test_tras_tres_fallos_el_aviso_deja_de_ofrecer_reintentar(self) -> None:
        self._anotar_fallando()
        self._reintentar_fallando(2)
        self.assertIn("Reintentar anotar", self._botones(self.w._aviso_anotacion))
        self._reintentar_fallando(1)
        aviso = self.w._aviso_anotacion
        self.assertEqual(set(self._botones(aviso)), {"Entendido (queda pendiente)"})
        self.assertIn("deja de reintentar", aviso.text())
        self.assertIn("Daniel", aviso.text())
        # Nada se pierde: sigue en memoria, en disco y con el botón del escáner.
        self.assertEqual(len(self.w._anotaciones_pendientes), 1)
        self.assertEqual(len(self._archivos()), 1)
        self.assertFalse(self.w._btn_reintentar_anotar.isHidden())

    def test_el_boton_del_escaner_sigue_reintentando_despues_del_limite(self) -> None:
        self._anotar_fallando()
        self._reintentar_fallando(3)
        self.assertTrue(self.w._reintentar_anotacion())
        self.assertEqual(self.w._anotaciones_pendientes, [])
        self.assertEqual(len(self._cola()), 1)
        self.assertEqual(self.w._reintentos_fallidos, 0)

    def test_un_exito_reinicia_la_cuenta_para_la_siguiente(self) -> None:
        self._anotar_fallando()
        self._reintentar_fallando(2)
        self.assertTrue(self.w._reintentar_anotacion())
        self.w._items = _items()
        self._anotar_fallando()
        self.assertIn("Reintentar anotar", self._botones(self.w._aviso_anotacion))

    def test_los_botones_del_aviso_no_quedan_cortados(self) -> None:
        self._anotar_fallando()
        for boton in self.w._aviso_anotacion.buttons():
            with self.subTest(boton.text()):
                self.assertGreaterEqual(boton.minimumWidth(), boton.sizeHint().width())

    def test_los_botones_del_cierre_no_quedan_cortados(self) -> None:
        self._anotar_fallando()
        vistos: dict[str, tuple[int, int]] = {}

        def contestar(box):
            for b in box.buttons():
                vistos[b.text()] = (b.minimumWidth(), b.sizeHint().width())
            return 0

        with patch.object(QMessageBox, "exec", new=contestar):
            self.w.confirmar_cierre()
        self.assertEqual(set(vistos), {"Cancelar (no cerrar)", "Cerrar de todos modos"})
        for texto, (minimo, pide) in vistos.items():
            with self.subTest(texto):
                self.assertGreaterEqual(minimo, pide)


class HigieneQtTests(_Base):
    def test_no_deja_avisos_ni_modal_activo(self) -> None:
        """C1 no contamina a otras pruebas (p. ej. la cartelera)."""
        self._anotar_fallando()
        self.w._items = _items()
        self._apartado_falla_solo_el_anticipo()
        w2 = self._kiosko()
        w2._avisar_pendientes_recuperados()
        self.assertTrue(_modales_visibles() - self._modales_antes)  # sí hubo avisos
        self._cerrar_widgets()
        self.assertEqual(_modales_visibles() - self._modales_antes, set())
        self.assertIsNone(QApplication.activeModalWidget())


class LogKioskoTests(unittest.TestCase):
    # 16
    def test_log_a_archivo_sin_consola(self) -> None:
        """Proceso aparte con stdout/stderr en None, como el .exe con
        console=False: el error queda en logs/kiosko.log."""
        raiz = Path(tempfile.mkdtemp(prefix="kiosko_log_"))
        self.addCleanup(shutil.rmtree, raiz, True)
        codigo = (
            "import sys, logging\n"
            "sys.stdout = None; sys.stderr = None\n"
            "from pathlib import Path\n"
            "from pos_uniformes.utils.kiosk_logging import configurar_log_kiosko\n"
            f"base = Path({str(raiz)!r})\n"
            "configurar_log_kiosko(base); configurar_log_kiosko(base)\n"
            "logging.getLogger('pos_uniformes.ui.views.quick_sale_view').error(\n"
            "    'Libreta: operación cobrada SIN anotar. operacion=%s', 'u-123')\n"
            "assert sum(1 for h in logging.getLogger().handlers if getattr(h, '_pos_uniformes_kiosko_log', False)) == 1\n"
        )
        repo = Path(__file__).resolve().parents[2]
        r = subprocess.run(
            [sys.executable, "-c", codigo], cwd=repo, capture_output=True, text=True, timeout=60,
            env={**os.environ, "PYTHONPATH": str(repo)},
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        texto = (raiz / "logs" / "kiosko.log").read_text(encoding="utf-8")
        self.assertIn("operacion=u-123", texto)
        self.assertIn("ERROR", texto)
        self.assertEqual(texto.count("cobrada SIN anotar"), 1)  # un solo handler

    def test_resumen_de_log_sin_datos_personales(self) -> None:
        resumen = sin_anotar.resumen_para_log([{
            "tipo": "venta", "operacion_uuid": "u-1", "employee_code": "VEND-3", "cliente": "Blanca Pérez",
            "cliente_codigo": "QR-999", "monto_total": "10", "items": [], "created_at": "2026-11-08T10:00:00",
        }])
        self.assertIn("u-1", resumen)
        self.assertNotIn("Blanca", resumen)
        self.assertNotIn("QR-999", resumen)


if __name__ == "__main__":
    unittest.main()
