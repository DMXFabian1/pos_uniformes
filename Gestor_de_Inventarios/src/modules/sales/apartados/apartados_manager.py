import customtkinter as ctk
import logging
from .apartados_logic import ApartadosLogic
from src.core.config.db_manager import DatabaseManager
from .clientes_tab import ClientesTab
from .apartados_tab import ApartadosTab

logger = logging.getLogger(__name__)

class ApartadosManager:
    def __init__(self, user_id, parent_frame, root, db_manager=None, store_id=1, skip_ui_setup=False):
        logging.debug(f"Iniciando ApartadosManager con store_id={store_id}")
        self.user_id = user_id
        self.store_id = store_id
        self.parent_frame = parent_frame
        self.root = root
        self.db_manager = db_manager or DatabaseManager()
        self.logic = ApartadosLogic(self.db_manager, user_id=self.user_id, store_id=self.store_id)
        logging.debug("ApartadosLogic creado")

        self.main_frame = ctk.CTkFrame(self.parent_frame)
        logging.debug("main_frame creado")

        self.clientes_tab = None
        self.apartados_tab = None

        if not skip_ui_setup:
            self.setup_ui()
        logger.info(f"Interfaz de gestión de apartados inicializada para usuario con ID '{self.user_id}' en tienda {self.store_id}.")

    def setup_ui(self):
        for widget in self.main_frame.winfo_children():
            widget.destroy()

        ctk.CTkLabel(self.main_frame, text="Gestión de Clientes y Apartados", font=("Arial", 24, "bold")).pack(pady=(20, 10))

        tab_control = ctk.CTkTabview(self.main_frame)
        tab_control.pack(fill="both", expand=True, padx=10, pady=5)

        clientes_tab = tab_control.add("Clientes")
        apartados_tab = tab_control.add("Apartados")

        self.apartados_tab = ApartadosTab(apartados_tab, self.db_manager, self.logic, self.root, self.user_id, store_id=self.store_id)
        self.clientes_tab = ClientesTab(clientes_tab, self.logic, self.root, self.user_id, store_id=self.store_id)

        def on_ver_apartados(apartado_values):
            if apartado_values:
                self.apartados_tab.tree.delete(*self.apartados_tab.tree.get_children())
                self.apartados_tab.tree.insert("", "end", values=apartado_values)
                self.root.nametowidget(self.main_frame.winfo_parent()).select(1)

        self.clientes_tab.crear_apartado_cliente = lambda: self.clientes_tab.crear_apartado_cliente(callback=self.cargar_apartados)
        self.clientes_tab.ver_apartados_cliente = lambda: self.clientes_tab.ver_apartados_cliente().configure(command=on_ver_apartados)

    def cargar_apartados(self):
        self.apartados_tab.cargar_apartados_paginated(page=1)

    def pack(self, **kwargs):
        self.main_frame.pack(**kwargs)