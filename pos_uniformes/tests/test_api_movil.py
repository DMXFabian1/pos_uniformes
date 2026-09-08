"""Tests de la API móvil Fase 1 (solo lectura) y del snapshot SQLite.

La app FastAPI se prueba con TestClient y una base SQLite en memoria via
dependency_overrides — sin tocar Postgres.
"""

from __future__ import annotations

import unittest
from datetime import timedelta
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pos_uniformes.api.dependencies import get_current_employee, get_db
from pos_uniformes.api.main import app
from pos_uniformes.database.models import (
    Empleada,
    EmpleadaEvento,
    EmpleadaHorario,
    LibretaCorte,
    LibretaVenta,
    CajaParametros,
    CajaRetiro,
    EmpleadaPago,
)

_TABLAS = (Empleada, EmpleadaHorario, EmpleadaEvento, LibretaCorte, LibretaVenta, CajaParametros, EmpleadaPago, CajaRetiro)


class ApiMovilTests(unittest.TestCase):
    def setUp(self) -> None:
        # TestClient corre la app en otro hilo y sqlite :memory: vive POR
        # conexión: StaticPool fuerza una sola conexión compartida.
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        for t in _TABLAS:
            t.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()
        self._sembrar()
        app.dependency_overrides[get_db] = lambda: self.session
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.session.close()

    def _sembrar(self) -> None:
        s = self.session
        s.add_all(
            [
                Empleada(codigo="VEND-1", nombre_completo="Daniel Fabian", activo=True),
                Empleada(codigo="ENC-1", nombre_completo="León Fabian", activo=True),
                Empleada(codigo="VEND-4", nombre_completo="Fanny Ortiz", activo=True),
            ]
        )
        s.add(
            EmpleadaHorario(
                employee_code="VEND-4", descanso_weekday=3,
                ciclo_dias_pago=7, fecha_ultimo_pago=date.today(),
            )
        )
        s.add(
            LibretaVenta(
                employee_code="VEND-4", employee_name="Fanny", tipo="venta",
                piezas=2, comisiones=2, monto_total=Decimal("500.00"),
                monto_neto=Decimal("500.00"), detalle=[],
                created_at=datetime.now(),
            )
        )
        s.add(
            LibretaCorte(
                fecha=date.today(), monto_final=Decimal("17180.00"),
                operaciones=29, piezas=76, creado_por="VEND-1",
            )
        )
        s.commit()

    def _como(self, codigo: str) -> None:
        emp = (
            self.session.query(Empleada).filter(Empleada.codigo == codigo).one()
        )
        app.dependency_overrides[get_current_employee] = lambda: (emp, None)

    def test_empleada_ve_su_banner_y_calendario(self) -> None:
        self._como("VEND-4")
        data = self.client.get("/api/v1/movil/inicio").json()
        self.assertEqual(data["rol"], "empleada")
        self.assertEqual(data["nombre"], "Fanny")
        emp = data["empleada"]
        self.assertEqual(emp["comisiones_ciclo"], 0)  # pagada hoy: en ceros
        self.assertIsNotNone(emp["proximo_pago"])
        self.assertTrue(emp["calendario"]["dias"])  # el mes viene pintado
        # Su jueves fijo aparece pintado como descanso en el mes.
        self.assertIn("descanso", set(emp["calendario"]["dias"].values()))

    def test_encargado_ve_solo_cortes(self) -> None:
        self._como("ENC-1")
        data = self.client.get("/api/v1/movil/inicio").json()
        self.assertEqual(data["rol"], "encargado")
        self.assertEqual(len(data["cortes"]), 1)
        self.assertEqual(data["cortes"][0]["monto"], "17180.00")
        self.assertNotIn("dueno", data)
        self.assertNotIn("empleada", data)

    def test_dueno_ve_resumen_completo(self) -> None:
        self._como("VEND-1")
        data = self.client.get("/api/v1/movil/inicio").json()
        self.assertEqual(data["rol"], "dueno")
        d = data["dueno"]
        self.assertEqual(d["hoy"]["venta"], "500.00")
        self.assertEqual(d["hoy"]["piezas"], 2)
        self.assertEqual(d["ranking"][0]["codigo"], "VEND-4")
        self.assertEqual(d["ciclos"][0]["nombre"], "Fanny Ortiz")
        self.assertEqual(len(d["cortes"]), 1)

    def test_calendario_navegable(self) -> None:
        self._como("VEND-4")
        data = self.client.get("/api/v1/movil/calendario?year=2026&month=10").json()
        self.assertEqual(data["month"], 10)
        # Octubre 2026: los jueves (su descanso fijo) van pintados.
        self.assertEqual(data["dias"]["2026-10-01"], "descanso")  # jueves
        self.assertEqual(data["dias"]["2026-10-02"], "trabajo")

    def test_sin_token_da_401_o_403(self) -> None:
        app.dependency_overrides.pop(get_current_employee, None)
        r = self.client.get("/api/v1/movil/inicio")
        self.assertIn(r.status_code, (401, 403))


