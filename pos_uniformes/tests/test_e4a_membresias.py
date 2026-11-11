"""E4-A: reglas de membresías. Base local de prueba, transacción revertida."""

from __future__ import annotations

import unittest
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pos_uniformes.database.models import (
    Cliente,
    ClienteEvento,
    ClienteTipo,
    Empleada,
    LibretaVenta,
    Membresia,
    MembresiaEvento,
    RolUsuario,
    Usuario,
    Venta,
)
from pos_uniformes.services.clientes import admin_service as adm
from pos_uniformes.services.clientes import identidad_service as ids
from pos_uniformes.services.fidelizacion import membresia_service as ms
from pos_uniformes.utils.config import settings
from tests.base_por_trabajador import es_base_de_prueba_local


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        url = make_url(settings.database_url)
        if not es_base_de_prueba_local(url):
            self.skipTest("Solo corre contra la base local de prueba.")
        self.engine = create_engine(url)
        self.addCleanup(self.engine.dispose)
        self.conn = self.engine.connect()
        self.addCleanup(self.conn.close)
        self.tx = self.conn.begin()
        self.addCleanup(self.tx.rollback)
        self.s = Session(bind=self.conn, join_transaction_mode="create_savepoint")
        self.addCleanup(self.s.close)
        sufijo = uuid.uuid4().hex[:6]
        self.admin = Usuario(username=f"e4a_{sufijo}", nombre_completo="Admin", password_hash="x", rol=RolUsuario.ADMIN, activo=True)
        self.cajero = Usuario(username=f"e4c_{sufijo}", nombre_completo="Cajero", password_hash="x", rol=RolUsuario.CAJERO, activo=True)
        self.lupita = Empleada(codigo=f"E4A{sufijo}".upper(), nombre_completo="Lupita Prueba", activo=True)
        self.baja = Empleada(codigo=f"E4B{sufijo}".upper(), nombre_completo="Ex Empleada", activo=False)
        self.s.add_all([self.admin, self.cajero, self.lupita, self.baja])
        self.s.flush()
        self.n = uuid.uuid4().int % 10**6
        self.cliente = self._cliente("Ana E4A")

    def _cliente(self, nombre, tipo="GENERAL") -> Cliente:
        self.n += 1
        return ids.dar_de_alta(self.s, nombre=nombre, telefono=f"66{self.n:08d}", origen=ids.ORIGEN_VENTA_RAPIDA, tipo_clave=tipo)

    def _eventos(self, m: Membresia) -> list[str]:
        return [e.tipo for e in self.s.scalars(select(MembresiaEvento).where(MembresiaEvento.membresia_id == m.id).order_by(MembresiaEvento.id))]

    def _tipo(self, c: Cliente) -> str:
        self.s.refresh(c)
        return self.s.get(ClienteTipo, c.tipo_cliente_id).clave

    def _proponer(self, clave="PROFESIONAL", cliente=None):
        return ms.proponer(self.s, cliente_id=(cliente or self.cliente).id, programa_clave=clave,
                           employee_code=self.lupita.codigo, motivo="Maestra de la Benito Juárez")


class ProgramasIniciales(_Base):
    def test_cuatro_programas_activos(self) -> None:
        """E5-A (2026-11-10) agregó Maximoda Leal en segundo lugar."""
        progs = {p.clave: p for p in ms.programas_activos(self.s)}
        self.assertEqual(list(progs), ["CLUB", "LEAL", "PROFESIONAL", "MAYORISTA"])
        self.assertEqual(progs["CLUB"].ingreso_modo, ms.DIRECTO_EMPLEADA)
        self.assertEqual(progs["PROFESIONAL"].ingreso_modo, ms.APROBACION_DUENO)
        self.assertTrue(all(p.vigencia_dias is None for p in progs.values()), "sin vencimiento (P-E4-3)")


