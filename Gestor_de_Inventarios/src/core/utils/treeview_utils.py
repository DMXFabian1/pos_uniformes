from tkinter import ttk

def apply_treeview_styles(tree, items_data, inventory_column="inventario", low_inventory_threshold=5):
    """
    Aplica estilos condicionales y alternados a las filas del Treeview.

    Args:
        tree (ttk.Treeview): El widget Treeview.
        items_data (list): Lista de datos de los ítems (valores de las filas).
        inventory_column (str): Nombre de la columna de inventario.
        low_inventory_threshold (int): Umbral para considerar inventario bajo.
    """
    # Configurar tags para estilos
    tree.tag_configure("low_inventory", foreground="#FF5555")  # Rojo para inventario bajo
    tree.tag_configure("normal_inventory", foreground="#1A2E5A")  # Azul oscuro para normal
    tree.tag_configure("evenrow", background="#F5F7FA")  # Gris claro para filas pares
    tree.tag_configure("oddrow", background="#FFFFFF")  # Blanco para filas impares

    # Limpiar ítems existentes
    tree.delete(*tree.get_children())

    # Insertar ítems con estilos condicionales
    for index, item in enumerate(items_data):
        # Determinar el tag de inventario
        try:
            inventory = float(item[tree["columns"].index(inventory_column)])
            inventory_tag = "low_inventory" if inventory < low_inventory_threshold else "normal_inventory"
        except (ValueError, IndexError):
            inventory_tag = "normal_inventory"

        # Determinar el tag de fila
        row_tag = "evenrow" if index % 2 == 0 else "oddrow"

        # Insertar el ítem con los tags combinados
        tree.insert("", "end", values=item, tags=(inventory_tag, row_tag))