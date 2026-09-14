"""Paper trading en vivo: recolector + motor sobre los mismos libros, sin dinero real."""
from __future__ import annotations

import asyncio
import logging
import time

from ..collector import Collector
from ..config import Config
from ..experimento import MotorCambiado, assert_engine_frozen, congelar, registrar
from ..storage import ParquetWriter
from .engine import Engine

log = logging.getLogger(__name__)


async def run_paper(cfg: Config, duration_seconds: int | None = None, run_id: str | None = None,
                    persist_market_data: bool = True) -> Engine:
    run_id = run_id or f"paper-{int(time.time())}"
    # congelar el motor antes de empezar: si algo que decide cambia, esto será otro experimento
    congelado = cfg.validacion.motor_congelado
    if congelado and cfg.learn.enabled:
        # Congelar de verdad significa que el reentrenamiento no puede promocionar nada a mitad de
        # corrida. Se apaga aquí, sobre una copia, antes de tomar la huella, para que la huella
        # refleje el motor que va a correr y no el que había configurado.
        cfg = cfg.model_copy(deep=True)
        cfg.learn.enabled = False
        log.info("motor congelado: reentrenamiento desactivado para esta corrida")
    exp = congelar(cfg, nota=f"paper {run_id}")
    registrar(cfg, exp)
    log.info("motor congelado:\n%s", exp.resumen())
    if exp.dirty:
        log.warning("el árbol de trabajo tiene cambios sin comprometer: los datos de esta corrida "
                    "no se podrán reproducir exactamente")
    if congelado and exp.dirty:
        raise MotorCambiado(
            "corrida congelada con el árbol de trabajo sucio: el commit no describe el código que "
            "va a correr, así que el experimento no sería reproducible. Comprometa los cambios "
            "primero, o desactive validacion.motor_congelado si esta corrida no es para medir.")
    col = Collector(cfg, persist=persist_market_data)
    writer = ParquetWriter(cfg.data_dir, cfg.collector.flush_seconds, cfg.collector.flush_rows, subdir=f"run={run_id}")
    eng = Engine(cfg, run_id, "paper", writer, experiment=exp.experiment_id)
    eng.attach_books(col.books)
    if col.wallets is not None:
        eng.attach_wallets(col.wallets.profiles)
    col.add_listener(eng.on_event)

    async def ticker() -> None:
        while True:
            await asyncio.sleep(1)
            # el motor necesita saber si está mirando un libro viejo antes de decidir nada
            eng.registrar_salud(int(time.time() * 1000), col.salud_feed())
            eng.tick(int(time.time() * 1000))
            writer.maybe_flush()

    async def reporter() -> None:
        while True:
            await asyncio.sleep(120)
            log.info("paper: %s", eng.summary())

    async def guardian() -> None:
        """Comprueba que el motor sigue siendo el que se congeló. Si no, corta la corrida.

        Que la huella coincida significa que el commit, los umbrales, los modelos promovidos y el
        código de simulación son los mismos que al arrancar. Seguir escribiendo filas con el mismo
        experiment_id después de que algo se mueva produce exactamente el dato inservible que esto
        existe para evitar, así que se para y se dice por qué.
        """
        while True:
            await asyncio.sleep(max(cfg.validacion.comprobar_congelado_s, 5))
            try:
                assert_engine_frozen(cfg, exp)
            except MotorCambiado as e:
                log.error("CORRIDA ABORTADA: %s", e)
                eng.stats["abortada_motor_cambiado"] += 1
                col.stop()
                return

    async def retrainer() -> None:
        """Reentrena y, si eso cambia lo que el motor decide, abre un experimento nuevo.

        Promocionar un modelo a mitad de corrida cambia el motor. Sin esto, las filas de antes y
        las de después llevaban el mismo `experiment_id` y quedaban mezcladas para siempre: en
        `muestra-3`, 186 de 680 posiciones se decidieron con un modelo que no existía al congelar.
        La huella no puede detectarlo sola porque se calcula una vez, al arrancar.
        """
        from .learn_loop import retrain_and_reload
        nonlocal exp
        period = max(cfg.learn.retrain_hours, 0.1) * 3600
        while True:
            await asyncio.sleep(period)
            writer.flush()
            await asyncio.to_thread(retrain_and_reload, cfg, eng)
            nuevo_exp = congelar(cfg, nota=f"paper {run_id} (modelos nuevos)")
            if nuevo_exp.huella != exp.huella:
                registrar(cfg, nuevo_exp)
                log.warning("el reentrenamiento cambió lo que el motor decide: a partir de aquí, "
                            "experimento %s (antes %s). Los datos de las dos mitades no se mezclan.",
                            nuevo_exp.experiment_id, exp.experiment_id)
                exp = nuevo_exp
                eng.experiment = exp.experiment_id

    tasks = [asyncio.create_task(ticker()), asyncio.create_task(reporter())]
    if congelado:
        tasks.append(asyncio.create_task(guardian()))
    if cfg.learn.enabled:
        tasks.append(asyncio.create_task(retrainer()))
    if duration_seconds:
        async def stopper() -> None:
            await asyncio.sleep(duration_seconds)
            col.stop()
        tasks.append(asyncio.create_task(stopper()))
    try:
        await col.run()
    finally:
        for t in tasks:
            t.cancel()
        eng.close_all(int(time.time() * 1000), "end")
        writer.close()
        log.info("paper terminado: %s", eng.summary())
    return eng
