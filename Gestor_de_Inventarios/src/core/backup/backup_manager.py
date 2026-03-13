# backup_manager.py
import os
import shutil
import logging
from datetime import datetime
from src.core.config.config import CONFIG
import threading
import time

class BackupManager:
    def __init__(self, db_path, config=None):
        self.db_path = db_path
        self.backups_folder = os.path.join(CONFIG["ROOT_FOLDER"], CONFIG["BACKUPS_DIR"])
        self.max_backups = config.get("max_backups", 15) if config else 15
        self.backup_filename_format = config.get("backup_filename_format", "productos_backup_{prefix}_{reason}_{timestamp}.db") if config else "productos_backup_{prefix}_{reason}_{timestamp}.db"
        self.auto_folder = os.path.join(self.backups_folder, "Automatic")
        self.manual_folder = os.path.join(self.backups_folder, "Manual")

        # Crear carpetas si no existen
        try:
            os.makedirs(self.auto_folder, exist_ok=True)
            os.makedirs(self.manual_folder, exist_ok=True)
        except Exception as e:
            logging.error(f"Error al crear carpetas de respaldo: {str(e)}")
            raise RuntimeError(f"No se pudieron crear las carpetas de respaldo: {str(e)}")

        # Validar que db_path exista
        if not os.path.exists(self.db_path):
            logging.error(f"La base de datos {self.db_path} no existe.")
            raise FileNotFoundError(f"La base de datos {self.db_path} no existe.")

    def create_backup(self, reason="manual", async_mode=False):
        """
        Crea una copia de seguridad de la base de datos.
        Si async_mode=True, el respaldo se realiza en un hilo separado.
        """
        if async_mode:
            # Ejecutar el respaldo en un hilo separado
            thread = threading.Thread(target=self._create_backup_sync, args=(reason,))
            thread.start()
            logging.debug(f"Respaldo iniciado en segundo plano con motivo: {reason}")
            return None  # No devolvemos backup_path porque se ejecuta asíncronamente
        else:
            # Ejecutar el respaldo de forma síncrona
            return self._create_backup_sync(reason)

    def _create_backup_sync(self, reason):
        """Método síncrono para crear la copia de seguridad."""
        try:
            start_time = time.time()
            # Validar el motivo del respaldo
            valid_reasons = ["manual", "close", "before_restore"]
            if reason not in valid_reasons:
                raise ValueError(f"Motivo de respaldo '{reason}' no válido. Use: {valid_reasons}")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            is_auto = reason in ["close", "before_restore"]
            folder = self.auto_folder if is_auto else self.manual_folder
            prefix = "auto" if is_auto else "manual"
            backup_filename = self.backup_filename_format.format(prefix=prefix, reason=reason, timestamp=timestamp)
            backup_path = os.path.join(folder, backup_filename)

            # Copiar la base de datos
            shutil.copy2(self.db_path, backup_path)
            logging.info(f"Copia de seguridad creada: {backup_path}")

            # Limitar el número de copias automáticas
            if is_auto:
                self._limit_auto_backups()

            end_time = time.time()
            logging.debug(f"Tiempo de creación de respaldo: {end_time - start_time:.2f} segundos")
            return backup_path
        except Exception as e:
            logging.error(f"Error al crear copia de seguridad: {str(e)}")
            raise RuntimeError(f"No se pudo crear la copia de seguridad: {str(e)}")

    def _limit_auto_backups(self):
        try:
            start_time = time.time()
            # Listar y ordenar copias automáticas
            auto_backups = [
                f for f in os.listdir(self.auto_folder)
                if f.startswith("productos_backup_auto_") and f.endswith(".db")
            ]
            auto_backups.sort(reverse=True)  # Ordenar por nombre (más reciente primero)

            # Eliminar copias antiguas si exceden el límite
            while len(auto_backups) > self.max_backups:
                oldest_backup = auto_backups.pop()
                backup_to_remove = os.path.join(self.auto_folder, oldest_backup)
                os.remove(backup_to_remove)
                logging.info(f"Copia de seguridad automática antigua eliminada: {backup_to_remove}")

            end_time = time.time()
            logging.debug(f"Tiempo de limitación de respaldos automáticos: {end_time - start_time:.2f} segundos")
        except Exception as e:
            logging.error(f"Error al limitar copias automáticas: {str(e)}")
            raise RuntimeError(f"No se pudieron limitar las copias automáticas: {str(e)}")

    def list_backups(self):
        backup_list = []
        try:
            # Listar copias automáticas
            if os.path.exists(self.auto_folder):
                for backup in os.listdir(self.auto_folder):
                    if backup.endswith(".db"):
                        backup_path = os.path.join(self.auto_folder, backup)
                        creation_time = datetime.fromtimestamp(os.path.getctime(backup_path)).strftime("%Y-%m-%d %H:%M:%S")
                        backup_list.append(("Automatic", backup, creation_time))
            # Listar copias manuales
            if os.path.exists(self.manual_folder):
                for backup in os.listdir(self.manual_folder):
                    if backup.endswith(".db"):
                        backup_path = os.path.join(self.manual_folder, backup)
                        creation_time = datetime.fromtimestamp(os.path.getctime(backup_path)).strftime("%Y-%m-%d %H:%M:%S")
                        backup_list.append(("Manual", backup, creation_time))
            # Ordenar por fecha de creación (más reciente primero)
            backup_list.sort(key=lambda x: x[2], reverse=True)
            return backup_list
        except Exception as e:
            logging.error(f"Error al listar copias de seguridad: {str(e)}")
            raise RuntimeError(f"No se pudieron listar las copias de seguridad: {str(e)}")

    def restore_backup(self, backup_type, backup_filename):
        try:
            folder = self.auto_folder if backup_type == "Automatic" else self.manual_folder
            backup_path = os.path.join(folder, backup_filename)
            if not os.path.exists(backup_path):
                raise FileNotFoundError(f"La copia de seguridad {backup_filename} no existe.")
            # Crear una copia de seguridad de la base de datos actual antes de restaurar
            self.create_backup(reason="before_restore")
            # Restaurar la copia de seguridad
            shutil.copy2(backup_path, self.db_path)
            logging.info(f"Base de datos restaurada desde: {backup_filename}")
        except Exception as e:
            logging.error(f"Error al restaurar copia de seguridad: {str(e)}")
            raise RuntimeError(f"No se pudo restaurar la copia de seguridad: {str(e)}")

    def delete_backup(self, backup_type, backup_filename):
        """Elimina una copia de seguridad específica."""
        try:
            folder = self.auto_folder if backup_type == "Automatic" else self.manual_folder
            backup_path = os.path.join(folder, backup_filename)
            if not os.path.exists(backup_path):
                raise FileNotFoundError(f"La copia de seguridad {backup_filename} no existe.")
            os.remove(backup_path)
            logging.info(f"Copia de seguridad eliminada: {backup_filename}")
        except Exception as e:
            logging.error(f"Error al eliminar copia de seguridad: {str(e)}")
            raise RuntimeError(f"No se pudo eliminar la copia de seguridad: {str(e)}")