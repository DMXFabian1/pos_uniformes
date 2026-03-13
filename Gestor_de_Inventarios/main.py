import os
import sys
import logging
import sqlite3
import customtkinter as ctk
from src.modules.products.generador_codigos import GeneradorCodigos
from src.modules.products.product_manager import abrir_gestion_productos
from src.modules.synchronizer.synchronizer import Synchronizer
from src.modules.sales.apartados.apartados_manager import ApartadosManager
from src.modules.scanner.scan_and_print import ScanAndPrintApp
from src.core.config.db_manager import DatabaseManager
from PIL import Image, ImageSequence
import time

# Configurar logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Gestor de Inventarios")
        self.root.geometry("1200x800")
        self.root.resizable(True, True)
        self.root.state('zoomed')  # Maximizar la ventana
        self.root_folder = os.path.abspath(os.path.dirname(__file__))
        self.db_manager = DatabaseManager()
        self.user_id = "admin"
        self.role = "admin"
        self.tallas_personalizadas = []
        self.icons = self.load_icons()
        
        # Bandera para rastrear el estado de carga
        self.is_loading = False
        self.after_id = None  # ID para eventos programados con root.after
        
        # Instancias precargadas
        self.product_manager_instance = None
        self.generador_codigos_instance = None
        self.synchronizer_instance = None
        self.apartados_manager_instance = None
        self.scan_and_print_instance = None
        
        # Interfaz actual
        self.current_interface = None
        
        # Control de animación del GIF
        self.gif_frames = []
        self.current_frame = 0
        self.animation_running = False
        
        # Contenedor principal
        self.content_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)
        
        # Pantalla de bienvenida
        self.setup_splash_screen()
        
        # Iniciar precarga de formularios
        self.preload_forms()

    def load_icons(self):
        icons = {}
        icon_folder = os.path.join(self.root_folder, "assets", "icons")
        icon_files = {
            "edit": "edit.png",
            "copy": "copy.png",
            "delete": "delete.png",
            "duplicate": "duplicate.png",
            "price": "price.png",
            "print": "print.png",
            "inventory": "inventory.png"
        }
        for key, file_name in icon_files.items():
            try:
                icon_path = os.path.join(icon_folder, file_name)
                if os.path.exists(icon_path):
                    img = Image.open(icon_path)
                    icons[key] = ctk.CTkImage(light_image=img, dark_image=img, size=(24, 24))
                    logger.debug(f"Ícono cargado: {key}")
                else:
                    logger.warning(f"Ícono no encontrado: {icon_path}")
            except Exception as e:
                logger.error(f"Error al cargar ícono {key}: {e}")
        return icons

    def setup_splash_screen(self):
        logger.debug("Configurando pantalla de bienvenida")
        self.splash_frame = ctk.CTkFrame(self.content_frame, fg_color="#FFFFFF")
        self.splash_frame.pack(fill="both", expand=True)
        
        try:
            gif_path = os.path.join(self.root_folder, "assets", "images", "loading.gif")
            if os.path.exists(gif_path):
                gif = Image.open(gif_path)
                self.gif_frames = []
                for frame in ImageSequence.Iterator(gif):
                    frame = frame.copy()
                    frame = frame.resize((200, 200), Image.Resampling.LANCZOS)
                    self.gif_frames.append(ctk.CTkImage(light_image=frame, dark_image=frame, size=(200, 200)))
                logger.debug(f"Cargados {len(self.gif_frames)} fotogramas del GIF")
            else:
                logger.warning(f"GIF no encontrado: {gif_path}")
                self.gif_frames = []
        except Exception as e:
            logger.error(f"Error al cargar el GIF: {e}")
            self.gif_frames = []

        self.gif_label = ctk.CTkLabel(self.splash_frame, text="")
        self.gif_label.pack(pady=20)
        
        if self.gif_frames:
            self.animation_running = True
            logger.debug("Iniciando animación del GIF")
            self.animate_gif()
        else:
            logger.warning("No se encontraron fotogramas del GIF, mostrando texto placeholder")
            ctk.CTkLabel(
                self.splash_frame, text="Cargando animación...",
                font=("Helvetica", 20), text_color="#4B5EAA"
            ).pack(pady=20)

        ctk.CTkLabel(
            self.splash_frame, text="Gestor de Inventarios",
            font=("Helvetica", 30, "bold"), text_color="#003087"
        ).pack(pady=20)
        
        ctk.CTkLabel(
            self.splash_frame, text="Cargando formularios...",
            font=("Helvetica", 20), text_color="#4B5EAA"
        ).pack(pady=10)
        
        self.splash_progress = ctk.CTkProgressBar(
            self.splash_frame, mode="indeterminate", width=300
        )
        self.splash_progress.pack(pady=20)
        self.splash_progress.start()

        self.root.update()

    def animate_gif(self):
        if not self.animation_running or not self.gif_frames or not hasattr(self, 'gif_label') or not self.gif_label.winfo_exists():
            logger.debug("Animación del GIF detenida")
            return
        self.current_frame = (self.current_frame + 1) % len(self.gif_frames)
        self.gif_label.configure(image=self.gif_frames[self.current_frame])
        self.root.after(100, self.animate_gif)

    def verify_database(self):
        db_path = os.path.join(self.root_folder, "data", "productos.db")
        if not os.path.exists(db_path):
            logger.error(f"Base de datos {db_path} no encontrada")
            raise FileNotFoundError(f"Base de datos {db_path} no encontrada")
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='productos'")
                if not cursor.fetchone():
                    logger.error("Tabla 'productos' no encontrada en la base de datos")
                    raise ValueError("La base de datos no contiene la tabla 'productos'")
                logger.info("Base de datos verificada correctamente")
        except sqlite3.Error as e:
            logger.error(f"Error al verificar la base de datos: {e}")
            raise

    def preload_forms(self):
        logger.info("Iniciando precarga de formularios")
        self.is_loading = True
        
        def load_forms():
            try:
                logger.debug("Precargando Product Manager")
                start_time = time.time()
                temp_frame = ctk.CTkFrame(self.content_frame)
                self.product_manager_instance = abrir_gestion_productos(self, temp_frame, store_id=1)
                temp_frame.destroy()
                end_time = time.time()
                logger.debug(f"Tiempo de precarga de Product Manager: {end_time - start_time:.2f} segundos")
                
                logger.debug("Precargando Generador de Códigos")
                start_time = time.time()
                temp_frame = ctk.CTkFrame(self.content_frame)
                self.generador_codigos_instance = GeneradorCodigos(temp_frame, icons=self.icons, db_manager=self.db_manager, store_id=1)
                temp_frame.destroy()
                end_time = time.time()
                logger.debug(f"Tiempo de precarga de Generador de Códigos: {end_time - start_time:.2f} segundos")
                
                logger.debug("Precargando Apartados y Clientes")
                start_time = time.time()
                temp_frame = ctk.CTkFrame(self.content_frame)
                self.apartados_manager_instance = ApartadosManager(self.user_id, temp_frame, self.root, self.db_manager, store_id=1, skip_ui_setup=True)
                temp_frame.destroy()
                end_time = time.time()
                logger.debug(f"Tiempo de precarga de Apartados y Clientes: {end_time - start_time:.2f} segundos")
                
                logger.debug("Precargando Synchronizer")
                start_time = time.time()
                temp_frame = ctk.CTkFrame(self.content_frame)
                self.synchronizer_instance = Synchronizer(temp_frame, icons=self.icons, db_manager=self.db_manager, store_id=1)
                temp_frame.destroy()
                end_time = time.time()
                logger.debug(f"Tiempo de precarga de Synchronizer: {end_time - start_time:.2f} segundos")
                
                logger.debug("Precargando Scan and Print")
                start_time = time.time()
                self.scan_and_print_instance = None  # Se instanciará al abrir la ventana
                end_time = time.time()
                logger.debug(f"Tiempo de precarga de Scan and Print: {end_time - start_time:.2f} segundos")
                
                self.verify_database()
                
                self.transition_to_main_interface()
                
            except Exception as e:
                logger.error(f"Error durante la precarga de formularios: {e}")
                self.animation_running = False
                if hasattr(self, 'splash_frame') and self.splash_frame.winfo_exists():
                    self.splash_frame.destroy()
                self.show_error_message(f"Error al precargar formularios: {str(e)}")
                self.is_loading = False
        
        self.root.after(50, load_forms)

    def transition_to_main_interface(self):
        try:
            self.animation_running = False
            logger.debug("Deteniendo animación del GIF")
            if hasattr(self, 'splash_frame') and self.splash_frame.winfo_exists():
                self.splash_frame.destroy()
            self.setup_main_interface()
            self.is_loading = False
            logger.debug("is_loading establecido en False")
            self.switch_to_product_manager()
            logger.info("Precarga de formularios completada")
        except Exception as e:
            logger.error(f"Error durante la transición a la interfaz principal: {e}")
            self.show_error_message(f"Error durante la transición: {str(e)}")
            self.is_loading = False

    def setup_main_interface(self):
        logger.debug("Configurando interfaz principal")
        self.top_bar = ctk.CTkFrame(self.content_frame, fg_color="#003087", corner_radius=0, height=50)
        self.top_bar.pack(fill="x")
        self.top_bar.pack_propagate(False)
        
        ctk.CTkLabel(
            self.top_bar, text="Gestor de Inventarios",
            font=("Helvetica", 20, "bold"), text_color="#FFFFFF"
        ).pack(side="left", padx=20, pady=10)
        
        self.btn_product_manager = ctk.CTkButton(
            self.top_bar, text="Product Manager", command=self.switch_to_product_manager,
            fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8,
            width=150, height=30, font=("Helvetica", 12, "bold")
        )
        self.btn_product_manager.pack(side="left", padx=10)
        
        self.btn_generador_codigos = ctk.CTkButton(
            self.top_bar, text="Generador de Códigos", command=self.switch_to_generador_codigos,
            fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8,
            width=150, height=30, font=("Helvetica", 12, "bold")
        )
        self.btn_generador_codigos.pack(side="left", padx=10)
        
        self.btn_apartados_clientes = ctk.CTkButton(
            self.top_bar, text="Apartados y Clientes", command=self.switch_to_apartados_clientes,
            fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8,
            width=150, height=30, font=("Helvetica", 12, "bold")
        )
        self.btn_apartados_clientes.pack(side="left", padx=10)
        
        self.btn_synchronizer = ctk.CTkButton(
            self.top_bar, text="Sincronizar", command=self.switch_to_synchronizer,
            fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8,
            width=150, height=30, font=("Helvetica", 12, "bold")
        )
        self.btn_synchronizer.pack(side="left", padx=10)
        
        self.btn_scan_and_print = ctk.CTkButton(
            self.top_bar, text="Escanear e Imprimir", command=self.switch_to_scan_and_print,
            fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8,
            width=150, height=30, font=("Helvetica", 12, "bold")
        )
        self.btn_scan_and_print.pack(side="left", padx=10)
        
        self.btn_exit = ctk.CTkButton(
            self.top_bar, text="Salir", command=self.root.quit,
            fg_color="#FF4C4C", hover_color="#CC3D3D", corner_radius=8,
            width=100, height=30, font=("Helvetica", 12, "bold")
        )
        self.btn_exit.pack(side="right", padx=20)
        
        self.interface_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.interface_frame.pack(fill="both", expand=True)
        
        # Inicializar loading_container aquí para evitar referencias prematuras
        self.loading_container = ctk.CTkFrame(self.interface_frame, fg_color="#E6E6E6", corner_radius=10)
        ctk.CTkLabel(
            self.loading_container, text="Cargando...", font=("Helvetica", 20, "bold"),
            text_color="#4B5EAA", fg_color="transparent"
        ).pack(pady=10)
        self.loading_progress = ctk.CTkProgressBar(
            self.loading_container, mode="indeterminate", width=200
        )
        self.loading_progress.pack(pady=10)

    def clear_content(self):
        logger.debug("Limpiando contenido del contenedor de interfaz")
        if self.after_id:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        if hasattr(self, 'loading_container') and self.loading_container.winfo_exists():
            try:
                self.loading_container.pack_forget()
                self.loading_progress.stop()
            except Exception as e:
                logger.error(f"Error al ocultar loading_container: {e}")
        if self.current_interface and self.current_interface.winfo_exists():
            try:
                self.current_interface.destroy()
                logger.debug("Interfaz actual destruida")
            except Exception as e:
                logger.error(f"Error al destruir interfaz actual: {e}")
        for widget in self.interface_frame.winfo_children():
            if widget.winfo_exists():
                try:
                    widget.destroy()
                except Exception as e:
                    logger.error(f"Error al destruir widget {widget}: {e}")
        self.current_interface = None

    def switch_to_product_manager(self):
        if self.is_loading or (self.current_interface is not None and self.btn_product_manager.cget("state") == "disabled"):
            logger.debug("Cambio a Product Manager bloqueado")
            return
        logger.info("Iniciando cambio a Product Manager")
        self.is_loading = True
        self.btn_product_manager.configure(state="disabled")
        self.btn_generador_codigos.configure(state="disabled")
        self.btn_apartados_clientes.configure(state="disabled")
        self.btn_synchronizer.configure(state="disabled")
        self.btn_scan_and_print.configure(state="disabled")
        self.btn_exit.configure(state="disabled")
        self.clear_content()
        
        if hasattr(self, 'loading_container') and self.loading_container.winfo_exists():
            self.loading_container.pack(expand=True)
            self.loading_progress.start()
        
        def load_interface():
            try:
                if hasattr(self, 'loading_container') and self.loading_container.winfo_exists():
                    self.loading_container.pack_forget()
                    self.loading_progress.stop()
                self.current_interface = ctk.CTkFrame(self.interface_frame)
                self.current_interface.pack(fill="both", expand=True)
                start_time = time.time()
                abrir_gestion_productos(self, self.current_interface, store_id=1)
                end_time = time.time()
                logger.debug(f"Tiempo de carga de Product Manager: {end_time - start_time:.2f} segundos")
                self.btn_product_manager.configure(state="disabled")
                self.btn_generador_codigos.configure(state="normal")
                self.btn_apartados_clientes.configure(state="normal")
                self.btn_synchronizer.configure(state="normal")
                self.btn_scan_and_print.configure(state="normal")
                self.btn_exit.configure(state="normal")
                self.is_loading = False
                logger.info("Interfaz de Product Manager cargada exitosamente")
            except Exception as e:
                logger.error(f"Error al cargar Product Manager: {e}")
                self.is_loading = False
                self.btn_product_manager.configure(state="normal")
                self.btn_generador_codigos.configure(state="normal")
                self.btn_apartados_clientes.configure(state="normal")
                self.btn_synchronizer.configure(state="normal")
                self.btn_scan_and_print.configure(state="normal")
                self.btn_exit.configure(state="normal")
                self.show_error_message(f"Error al cargar Product Manager: {str(e)}")
        
        self.after_id = self.root.after(100, load_interface)

    def switch_to_generador_codigos(self):
        if self.is_loading or (self.current_interface is not None and self.btn_generador_codigos.cget("state") == "disabled"):
            logger.debug("Cambio a Generador de Códigos bloqueado")
            return
        logger.info("Iniciando cambio a Generador de Códigos")
        self.is_loading = True
        self.btn_product_manager.configure(state="disabled")
        self.btn_generador_codigos.configure(state="disabled")
        self.btn_apartados_clientes.configure(state="disabled")
        self.btn_synchronizer.configure(state="disabled")
        self.btn_scan_and_print.configure(state="disabled")
        self.btn_exit.configure(state="disabled")
        self.clear_content()
        
        if hasattr(self, 'loading_container') and self.loading_container.winfo_exists():
            self.loading_container.pack(expand=True)
            self.loading_progress.start()
        
        def load_interface():
            try:
                if hasattr(self, 'loading_container') and self.loading_container.winfo_exists():
                    self.loading_container.pack_forget()
                    self.loading_progress.stop()
                self.current_interface = ctk.CTkFrame(self.interface_frame)
                self.current_interface.pack(fill="both", expand=True)
                start_time = time.time()
                generador = GeneradorCodigos(self.current_interface, icons=self.icons, db_manager=self.db_manager, store_id=1)
                generador.main_frame.pack(fill="both", expand=True)
                end_time = time.time()
                logger.debug(f"Tiempo de carga de Generador de Códigos: {end_time - start_time:.2f} segundos")
                self.btn_generador_codigos.configure(state="disabled")
                self.btn_product_manager.configure(state="normal")
                self.btn_apartados_clientes.configure(state="normal")
                self.btn_synchronizer.configure(state="normal")
                self.btn_scan_and_print.configure(state="normal")
                self.btn_exit.configure(state="normal")
                self.is_loading = False
                logger.info("Interfaz de Generador de Códigos cargada exitosamente")
            except Exception as e:
                logger.error(f"Error al cargar Generador de Códigos: {e}")
                self.is_loading = False
                self.btn_product_manager.configure(state="normal")
                self.btn_generador_codigos.configure(state="normal")
                self.btn_apartados_clientes.configure(state="normal")
                self.btn_synchronizer.configure(state="normal")
                self.btn_scan_and_print.configure(state="normal")
                self.btn_exit.configure(state="normal")
                self.show_error_message(f"Error al cargar Generador de Códigos: {str(e)}")
        
        self.after_id = self.root.after(100, load_interface)

    def switch_to_apartados_clientes(self):
        if self.is_loading or (self.current_interface is not None and self.btn_apartados_clientes.cget("state") == "disabled"):
            logger.debug("Cambio a Apartados y Clientes bloqueado")
            return
        logger.info("Iniciando cambio a Apartados y Clientes")
        self.is_loading = True
        self.btn_product_manager.configure(state="disabled")
        self.btn_generador_codigos.configure(state="disabled")
        self.btn_apartados_clientes.configure(state="disabled")
        self.btn_synchronizer.configure(state="disabled")
        self.btn_scan_and_print.configure(state="disabled")
        self.btn_exit.configure(state="disabled")
        self.clear_content()
        
        if hasattr(self, 'loading_container') and self.loading_container.winfo_exists():
            self.loading_container.pack(expand=True)
            self.loading_progress.start()
        
        def load_interface():
            try:
                if hasattr(self, 'loading_container') and self.loading_container.winfo_exists():
                    self.loading_container.pack_forget()
                    self.loading_progress.stop()
                self.current_interface = ctk.CTkFrame(self.interface_frame)
                self.current_interface.pack(fill="both", expand=True)
                start_time = time.time()
                apartados_manager = ApartadosManager(self.user_id, self.current_interface, self.root, self.db_manager, store_id=1)
                apartados_manager.pack(fill="both", expand=True)
                end_time = time.time()
                logger.debug(f"Tiempo de carga de Apartados y Clientes: {end_time - start_time:.2f} segundos")
                self.btn_apartados_clientes.configure(state="disabled")
                self.btn_product_manager.configure(state="normal")
                self.btn_generador_codigos.configure(state="normal")
                self.btn_synchronizer.configure(state="normal")
                self.btn_scan_and_print.configure(state="normal")
                self.btn_exit.configure(state="normal")
                self.is_loading = False
                logger.info("Interfaz de Apartados y Clientes cargada exitosamente")
            except Exception as e:
                logger.error(f"Error al cargar Apartados y Clientes: {e}")
                self.is_loading = False
                self.btn_product_manager.configure(state="normal")
                self.btn_generador_codigos.configure(state="normal")
                self.btn_apartados_clientes.configure(state="normal")
                self.btn_synchronizer.configure(state="normal")
                self.btn_scan_and_print.configure(state="normal")
                self.btn_exit.configure(state="normal")
                self.show_error_message(f"Error al cargar Apartados y Clientes: {str(e)}")
        
        self.after_id = self.root.after(100, load_interface)

    def switch_to_synchronizer(self):
        if self.is_loading or (self.current_interface is not None and self.btn_synchronizer.cget("state") == "disabled"):
            logger.debug("Cambio a Synchronizer bloqueado")
            return
        logger.info("Iniciando cambio a Synchronizer")
        self.is_loading = True
        self.btn_product_manager.configure(state="disabled")
        self.btn_generador_codigos.configure(state="disabled")
        self.btn_apartados_clientes.configure(state="disabled")
        self.btn_synchronizer.configure(state="disabled")
        self.btn_scan_and_print.configure(state="disabled")
        self.btn_exit.configure(state="disabled")
        self.clear_content()
        
        if hasattr(self, 'loading_container') and self.loading_container.winfo_exists():
            self.loading_container.pack(expand=True)
            self.loading_progress.start()
        
        def load_interface():
            try:
                if hasattr(self, 'loading_container') and self.loading_container.winfo_exists():
                    self.loading_container.pack_forget()
                    self.loading_progress.stop()
                self.current_interface = ctk.CTkFrame(self.interface_frame)
                self.current_interface.pack(fill="both", expand=True)
                start_time = time.time()
                synchronizer = Synchronizer(self.current_interface, icons=self.icons, db_manager=self.db_manager, store_id=1)
                synchronizer.main_frame.pack(fill="both", expand=True)
                end_time = time.time()
                logger.debug(f"Tiempo de carga de Synchronizer: {end_time - start_time:.2f} segundos")
                self.btn_synchronizer.configure(state="disabled")
                self.btn_product_manager.configure(state="normal")
                self.btn_generador_codigos.configure(state="normal")
                self.btn_apartados_clientes.configure(state="normal")
                self.btn_scan_and_print.configure(state="normal")
                self.btn_exit.configure(state="normal")
                self.is_loading = False
                logger.info("Interfaz de Synchronizer cargada exitosamente")
            except Exception as e:
                logger.error(f"Error al cargar Synchronizer: {e}")
                self.is_loading = False
                self.btn_product_manager.configure(state="normal")
                self.btn_generador_codigos.configure(state="normal")
                self.btn_apartados_clientes.configure(state="normal")
                self.btn_synchronizer.configure(state="normal")
                self.btn_scan_and_print.configure(state="normal")
                self.btn_exit.configure(state="normal")
                self.show_error_message(f"Error al cargar Synchronizer: {str(e)}")
        
        self.after_id = self.root.after(100, load_interface)

    def switch_to_scan_and_print(self):
        if self.is_loading:
            logger.debug("Cambio a Escanear e Imprimir bloqueado")
            return
        logger.info("Iniciando cambio a Escanear e Imprimir")
        self.is_loading = True
        self.btn_product_manager.configure(state="disabled")
        self.btn_generador_codigos.configure(state="disabled")
        self.btn_apartados_clientes.configure(state="disabled")
        self.btn_synchronizer.configure(state="disabled")
        self.btn_scan_and_print.configure(state="disabled")
        self.btn_exit.configure(state="disabled")
        
        def load_interface():
            try:
                self.scan_and_print_instance = ScanAndPrintApp(self.root, self.root_folder, self.db_manager, store_id=1)
                self.btn_product_manager.configure(state="normal")
                self.btn_generador_codigos.configure(state="normal")
                self.btn_apartados_clientes.configure(state="normal")
                self.btn_synchronizer.configure(state="normal")
                self.btn_scan_and_print.configure(state="normal")
                self.btn_exit.configure(state="normal")
                self.is_loading = False
                logger.info("Ventana de Escanear e Imprimir cargada exitosamente")
            except Exception as e:
                logger.error(f"Error al cargar Escanear e Imprimir: {e}")
                self.is_loading = False
                self.btn_product_manager.configure(state="normal")
                self.btn_generador_codigos.configure(state="normal")
                self.btn_apartados_clientes.configure(state="normal")
                self.btn_synchronizer.configure(state="normal")
                self.btn_scan_and_print.configure(state="normal")
                self.btn_exit.configure(state="normal")
                self.show_error_message(f"Error al cargar Escanear e Imprimir: {str(e)}")
        
        self.after_id = self.root.after(100, load_interface)

    def show_error_message(self, message):
        try:
            error_label = ctk.CTkLabel(
                self.content_frame, text=message, font=("Helvetica", 14),
                text_color="#FF4C4C", fg_color="transparent", wraplength=600
            )
            error_label.pack()
            self.root.after(5000, lambda: error_label.destroy() if error_label.winfo_exists() else None)
        except Exception as e:
            logger.error(f"Error al mostrar mensaje de error: {e}")

def main():
    try:
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        root = ctk.CTk()
        app = App(root)
        root.mainloop()
    except Exception as e:
        logger.error(f"Error al iniciar Gestor de Inventarios: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 