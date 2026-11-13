"""El informe de finanzas contra la base de verdad.

Estas pruebas van contra la base (no con mocks) a proposito: los dos
errores que tuvo el script al escribirlo fueron de SQL —un GROUP BY que
Postgres rechaza y dos columnas de apartado que no existen con ese
nombre—, y ninguno de los dos se ve con una sesion falsa.
"""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import CajaRetiro, LibretaCorte, LibretaVenta
from pos_uniformes.scripts.informe_finanzas import _entradas, construir

_MARCA = "TEST-INFORME"
# La base agrupa el mes en la hora de la tienda: la etiqueta esperada tambien.
_TIENDA = ZoneInfo("America/Mexico_City")


class InformeDeFinanzasTests(unittest.TestCase):
    """Siembra unos movimientos conocidos y revisa que el informe los cuente.

    `construir` suma las tablas ENTERAS, así que la prueba es hermética: todo
    pasa en una transacción que se revierte. Dentro de ella se vacían las tres
    tablas que el informe suma y se siembra lo conocido; el informe lee con la
    misma sesión. Nada se escribe de verdad, y nada que otra prueba haya dejado
    (o esté escribiendo) entra en la suma (2026-11-11)."""

    def setUp(self) -> None:
        self.session = get_session()
        self.addCleanup(self._limpiar)
        self._vaciar_lo_que_el_informe_suma()
        ahora = datetime.now(timezone.utc)
        self.hoy = ahora
        self.mes_pasado = ahora - timedelta(days=40)
        self.session.add_all(
            [
                LibretaVenta(
                    employee_code=_MARCA,
                    employee_name="Empleada de prueba",
                    tipo="venta",
                    piezas=3,
                    comisiones=2,
                    monto_total=Decimal("1000.00"),
                    monto_neto=Decimal("1000.00"),
                    pago_tarjeta=False,
                    created_at=self.hoy,
                ),
                LibretaVenta(
                    employee_code=_MARCA,
                    employee_name="Empleada de prueba",
                    tipo="venta",
                    piezas=1,
                    comisiones=1,
                    monto_total=Decimal("500.00"),
                    # Con tarjeta entra menos: eso es lo que hay que ver.
                    monto_neto=Decimal("477.50"),
                    pago_tarjeta=True,
                    created_at=self.hoy,
                ),
                LibretaVenta(
                    employee_code=_MARCA,
                    employee_name="Empleada de prueba",
                    tipo="abono",
                    piezas=0,
                    comisiones=0,
                    monto_total=Decimal("200.00"),
                    monto_neto=Decimal("200.00"),
                    pago_tarjeta=False,
                    created_at=self.mes_pasado,
                ),
            ]
        )
        self.session.add(
            CajaRetiro(
                monto=Decimal("91.00"),
                motivo=_MARCA,
                creado_por=_MARCA,
                created_at=self.hoy,
            )
        )
        self.session.add(
            LibretaCorte(
                fecha=self.hoy.date(),
                periodo_label=_MARCA,
                monto_esperado=Decimal("1500.00"),
                monto_final=Decimal("1300.00"),
                operaciones=2,
                piezas=4,
                nota=_MARCA,
                created_at=self.hoy,
            )
        )
        self.session.flush()  # visible para `construir`; nunca se confirma

    def _vaciar_lo_que_el_informe_suma(self) -> None:
        for modelo in (CajaRetiro, LibretaCorte, LibretaVenta):
            self.session.query(modelo).delete(synchronize_session=False)
        self.session.flush()

    def _limpiar(self) -> None:
        try:
            self.session.rollback()  # deshace la siembra y el vaciado
        finally:
            self.session.close()

    def test_separa_lo_cobrado_de_lo_que_de_verdad_entro(self) -> None:
        informe = construir(self.session, 7)
        self.assertIn("$1,500.00", informe)  # cobrado
        self.assertIn("$1,477.50", informe)  # recibido
        self.assertIn("$22.50", informe)  # se quedo la terminal

    def test_el_corte_corto_sale_como_faltante(self) -> None:
        informe = construir(self.session, 7)
        self.assertIn("$-200.00", informe)
        self.assertIn("Faltante acumulado   : $200.00", informe)

    def test_agrupa_por_mes_sin_que_postgres_se_queje(self) -> None:
        """El GROUP BY del mes: con "month" como parametro, Postgres falla."""
        informe = construir(self.session, 60)
        self.assertIn(f"{self.hoy.astimezone(_TIENDA):%Y-%m}", informe)
        self.assertIn(f"{self.mes_pasado.astimezone(_TIENDA):%Y-%m}", informe)

    def test_el_retiro_aparece_como_gasto_descontado(self) -> None:
        informe = construir(self.session, 7)
        self.assertIn("retiros del cajon (gastos descontados)", informe)
        self.assertIn("$91.00", informe)

    def test_dice_en_voz_alta_que_no_es_una_utilidad(self) -> None:
        """Lo mas importante del informe es lo que no sabe."""
        informe = construir(self.session, 7)
        self.assertIn("NO es una utilidad", informe)

    def test_los_apartados_vivos_se_consultan_con_las_columnas_que_existen(self) -> None:
        """total_abonado y saldo_pendiente; `abonado` y `total` no van."""
        informe = construir(self.session, 7)
        self.assertIn("apartados vivos", informe)
        self.assertIn("Falta que paguen", informe)


