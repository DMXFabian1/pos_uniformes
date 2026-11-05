"""Cambiar el descanso fijo pregunta «¿desde cuándo?» (2026-11-05).

Stayce pidió pasar su descanso del sábado al lunes. Sin la pregunta, el cambio
repintaba toda su historia: los sábados que sí descansó se volvían trabajados."""
from __future__ import annotations

from datetime import date

import pytest
from PyQt6.QtWidgets import QApplication, QDialog

from pos_uniformes.ui.dialogs import calendario_empleadas_dialog as mod


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_la_frase_dice_que_pasa_antes_y_despues():
    texto = mod.texto_del_cambio(5, 0, date(2026, 11, 9))
    antes, despues = texto.split("\n")
    assert "domingo 8" in antes and "sábado" in antes
    assert "lunes 9" in despues and "descansa en lunes" in despues


def test_propone_el_lunes_de_la_semana_que_viene():
    assert mod.lunes_siguiente(date(2026, 11, 5)) == date(2026, 11, 9)
    assert mod.lunes_siguiente(date(2026, 11, 9)) == date(2026, 11, 16)


def _responder(monkeypatch, accion):
    """`exec` no abre nada: deja que la prueba toque el diálogo y responde."""
    def exec_falso(dlg):
        return accion(dlg)
    monkeypatch.setattr(QDialog, "exec", exec_falso)


def test_aceptar_devuelve_el_dia_propuesto(app, monkeypatch):
    _responder(monkeypatch, lambda dlg: QDialog.DialogCode.Accepted)
    r = mod.preguntar_desde_cuando(None, nombre="Stayce", viejo=5, nuevo=0, hoy=date(2026, 11, 5))
    assert r == date(2026, 11, 9)


def test_error_de_captura_cambia_toda_la_historia(app, monkeypatch):
    def accion(dlg):
        dlg.error_de_captura.setChecked(True)
        assert "toda su historia" in dlg.resumen.text()
        assert not dlg.calendario.isEnabled()
        return QDialog.DialogCode.Accepted
    _responder(monkeypatch, accion)
    assert mod.preguntar_desde_cuando(None, nombre="Stayce", viejo=5, nuevo=0, hoy=date(2026, 11, 5)) == mod.SIEMPRE


def test_cancelar_no_cambia_nada(app, monkeypatch):
    _responder(monkeypatch, lambda dlg: QDialog.DialogCode.Rejected)
    llamadas = []
    monkeypatch.setattr(mod, "guardar_horario", lambda *a, **k: llamadas.append(k))
    ok = mod.guardar_cambio_de_descanso(
        None, lambda: pytest.fail("no debe abrir sesión"),
        code="VEND-9", nombre="Stayce", viejo=5, nuevo=0, minimo=None, creado_por="VEND-1",
    )
    assert ok is False and llamadas == []


class _Sesion:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_guarda_con_la_fecha_elegida(app, monkeypatch):
    _responder(monkeypatch, lambda dlg: QDialog.DialogCode.Accepted)
    llamadas = []
    monkeypatch.setattr(mod, "guardar_horario", lambda s, code, **k: llamadas.append((code, k)))
    monkeypatch.setattr(mod, "lunes_siguiente", lambda hoy: date(2026, 11, 9))
    assert mod.guardar_cambio_de_descanso(
        None, _Sesion, code="VEND-9", nombre="Stayce", viejo=5, nuevo=0, minimo=None,
        creado_por="VEND-1", ciclo_dias_pago=7,
    )
    code, k = llamadas[0]
    assert code == "VEND-9"
    assert k["descanso_weekday"] == 0 and k["descanso_desde"] == date(2026, 11, 9)
    assert k["creado_por"] == "VEND-1" and k["ciclo_dias_pago"] == 7


def test_sin_cambio_de_dia_no_pregunta(app, monkeypatch):
    monkeypatch.setattr(mod, "preguntar_desde_cuando", lambda *a, **k: pytest.fail("no debe preguntar"))
    llamadas = []
    monkeypatch.setattr(mod, "guardar_horario", lambda s, code, **k: llamadas.append(k))
    assert mod.guardar_cambio_de_descanso(
        None, _Sesion, code="VEND-9", nombre="Stayce", viejo=5, nuevo=5, minimo=None, creado_por="VEND-1",
    )
    # Y la primera vez que se le pone descanso tampoco: no hay historia que cuidar.
    assert mod.guardar_cambio_de_descanso(
        None, _Sesion, code="VEND-9", nombre="Stayce", viejo=None, nuevo=5, minimo=None, creado_por="VEND-1",
    )
    assert [k["descanso_desde"] for k in llamadas] == [None, None]
