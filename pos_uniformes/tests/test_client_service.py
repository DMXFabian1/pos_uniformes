"""ClientService sobre el tipo que manda (`ClienteTipo` por `tipo_cliente_id`).

2026-11-12 (Daniel: «la caja antigua ya no es de utilidad, todo lo demás
corre en libreta y kioskos»; auditoría del legado, «Pantallas con datos
viejos»): editar a un cliente solo escribía el enum viejo (`tipo_cliente`) y
su tipo real no cambiaba; buscar «docente» o «institución» no encontraba a
nadie. Base local de prueba, transacción revertida.
"""

from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select

from pos_uniformes.database.models import ClienteEvento, ClienteTipo, RolUsuario, TipoCliente
from pos_uniformes.services.client_service import ClientService
from pos_uniformes.services.clientes import identidad_service as ids
from pos_uniformes.tests.test_e1b_identidad_service import _EnTransaccion

ADMIN = SimpleNamespace(id=None, rol=RolUsuario.ADMIN, activo=True)


class _Base(_EnTransaccion):
    def _alta(self, sufijo: str, clave: str = "GENERAL"):
        return ids.dar_de_alta(self.s, nombre=f"Cli {clave} {self.marca}", telefono=self._tel(sufijo),
                               origen=ids.ORIGEN_VENTA_RAPIDA, tipo_clave=clave)

    def _clave(self, c) -> str:
        self.s.flush()
        self.s.refresh(c)
        return self.s.get(ClienteTipo, c.tipo_cliente_id).clave

    def _cambios(self, c) -> list[dict]:
        return [e.detalle for e in self.s.scalars(
            select(ClienteEvento).where(ClienteEvento.cliente_id == c.id, ClienteEvento.tipo == ids.EVENTO_CAMBIO_TIPO)
            .order_by(ClienteEvento.id))]

    def _editar(self, c, **kw):
        return ClientService.update_client(self.s, ADMIN, c, c.nombre, telefono=c.telefono or "", notas="", **kw)


class EditarTipoTests(_Base):
    def test_el_enum_viejo_ya_cambia_el_tipo_real(self) -> None:
        c = self._alta("21")
        self._editar(c, tipo_cliente=TipoCliente.MAYORISTA)
        self.assertEqual(self._clave(c), "MAYORISTA")
        self.assertEqual(c.tipo_cliente, TipoCliente.MAYORISTA)
        self.assertEqual(self._cambios(c), [{"antes": "GENERAL", "despues": "MAYORISTA"}])

    def test_profesor_es_docente(self) -> None:
        c = self._alta("22")
        self._editar(c, tipo_cliente=TipoCliente.PROFESOR)
        self.assertEqual(self._clave(c), "DOCENTE")

    def test_con_clave_del_catalogo_y_enum_sincronizado(self) -> None:
        c = self._alta("23")
        self._editar(c, tipo_clave="institucion")
        self.assertEqual(self._clave(c), "INSTITUCION")
        self.assertEqual(c.tipo_cliente, TipoCliente.MAYORISTA)

    def test_mismo_tipo_no_deja_evento(self) -> None:
        c = self._alta("24", "DOCENTE")
        self._editar(c, tipo_cliente=TipoCliente.PROFESOR)
        self.assertEqual(self._cambios(c), [])

    def test_mayorista_del_enum_respeta_institucion(self) -> None:
        """El enum viejo no tiene Institución: la misma regla que al aprobar
        Maximoda Mayorista (Institución se queda Institución)."""
        c = self._alta("25", "INSTITUCION")
        self._editar(c, tipo_cliente=TipoCliente.MAYORISTA)
        self.assertEqual(self._clave(c), "INSTITUCION")
        self._editar(c, tipo_clave="MAYORISTA")  # elegido a propósito en el catálogo
        self.assertEqual(self._clave(c), "MAYORISTA")

    def test_cambiar_tipo_no_da_nivel_ni_descuento(self) -> None:
        c = self._alta("26")
        self._editar(c, tipo_clave="MAYORISTA")
        self._assert_sin_nivel(c, ids.ORIGEN_VENTA_RAPIDA)

    def test_tipo_inexistente_falla(self) -> None:
        c = self._alta("27")
        with self.assertRaises(ValueError):
            self._editar(c, tipo_clave="PROFESOR")

    def test_alta_con_clave_del_catalogo(self) -> None:
        c = ClientService.create_client(self.s, ADMIN, f"Alta {self.marca}", telefono=self._tel("28"),
                                        tipo_clave="DOCENTE")
        self.assertEqual(self._clave(c), "DOCENTE")
        self.assertEqual(c.tipo_cliente, TipoCliente.PROFESOR)


class BuscarPorTipoTests(_Base):
    def test_encuentra_docente_e_institucion(self) -> None:
        docente = self._alta("31", "DOCENTE")
        inst = self._alta("32", "INSTITUCION")
        general = self._alta("33")
        for texto, esperado in (("docente", docente), ("Institución", inst), ("institucion", inst)):
            with self.subTest(texto=texto):
                encontrados = {c.id for c in ClientService.list_clients(self.s, texto)}
                self.assertIn(esperado.id, encontrados)
                self.assertNotIn(general.id, encontrados)

    def test_sigue_buscando_por_nombre(self) -> None:
        c = self._alta("34")
        self.assertIn(c.id, {x.id for x in ClientService.list_clients(self.s, self.marca)})