class EmpleadaTests(_Base):
    def test_inscribe_al_club_al_instante(self) -> None:
        m = ms.inscribir_por_empleada(self.s, cliente_id=self.cliente.id, programa_clave="club", employee_code=self.lupita.codigo.lower())
        self.assertEqual((m.estado, m.propuesta_por_employee_code), (ms.ACTIVA, self.lupita.codigo))
        self.assertIsNone(m.hasta)
        self.assertEqual(self._eventos(m), [ms.EV_ALTA])
        self.assertEqual(ms.estado_de_cliente(self.s, self.cliente.id).activa.id, m.id)

    def test_no_inscribe_directo_a_profesional_ni_dos_veces(self) -> None:
        with self.assertRaisesRegex(ms.NoSePuede, "aprueba el dueño"):
            ms.inscribir_por_empleada(self.s, cliente_id=self.cliente.id, programa_clave="PROFESIONAL", employee_code=self.lupita.codigo)
        ms.inscribir_por_empleada(self.s, cliente_id=self.cliente.id, programa_clave="CLUB", employee_code=self.lupita.codigo)
        with self.assertRaisesRegex(ms.NoSePuede, "Ya está en Maximoda Club"):
            ms.inscribir_por_empleada(self.s, cliente_id=self.cliente.id, programa_clave="CLUB", employee_code=self.lupita.codigo)

    def test_empleada_inactiva_o_desconocida(self) -> None:
        for codigo in (self.baja.codigo, "NOEXISTE", ""):
            with self.subTest(codigo=codigo), self.assertRaises(PermissionError):
                ms.inscribir_por_empleada(self.s, cliente_id=self.cliente.id, programa_clave="CLUB", employee_code=codigo)

    def test_ficha_inactiva_o_archivada_no_se_inscribe(self) -> None:
        adm.archivar(self.s, cliente_id=self.cliente.id, usuario_id=self.admin.id, motivo="Ficha de prueba")
        with self.assertRaisesRegex(ms.NoSePuede, "no está activa"):
            ms.inscribir_por_empleada(self.s, cliente_id=self.cliente.id, programa_clave="CLUB", employee_code=self.lupita.codigo)
        with self.assertRaisesRegex(ms.NoSePuede, "no está activa"):
            self._proponer()

    def test_propuesta_pide_motivo_y_es_una_sola(self) -> None:
        with self.assertRaisesRegex(ms.NoSePuede, "10 caracteres"):
            ms.proponer(self.s, cliente_id=self.cliente.id, programa_clave="PROFESIONAL", employee_code=self.lupita.codigo, motivo="maestra")
        with self.assertRaisesRegex(ms.NoSePuede, "inscríbelo directo"):
            ms.proponer(self.s, cliente_id=self.cliente.id, programa_clave="CLUB", employee_code=self.lupita.codigo, motivo="Cliente frecuente de la tienda")
        m = self._proponer()
        self.assertEqual((m.estado, m.motivo_propuesta), (ms.PENDIENTE, "Maestra de la Benito Juárez"))
        with self.assertRaisesRegex(ms.NoSePuede, "esperando respuesta"):
            self._proponer("MAYORISTA")

    def test_club_sigue_mientras_la_propuesta_espera(self) -> None:
        club = ms.inscribir_por_empleada(self.s, cliente_id=self.cliente.id, programa_clave="CLUB", employee_code=self.lupita.codigo)
        prop = self._proponer()
        estado = ms.estado_de_cliente(self.s, self.cliente.id)
        self.assertEqual((estado.activa.id, estado.pendiente.id), (club.id, prop.id))