class MonederoYApartadosEnElInformeTests(unittest.TestCase):
    """WALLET-005 e INF-PRE-001: solo cuenta el dinero que de verdad entró.

    Cada prueba usa su propio código de empleada y lee `_entradas` filtrado
    por él: así los números no dependen de lo demás que haya en la base."""

    def setUp(self) -> None:
        self.session = get_session()
        self.codigo = f"TST-FIN-{uuid.uuid4().hex[:8].upper()}"
        self.addCleanup(self._limpiar)
        self.desde = datetime.now(timezone.utc) - timedelta(days=1)

    def _limpiar(self) -> None:
        try:
            self.session.rollback()
            self.session.query(LibretaVenta).filter_by(employee_code=self.codigo).delete()
            self.session.commit()
        finally:
            self.session.close()

    def _op(self, tipo, total, neto, *, monedero="0", tarjeta=False, piezas=1, comisiones=1):
        self.session.add(LibretaVenta(
            employee_code=self.codigo, employee_name="Prueba informe", tipo=tipo,
            piezas=piezas, comisiones=comisiones, monto_total=Decimal(total),
            monto_neto=Decimal(neto), monto_monedero=Decimal(monedero),
            pago_tarjeta=tarjeta, detalle=[], created_at=datetime.now(timezone.utc),
        ))

    def _informe(self) -> str:
        self.session.commit()
        return "\n".join(_entradas(self.session, self.desde, solo_empleada=self.codigo))

    def _renglon(self, texto: str, empieza: str) -> str:
        return next(l for l in texto.splitlines() if l.startswith(empieza))

    # ── monedero ─────────────────────────────────────────────────────────
    def test_30_monedero_70_efectivo(self) -> None:
        self._op("venta", "100.00", "70.00", monedero="30.00")
        texto = self._informe()
        self.assertIn("Cobrado              : $70.00", texto)
        self.assertIn("Recibido de verdad   : $70.00", texto)
        self.assertNotIn("Se quedo la terminal", texto)   # el monedero NO es comisión
        self.assertIn("Pagado con monedero  : $30.00", texto)
        self.assertIn("$70.00", self._renglon(texto, "Efectivo"))
        self.assertIn("1 cobros", self._renglon(texto, "Efectivo"))
        self.assertIn("0 cobros", self._renglon(texto, "Tarjeta"))

    def test_30_monedero_70_tarjeta(self) -> None:
        from pos_uniformes.services.libreta_service import neto_de_cobro

        neto = neto_de_cobro(Decimal("100"), Decimal("30"), True)
        self.assertEqual(neto, Decimal("67.00"))   # 70 − 4.5% con el redondeo de la tienda
        self._op("venta", "100.00", str(neto), monedero="30.00", tarjeta=True)
        texto = self._informe()
        self.assertIn("Cobrado              : $70.00", texto)
        self.assertIn("Recibido de verdad   : $67.00", texto)
        self.assertIn("Se quedo la terminal : $3.00", texto)   # solo sobre los $70
        tarjeta = self._renglon(texto, "Tarjeta")
        self.assertIn("$70.00", tarjeta)
        self.assertIn("neto         $67.00", tarjeta)

    def test_venta_toda_con_monedero(self) -> None:
        self._op("venta", "100.00", "0.00", monedero="100.00")
        texto = self._informe()
        self.assertIn("Cobrado              : $0.00", texto)
        self.assertIn("Recibido de verdad   : $0.00", texto)
        self.assertNotIn("Se quedo la terminal", texto)
        self.assertIn("Pagado con monedero  : $100.00", texto)
        self.assertIn("0 cobros", self._renglon(texto, "Efectivo"))   # no entró por el cajón
        self.assertIn("0 cobros", self._renglon(texto, "Tarjeta"))

    def test_desgloses_cuadran_con_el_encabezado(self) -> None:
        self._op("venta", "100.00", "70.00", monedero="30.00")
        self._op("venta", "100.00", "67.00", monedero="30.00", tarjeta=True)
        self._op("venta", "100.00", "0.00", monedero="100.00")
        texto = self._informe()
        self.assertIn("Cobrado              : $140.00", texto)
        self.assertIn("Recibido de verdad   : $137.00", texto)
        self.assertIn("Se quedo la terminal : $3.00", texto)
        self.assertIn("$160.00", self._renglon(texto, "Monedero"))
        venta = self._renglon(texto, "venta ")
        self.assertIn("$140.00", venta)
        self.assertIn("$137.00", venta)
        mes = self._renglon(texto, f"{datetime.now(_TIENDA):%Y-%m}")
        self.assertIn("cobrado        $140.00", mes)
        self.assertIn("neto        $137.00", mes)
        quien = self._renglon(texto, "Prueba informe")
        self.assertIn("$140.00", quien)
        self.assertIn("100.0%", quien)

    # ── apartados (INF-PRE-001) ──────────────────────────────────────────
    def test_apartado_sin_abono_no_es_dinero(self) -> None:
        self._op("apartado", "1000.00", "1000.00", piezas=3, comisiones=2)
        texto = self._informe()
        self.assertIn("Cobros               : 0", texto)
        self.assertIn("Cobrado              : $0.00", texto)
        self.assertIn("Recibido de verdad   : $0.00", texto)
        self.assertIn("Apartados hechos     : 1 por $1,000.00", texto)
        self.assertIn("(no es dinero)", self._renglon(texto, "apartado"))
        self.assertIn("2 com", self._renglon(texto, "Prueba informe"))   # la comisión sí cuenta

    def test_mes_cuenta_piezas_del_apartado_sin_sumar_dinero(self) -> None:
        """MEDIA-2: el apartado cuenta en ops y piezas del mes, no en dinero."""
        self._op("apartado", "1000.00", "1000.00", piezas=3, comisiones=2)
        self._op("venta", "100.00", "100.00", piezas=1, comisiones=1)
        texto = self._informe()
        self.assertIn("Cobros               : 1 (1 piezas)", texto)   # el encabezado no cambia
        self.assertIn("Cobrado              : $100.00", texto)
        self.assertIn("Recibido de verdad   : $100.00", texto)
        self.assertNotIn("Se quedo la terminal", texto)
        mes = self._renglon(texto, f"{datetime.now(_TIENDA):%Y-%m}")
        self.assertIn("cobrado        $100.00", mes)
        self.assertIn("neto        $100.00", mes)
        self.assertIn("    2 ops", mes)
        self.assertIn("     4 pz", mes)

    def test_apartado_con_anticipo_abonos_y_liquidacion(self) -> None:
        self._op("apartado", "1000.00", "1000.00", piezas=3, comisiones=2)
        self._op("abono", "300.00", "300.00", piezas=0, comisiones=0)   # anticipo
        self._op("abono", "400.00", "400.00", piezas=0, comisiones=0)
        self._op("abono", "300.00", "286.50", tarjeta=True, piezas=0, comisiones=0)   # liquida con tarjeta
        texto = self._informe()
        self.assertIn("Cobros               : 3", texto)
        self.assertIn("Cobrado              : $1,000.00", texto)    # no $2,000
        self.assertIn("Recibido de verdad   : $986.50", texto)
        self.assertIn("Se quedo la terminal : $13.50", texto)
        abono = self._renglon(texto, "abono ")
        self.assertIn("$1,000.00", abono)
        self.assertIn("3 cobros", abono)
        quien = self._renglon(texto, "Prueba informe")
        self.assertIn("$1,000.00", quien)
        # Un abono no es operación (Daniel, 2026-11-12): solo el apartado.
        self.assertIn("   1 ops", quien)
        mes = self._renglon(texto, f"{datetime.now(_TIENDA):%Y-%m}")
        self.assertIn("    1 ops", mes)
        self.assertIn("     3 pz", mes)
        self.assertNotIn("Operaciones cobradas", texto)


if __name__ == "__main__":
    unittest.main()
