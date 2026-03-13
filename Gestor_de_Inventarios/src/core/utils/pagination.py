import customtkinter as ctk
import logging

logger = logging.getLogger(__name__)

class Paginator:
    def __init__(self, parent, items_per_page, load_callback):
        """
        Gestiona la paginación de una lista de elementos.

        Args:
            parent: Widget padre donde se mostrarán los controles de paginación.
            items_per_page (int): Número de elementos por página.
            load_callback (callable): Función para cargar los elementos de una página específica.
                                      Recibe el número de página como argumento.
        """
        self.parent = parent
        self.items_per_page = items_per_page
        self.load_callback = load_callback
        self.current_page = 1
        self.total_items = 0
        self.total_pages = 1

        # UI para controles de paginación
        self.pagination_frame = ctk.CTkFrame(self.parent)
        self.prev_button = ctk.CTkButton(self.pagination_frame, text="Anterior", command=self.prev_page)
        self.prev_button.pack(side="left", padx=5)
        self.page_label = ctk.CTkLabel(self.pagination_frame, text="Página 1 de 1")
        self.page_label.pack(side="left", padx=5)
        self.next_button = ctk.CTkButton(self.pagination_frame, text="Siguiente", command=self.next_page)
        self.next_button.pack(side="left", padx=5)

    def set_total_items(self, total_items):
        """Configura el número total de elementos y calcula las páginas."""
        self.total_items = total_items
        self.total_pages = max(1, (self.total_items + self.items_per_page - 1) // self.items_per_page)
        self.current_page = min(self.current_page, self.total_pages)
        self.update_ui()

    def get_offset(self):
        """Devuelve el desplazamiento (OFFSET) para la consulta SQL."""
        return (self.current_page - 1) * self.items_per_page

    def prev_page(self):
        """Navega a la página anterior."""
        if self.current_page > 1:
            self.current_page -= 1
            self.load_callback(self.current_page)
            self.update_ui()

    def next_page(self):
        """Navega a la página siguiente."""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_callback(self.current_page)
            self.update_ui()

    def update_ui(self):
        """Actualiza los controles de paginación."""
        self.page_label.configure(text=f"Página {self.current_page} de {self.total_pages}")
        self.prev_button.configure(state="normal" if self.current_page > 1 else "disabled")
        self.next_button.configure(state="normal" if self.current_page < self.total_pages else "disabled")

    def pack(self, **kwargs):
        """Empaqueta el frame de paginación."""
        self.pagination_frame.pack(**kwargs)