"""El informe de finanzas contra la base de verdad.

Estas pruebas van contra la base (no con mocks) a proposito: los dos
errores que tuvo el script al escribirlo fueron de SQL —un GROUP BY que
Postgres rechaza y dos columnas de apartado que no existen con ese
nombre—, y ninguno de los dos se ve con una sesion falsa.
"""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pos_uniformes.database.connection import get_session
from pos_uniformes.database.models import CajaRetiro, LibretaCorte, LibretaVenta
from pos_uniformes.scripts.informe_finanzas import construir

_MARCA = "TEST-INFORME"


class InformeDeFinanzasTests(unittest.TestCase):
    """Siembra unos movimientos conocidos y revisa que el informe los cuente."""

    def setUp(self) -> None:
        self.session = get_session()
        self.addCleanup(self._limpiar)
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
        self.session.commit()

    def _limpiar(self) -> None:
        try:
            self.session.query(LibretaVenta).filter_by(employee_code=_MARCA).delete()
            self.session.query(CajaRetiro).filter_by(motivo=_MARCA).delete()
            self.session.query(LibretaCorte).filter_by(periodo_label=_MARCA).delete()
            self.session.commit()
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
        self.assertIn(f"{self.hoy:%Y-%m}", informe)
        self.assertIn(f"{self.mes_pasado:%Y-%m}", informe)

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


if __name__ == "__main__":
    unittest.main()
