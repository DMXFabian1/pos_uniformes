"""Un respaldo cortado a la mitad no se hace pasar por respaldo (R1, 2026-11-09).

pg_dump escribía directo a `pos_uniformes_<fecha>.dump`. Si se cortaba a la
mitad (apagón, red, disco lleno) quedaba un `.dump` trunco de más de 50 KB y
`leer_estado` lo tomaba como «el respaldo de hoy»: callaba el aviso de 36 h y
el botón del bot contestaba ✅. La PC servidor tuvo 5 apagones bruscos en 10
días.

Ahora pg_dump escribe a un `.parcial`; solo si termina bien y el archivo se lee
completo se publica con su nombre final, sin pisar ningún otro respaldo.
Aquí no corre ningún pg_dump real: se simula lo que deja en disco.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading
import time
import unittest
from datetime import datetime as _dt
from pathlib import Path
from unittest.mock import patch

from pos_uniformes.services import backup_service as bs
from pos_uniformes.services import respaldo_estado_service as est

#: Más que el mínimo creíble (50 KB): el caso que antes se colaba.
GRANDE = b"PGDMP" + b"x" * (200 * 1024)
#: Lo que nuestro pg_restore falso reconoce como archivo completo.
MARCA_COMPLETO = b"<<FIN-COMPLETO>>"

#: Un .sql como los que escribe pg_dump 18.3 (cabeza y cierre reales).
CLAVE = b"Ab12Cd34Ef56"
SQL_CABEZA = b"--\n-- PostgreSQL database dump\n--\n\n\\restrict " + CLAVE + b"\n\n-- Dumped by pg_dump version 18.3\n\n"
SQL_CUERPO = b"COPY public.nota (id, texto) FROM stdin;\n1\thola\n\\.\n\n" + b"-- relleno\n" * 6000
SQL_CIERRE = b"\n\n--\n-- PostgreSQL database dump complete\n--\n\n\\unrestrict " + CLAVE + b"\n\n"
SQL_BUENO = SQL_CABEZA + SQL_CUERPO + SQL_CIERRE


def _archivo_de(cmd) -> Path:
    return Path(cmd[cmd.index("--file") + 1])


class _PgFalso:
    """Reemplaza `subprocess.run` dentro de backup_service.

    `contenido`/`codigo`/`excepcion` deciden qué deja pg_dump en disco y cómo
    termina; `pg_restore` contesta 0 solo si el archivo trae la marca de
    completo. `antes_de_salir` corre dentro de pg_dump (para sincronizar hilos)."""

    def __init__(self, *, contenido: bytes = GRANDE + MARCA_COMPLETO, codigo: int = 0,
                 excepcion: BaseException | None = None, antes_de_salir=None) -> None:
        self.contenido, self.codigo, self.excepcion = contenido, codigo, excepcion
        self.antes_de_salir = antes_de_salir
        self.llamadas: list[list[str]] = []

    def __call__(self, cmd, *args, **kwargs):
        cmd = list(cmd)
        self.llamadas.append(cmd)
        if cmd[0] == "pg_dump":
            _archivo_de(cmd).write_bytes(self.contenido)
            if self.antes_de_salir is not None:
                self.antes_de_salir()
            if self.excepcion is not None:
                raise self.excepcion
            if self.codigo != 0:
                raise subprocess.CalledProcessError(self.codigo, cmd)
            return subprocess.CompletedProcess(cmd, 0)
        if cmd[0] == "pg_restore":
            ok = Path(cmd[-1]).read_bytes().endswith(MARCA_COMPLETO)
            return subprocess.CompletedProcess(
                cmd, 0 if ok else 1, stdout="",
                stderr="" if ok else "pg_restore: error: could not read from input file: end of file",
            )
        raise AssertionError(f"comando inesperado: {cmd}")


class _RelojFijo(_dt):
    """`datetime` con `now()` congelado: dos respaldos «en el mismo segundo»."""

    @classmethod
    def now(cls, tz=None):  # noqa: D102
        return cls(2026, 11, 9, 13, 0, 0, tzinfo=tz)


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name).resolve()
        self.addCleanup(self._tmp.cleanup)
        # Un respaldo bueno de ayer y uno viejo que la rotación borraría.
        self.bueno = self.dir / "pos_uniformes_20261108_102041.dump"
        self.bueno.write_bytes(GRANDE + MARCA_COMPLETO)
        ayer = time.time() - 26 * 3600
        os.utime(self.bueno, (ayer, ayer))
        self.viejo = self.dir / "pos_uniformes_20261001_102041.dump"
        self.viejo.write_bytes(GRANDE + MARCA_COMPLETO)
        hace_un_mes = time.time() - 30 * 86400
        os.utime(self.viejo, (hace_un_mes, hace_un_mes))
        p = patch.object(bs, "_resolve_postgres_binary", side_effect=lambda nombre, *a: nombre)
        p.start()
        self.addCleanup(p.stop)

    def _correr(self, pg: _PgFalso, dump_format: str = "custom"):
        with patch.object(bs.subprocess, "run", pg):
            return bs.create_backup(output_dir=self.dir, dump_format=dump_format, retention_days=14)

    def _dumps(self) -> set[str]:
        return {p.name for p in self.dir.glob("*.dump")}

    def _parciales(self) -> list[Path]:
        return list(self.dir.glob(f"*{bs.PARCIAL_SUFFIX}"))

    def _sin_rastro_del_intento(self) -> None:
        self.assertEqual(self._dumps(), {self.bueno.name, self.viejo.name})
        self.assertEqual(self._parciales(), [])
        self.assertEqual(self.bueno.read_bytes(), GRANDE + MARCA_COMPLETO)

    def _parcial(self, nombre: str, *, horas: float) -> Path:
        p = self.dir / nombre
        p.write_bytes(GRANDE)
        t = time.time() - horas * 3600
        os.utime(p, (t, t))
        return p


# ── R1: lo básico ────────────────────────────────────────────────────────────


class RespaldoCompletoTests(_Base):
    def test_sale_bien_queda_el_dump_final_y_ninguno_parcial(self) -> None:
        pg = _PgFalso()
        archivo, borrados = self._correr(pg)
        self.assertTrue(archivo.exists())
        self.assertEqual(archivo.suffix, ".dump")
        self.assertEqual(archivo.read_bytes(), GRANDE + MARCA_COMPLETO)
        self.assertEqual(self._parciales(), [])
        # pg_dump escribió a un temporal `<final>.<pid>.<al azar>.parcial`.
        temporal = _archivo_de(pg.llamadas[0])
        self.assertTrue(temporal.name.startswith(archivo.name + f".{os.getpid()}."))
        self.assertRegex(temporal.name, bs._PARCIAL_RE)
        # Se verificó leyendo todo, sin tocar ninguna base.
        restore = pg.llamadas[1]
        self.assertEqual(restore[0], "pg_restore")
        self.assertIn(os.devnull, restore)
        self.assertNotIn("--dbname", restore)
        # Y solo entonces rota.
        self.assertEqual(borrados, [self.viejo])

    def test_texto_completo_pasa(self) -> None:
        archivo, _ = self._correr(_PgFalso(contenido=SQL_BUENO), dump_format="plain")
        self.assertEqual(archivo.suffix, ".sql")
        self.assertEqual(archivo.read_bytes(), SQL_BUENO)


class RespaldoCortadoTests(_Base):
    def test_pg_dump_truena_a_la_mitad(self) -> None:
        with self.assertRaises(subprocess.CalledProcessError):
            self._correr(_PgFalso(contenido=GRANDE, codigo=1))
        self._sin_rastro_del_intento()
        self.assertTrue(self.viejo.exists())  # sin respaldo nuevo no se rota

    def test_pg_dump_dice_que_bien_pero_el_archivo_esta_trunco(self) -> None:
        # El caso de R1: más de 50 KB, código 0, y no se puede leer completo.
        with self.assertRaises(bs.BackupIncompletoError) as ctx:
            self._correr(_PgFalso(contenido=GRANDE, codigo=0))
        self.assertIn("incompleto", str(ctx.exception))
        self._sin_rastro_del_intento()
        self.assertTrue(self.viejo.exists())

    def test_interrupcion_del_proceso(self) -> None:
        with self.assertRaises(KeyboardInterrupt):
            self._correr(_PgFalso(contenido=GRANDE, excepcion=KeyboardInterrupt()))
        self._sin_rastro_del_intento()

    def test_archivo_vacio_no_es_respaldo(self) -> None:
        with self.assertRaises(bs.BackupIncompletoError):
            self._correr(_PgFalso(contenido=b"", codigo=0))
        self._sin_rastro_del_intento()

    def test_texto_cortado_no_se_publica(self) -> None:
        with self.assertRaises(bs.BackupIncompletoError):
            self._correr(_PgFalso(contenido=SQL_CABEZA + SQL_CUERPO), dump_format="plain")
        self.assertEqual(list(self.dir.glob("*.sql")), [])
        self.assertEqual(self._parciales(), [])

    def test_si_falla_la_publicacion_no_queda_nada_a_medias(self) -> None:
        with patch.object(bs, "_enlazar_sin_pisar", side_effect=PermissionError("archivo en uso")):
            with self.assertRaises(PermissionError):
                self._correr(_PgFalso())
        self._sin_rastro_del_intento()

    def test_si_falla_fsync_no_se_publica(self) -> None:
        with patch.object(bs.os, "fsync", side_effect=OSError(28, "No space left on device")):
            with self.assertRaises(OSError):
                self._correr(_PgFalso())
        self._sin_rastro_del_intento()


class EstadoTrasUnFalloTests(_Base):
    def test_el_estado_guarda_el_error_y_conserva_el_ultimo_bueno(self) -> None:
        with patch.object(bs.subprocess, "run", _PgFalso()):
            bueno_hoy, _, _ = bs.run_automatic_backup(output_dir=self.dir, dump_format="custom", retention_days=14)
        antes = bs.read_automatic_backup_status(self.dir)
        assert antes is not None

        with patch.object(bs.subprocess, "run", _PgFalso(contenido=GRANDE, codigo=0)):
            with self.assertRaises(bs.BackupIncompletoError):
                bs.run_automatic_backup(output_dir=self.dir, dump_format="custom", retention_days=14)

        despues = bs.read_automatic_backup_status(self.dir)
        assert despues is not None
        self.assertIn("incompleto", despues.last_error or "")
        self.assertEqual(despues.last_success_at, antes.last_success_at)
        self.assertEqual(despues.last_backup_path, bueno_hoy)
        self.assertTrue(bueno_hoy.exists())

    def test_leer_estado_sigue_viendo_el_ultimo_bueno(self) -> None:
        antes = est.leer_estado(self.dir)
        with self.assertRaises(bs.BackupIncompletoError):
            self._correr(_PgFalso(contenido=GRANDE, codigo=0))
        despues = est.leer_estado(self.dir)
        self.assertEqual(despues.archivo, self.bueno)
        self.assertEqual(despues.ultimo, antes.ultimo)
        # Lo que mira el botón del bot: no hay uno NUEVO, no puede decir ✅.
        self.assertFalse(despues.ultimo > antes.ultimo)

    def test_respaldo_diario_sale_con_error_y_no_aparece_respaldo_nuevo(self) -> None:
        from pos_uniformes.scripts import respaldo_diario

        antes = est.leer_estado(self.dir)
        with patch.object(bs.subprocess, "run", _PgFalso(contenido=GRANDE, codigo=0)):
            codigo = respaldo_diario.main(["--carpeta", str(self.dir), "--sin-avisar", "--callado"])
        self.assertEqual(codigo, 1)
        self.assertEqual(est.leer_estado(self.dir).ultimo, antes.ultimo)
        self._sin_rastro_del_intento()


# ── A1: limpieza de huérfanos ───────────────────────────────────────────────


class ParcialesHuerfanosTests(_Base):
    VIEJO = f"pos_uniformes_20261108_130000.dump.4242.a1b2c3d4{bs.PARCIAL_SUFFIX}"

    def test_nadie_lista_un_parcial_como_respaldo(self) -> None:
        self._parcial(f"pos_uniformes_20261109_130000.dump.123.abcd{bs.PARCIAL_SUFFIX}", horas=0)
        nombres = {e.path.name for e in bs.list_backups(self.dir)}
        self.assertEqual(nombres, {self.bueno.name, self.viejo.name})
        self.assertEqual(est.leer_estado(self.dir).archivo, self.bueno)
        # Ni la rotación lo ve como .dump.
        self.assertEqual(bs.prune_old_backups(self.dir, "custom", 3650), [])

    def test_viejo_y_su_proceso_ya_no_existe_se_borra(self) -> None:
        p = self._parcial(self.VIEJO, horas=7)
        with patch.object(bs, "_proceso_existe", return_value=False) as consulta:
            self.assertEqual(bs.limpiar_parciales_huerfanos(self.dir), [p])
        consulta.assert_called_once_with(4242)
        self.assertFalse(p.exists())

    def test_viejo_pero_su_proceso_sigue_vivo_se_queda(self) -> None:
        # pg_dump esperando un bloqueo: lleva horas sin escribir pero vive.
        p = self._parcial(self.VIEJO, horas=30)
        with patch.object(bs, "_proceso_existe", return_value=True):
            self.assertEqual(bs.limpiar_parciales_huerfanos(self.dir), [])
        self.assertTrue(p.exists())

    def test_si_no_se_puede_saber_se_queda(self) -> None:
        p = self._parcial(self.VIEJO, horas=30)
        with patch.object(bs, "_proceso_existe", return_value=None):
            self.assertEqual(bs.limpiar_parciales_huerfanos(self.dir), [])
        self.assertTrue(p.exists())

    def test_reciente_no_se_consulta_ni_se_borra(self) -> None:
        p = self._parcial(self.VIEJO, horas=1)
        with patch.object(bs, "_proceso_existe", return_value=False) as consulta:
            self.assertEqual(bs.limpiar_parciales_huerfanos(self.dir), [])
        consulta.assert_not_called()
        self.assertTrue(p.exists())

    def test_sin_pid_en_el_nombre_se_queda(self) -> None:
        # El formato de la primera versión de R1 (sin la parte al azar), o
        # cualquier cosa que no sepamos leer: no se adivina.
        p = self._parcial(f"pos_uniformes_20261108_130000.dump.4242{bs.PARCIAL_SUFFIX}", horas=30)
        with patch.object(bs, "_proceso_existe", return_value=False):
            self.assertEqual(bs.limpiar_parciales_huerfanos(self.dir), [])
        self.assertTrue(p.exists())

    def test_nunca_toca_dump_ni_sql(self) -> None:
        sql = self.dir / "pos_uniformes_20261001_101010.sql"
        sql.write_bytes(SQL_BUENO)
        hace_un_mes = time.time() - 30 * 86400
        os.utime(sql, (hace_un_mes, hace_un_mes))
        with patch.object(bs, "_proceso_existe", return_value=False):
            bs.limpiar_parciales_huerfanos(self.dir)
        self.assertTrue(self.bueno.exists())
        self.assertTrue(self.viejo.exists())
        self.assertTrue(sql.exists())

    def test_si_windows_no_deja_borrarlo_se_queda_para_la_proxima(self) -> None:
        p = self._parcial(self.VIEJO, horas=30)
        with patch.object(bs, "_proceso_existe", return_value=False), \
             patch.object(Path, "unlink", side_effect=PermissionError("en uso")):
            self.assertEqual(bs.limpiar_parciales_huerfanos(self.dir), [])
        self.assertTrue(p.exists())


class ProcesoExisteTests(unittest.TestCase):
    def test_el_propio_proceso_existe(self) -> None:
        self.assertIs(bs._proceso_existe(os.getpid()), True)

    def test_pid_invalido_no_se_sabe(self) -> None:
        self.assertIsNone(bs._proceso_existe(0))
        self.assertIsNone(bs._proceso_existe(-5))

    @unittest.skipIf(os.name == "nt", "rama POSIX")
    def test_un_proceso_que_ya_termino_no_existe(self) -> None:
        hijo = subprocess.Popen(["true"])
        hijo.wait()
        self.assertIs(bs._proceso_existe(hijo.pid), False)

    @unittest.skipIf(os.name == "nt", "rama POSIX")
    def test_un_proceso_vivo_existe(self) -> None:
        hijo = subprocess.Popen(["sleep", "5"])
        self.addCleanup(hijo.wait)
        self.addCleanup(hijo.kill)
        self.assertIs(bs._proceso_existe(hijo.pid), True)

    @unittest.skipIf(os.name == "nt", "rama POSIX")
    def test_de_otro_usuario_cuenta_como_vivo(self) -> None:
        with patch.object(bs.os, "kill", side_effect=PermissionError()):
            self.assertIs(bs._proceso_existe(999_999), True)

    @unittest.skipIf(os.name == "nt", "rama POSIX")
    def test_error_raro_al_consultar_no_se_sabe(self) -> None:
        with patch.object(bs.os, "kill", side_effect=OSError(22, "Invalid argument")):
            self.assertIsNone(bs._proceso_existe(999_999))

    def test_en_windows_un_fallo_de_ctypes_no_se_sabe(self) -> None:
        # Fuera de Windows no hay kernel32: la función debe contestar None,
        # nunca «no existe».
        if os.name == "nt":
            self.skipTest("en Windows la rama real se prueba en la PC")
        self.assertIsNone(bs._proceso_existe_windows(4242))


# ── A2: publicar sin pisar ──────────────────────────────────────────────────


class PublicarSinPisarTests(_Base):
    def _dump_de(self, nombre: str) -> Path:
        return self.dir / nombre

    def test_nombre_ocupado_usa_sufijo_y_no_pisa(self) -> None:
        ocupado = self._dump_de("pos_uniformes_test_20261109_130000.dump")
        ocupado.write_bytes(b"EL-QUE-YA-ESTABA" + MARCA_COMPLETO)
        with patch.object(bs, "datetime", _RelojFijo), patch.object(bs.settings, "db_name", "pos_uniformes_test"):
            archivo, _ = self._correr(_PgFalso())
        self.assertEqual(archivo.name, "pos_uniformes_test_20261109_130000_2.dump")
        self.assertEqual(ocupado.read_bytes(), b"EL-QUE-YA-ESTABA" + MARCA_COMPLETO)
        self.assertEqual(archivo.read_bytes(), GRANDE + MARCA_COMPLETO)

    def test_sigue_con_3_si_tambien_esta_el_2(self) -> None:
        for nombre in ("pos_uniformes_test_20261109_130000.dump", "pos_uniformes_test_20261109_130000_2.dump"):
            self._dump_de(nombre).write_bytes(nombre.encode() + MARCA_COMPLETO)
        with patch.object(bs, "datetime", _RelojFijo), patch.object(bs.settings, "db_name", "pos_uniformes_test"):
            archivo, _ = self._correr(_PgFalso())
        self.assertEqual(archivo.name, "pos_uniformes_test_20261109_130000_3.dump")
        for nombre in ("pos_uniformes_test_20261109_130000.dump", "pos_uniformes_test_20261109_130000_2.dump"):
            self.assertEqual(self._dump_de(nombre).read_bytes(), nombre.encode() + MARCA_COMPLETO)

    def test_dos_respaldos_a_la_vez_en_el_mismo_segundo(self) -> None:
        # Dos hilos, mismo segundo, mismo nombre final: los dos pg_dump
        # terminan juntos (barrera) y publican casi al mismo tiempo.
        barrera = threading.Barrier(2, timeout=5)
        contenidos = {"A": b"A" * 70_000 + MARCA_COMPLETO, "B": b"B" * 70_000 + MARCA_COMPLETO}
        resultados: dict[str, Path] = {}
        errores: list[BaseException] = []
        locales = threading.local()

        def correr_pg(cmd, *a, **k):
            return locales.pg(cmd, *a, **k)

        def uno(etiqueta: str) -> None:
            locales.pg = _PgFalso(contenido=contenidos[etiqueta], antes_de_salir=barrera.wait)
            try:
                resultados[etiqueta], _ = bs.create_backup(output_dir=self.dir, dump_format="custom", retention_days=3650)
            except BaseException as exc:  # noqa: BLE001
                errores.append(exc)

        with patch.object(bs, "datetime", _RelojFijo), patch.object(bs.settings, "db_name", "pos_uniformes_test"), \
             patch.object(bs.subprocess, "run", correr_pg):
            hilos = [threading.Thread(target=uno, args=(e,)) for e in "AB"]
            for h in hilos:
                h.start()
            for h in hilos:
                h.join(10)

        self.assertEqual(errores, [])
        self.assertEqual(
            {p.name for p in resultados.values()},
            {"pos_uniformes_test_20261109_130000.dump", "pos_uniformes_test_20261109_130000_2.dump"},
        )
        for etiqueta, archivo in resultados.items():
            self.assertEqual(archivo.read_bytes(), contenidos[etiqueta])   # nadie pisó a nadie
        self.assertEqual(self._parciales(), [])

    def test_nunca_usa_os_replace(self) -> None:
        with patch.object(bs.os, "replace", side_effect=AssertionError("os.replace pisa")):
            archivo, _ = self._correr(_PgFalso())
        self.assertTrue(archivo.exists())

    def test_si_todos_los_nombres_estan_ocupados_falla_sin_pisar(self) -> None:
        with patch.object(bs, "_enlazar_sin_pisar", side_effect=FileExistsError("ocupado")):
            with self.assertRaises(FileExistsError):
                self._correr(_PgFalso())
        self._sin_rastro_del_intento()

    def test_enlazar_real_falla_si_el_destino_existe(self) -> None:
        origen = self.dir / "x.dump.1.ab.parcial"
        origen.write_bytes(b"nuevo")
        destino = self.dir / "ocupado.dump"
        destino.write_bytes(b"viejo")
        with self.assertRaises(FileExistsError):
            bs._enlazar_sin_pisar(origen, destino)
        self.assertEqual(destino.read_bytes(), b"viejo")
        self.assertEqual(origen.read_bytes(), b"nuevo")

    def test_fallo_de_publicacion_no_registra_exito(self) -> None:
        with patch.object(bs.subprocess, "run", _PgFalso()):
            bs.run_automatic_backup(output_dir=self.dir, dump_format="custom", retention_days=14)
        antes = bs.read_automatic_backup_status(self.dir)
        with patch.object(bs.subprocess, "run", _PgFalso()), \
             patch.object(bs, "_enlazar_sin_pisar", side_effect=PermissionError("antivirus")):
            with self.assertRaises(PermissionError):
                bs.run_automatic_backup(output_dir=self.dir, dump_format="custom", retention_days=14)
        despues = bs.read_automatic_backup_status(self.dir)
        self.assertEqual(despues.last_success_at, antes.last_success_at)
        self.assertEqual(despues.last_backup_path, antes.last_backup_path)
        self.assertIn("antivirus", despues.last_error or "")


# ── A3: el error original no se pierde ──────────────────────────────────────


class ErrorOriginalTests(_Base):
    def _unlink_que_falla(self):
        real = Path.unlink

        def unlink(ruta, *a, **k):
            if ruta.name.endswith(bs.PARCIAL_SUFFIX):
                raise PermissionError(13, "El proceso no tiene acceso al archivo")
            return real(ruta, *a, **k)

        return patch.object(Path, "unlink", unlink)

    def test_ctrl_c_sigue_siendo_ctrl_c_aunque_no_se_pueda_borrar_el_temporal(self) -> None:
        with self._unlink_que_falla(), self.assertLogs("pos_uniformes.services.backup_service", "WARNING") as log:
            with self.assertRaises(KeyboardInterrupt) as ctx:
                self._correr(_PgFalso(contenido=GRANDE, excepcion=KeyboardInterrupt()))
        notas = " ".join(getattr(ctx.exception, "__notes__", []))
        self.assertIn("no se pudo borrar el temporal", notas)
        self.assertIn("El proceso no tiene acceso", notas)
        self.assertIn("no se pudo borrar el temporal", " ".join(log.output))
        # Lo que quedó no es un respaldo: sigue siendo un .parcial invisible.
        self.assertEqual(self._dumps(), {self.bueno.name, self.viejo.name})
        self.assertEqual(len(self._parciales()), 1)
        self.assertEqual(est.leer_estado(self.dir).archivo, self.bueno)

    def test_trunco_sigue_siendo_trunco_y_el_estado_guarda_el_original(self) -> None:
        with self._unlink_que_falla():
            with patch.object(bs.subprocess, "run", _PgFalso(contenido=GRANDE, codigo=0)):
                with self.assertRaises(bs.BackupIncompletoError):
                    bs.run_automatic_backup(output_dir=self.dir, dump_format="custom", retention_days=14)
        estado = bs.read_automatic_backup_status(self.dir)
        self.assertIn("incompleto", estado.last_error or "")
        self.assertNotIn("acceso", estado.last_error or "")
        self.assertIsNone(estado.last_success_at)

    def test_el_error_de_pg_dump_no_se_cambia_por_el_de_limpieza(self) -> None:
        with self._unlink_que_falla():
            with self.assertRaises(subprocess.CalledProcessError):
                self._correr(_PgFalso(contenido=GRANDE, codigo=1))


# ── A4: cierre estricto del .sql ────────────────────────────────────────────


class CierreSqlTests(unittest.TestCase):
    def _ok(self, contenido: bytes) -> bool:
        return bs._sql_cerro_bien(contenido[:8192], contenido[-4096:])

    def test_respaldo_de_pg_dump_18_pasa(self) -> None:
        self.assertTrue(self._ok(SQL_BUENO))

    def test_con_finales_de_linea_de_windows_pasa(self) -> None:
        self.assertTrue(self._ok(SQL_BUENO.replace(b"\n", b"\r\n")))

    def test_pg_dump_viejo_sin_restrict_pasa(self) -> None:
        viejo = (b"--\n-- PostgreSQL database dump\n--\n\n" + SQL_CUERPO
                 + b"\n\n--\n-- PostgreSQL database dump complete\n--\n\n")
        self.assertTrue(self._ok(viejo))

    def test_cortado_antes_del_cierre_no_pasa(self) -> None:
        self.assertFalse(self._ok(SQL_CABEZA + SQL_CUERPO))

    def test_cortado_a_media_linea_del_cierre_no_pasa(self) -> None:
        for corte in (b"-- PostgreSQL database dump compl", b"-- PostgreSQL database dump complete\n",
                      b"-- PostgreSQL database dump complete\n--\n\n\\unrestr"):
            with self.subTest(corte=corte):
                i = SQL_BUENO.index(b"-- PostgreSQL database dump complete")
                cola = SQL_BUENO[:i] + corte
                self.assertFalse(self._ok(cola))

    def test_sin_el_unrestrict_cuando_empezo_con_restrict_no_pasa(self) -> None:
        # El cierre de texto está entero, pero falta la última línea de pg_dump 18.
        sin = SQL_BUENO[: SQL_BUENO.index(b"\\unrestrict")]
        self.assertFalse(self._ok(sin))

    def test_el_texto_de_cierre_como_dato_de_tabla_no_pasa(self) -> None:
        # Una nota de cliente que dice lo mismo, y el archivo cortado ahí.
        dato = (b"COPY public.nota (id, texto) FROM stdin;\n7\t\n--\n-- PostgreSQL database dump complete\n--\n")
        self.assertFalse(self._ok(SQL_CABEZA + SQL_CUERPO + dato))

    def test_el_dato_con_el_cierre_y_hasta_un_unrestrict_falso_no_pasa(self) -> None:
        falso = (b"\n\n--\n-- PostgreSQL database dump complete\n--\n\n\\unrestrict OTRACLAVE99\n\n")
        self.assertFalse(self._ok(SQL_CABEZA + SQL_CUERPO + falso))

    def test_unrestrict_sin_restrict_no_pasa(self) -> None:
        sin_cabeza = b"--\n-- PostgreSQL database dump\n--\n\n" + SQL_CUERPO + SQL_CIERRE
        self.assertFalse(self._ok(sin_cabeza))

    def test_basura_despues_del_cierre_no_pasa(self) -> None:
        self.assertFalse(self._ok(SQL_BUENO + b"COPY public.x FROM stdin;\n"))

    def test_vacio_o_solo_espacios_no_pasa(self) -> None:
        self.assertFalse(self._ok(b""))
        self.assertFalse(self._ok(b"\n\n  \r\n"))

    def test_el_cierre_en_medio_del_archivo_no_cuenta(self) -> None:
        # Cierre completo y luego más datos: el cierre no está al final.
        self.assertFalse(self._ok(SQL_CABEZA + SQL_CIERRE + SQL_CUERPO))


if __name__ == "__main__":
    unittest.main()
