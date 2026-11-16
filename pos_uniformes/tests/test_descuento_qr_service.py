"""QR de descuento de temporada: el servicio (prefijo, candados, intentos,
vencimiento, opciones del diálogo). Daniel, 2026-11-16: «Sí, con candados».

Puras: sin base, sin Qt. El hash se arma con `AuthService` como lo guarda
Configuración; los códigos de prueba son inventados aquí.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

from pos_uniformes.services import descuento_qr_service as qr
from pos_uniformes.services.auth_service import AuthService
from pos_uniformes.services.beneficios.contrato import ReglasCtx
from pos_uniformes.services.manual_promo_service import (
    DEFAULT_PROMO_AUTHORIZATION_CODE,
    LEGACY_DEFAULT_PROMO_AUTHORIZATION_CODES,
)

D = Decimal
CODIGO = "Temporada-Prueba-77"   # inventado para la prueba
HASH = AuthService.hash_password(CODIGO)


class PrefijoTests(unittest.TestCase):
    def test_reconoce_el_prefijo(self) -> None:
        self.assertTrue(qr.es_qr_descuento(f"DSCT-{CODIGO}"))
        self.assertTrue(qr.es_qr_descuento(f"  dsct-{CODIGO}\n"))
        # Escáner con teclado en español: «-» llega como «'».
        self.assertTrue(qr.es_qr_descuento(f"DSCT'{CODIGO}"))

    def test_no_confunde_otros_escaneos(self) -> None:
        for texto in ("DSCT-", "DSCT", "SKU-123", "EMP:VEND-2", "CLI-000009", "", None, "XDSCT-abc"):
            self.assertFalse(qr.es_qr_descuento(texto), texto)

    def test_el_codigo_llega_tal_cual(self) -> None:
        self.assertEqual(qr.codigo_de(f"DSCT-{CODIGO}"), CODIGO)
        self.assertEqual(qr.codigo_de(f"dsct'{CODIGO}"), CODIGO)
        self.assertEqual(qr.codigo_de("SKU-1"), "")


class CandadosTests(unittest.TestCase):
    def test_codigo_bueno(self) -> None:
        self.assertEqual(qr.validar_contra_hash(CODIGO, HASH), qr.VALIDO)

    def test_codigo_equivocado(self) -> None:
        self.assertEqual(qr.validar_contra_hash("otro-codigo", HASH), qr.NO_VALIDO)
        self.assertEqual(qr.validar_contra_hash("", HASH), qr.NO_VALIDO)

    def test_codigo_de_fabrica_se_rechaza_aunque_sea_el_guardado(self) -> None:
        guardado = AuthService.hash_password(DEFAULT_PROMO_AUTHORIZATION_CODE)
        self.assertEqual(qr.validar_contra_hash(DEFAULT_PROMO_AUTHORIZATION_CODE, guardado), qr.CODIGO_CONOCIDO)
        # Y con el de fábrica guardado, ningún código abre el QR.
        self.assertEqual(qr.validar_contra_hash(CODIGO, guardado), qr.CODIGO_CONOCIDO)

    def test_codigos_de_antes_se_rechazan(self) -> None:
        for legado in LEGACY_DEFAULT_PROMO_AUTHORIZATION_CODES:
            guardado = AuthService.hash_password(legado)
            self.assertEqual(qr.validar_contra_hash(legado, guardado), qr.CODIGO_CONOCIDO, legado)
            self.assertEqual(qr.validar_contra_hash(legado, HASH), qr.CODIGO_CONOCIDO, legado)
            self.assertEqual(qr.validar_contra_hash(CODIGO, guardado), qr.CODIGO_CONOCIDO, legado)

    def test_sin_hash_guardado_se_rechaza(self) -> None:
        # La caja usaría el de fábrica: está en el repo público.
        self.assertEqual(qr.validar_contra_hash(CODIGO, None), qr.CODIGO_CONOCIDO)

    def test_el_texto_dice_que_hacer(self) -> None:
        self.assertEqual(qr.TXT_CODIGO_CONOCIDO, "Cambia el código del QR en Configuración")

    def test_validar_codigo_lee_la_configuracion(self) -> None:
        sesion = SimpleNamespace(scalar=lambda _consulta: HASH)
        self.assertEqual(qr.validar_codigo(sesion, f"DSCT-{CODIGO}"), qr.VALIDO)
        self.assertEqual(qr.validar_codigo(sesion, "DSCT-nada"), qr.NO_VALIDO)


class IntentosTests(unittest.TestCase):
    def _contador(self):
        self.ahora = 1000.0
        return qr.ContadorIntentos(reloj=lambda: self.ahora)

    def test_tres_fallos_seguidos_bloquean_cinco_minutos(self) -> None:
        c = self._contador()
        self.assertFalse(c.fallo())
        self.assertFalse(c.fallo())
        self.assertFalse(c.bloqueado())
        self.assertTrue(c.fallo())
        self.assertTrue(c.bloqueado())
        self.assertEqual(c.segundos_bloqueado(), 300)
        self.ahora += 299
        self.assertTrue(c.bloqueado())
        self.ahora += 2
        self.assertFalse(c.bloqueado())
        # Pasado el bloqueo la cuenta empieza de cero.
        self.assertFalse(c.fallo())

    def test_un_codigo_bueno_reinicia_la_cuenta(self) -> None:
        c = self._contador()
        c.fallo()
        c.fallo()
        c.exito()
        self.assertFalse(c.fallo())
        self.assertFalse(c.bloqueado())

    def test_el_bloqueo_sobrevive_a_reiniciar_la_app(self) -> None:
        """Revisión 2026-11-16: cerrar y abrir el kiosko no da 3 intentos más."""
        import tempfile
        from pathlib import Path

        d = Path(tempfile.mkdtemp())
        ruta = d / "intentos.json"
        self.ahora = 1000.0
        reloj = lambda: self.ahora  # noqa: E731
        c = qr.ContadorIntentos(reloj=reloj, archivo=lambda: ruta)
        c.fallo()
        c.fallo()
        # «Reinicio»: un contador nuevo lee lo que dejó el anterior.
        otro = qr.ContadorIntentos(reloj=reloj, archivo=lambda: ruta)
        self.assertTrue(otro.fallo())
        nuevo = qr.ContadorIntentos(reloj=reloj, archivo=lambda: ruta)
        self.assertEqual(nuevo.segundos_bloqueado(), 300)
        # En el archivo no va ningún código, solo la cuenta y la hora.
        self.assertEqual(set(__import__("json").loads(ruta.read_text())), {"fallos", "hasta"})
        self.ahora += 301
        self.assertFalse(qr.ContadorIntentos(reloj=reloj, archivo=lambda: ruta).bloqueado())
        nuevo.exito()
        self.assertFalse(qr.ContadorIntentos(reloj=reloj, archivo=lambda: ruta).fallo())

    def test_archivo_danado_no_tumba_la_venta(self) -> None:
        import tempfile
        from pathlib import Path

        ruta = Path(tempfile.mkdtemp()) / "intentos.json"
        ruta.write_text("{no es json")
        c = qr.ContadorIntentos(reloj=lambda: 1000.0, archivo=lambda: ruta)
        self.assertFalse(c.bloqueado())
        self.assertFalse(c.fallo())

    def test_el_de_la_maquina_guarda_en_su_carpeta_de_datos(self) -> None:
        self.assertEqual(qr.ruta_intentos().name, "descuento_qr_intentos.json")

    def test_rechazo_previo_bloqueado(self) -> None:
        c = self._contador()
        for _ in range(3):
            c.fallo()
        texto = qr.rechazo_previo(hay_empleada=True, en_linea=True, momento=date(2026, 12, 1), contador=c)
        self.assertIn("Espera 5 min", texto)

    def test_rechazo_previo_orden(self) -> None:
        c = self._contador()
        hoy = date(2026, 12, 1)
        self.assertEqual(qr.rechazo_previo(hay_empleada=False, en_linea=True, momento=hoy, contador=c),
                         qr.TXT_SIN_EMPLEADA)
        self.assertEqual(qr.rechazo_previo(hay_empleada=True, en_linea=False, momento=hoy, contador=c),
                         "El QR de descuento necesita conexión")
        self.assertIsNone(qr.rechazo_previo(hay_empleada=True, en_linea=True, momento=hoy, contador=c))


class VencimientoTests(unittest.TestCase):
    def test_vence_al_final_del_6_de_enero(self) -> None:
        self.assertEqual(qr.VENCE, date(2027, 1, 6))
        self.assertFalse(qr.vencido(datetime(2027, 1, 6, 23, 59)))
        self.assertTrue(qr.vencido(datetime(2027, 1, 7, 0, 0)))
        self.assertFalse(qr.vencido(date(2026, 11, 16)))

    def test_hora_con_zona_se_lee_en_hora_local(self) -> None:
        local = datetime(2027, 1, 6, 23, 30).astimezone()
        self.assertFalse(qr.vencido(local.astimezone(timezone.utc)))
        self.assertTrue(qr.vencido((local + timedelta(hours=1)).astimezone(timezone.utc)))

    def test_vencido_se_rechaza_al_escanear(self) -> None:
        texto = qr.rechazo_previo(hay_empleada=True, en_linea=True, momento=date(2027, 1, 7),
                                  contador=qr.ContadorIntentos())
        self.assertEqual(texto, "El descuento de temporada terminó")

    def test_las_reglas_del_motor_usan_la_misma_fecha(self) -> None:
        self.assertEqual(ReglasCtx().qr_vence, qr.VENCE.isoformat())


class RopaNormalTests(unittest.TestCase):
    def test_categorias(self) -> None:
        for cat in ("Ropa casual", "  ropa   CASUAL ", "Temporada", "Deportivo casual", "Ropa interior"):
            self.assertTrue(qr.es_ropa_normal(cat), cat)
        for cat in ("Accesorio", "Oficial", "Deportivo", "Uniformes", "", None):
            self.assertFalse(qr.es_ropa_normal(cat), cat)

    def test_base_elegible_sin_rebajas_ni_3pz(self) -> None:
        items = [
            {"sku": "SC1", "precio": D("400"), "cantidad": 1, "categoria": "Ropa casual"},
            {"sku": "TE1", "precio": D("150"), "cantidad": 2, "categoria": "Temporada"},
            {"sku": "PO1", "precio": D("180"), "cantidad": 1, "categoria": "Oficial"},
            {"sku": "CA1", "precio": D("45"), "cantidad": 1, "categoria": "Accesorio"},
            {"sku": "LQ1", "precio": D("200"), "precio_normal": D("300"), "rebaja": "liquidacion", "cantidad": 1,
             "categoria": "Ropa casual"},
        ]
        self.assertEqual(qr.base_elegible(items), D("700.00"))


class OpcionesTests(unittest.TestCase):
    def test_con_600_el_15_esta_habilitado(self) -> None:
        ops = qr.opciones(D("600"))
        self.assertEqual([o.texto for o in ops], ["5 %", "10 %", "15 %"])
        self.assertTrue(all(o.habilitada for o in ops))

    def test_bajo_600_el_15_sale_deshabilitado_con_su_porque(self) -> None:
        ops = qr.opciones(D("599.99"))
        self.assertTrue(ops[0].habilitada and ops[1].habilitada)
        self.assertFalse(ops[2].habilitada)
        self.assertIn("$600", ops[2].razon)
        self.assertIn("ropa normal", ops[2].razon)

    def test_chip(self) -> None:
        self.assertEqual(qr.texto_chip(D("10")), "Descuento QR 10 %  ✕")
        info = SimpleNamespace(pct_pedido=D("15"), pct=D("10"), importe=D("50"), motivo="QR_15_A_10")
        texto = qr.texto_chip(D("15"), SimpleNamespace(descuento_qr=info))
        self.assertIn("Descuento QR 10 %", texto)
        self.assertIn("15 % pide $600 de ropa normal; se aplicó 10 %", texto)


if __name__ == "__main__":
    unittest.main()
