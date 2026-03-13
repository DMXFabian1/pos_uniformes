import customtkinter as ctk
from tkinter import ttk
import logging
from src.core.config.config import CONFIG
from src.core.utils.pagination import Paginator

logger = logging.getLogger(__name__)

class ApartadosUI:
    def __init__(self, tab, root, items_per_page, store_id=1, cargar_apartados_callback=None, buscar_apartados_callback=None, action_callbacks=None):
        self.tab = tab
        self.root = root
        self.items_per_page = items_per_page
        self.store_id = store_id
        self.cargar_apartados_callback = cargar_apartados_callback
        self.buscar_apartados_callback = buscar_apartados_callback
        self.action_callbacks = action_callbacks or {}
        self.dias_vencimiento_filtro = 2
        self.notif_label = None
        self.entry_dias_vencimiento = None
        self.entry_busqueda = None
        self.tree = None
        self.apartados_paginator = None
        self.sort_column_name = None
        self.sort_reverse = False
        logger.info(f"ApartadosUI inicializado para tienda {self.store_id}")

    def setup_ui(self, actualizar_dias_vencimiento_callback):
        """Configura la interfaz de usuario de la pestaña de apartados."""
        self._setup_notif_frame(actualizar_dias_vencimiento_callback)
        self._setup_search_frame()
        self._setup_treeview()
        self._setup_action_buttons()
        self._setup_paginator()
        self.entry_busqueda.focus_set()
        logging.debug(f"Interfaz de usuario de ApartadosUI configurada para tienda {self.store_id}")

    def _setup_notif_frame(self, actualizar_dias_vencimiento_callback):
        """Configura el marco de notificaciones para apartados por vencer."""
        self.notif_frame = ctk.CTkFrame(self.tab)
        self.notif_frame.pack(fill="x", pady=5)

        self.notif_label = ctk.CTkLabel(
            self.notif_frame,
            text=f"Apartados por vencer (próximos {self.dias_vencimiento_filtro} días): 0"
        )
        self.notif_label.pack(side="left", padx=5)

        ctk.CTkLabel(self.notif_frame, text="Días:").pack(side="left", padx=5)
        self.entry_dias_vencimiento = ctk.CTkEntry(self.notif_frame, width=50)
        self.entry_dias_vencimiento.insert(0, str(self.dias_vencimiento_filtro))
        self.entry_dias_vencimiento.pack(side="left", padx=5)

        ctk.CTkButton(
            self.notif_frame,
            text="Actualizar",
            command=actualizar_dias_vencimiento_callback
        ).pack(side="left", padx=5)

        logging.debug("notif_frame configurado")

    def _setup_search_frame(self):
        """Configura el marco de búsqueda para apartados."""
        self.search_frame = ctk.CTkFrame(self.tab)
        self.search_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(
            self.search_frame,
            text="Buscar Apartado (Nombre Cliente/Número):"
        ).pack(side="left", padx=5)

        self.entry_busqueda = ctk.CTkEntry(self.search_frame, width=250)
        self.entry_busqueda.pack(side="left", padx=5)
        self.entry_busqueda.bind("<Return>", lambda event: self.buscar_apartados_callback())

        ctk.CTkButton(
            self.search_frame,
            text="Buscar",
            command=self.buscar_apartados_callback
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            self.search_frame,
            text="Refrescar",
            command=lambda: self.cargar_apartados_callback(page=1)
        ).pack(side="left", padx=5)

        logging.debug("search_frame configurado")

    def _setup_treeview(self):
        """Configura el Treeview para mostrar los apartados."""
        self.tree_frame = ctk.CTkFrame(self.tab)
        self.tree_frame.pack(fill="both", expand=True, pady=5)

        self.tree_container = ctk.CTkFrame(self.tree_frame)
        self.tree_container.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(
            self.tree_container,
            columns=("ID", "Cliente", "Productos", "Anticipo", "Total", "Saldo Pendiente",
                     "Fecha Creación", "Fecha Modificación", "Fecha Vencimiento", "Estado"),
            show="headings"
        )

        self.tree.heading("ID", text="ID", command=lambda: self.sort_column("ID"))
        self.tree.heading("Cliente", text="Cliente", command=lambda: self.sort_column("Cliente"))
        self.tree.heading("Productos", text="Productos", command=lambda: self.sort_column("Productos"))
        self.tree.heading("Anticipo", text="Anticipo", command=lambda: self.sort_column("Anticipo"))
        self.tree.heading("Total", text="Total", command=lambda: self.sort_column("Total"))
        self.tree.heading("Saldo Pendiente", text="Saldo Pendiente", command=lambda: self.sort_column("Saldo Pendiente"))
        self.tree.heading("Fecha Creación", text="Fecha Creación", command=lambda: self.sort_column("Fecha Creación"))
        self.tree.heading("Fecha Modificación", text="Fecha Modificación", command=lambda: self.sort_column("Fecha Modificación"))
        self.tree.heading("Fecha Vencimiento", text="Fecha Vencimiento", command=lambda: self.sort_column("Fecha Vencimiento"))
        self.tree.heading("Estado", text="Estado", command=lambda: self.sort_column("Estado"))

        self.tree.column("ID", width=50)
        self.tree.column("Cliente", width=150)
        self.tree.column("Productos", width=100)
        self.tree.column("Anticipo", width=100)
        self.tree.column("Total", width=100)
        self.tree.column("Saldo Pendiente", width=100)
        self.tree.column("Fecha Creación", width=100)
        self.tree.column("Fecha Modificación", width=100)
        self.tree.column("Fecha Vencimiento", width=100)
        self.tree.column("Estado", width=100)

        self.tree.tag_configure("activo", background="#90EE90")
        self.tree.tag_configure("venciendo", background="#FF0000")

        self.v_scrollbar = ttk.Scrollbar(self.tree_container, orient="vertical", command=self.tree.yview)
        self.v_scrollbar.pack(side="right", fill="y")
        self.h_scrollbar = ttk.Scrollbar(self.tree_container, orient="horizontal", command=self.tree.xview)
        self.h_scrollbar.pack(side="bottom", fill="x")
        self.tree.configure(yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)

        logging.debug("Treeview configurado con tags activo y venciendo")

    def _setup_action_buttons(self):
        """Configura los botones de acción para el manejo de apartados."""
        buttons_container = ctk.CTkFrame(self.tree_frame, fg_color="transparent")
        buttons_container.pack(side="right", padx=5)

        buttons = [
            {"text": "Completar Apartado", "command": self.action_callbacks.get("completar", lambda: None), "icon": "✅"},
            {"text": "Cancelar Apartado", "command": self.action_callbacks.get("cancelar", lambda: None), "icon": "❌"},
            {"text": "Extender Apartado", "command": self.action_callbacks.get("extender", lambda: None), "icon": "📅"},
            {"text": "Agregar Anticipo", "command": self.action_callbacks.get("agregar_anticipo", lambda: None), "icon": "💰"},
            {"text": "Modificar Productos", "command": self.action_callbacks.get("modificar_productos", lambda: None), "icon": "🛠"},
            {"text": "Ver Detalles", "command": self.action_callbacks.get("ver_detalles", lambda: None), "icon": "🔍"},
            {"text": "Enviar Recordatorio", "command": self.action_callbacks.get("enviar_recordatorio", lambda: None), "icon": "📨"}
        ]

        for btn_info in buttons:
            card_frame = ctk.CTkFrame(
                buttons_container,
                corner_radius=10,
                border_width=2,
                border_color="#1f6aa5",
                fg_color="white" if CONFIG["THEME_MODE"] == "light" else "#2b2b2b"
            )
            card_frame.pack(pady=5)

            button = ctk.CTkButton(
                card_frame,
                text=f"{btn_info['icon']} {btn_info['text']}",
                command=btn_info['command'],
                width=150,
                height=40,
                font=("Arial", 14),
                corner_radius=8,
                hover_color="#4a90e2" if CONFIG["THEME_MODE"] == "light" else "#1f6aa5"
            )
            button.pack(padx=5, pady=5)

        logging.debug("Botones de acción configurados")

    def _setup_paginator(self):
        """Configura el paginador para la navegación de apartados."""
        from src.core.utils.pagination import Paginator
        self.apartados_paginator = Paginator(self.tab, self.items_per_page, self.cargar_apartados_callback)
        self.apartados_paginator.pack(fill="x", pady=5)
        logging.debug("Paginador configurado")

    def sort_column(self, col):
        """Ordena las columnas del Treeview."""
        items = [(self.tree.item(item, "values"), item) for item in self.tree.get_children()]
        if self.sort_column_name == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_reverse = False
            self.sort_column_name = col
        col_index = self.tree["columns"].index(col)

        def get_sort_key(x):
            value = x[0][col_index]
            if col in ("Anticipo", "Total", "Saldo Pendiente"):
                try:
                    return float(value.replace("$", ""))
                except ValueError:
                    return 0.0
            return value

        items.sort(key=get_sort_key, reverse=self.sort_reverse)
        for item in self.tree.get_children():
            self.tree.delete(item)
        for values, item_id in items:
            tags = ("venciendo",) if self.tree.item(item_id, "tags") else ()
            self.tree.insert("", "end", values=values, tags=tags)

    def update_notif_label(self, count):
        """Actualiza la etiqueta de notificación con el número de apartados por vencer."""
        self.notif_label.configure(
            text=f"Apartados por vencer (próximos {self.dias_vencimiento_filtro} días): {count}"
        )