class EtiquetaMovilTests(unittest.TestCase):
    """POST /movil/etiqueta: encola a la Brother en modo tienda; en modo
    casa (snapshot) se niega con un mensaje claro."""

    def setUp(self) -> None:
        from pos_uniformes.database.models import (
            Categoria,
            Marca,
            Producto,
            Trabajo,
            Variante,
        )

        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        for t in (*_TABLAS, Categoria, Marca, Producto, Variante, Trabajo):
            t.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()
        cat = Categoria(nombre="Deportivo")
        marca = Marca(nombre="Genérica")
        self.session.add_all([cat, marca])
        self.session.flush()
        prod = Producto(
            nombre="Pants Sec Tec", nombre_base="Pants Sec Tec",
            categoria_id=cat.id, marca_id=marca.id,
        )
        self.session.add(prod)
        self.session.flush()
        self.session.add(
            Variante(
                producto_id=prod.id, sku="SKU777", talla="6", color="Marino",
                precio_venta=Decimal("515.00"), stock_actual=4, activo=True,
            )
        )
        self.session.add(
            Empleada(codigo="VEND-4", nombre_completo="Fanny Ortiz", activo=True)
        )
        self.session.commit()
        app.dependency_overrides[get_db] = lambda: self.session
        emp = self.session.query(Empleada).first()
        app.dependency_overrides[get_current_employee] = lambda: (emp, None)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.session.close()

    def test_en_modo_casa_se_niega(self) -> None:
        with patch(
            "pos_uniformes.api.routers.movil._modo_servidor", return_value="casa"
        ):
            r = self.client.post(
                "/api/v1/movil/etiqueta", json={"sku": "SKU777", "copies": 2}
            )
        self.assertEqual(r.status_code, 409)
        self.assertIn("tienda", r.json()["detail"]["error"]["message"])

    def test_en_tienda_renderiza_y_encola(self) -> None:
        import tempfile
        from pathlib import Path
        from types import SimpleNamespace

        from pos_uniformes.database.models import EstadoTrabajo, Trabajo, TipoTrabajo

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"png-falso")
            ruta = Path(f.name)
        try:
            with patch(
                "pos_uniformes.api.routers.movil._modo_servidor",
                return_value="tienda",
            ), patch(
                "pos_uniformes.services.inventory_label_service.render_inventory_label",
                return_value=SimpleNamespace(
                    image_path=ruta, effective_copies=3, mode="standard"
                ),
            ) as render:
                r = self.client.post(
                    "/api/v1/movil/etiqueta", json={"sku": "sku777", "copies": 3}
                )
            self.assertEqual(r.status_code, 200, r.text)
            data = r.json()
            self.assertTrue(data["encolada"])
            self.assertEqual(data["copias"], 3)
            render.assert_called_once()

            trabajo = self.session.query(Trabajo).one()
            self.assertEqual(trabajo.tipo, TipoTrabajo.ETIQUETA)
            self.assertEqual(trabajo.estado, EstadoTrabajo.PENDIENTE)
            self.assertEqual(trabajo.origen, "pwa")
            self.assertEqual(trabajo.creado_por, "VEND-4")
            self.assertEqual(trabajo.contenido["sku"], "SKU777")
            self.assertEqual(trabajo.contenido["copies"], 3)
        finally:
            ruta.unlink(missing_ok=True)

    def test_sku_inexistente_da_404(self) -> None:
        with patch(
            "pos_uniformes.api.routers.movil._modo_servidor", return_value="tienda"
        ):
            r = self.client.post(
                "/api/v1/movil/etiqueta", json={"sku": "NOEXISTE"}
            )
        self.assertEqual(r.status_code, 404)