class AprobacionTests(_Base):
    def test_dueno_aprueba_reemplaza_club_y_cambia_tipo(self) -> None:
        club = ms.inscribir_por_empleada(self.s, cliente_id=self.cliente.id, programa_clave="CLUB", employee_code=self.lupita.codigo)
        prop = self._proponer()
        ms.aprobar_por_dueno(self.s, prop.id)
        self.s.refresh(club)
        self.assertEqual((club.estado, prop.estado), (ms.REEMPLAZADA, ms.ACTIVA))
        self.assertEqual(prop.resuelta_por, ms.QUIEN_DUENO_TELEGRAM)
        self.assertEqual(self._eventos(club), [ms.EV_ALTA, ms.EV_REEMPLAZO])
        self.assertEqual(self._eventos(prop), [ms.EV_PROPUESTA, ms.EV_APROBACION])
        self.assertEqual(self._tipo(self.cliente), "DOCENTE")
        ev = self.s.scalars(select(ClienteEvento).where(ClienteEvento.cliente_id == self.cliente.id, ClienteEvento.tipo == "cambio_tipo")).one()
        self.assertEqual((ev.detalle["antes"], ev.detalle["despues"], ev.origen), ("GENERAL", "DOCENTE", ms.ORIGEN_TELEGRAM))

    def test_mayorista_respeta_institucion(self) -> None:
        inst = self._cliente("Colegio E4A", tipo="INSTITUCION")
        ms.aprobar_por_dueno(self.s, self._proponer("MAYORISTA", inst).id)
        self.assertEqual(self._tipo(inst), "INSTITUCION")
        gen = self._cliente("Tienda E4A")
        ms.aprobar_por_dueno(self.s, self._proponer("MAYORISTA", gen).id)
        self.assertEqual(self._tipo(gen), "MAYORISTA")

    def test_tocar_dos_veces_o_tarde_no_hace_nada(self) -> None:
        prop = self._proponer()
        ms.rechazar_por_dueno(self.s, prop.id, motivo="No es docente")
        self.assertEqual((prop.estado, prop.motivo_resolucion), (ms.RECHAZADA, "No es docente"))
        for accion in (ms.aprobar_por_dueno, ms.rechazar_por_dueno):
            with self.subTest(accion=accion.__name__), self.assertRaisesRegex(ms.NoSePuede, "quedó rechazada"):
                accion(self.s, prop.id)
        self.assertEqual(self._eventos(prop), [ms.EV_PROPUESTA, ms.EV_RECHAZO])
        self.assertEqual(self._tipo(self.cliente), "GENERAL")
        with self.assertRaisesRegex(ms.NoSePuede, "No encontré"):
            ms.aprobar_por_dueno(self.s, 999_999_999)

    def test_no_aprueba_si_la_ficha_se_archivo_mientras_esperaba(self) -> None:
        prop = self._proponer()
        adm.archivar(self.s, cliente_id=self.cliente.id, usuario_id=self.admin.id, motivo="Ficha de prueba")
        with self.assertRaisesRegex(ms.NoSePuede, "ya no está activa"):
            ms.aprobar_por_dueno(self.s, prop.id)

    def test_admin_aprueba_y_rechaza_desde_el_pos(self) -> None:
        prop = self._proponer()
        with self.assertRaises(PermissionError):
            ms.aprobar_por_admin(self.s, prop.id, usuario_id=self.cajero.id)
        with self.assertRaisesRegex(ms.NoSePuede, "5 caracteres"):
            ms.rechazar_por_admin(self.s, prop.id, usuario_id=self.admin.id, motivo="no")
        ms.aprobar_por_admin(self.s, prop.id, usuario_id=self.admin.id)
        self.assertEqual(prop.resuelta_por, self.admin.username)


class AdminTests(_Base):
    def test_cambiar_y_sacar_de_programa(self) -> None:
        club = ms.inscribir_por_empleada(self.s, cliente_id=self.cliente.id, programa_clave="CLUB", employee_code=self.lupita.codigo)
        may = ms.inscribir_por_admin(self.s, cliente_id=self.cliente.id, programa_clave="MAYORISTA", usuario_id=self.admin.id, motivo="Compra para tres escuelas")
        self.s.refresh(club)
        self.assertEqual((club.estado, may.estado), (ms.REEMPLAZADA, ms.ACTIVA))
        self.assertEqual(self._eventos(may), [ms.EV_CAMBIO_PROGRAMA, ms.EV_APROBACION])
        with self.assertRaisesRegex(ms.NoSePuede, "Ya está en"):
            ms.inscribir_por_admin(self.s, cliente_id=self.cliente.id, programa_clave="MAYORISTA", usuario_id=self.admin.id, motivo="otra vez")
        ms.sacar_del_programa(self.s, cliente_id=self.cliente.id, usuario_id=self.admin.id, motivo="Ya no compra al mayoreo")
        self.assertEqual(may.estado, ms.CANCELADA)
        self.assertIsNone(ms.estado_de_cliente(self.s, self.cliente.id).activa)
        with self.assertRaisesRegex(ms.NoSePuede, "ningún programa"):
            ms.sacar_del_programa(self.s, cliente_id=self.cliente.id, usuario_id=self.admin.id, motivo="Otra vez más")

    def test_admin_no_pisa_una_propuesta_pendiente(self) -> None:
        self._proponer()
        with self.assertRaisesRegex(ms.NoSePuede, "propuesta pendiente"):
            ms.inscribir_por_admin(self.s, cliente_id=self.cliente.id, programa_clave="CLUB", usuario_id=self.admin.id, motivo="Cliente de años")

    def test_solo_admin(self) -> None:
        for usuario in (self.cajero.id, None):
            with self.subTest(usuario=usuario), self.assertRaises(PermissionError):
                ms.inscribir_por_admin(self.s, cliente_id=self.cliente.id, programa_clave="CLUB", usuario_id=usuario, motivo="Cliente de años")


