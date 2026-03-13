import customtkinter as ctk
from tkinter import ttk, messagebox
import logging

logger = logging.getLogger(__name__)

def mostrar_ventana_seleccion(parent, title, items, columns, column_widths, on_select_callback):
    """
    Muestra una ventana modal con una tabla de elementos para que el usuario seleccione uno.

    Args:
        parent: Ventana padre (CTkToplevel o CTk).
        title (str): Título de la ventana.
        items (list): Lista de elementos a mostrar (cada elemento es un dict con claves que coinciden con columns).
        columns (list): Lista de nombres de columnas (por ejemplo, ["ID", "Nombre", "Teléfono"]).
        column_widths (dict): Diccionario con los anchos de las columnas (por ejemplo, {"ID": 50, "Nombre": 250}).
        on_select_callback (callable): Función a llamar cuando se selecciona un elemento, recibe el elemento seleccionado como argumento.
    """
    dialog = ctk.CTkToplevel(parent)
    dialog.title(title)
    dialog.geometry("600x400")
    dialog.transient(parent)
    dialog.grab_set()

    # Lista original de elementos para filtrar
    items_originales = items.copy()

    # Campo de búsqueda para filtrar dinámicamente
    search_frame = ctk.CTkFrame(dialog)
    search_frame.pack(fill="x", padx=10, pady=5)
    ctk.CTkLabel(search_frame, text="Filtrar:", font=("Arial", 12, "bold")).pack(side="left", padx=5)
    entry_busqueda = ctk.CTkEntry(search_frame, width=250)
    entry_busqueda.pack(side="left", padx=5)

    # Tabla para mostrar los elementos
    tree_frame = ctk.CTkFrame(dialog)
    tree_frame.pack(fill="both", expand=True, padx=10, pady=5)

    tree = ttk.Treeview(
        tree_frame,
        columns=columns,
        show="headings",
        height=10
    )
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=column_widths.get(col, 100))
    tree.pack(fill="both", expand=True)

    # Método para actualizar la tabla con los elementos filtrados
    def filtrar_items(event=None):
        query = entry_busqueda.get().strip().lower()
        tree.delete(*tree.get_children())  # Limpiar la tabla
        items_filtrados = [
            item for item in items_originales
            if any(query in str(value).lower() for value in item.values())
        ]
        for item in items_filtrados:
            values = [item.get(col, "N/A") for col in columns]
            tree.insert("", "end", values=values)

    # Vincular la búsqueda dinámica al evento KeyRelease
    entry_busqueda.bind("<KeyRelease>", filtrar_items)

    # Llenar la tabla inicialmente con todos los elementos
    for item in items:
        values = [item.get(col, "N/A") for col in columns]
        tree.insert("", "end", values=values)

    button_frame = ctk.CTkFrame(dialog)
    button_frame.pack(fill="x", padx=10, pady=5)

    def seleccionar_item():
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Selección", "Seleccione un elemento para continuar.")
            return
        item_values = tree.item(selected[0])['values']
        selected_item = {columns[i]: item_values[i] for i in range(len(columns))}
        on_select_callback(selected_item)
        dialog.destroy()

    ctk.CTkButton(button_frame, text="Seleccionar", command=seleccionar_item, fg_color="#4CAF50", hover_color="#45A049").pack(side="left", padx=5)
    ctk.CTkButton(button_frame, text="Cancelar", command=dialog.destroy, fg_color="#F44336", hover_color="#D32F2F").pack(side="left", padx=5)

    entry_busqueda.focus_set()