class SnapshotTests(unittest.TestCase):
    def test_exporta_y_el_snapshot_sirve_para_leer(self) -> None:
        import tempfile
        from pathlib import Path

        from sqlalchemy import create_engine as _ce
        from sqlalchemy.orm import sessionmaker as _sm

        # Origen simulado: un sqlite con TODAS las tablas que exporta el
        # snapshot (incluye el catálogo para consultar precios desde casa).
        from pos_uniformes.database.models import (
            Categoria,
            Escuela,
            Marca,
            NivelEducativo,
            Producto,
            TipoPieza,
            Variante,
        )

        origen = _ce("sqlite://")
        for t in (
            *_TABLAS,
            Categoria,
            Marca,
            TipoPieza,
            Escuela,
            NivelEducativo,
            Producto,
            Variante,
        ):
            t.__table__.create(origen)
        ses = _sm(bind=origen)()
        ses.add(Empleada(codigo="VEND-4", nombre_completo="Fanny", activo=True))
        ses.add(
            LibretaCorte(
                fecha=date(2026, 9, 4), monto_final=Decimal("100.00"),
                operaciones=1, piezas=1, creado_por="VEND-1",
            )
        )
        ses.commit()

        with tempfile.TemporaryDirectory() as tmp, patch(
            "pos_uniformes.database.connection.engine", origen
        ):
            destino = Path(tmp) / "snap.sqlite"
            from pos_uniformes.scripts.exportar_snapshot_movil import exportar

            conteos = exportar(destino)
            self.assertEqual(conteos["empleada"], 1)
            self.assertEqual(conteos["libreta_corte"], 1)
            self.assertTrue(destino.exists())

            # El snapshot se puede leer con los mismos modelos.
            lector = _sm(bind=_ce(f"sqlite:///{destino}"))()
            self.assertEqual(lector.query(Empleada).count(), 1)
            corte = lector.query(LibretaCorte).one()
            self.assertEqual(corte.monto_final, Decimal("100.00"))
            lector.close()
        ses.close()


if __name__ == "__main__":
    unittest.main()


