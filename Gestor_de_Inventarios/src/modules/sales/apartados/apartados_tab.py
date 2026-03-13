import logging
from .apartados_ui import ApartadosUI
from .apartados_data import ApartadosData
from .apartados_actions import ApartadosActions

logger = logging.getLogger(__name__)

class ApartadosTab:
    def __init__(self, tab, db_manager, logic, root, user_id, store_id=1, items_per_page=20):
        self.tab = tab
        self.db_manager = db_manager
        self.logic = logic
        self.root = root
        self.user_id = user_id
        self.store_id = store_id
        self.items_per_page = items_per_page

        # Inicializar módulos en el orden correcto
        self.data = ApartadosData(self.db_manager, None, self.items_per_page, store_id=self.store_id)
        self.ui = ApartadosUI(
            tab=self.tab,
            root=self.root,
            items_per_page=self.items_per_page,
            store_id=self.store_id,
            cargar_apartados_callback=lambda page: self.data.cargar_apartados_paginated(page),
            buscar_apartados_callback=self.data.buscar_apartados,
            action_callbacks={
                "completar": lambda: self.actions.completar_apartado(),
                "cancelar": lambda: self.actions.cancelar_apartado(),
                "extender": lambda: self.actions.extender_apartado(),
                "agregar_anticipo": lambda: self.actions.agregar_anticipo(),
                "modificar_productos": lambda: self.actions.modificar_productos(),
                "ver_detalles": lambda: self.actions.ver_detalles(),
                "enviar_recordatorio": lambda: self.actions.enviar_recordatorio()
            }
        )
        self.data.ui = self.ui
        self.actions = ApartadosActions(self.root, self.db_manager, self.logic, self.ui, self.data, store_id=self.store_id)

        self.setup_ui()
        logger.info(f"Pestaña Apartados inicializada para usuario con ID '{self.user_id}' en tienda {self.store_id}.")

    def setup_ui(self):
        """Inicializa la interfaz de usuario."""
        self.ui.setup_ui(self.data.actualizar_dias_vencimiento)
        self.db_manager.verificar_apartados_vencidos(store_id=self.store_id)
        self.data.cargar_apartados_paginated(page=1)