class CandadosYExpiracionTests(_Base):
    def test_la_base_impide_dos_activas_o_dos_pendientes(self) -> None:
        club = self.s.scalar(select(ms.Programa).where(ms.Programa.clave == "CLUB"))
        for estado in (ms.ACTIVA, ms.PENDIENTE):
            with self.subTest(estado=estado):
                otro = self._cliente(f"Candado {estado}")
                self.s.add(Membresia(cliente_id=otro.id, programa_id=club.id, estado=estado))
                self.s.flush()
                punto = self.s.begin_nested()
                with self.assertRaises(IntegrityError):
                    self.s.add(Membresia(cliente_id=otro.id, programa_id=club.id, estado=estado))
                    self.s.flush()
                punto.rollback()

    def test_choque_simultaneo_da_mensaje_claro(self) -> None:
        club = self.s.scalar(select(ms.Programa).where(ms.Programa.clave == "CLUB"))
        # Otra caja ya lo inscribió, pero esta no lo vio en su consulta previa.
        self.s.add(Membresia(cliente_id=self.cliente.id, programa_id=club.id, estado=ms.ACTIVA))
        self.s.flush()
        original = ms.estado_de_cliente
        ms.estado_de_cliente = lambda s, cid: ms.EstadoCliente(activa=None, pendiente=None)
        try:
            with self.assertRaisesRegex(ms.NoSePuede, "ya tiene un programa"):
                ms.inscribir_por_empleada(self.s, cliente_id=self.cliente.id, programa_clave="CLUB", employee_code=self.lupita.codigo)
        finally:
            ms.estado_de_cliente = original

    def test_propuestas_expiran_a_los_7_dias(self) -> None:
        prop = self._proponer()
        ahora = datetime.now(timezone.utc)
        self.assertEqual(ms.expirar_pendientes(self.s, ahora=ahora + timedelta(days=6)), [])
        vencidas = ms.expirar_pendientes(self.s, ahora=ahora + timedelta(days=8))
        self.assertIn(prop.id, [m.id for m in vencidas])
        self.assertEqual(prop.estado, ms.EXPIRADA)
        self.assertEqual(self._eventos(prop)[-1], ms.EV_EXPIRACION)
        self.assertIsNone(ms.estado_de_cliente(self.s, self.cliente.id).pendiente)

    def test_membresias_no_tocan_ventas_ni_libreta_ni_ficha(self) -> None:
        cid = self.cliente.id  # solo las de este cliente: en paralelo otras pruebas escriben en la base
        conteos = lambda: (
            self.s.scalar(select(func.count(Venta.id)).where(Venta.cliente_id == cid)),
            self.s.scalar(select(func.count(LibretaVenta.id)).where(LibretaVenta.cliente_id == cid)),
        )
        antes = conteos()
        self.s.refresh(self.cliente)
        ficha = (self.cliente.nivel_lealtad, self.cliente.descuento_preferente, self.cliente.tipo_cliente)
        ms.inscribir_por_empleada(self.s, cliente_id=self.cliente.id, programa_clave="CLUB", employee_code=self.lupita.codigo)
        ms.aprobar_por_dueno(self.s, self._proponer().id)
        self.s.refresh(self.cliente)
        self.assertEqual(conteos(), antes)
        self.assertEqual((self.cliente.nivel_lealtad, self.cliente.descuento_preferente, self.cliente.tipo_cliente), ficha)


if __name__ == "__main__":
    unittest.main()