class EncargadoMovilTests(unittest.TestCase):
    """El modo de León en el celular: espejo del kiosko (apuntar, cortes)."""

    def setUp(self) -> None:
        from pos_uniformes.database.models import Trabajo

        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        for t in (*_TABLAS, Trabajo):
            t.__table__.create(engine)
        self.session = sessionmaker(bind=engine)()
        self.session.add_all(
            [
                Empleada(codigo="ENC-1", nombre_completo="León Fabian", activo=True),
                Empleada(codigo="VEND-1", nombre_completo="Daniel", activo=True),
                Empleada(codigo="VEND-4", nombre_completo="Fanny Ortiz", activo=True),
            ]
        )
        self.session.add(
            EmpleadaHorario(employee_code="VEND-4", descanso_weekday=date.today().weekday())
        )
        self.session.add(
            LibretaVenta(
                employee_code="VEND-4", employee_name="Fanny", tipo="venta",
                piezas=2, comisiones=2, monto_total=Decimal("500.00"),
                monto_neto=Decimal("500.00"), detalle=[], created_at=datetime.now(),
            )
        )
        self.session.commit()
        app.dependency_overrides[get_db] = lambda: self.session
        leon = self.session.query(Empleada).filter(Empleada.codigo == "ENC-1").one()
        app.dependency_overrides[get_current_employee] = lambda: (leon, None)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.session.close()

    def test_payload_encargado_equipo_y_descansos(self) -> None:
        with patch(
            "pos_uniformes.api.routers.movil._modo_servidor", return_value="tienda"
        ):
            data = self.client.get("/api/v1/movil/encargado").json()
        self.assertEqual([e["nombre"] for e in data["equipo"]], ["Fanny"])
        # Su descanso fijo cae hoy → aparece en la semana.
        self.assertTrue(
            any("Fanny" in d["nombres"] for d in data["descansos_semana"])
        )

    def test_marcar_falta_y_quitar(self) -> None:
        from pos_uniformes.database.models import EmpleadaEvento

        hoy = date.today().isoformat()
        with patch(
            "pos_uniformes.api.routers.movil._modo_servidor", return_value="tienda"
        ):
            r = self.client.post(
                "/api/v1/movil/encargado/marcar",
                json={"employee_code": "VEND-4", "fecha": hoy, "tipo": "falta"},
            )
            self.assertEqual(r.status_code, 200, r.text)
            evento = self.session.query(EmpleadaEvento).one()
            self.assertEqual(evento.tipo, "falta")
            self.assertIn("ENC-1", evento.nota)
            self.client.post(
                "/api/v1/movil/encargado/marcar",
                json={"employee_code": "VEND-4", "fecha": hoy, "tipo": "quitar"},
            )
            self.assertEqual(self.session.query(EmpleadaEvento).count(), 0)

    def test_marcar_en_modo_casa_se_niega(self) -> None:
        with patch(
            "pos_uniformes.api.routers.movil._modo_servidor", return_value="casa"
        ):
            r = self.client.post(
                "/api/v1/movil/encargado/marcar",
                json={
                    "employee_code": "VEND-4",
                    "fecha": date.today().isoformat(),
                    "tipo": "falta",
                },
            )
        self.assertEqual(r.status_code, 409)

    def test_corte_guarda_y_encola_ticket(self) -> None:
        """Corte de un botón: cifra calculada, pagos del día registrados solos,
        fondo intacto y ticket a la impresora de la tienda."""
        from pos_uniformes.database.models import CajaParametros, EmpleadaPago, LibretaCorte, TipoTrabajo, Trabajo

        self.session.add(
            CajaParametros(id=1, reactivo_actual=Decimal("11160.00"), sueldo_base=Decimal("1300.00"), tarifa_comision=Decimal("2.00"))
        )
        # A Fanny le toca pago hoy (último pago hace 7 días).
        horario = self.session.query(EmpleadaHorario).filter(EmpleadaHorario.employee_code == "VEND-4").one()
        horario.fecha_ultimo_pago = date.today() - timedelta(days=7)
        self.session.commit()
        with patch(
            "pos_uniformes.api.routers.movil._modo_servidor", return_value="tienda"
        ):
            datos = self.client.get("/api/v1/movil/encargado/corte_hoy").json()
            self.assertTrue(datos["hay_ventas"])
            self.assertEqual(datos["efectivo"], "500.00")
            self.assertEqual([p["nombre"] for p in datos["pagos_hoy"]], ["Fanny Ortiz"])
            self.assertEqual(datos["pagos_hoy"][0]["total"], "1304.00")
            self.assertEqual(datos["retiro"], "-804.00")
            r = self.client.post("/api/v1/movil/encargado/corte", json={})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["venta"], "500.00")
        self.assertEqual(r.json()["pagos"][0]["total"], "1304.00")
        self.assertEqual(r.json()["monto"], "10356.00")  # 11160 + 500 - 1304
        # El pago superó la venta: el fondo baja a lo que quedó y no se retira nada.
        self.assertEqual(r.json()["reactivo_final"], "10356.00")
        self.assertEqual(r.json()["retiro"], "0.00")
        self.assertTrue(r.json()["ticket_encolado"])
        corte = self.session.query(LibretaCorte).one()
        self.assertEqual(corte.creado_por, "ENC-1")
        self.assertEqual(corte.retiros_pagos, Decimal("1304.00"))
        self.assertEqual(self.session.query(EmpleadaPago).one().creado_por, "ENC-1")
        trabajo = self.session.query(Trabajo).one()
        self.assertEqual(trabajo.tipo, TipoTrabajo.TICKET)
        self.assertIn("PAGAR A FANNY", trabajo.contenido["texto"])
        self.assertIn("SACAR DE LA VENTA", trabajo.contenido["texto"])

    def test_pagar_registra_desglose(self) -> None:
        from pos_uniformes.database.models import CajaParametros, EmpleadaPago

        self.session.add(
            CajaParametros(id=1, sueldo_base=Decimal("1300.00"), tarifa_comision=Decimal("2.00"), descuento_falta=Decimal("216.67"))
        )
        self.session.commit()
        with patch(
            "pos_uniformes.api.routers.movil._modo_servidor", return_value="tienda"
        ):
            pend = self.client.get("/api/v1/movil/encargado/pago_pendiente/VEND-4").json()
            self.assertEqual(pend["comisiones"], 2)
            self.assertEqual(pend["total"], "1304.00")
            r = self.client.post("/api/v1/movil/encargado/pagar", json={"employee_code": "VEND-4"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["total"], "1304.00")
        pago = self.session.query(EmpleadaPago).one()
        self.assertEqual(pago.creado_por, "ENC-1")
        self.assertEqual(pago.employee_code, "VEND-4")
        inicio = self.client.get("/api/v1/movil/encargado").json()
        self.assertIn("descansa", inicio["resumen"])

    def test_empleada_no_puede_usar_encargado(self) -> None:
        fanny = self.session.query(Empleada).filter(Empleada.codigo == "VEND-4").one()
        app.dependency_overrides[get_current_employee] = lambda: (fanny, None)
        r = self.client.get("/api/v1/movil/encargado")
        self.assertEqual(r.status_code, 403)
