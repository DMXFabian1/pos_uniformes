import os
import tkinter as tk
from tkinter import messagebox, ttk
import customtkinter as ctk
from src.core.config.config import CONFIG, exportar_configuraciones
from src.modules.products.qr_generator import generate_product_labels
from src.core.config.db_manager import DatabaseManager
from src.core.utils.utils import sanitize_filename
from src.core.backup.backup_manager import BackupManager
from datetime import datetime
from src.ui.ui_components import create_treeview
import logging

class MaintenanceTool:
    def __init__(self, app):
        try:
            logging.info("Iniciando MaintenanceTool")
            print("Iniciando MaintenanceTool")
            self.app = app
            self.store_id = getattr(app, 'store_id', 1)  # Heredar store_id de app, con valor por defecto 1
            self.root = app.parent
            if not hasattr(app, 'db_path') or not hasattr(app, 'root_folder'):
                raise ValueError("El objeto app debe tener db_path y root_folder definidos")
            self.backups_folder = os.path.join(app.root_folder, CONFIG["BACKUPS_DIR"])
            try:
                self.backup_manager = BackupManager(app.db_path, config={
                    "max_backups": 15,
                    "backup_filename_format": "productos_backup_{prefix}_{reason}_{timestamp}.db"
                })
            except Exception as e:
                logging.error(f"Error al inicializar BackupManager para tienda {self.store_id}: {str(e)}")
                messagebox.showerror("Error", f"No se pudo inicializar BackupManager: {str(e)}")
                raise
            self.window = ctk.CTkToplevel(self.root)
            self.window.title("Mantenimiento del Programa")
            self.window.geometry("1200x700")
            self.window.configure(fg_color="#E6F0FA")
            self.window.transient(self.root)
            self.window.grab_set()
            logging.info(f"Ventana de mantenimiento creada para tienda {self.store_id}")
            print(f"Ventana de mantenimiento creada para tienda {self.store_id}")
            self.setup_ui()
        except Exception as e:
            logging.error(f"Error en inicialización de MaintenanceTool para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo inicializar la ventana de mantenimiento: {str(e)}")
            raise

    def setup_ui(self):
        try:
            logging.info(f"Iniciando setup_ui para tienda {self.store_id}")
            print(f"Iniciando setup_ui para tienda {self.store_id}")
            main_frame = ctk.CTkFrame(self.window, fg_color="#FFFFFF", corner_radius=10, border_width=1, border_color="#A3BFFA")
            main_frame.pack(padx=20, pady=20, fill="both", expand=True)
            logging.info("Main frame creado")
            print("Main frame creado")

            title_frame = ctk.CTkFrame(main_frame, fg_color="#003087", corner_radius=0)
            title_frame.pack(fill="x")
            ctk.CTkLabel(title_frame, text="Mantenimiento del Programa", font=("Helvetica", 20, "bold"), text_color="#FFFFFF").pack(pady=10)
            logging.info("Title frame creado")
            print("Title frame creado")

            content_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            content_frame.pack(fill="both", expand=True, padx=15, pady=5)
            logging.info("Content frame creado")
            print("Content frame creado")

            style = ttk.Style()
            style.configure("TNotebook", background="#E6F0FA")
            style.configure("TNotebook.Tab", font=("Helvetica", 12, "bold"), padding=[10, 5], background="#4A90E2", foreground="#1A2E5A")
            style.map("TNotebook.Tab", background=[("selected", "#2A6EBB")], foreground=[("selected", "#E6F0FA")])
            notebook = ttk.Notebook(content_frame)
            notebook.pack(fill="both", expand=True)
            logging.info("Notebook creado")
            print("Notebook creado")

            data_frame = ctk.CTkFrame(notebook, fg_color="transparent")
            notebook.add(data_frame, text="Corrección de Config y Datos")
            self.setup_data_correction(data_frame)
            logging.info("Data correction tab creada")
            print("Data correction tab creada")

            incomplete_frame = ctk.CTkFrame(notebook, fg_color="transparent")
            notebook.add(incomplete_frame, text="Datos Incompletos")
            self.setup_incomplete_data(incomplete_frame)
            logging.info("Incomplete data tab creada")
            print("Incomplete data tab creada")

            qr_frame = ctk.CTkFrame(notebook, fg_color="transparent")
            notebook.add(qr_frame, text="Mantenimiento de QR")
            self.setup_qr_maintenance(qr_frame)
            logging.info("QR maintenance tab creada")
            print("QR maintenance tab creada")

            config_frame = ctk.CTkFrame(notebook, fg_color="transparent")
            notebook.add(config_frame, text="Revisión de Config")
            self.setup_config_revision(config_frame)
            logging.info("Config revision tab creada")
            print("Config revision tab creada")

            backup_frame = ctk.CTkFrame(notebook, fg_color="transparent")
            notebook.add(backup_frame, text="Copias de Seguridad")
            self.setup_backup_management(backup_frame)
            logging.info("Backup management tab creada")
            print("Backup management tab creada")

            button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
            button_frame.pack(fill="x", pady=(0, 10))
            ctk.CTkButton(button_frame, text="Cerrar", command=self.window.destroy, fg_color="#FF4C4C", hover_color="#CC3D3D", corner_radius=8, width=120, font=("Helvetica", 12)).pack(side="right", padx=15)
            logging.info("Button frame creado")
            print("Button frame creado")
        except Exception as e:
            logging.error(f"Error en setup_ui para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo configurar la interfaz de mantenimiento: {str(e)}")
            raise

    def setup_data_correction(self, frame):
        try:
            logging.info(f"Configurando pestaña de corrección de datos para tienda {self.store_id}")
            tree_frame = ctk.CTkFrame(frame, fg_color="transparent")
            tree_frame.pack(fill="both", expand=True, padx=15, pady=(10, 5))

            columns = ["tipo", "valor", "acción"]
            self.data_tree = create_treeview(tree_frame, columns, columns)
            self.data_tree.pack(side="left", fill="both", expand=True)

            self.data_tree.column("tipo", width=150)
            self.data_tree.column("valor", width=300)
            self.data_tree.column("acción", width=150)

            scrollbar = ctk.CTkScrollbar(tree_frame, command=self.data_tree.yview)
            scrollbar.pack(side="right", fill="y")
            self.data_tree.configure(yscrollcommand=scrollbar.set)

            button_frame = ctk.CTkFrame(frame, fg_color="transparent")
            button_frame.pack(fill="x", pady=(5, 10), padx=15)

            ctk.CTkButton(button_frame, text="Cargar Valores", command=self.load_config_values, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12)).pack(side="left", padx=5)
            ctk.CTkButton(button_frame, text="Editar Seleccionado", command=self.edit_config_value, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12)).pack(side="left", padx=5)
            ctk.CTkButton(button_frame, text="Eliminar Seleccionado", command=self.delete_config_value, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12)).pack(side="left", padx=5)
            logging.info("Pestaña de corrección de datos configurada")
        except Exception as e:
            logging.error(f"Error en setup_data_correction para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo configurar la pestaña de corrección de datos: {str(e)}")
            raise

    def setup_incomplete_data(self, frame):
        try:
            logging.info(f"Configurando pestaña de datos incompletos para tienda {self.store_id}")
            tree_frame = ctk.CTkFrame(frame, fg_color="transparent")
            tree_frame.pack(fill="both", expand=True, padx=15, pady=(10, 5))

            columns = ["sku", "nombre", "campos_faltantes"]
            self.incomplete_tree = create_treeview(tree_frame, columns, columns)
            self.incomplete_tree.pack(side="left", fill="both", expand=True)

            self.incomplete_tree.column("sku", width=200)
            self.incomplete_tree.column("nombre", width=300)
            self.incomplete_tree.column("campos_faltantes", width=400)

            scrollbar = ctk.CTkScrollbar(tree_frame, command=self.incomplete_tree.yview)
            scrollbar.pack(side="right", fill="y")
            self.incomplete_tree.configure(yscrollcommand=scrollbar.set)

            button_frame = ctk.CTkFrame(frame, fg_color="transparent")
            button_frame.pack(fill="x", pady=(5, 10), padx=15)

            ctk.CTkButton(button_frame, text="Cargar Incompletos", command=self.load_incomplete_products, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12)).pack(side="left", padx=5)
            ctk.CTkButton(button_frame, text="Completar Seleccionado", command=self.complete_product, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12)).pack(side="left", padx=5)
            logging.info("Pestaña de datos incompletos configurada")
        except Exception as e:
            logging.error(f"Error en setup_incomplete_data para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo configurar la pestaña de datos incompletos: {str(e)}")
            raise

    def setup_qr_maintenance(self, frame):
        try:
            logging.info(f"Configurando pestaña de mantenimiento de QR para tienda {self.store_id}")
            tree_frame = ctk.CTkFrame(frame, fg_color="transparent")
            tree_frame.pack(fill="both", expand=True, padx=15, pady=(10, 5))

            columns = ["sku", "nombre", "estado_qr"]
            self.qr_tree = create_treeview(tree_frame, columns, columns)
            self.qr_tree.pack(side="left", fill="both", expand=True)

            self.qr_tree.column("sku", width=200)
            self.qr_tree.column("nombre", width=300)
            self.qr_tree.column("estado_qr", width=400)

            scrollbar = ctk.CTkScrollbar(tree_frame, command=self.qr_tree.yview)
            scrollbar.pack(side="right", fill="y")
            self.qr_tree.configure(yscrollcommand=scrollbar.set)

            button_frame = ctk.CTkFrame(frame, fg_color="transparent")
            button_frame.pack(fill="x", pady=(5, 10), padx=15)

            ctk.CTkButton(button_frame, text="Cargar QR Problemas", command=self.load_qr_issues, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12)).pack(side="left", padx=5)
            ctk.CTkButton(button_frame, text="Regenerar Seleccionados", command=self.regenerate_qr, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12)).pack(side="left", padx=5)
            logging.info("Pestaña de mantenimiento de QR configurada")
        except Exception as e:
            logging.error(f"Error en setup_qr_maintenance para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo configurar la pestaña de mantenimiento de QR: {str(e)}")
            raise

    def setup_config_revision(self, frame):
        try:
            logging.info(f"Configurando pestaña de revisión de config para tienda {self.store_id}")
            tree_frame = ctk.CTkFrame(frame, fg_color="transparent")
            tree_frame.pack(fill="both", expand=True, padx=15, pady=(10, 5))

            columns = ["sku", "nombre", "campo", "valor_actual", "valor_config"]
            self.config_tree = create_treeview(tree_frame, columns, columns)
            self.config_tree.pack(side="left", fill="both", expand=True)

            self.config_tree.column("sku", width=150)
            self.config_tree.column("nombre", width=250)
            self.config_tree.column("campo", width=200)
            self.config_tree.column("valor_actual", width=200)
            self.config_tree.column("valor_config", width=200)

            scrollbar = ctk.CTkScrollbar(tree_frame, command=self.config_tree.yview)
            scrollbar.pack(side="right", fill="y")
            self.config_tree.configure(yscrollcommand=scrollbar.set)

            button_frame = ctk.CTkFrame(frame, fg_color="transparent")
            button_frame.pack(fill="x", pady=(5, 10), padx=15)

            ctk.CTkButton(button_frame, text="Cargar Config Problemas", command=self.load_config_issues, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12)).pack(side="left", padx=5)
            ctk.CTkButton(button_frame, text="Actualizar Seleccionados", command=self.update_config_values, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12)).pack(side="left", padx=5)
            logging.info("Pestaña de revisión de config configurada")
        except Exception as e:
            logging.error(f"Error en setup_config_revision para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo configurar la pestaña de revisión de config: {str(e)}")
            raise

    def setup_backup_management(self, frame):
        try:
            logging.info(f"Configurando pestaña de copias de seguridad para tienda {self.store_id}")
            tree_frame = ctk.CTkFrame(frame, fg_color="transparent")
            tree_frame.pack(fill="both", expand=True, padx=15, pady=(10, 5))

            columns = ["tipo", "nombre", "fecha"]
            self.backup_tree = create_treeview(tree_frame, columns, columns)
            self.backup_tree.pack(side="left", fill="both", expand=True)

            self.backup_tree.column("tipo", width=150)
            self.backup_tree.column("nombre", width=400)
            self.backup_tree.column("fecha", width=200)

            scrollbar = ctk.CTkScrollbar(tree_frame, command=self.backup_tree.yview)
            scrollbar.pack(side="right", fill="y")
            self.backup_tree.configure(yscrollcommand=scrollbar.set)

            button_frame = ctk.CTkFrame(frame, fg_color="transparent")
            button_frame.pack(fill="x", pady=(5, 10), padx=15)

            ctk.CTkButton(button_frame, text="Crear Copia de Seguridad", command=self.create_manual_backup, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12)).pack(side="left", padx=5)
            ctk.CTkButton(button_frame, text="Restaurar Copia Seleccionada", command=self.restore_backup, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12)).pack(side="left", padx=5)
            ctk.CTkButton(button_frame, text="Eliminar Copia Seleccionada", command=self.delete_backup, fg_color="#FF4C4C", hover_color="#CC3D3D", corner_radius=8, width=120, font=("Helvetica", 12)).pack(side="left", padx=5)

            self.load_backups()
            logging.info("Pestaña de copias de seguridad configurada")
        except Exception as e:
            logging.error(f"Error en setup_backup_management para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo configurar la pestaña de copias de seguridad: {str(e)}")
            raise

    def load_config_values(self):
        try:
            logging.info(f"Cargando valores de configuración para tienda {self.store_id}")
            for item in self.data_tree.get_children():
                self.data_tree.delete(item)
            for tipo, valores in [
                ("Nivel Educativo", CONFIG["NIVELES_EDUCATIVOS"]),
                ("Color", CONFIG["COLORES"]),
                ("Tipo Prenda", CONFIG["TIPOS_PRENDA"]),
                ("Tipo Pieza", CONFIG["TIPOS_PIEZA"]),
                ("Género", CONFIG["GENEROS"]),
                ("Atributo", CONFIG["ATRIBUTOS"]),
                ("Ubicación", CONFIG["UBICACIONES"]),
                ("Escudo", CONFIG["ESCUDOS"]),
                ("Marca", CONFIG["MARCAS"])
            ]:
                for valor in valores:
                    self.data_tree.insert("", "end", values=(tipo, valor, ""))
            logging.info("Valores de configuración cargados")
        except Exception as e:
            logging.error(f"Error en load_config_values para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo cargar valores de configuración: {str(e)}")

    def edit_config_value(self):
        try:
            logging.info(f"Botón Editar Seleccionado clicado para tienda {self.store_id}")
            selected = self.data_tree.selection()
            if not selected:
                messagebox.showwarning("Advertencia", "Selecciona un valor para editar.")
                logging.warning("No se seleccionó ningún valor para editar")
                return
            item = self.data_tree.item(selected[0])["values"]
            tipo, valor_antiguo = item[0], item[1]
            config_dict = {
                "Nivel Educativo": CONFIG["NIVELES_EDUCATIVOS"],
                "Color": CONFIG["COLORES"],
                "Tipo Prenda": CONFIG["TIPOS_PRENDA"],
                "Tipo Pieza": CONFIG["TIPOS_PIEZA"],
                "Género": CONFIG["GENEROS"],
                "Atributo": CONFIG["ATRIBUTOS"],
                "Ubicación": CONFIG["UBICACIONES"],
                "Escudo": CONFIG["ESCUDOS"],
                "Marca": CONFIG["MARCAS"]
            }[tipo]

            ventana = ctk.CTkToplevel(self.window)
            ventana.title(f"Editar {tipo}")
            ventana.geometry("400x200")
            ventana.configure(fg_color="#E6F0FA")
            ventana.transient(self.window)
            ventana.grab_set()

            ctk.CTkLabel(ventana, text=f"Editar {tipo} '{valor_antiguo}':", font=("Helvetica", 12), text_color="#1A2E5A").pack(pady=5)
            entry = ctk.CTkEntry(ventana, width=200, fg_color="#FFFFFF", border_color="#A3BFFA")
            entry.pack(pady=5)
            entry.insert(0, valor_antiguo)
            update_db_var = tk.BooleanVar(value=True)
            ctk.CTkCheckBox(ventana, text="Actualizar productos en la base de datos", variable=update_db_var, fg_color="#4A90E2", text_color="#4B5EAA").pack(pady=5)

            def guardar():
                try:
                    nuevo_valor = entry.get().strip()
                    if not nuevo_valor:
                        messagebox.showwarning("Advertencia", "El nuevo valor no puede estar vacío.")
                        logging.warning("Intento de guardar valor vacío")
                        return
                    if nuevo_valor == valor_antiguo:
                        ventana.destroy()
                        return
                    if valor_antiguo in config_dict:
                        index = config_dict.index(valor_antiguo)
                        config_dict[index] = nuevo_valor
                    exportar_configuraciones(CONFIG, os.path.join(CONFIG["ROOT_FOLDER"], "config.json"))
                    if update_db_var.get():
                        cursor = DatabaseManager().get_cursor()
                        campo = tipo.lower().replace(" ", "_")
                        cursor.execute(f"UPDATE productos SET {campo} = ? WHERE {campo} = ? AND store_id = ?", (nuevo_valor, valor_antiguo, self.store_id))
                        DatabaseManager().commit()
                    self.load_config_values()
                    messagebox.showinfo("Éxito", f"'{valor_antiguo}' cambiado a '{nuevo_valor}'.")
                    logging.info(f"Valor '{valor_antiguo}' cambiado a '{nuevo_valor}' en {tipo} para tienda {self.store_id}")
                    ventana.destroy()
                except Exception as e:
                    logging.error(f"Error en edit_config_value (guardar) para tienda {self.store_id}: {str(e)}")
                    messagebox.showerror("Error", f"No se pudo guardar el cambio: {str(e)}")

            ctk.CTkButton(ventana, text="Guardar", command=guardar, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12)).pack(pady=10)
        except Exception as e:
            logging.error(f"Error en edit_config_value para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo editar el valor: {str(e)}")

    def delete_config_value(self):
        try:
            logging.info(f"Botón Eliminar Seleccionado clicado para tienda {self.store_id}")
            selected = self.data_tree.selection()
            if not selected:
                messagebox.showwarning("Advertencia", "Selecciona un valor para eliminar.")
                logging.warning("No se seleccionó ningún valor para eliminar")
                return
            item = self.data_tree.item(selected[0])["values"]
            tipo, valor = item[0], item[1]
            config_dict = {
                "Nivel Educativo": CONFIG["NIVELES_EDUCATIVOS"],
                "Color": CONFIG["COLORES"],
                "Tipo Prenda": CONFIG["TIPOS_PRENDA"],
                "Tipo Pieza": CONFIG["TIPOS_PIEZA"],
                "Género": CONFIG["GENEROS"],
                "Atributo": CONFIG["ATRIBUTOS"],
                "Ubicación": CONFIG["UBICACIONES"],
                "Escudo": CONFIG["ESCUDOS"],
                "Marca": CONFIG["MARCAS"]
            }[tipo]

            ventana = ctk.CTkToplevel(self.window)
            ventana.title(f"Eliminar {tipo}")
            ventana.geometry("400x300")
            ventana.configure(fg_color="#E6F0FA")
            ventana.transient(self.window)
            ventana.grab_set()

            ctk.CTkLabel(ventana, text=f"Eliminar {tipo} '{valor}':", font=("Helvetica", 12), text_color="#1A2E5A").pack(pady=5)
            try:
                cursor = DatabaseManager().get_cursor()
                campo = tipo.lower().replace(" ", "_")
                cursor.execute(f"SELECT COUNT(*) FROM productos WHERE {campo} = ? AND store_id = ?", (valor, self.store_id))
                count = cursor.fetchone()[0]
                ctk.CTkLabel(ventana, text=f"Productos afectados: {count}", font=("Helvetica", 12), text_color="#4B5EAA").pack(pady=5)
            except Exception as e:
                logging.error(f"Error en delete_config_value (contar productos) para tienda {self.store_id}: {str(e)}")
                messagebox.showerror("Error", f"No se pudo contar productos afectados: {str(e)}")
                ventana.destroy()
                return

            opciones = ["Dejar vacío", "Reasignar a otro valor"]
            opcion_var = tk.StringVar(value=opciones[0])
            ctk.CTkOptionMenu(ventana, values=opciones, variable=opcion_var, fg_color="#FFFFFF", button_color="#4A90E2", button_hover_color="#2A6EBB").pack(pady=5)

            reasignar_frame = ctk.CTkFrame(ventana, fg_color="transparent")
            reasignar_frame.pack(pady=5)
            ctk.CTkLabel(reasignar_frame, text="Nuevo valor:", text_color="#1A2E5A").pack(side="left", padx=5)
            reasignar_entry = ctk.CTkComboBox(reasignar_frame, values=[""] + sorted(config_dict), state="disabled", fg_color="#FFFFFF", button_color="#4A90E2", button_hover_color="#2A6EBB")
            reasignar_entry.pack(side="left", padx=5)

            def toggle_reasignar(*args):
                reasignar_entry.configure(state="normal" if opcion_var.get() == "Reasignar a otro valor" else "disabled")

            opcion_var.trace("w", toggle_reasignar)

            def eliminar():
                try:
                    if not messagebox.askyesno("Confirmar", f"¿Eliminar '{valor}' de {tipo}?"):
                        logging.info("Eliminación cancelada por el usuario")
                        ventana.destroy()
                        return
                    if valor in config_dict:
                        config_dict.remove(valor)
                    exportar_configuraciones(CONFIG, os.path.join(CONFIG["ROOT_FOLDER"], "config.json"))
                    cursor = DatabaseManager().get_cursor()
                    if opcion_var.get() == "Reasignar a otro valor" and reasignar_entry.get():
                        nuevo_valor = reasignar_entry.get()
                        cursor.execute(f"UPDATE productos SET {campo} = ? WHERE {campo} = ? AND store_id = ?", (nuevo_valor, valor, self.store_id))
                    else:
                        cursor.execute(f"UPDATE productos SET {campo} = ? WHERE {campo} = ? AND store_id = ?", ("", valor, self.store_id))
                    DatabaseManager().commit()
                    self.load_config_values()
                    messagebox.showinfo("Éxito", f"'{valor}' eliminado de {tipo}.")
                    logging.info(f"Valor '{valor}' eliminado de {tipo} para tienda {self.store_id}")
                    ventana.destroy()
                except Exception as e:
                    logging.error(f"Error en delete_config_value (eliminar) para tienda {self.store_id}: {str(e)}")
                    messagebox.showerror("Error", f"No se pudo actualizar productos: {str(e)}")

            ctk.CTkButton(ventana, text="Eliminar", command=eliminar, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12)).pack(pady=10)
        except Exception as e:
            logging.error(f"Error en delete_config_value para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo eliminar el valor: {str(e)}")

    def load_incomplete_products(self):
        try:
            logging.info(f"Cargando productos incompletos para tienda {self.store_id}")
            for item in self.incomplete_tree.get_children():
                self.incomplete_tree.delete(item)
            cursor = DatabaseManager().get_cursor()
            cursor.execute("SELECT sku, nombre, nivel_educativo, color, tipo_prenda, tipo_pieza, genero, atributo, ubicacion, escudo, marca, image_path FROM productos WHERE (color = '' OR tipo_prenda = '' OR tipo_pieza = '') AND store_id = ?", (self.store_id,))
            productos = cursor.fetchall()
            for producto in productos:
                sku, nombre, nivel_educativo, color, tipo_prenda, tipo_pieza, genero, atributo, ubicacion, escudo, marca, image_path = producto
                missing = []
                if not color:
                    missing.append("Color")
                if not tipo_prenda:
                    missing.append("Tipo Prenda")
                if not tipo_pieza:
                    missing.append("Tipo Pieza")
                self.incomplete_tree.insert("", "end", values=(sku, nombre, ", ".join(missing)))
            logging.info(f"Productos incompletos cargados: {len(productos)} para tienda {self.store_id}")
        except Exception as e:
            logging.error(f"Error en load_incomplete_products para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo cargar productos incompletos: {str(e)}")

    def complete_product(self):
        try:
            logging.info(f"Botón Completar Seleccionado clicado para tienda {self.store_id}")
            selected = self.incomplete_tree.selection()
            if not selected:
                messagebox.showwarning("Advertencia", "Selecciona un producto para completar.")
                logging.warning("No se seleccionó ningún producto para completar")
                return
            item = self.incomplete_tree.item(selected[0])["values"]
            sku = item[0]

            cursor = DatabaseManager().get_cursor()
            cursor.execute("SELECT * FROM productos WHERE sku = ? AND store_id = ?", (sku, self.store_id))
            producto = cursor.fetchone()

            ventana = ctk.CTkToplevel(self.window)
            ventana.title(f"Completar Producto {sku}")
            ventana.geometry("400x300")
            ventana.configure(fg_color="#E6F0FA")
            ventana.transient(self.window)
            ventana.grab_set()

            fields = {"nivel_educativo": "Nivel Educativo", "color": "Color", "tipo_prenda": "Tipo Prenda", "tipo_pieza": "Tipo Pieza", "genero": "Género", "atributo": "Atributo", "ubicacion": "Ubicación", "escudo": "Escudo", "marca": "Marca"}
            entries = {}
            for i, (field, label) in enumerate(fields.items()):
                ctk.CTkLabel(ventana, text=f"{label}:", font=("Helvetica", 12), text_color="#1A2E5A").grid(row=i, column=0, padx=10, pady=5, sticky="e")
                entries[field] = ctk.CTkComboBox(ventana, values=[""] + sorted(CONFIG[field.upper() + "S"]), fg_color="#FFFFFF", button_color="#4A90E2", button_hover_color="#2A6EBB")
                entries[field].grid(row=i, column=1, padx=10, pady=5)
                entries[field].set(producto[fields_to_index[field]] or "")

            def guardar():
                try:
                    cursor = DatabaseManager().get_cursor()
                    cursor.execute("""
                        UPDATE productos SET 
                            nivel_educativo = ?, color = ?, tipo_prenda = ?, tipo_pieza = ?, 
                            genero = ?, atributo = ?, ubicacion = ?, escudo = ?, marca = ?
                        WHERE sku = ? AND store_id = ?
                    """, (entries["nivel_educativo"].get(), entries["color"].get(), entries["tipo_prenda"].get(), 
                          entries["tipo_pieza"].get(), entries["genero"].get(), entries["atributo"].get(), 
                          entries["ubicacion"].get(), entries["escudo"].get(), entries["marca"].get(), sku, self.store_id))
                    DatabaseManager().commit()
                    self.load_incomplete_products()
                    messagebox.showinfo("Éxito", f"Datos de {sku} completados.")
                    logging.info(f"Datos de producto {sku} completados para tienda {self.store_id}")
                    ventana.destroy()
                except Exception as e:
                    logging.error(f"Error en complete_product (guardar) para tienda {self.store_id}: {str(e)}")
                    messagebox.showerror("Error", f"No se pudo guardar los cambios: {str(e)}")

            ctk.CTkButton(ventana, text="Guardar", command=guardar, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12)).grid(row=len(fields), column=0, columnspan=2, pady=10)
        except Exception as e:
            logging.error(f"Error en complete_product para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo completar el producto: {str(e)}")

    def load_qr_issues(self):
        try:
            logging.info(f"Cargando problemas de QR para tienda {self.store_id}")
            for item in self.qr_tree.get_children():
                self.qr_tree.delete(item)
            cursor = DatabaseManager().get_cursor()
            cursor.execute("SELECT sku, nombre, qr_path FROM productos WHERE store_id = ?", (self.store_id,))
            productos = cursor.fetchall()
            for sku, nombre, qr_path in productos:
                estado = "OK"
                if not qr_path or not os.path.exists(os.path.join(self.app.root_folder, qr_path)):
                    estado = "Falta o no encontrado"
                    self.qr_tree.insert("", "end", values=(sku, nombre, estado))
            logging.info(f"Problemas de QR cargados: {len(productos)} para tienda {self.store_id}")
        except Exception as e:
            logging.error(f"Error en load_qr_issues para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo cargar problemas de QR: {str(e)}")

    def regenerate_qr(self):
        try:
            logging.info(f"Botón Regenerar Seleccionados clicado para tienda {self.store_id}")
            selected_items = self.qr_tree.selection()
            if not selected_items:
                messagebox.showwarning("Advertencia", "Selecciona al menos un producto para regenerar su código QR.")
                logging.warning("No se seleccionaron productos para regenerar QR")
                return

            if not messagebox.askyesno("Confirmar", f"¿Estás seguro de que deseas regenerar los códigos QR de {len(selected_items)} producto(s)?"):
                logging.info("Regeneración de QR cancelada por el usuario")
                return

            cursor = DatabaseManager().get_cursor()
            for item in selected_items:
                sku = self.qr_tree.item(item)["values"][0]
                cursor.execute("""
                    SELECT nombre, nivel_educativo, escuela, tipo_prenda, tipo_pieza, genero, talla, qr_path
                    FROM productos WHERE sku = ? AND store_id = ?
                """, (sku, self.store_id))
                producto = cursor.fetchone()
                if not producto:
                    continue

                nombre = producto[0]
                nivel_educativo = producto[1]
                escuela = producto[2]
                tipo_prenda = producto[3]
                tipo_pieza = producto[4]
                genero = producto[5]
                talla = producto[6]

                qr_path_relative, label_path_relative = generate_product_labels(
                    sku, escuela, nivel_educativo, nombre, talla, genero, 
                    self.app.qr_folder, tipo_prenda, tipo_pieza
                )

                cursor.execute("UPDATE productos SET qr_path = ? WHERE sku = ? AND store_id = ?", (label_path_relative, sku, self.store_id))

            DatabaseManager().commit()
            self.load_qr_issues()
            messagebox.showinfo("Éxito", f"Códigos QR regenerados para {len(selected_items)} producto(s).")
            logging.info(f"Códigos QR regenerados para {len(selected_items)} productos en tienda {self.store_id}")
        except Exception as e:
            logging.error(f"Error en regenerate_qr para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo regenerar los códigos QR: {str(e)}")

    def load_config_issues(self):
        try:
            logging.info(f"Cargando problemas de configuración para tienda {self.store_id}")
            for item in self.config_tree.get_children():
                self.config_tree.delete(item)
            cursor = DatabaseManager().get_cursor()
            cursor.execute("SELECT sku, nombre, nivel_educativo, color, tipo_prenda, tipo_pieza, genero, atributo, ubicacion, escudo, marca, image_path FROM productos WHERE store_id = ?", (self.store_id,))
            productos = cursor.fetchall()
            issues = []
            for producto in productos:
                sku, nombre, nivel_educativo, color, tipo_prenda, tipo_pieza, genero, atributo, ubicacion, escudo, marca, image_path = producto
                if nivel_educativo and nivel_educativo not in CONFIG["NIVELES_EDUCATIVOS"]:
                    issues.append((sku, nombre, "Nivel Educativo", nivel_educativo, "No en CONFIG"))
                if color and color not in CONFIG["COLORES"]:
                    issues.append((sku, nombre, "Color", color, "No en CONFIG"))
                if tipo_prenda and tipo_prenda not in CONFIG["TIPOS_PRENDA"]:
                    issues.append((sku, nombre, "Tipo Prenda", tipo_prenda, "No en CONFIG"))
                if tipo_pieza and tipo_pieza not in CONFIG["TIPOS_PIEZA"]:
                    issues.append((sku, nombre, "Tipo Pieza", tipo_pieza, "No en CONFIG"))
                if genero and genero not in CONFIG["GENEROS"]:
                    issues.append((sku, nombre, "Género", genero, "No en CONFIG"))
                if atributo and atributo not in CONFIG["ATRIBUTOS"]:
                    issues.append((sku, nombre, "Atributo", atributo, "No en CONFIG"))
                if ubicacion and ubicacion not in CONFIG["UBICACIONES"]:
                    issues.append((sku, nombre, "Ubicación", ubicacion, "No en CONFIG"))
                if escudo and escudo not in CONFIG["ESCUDOS"]:
                    issues.append((sku, nombre, "Escudo", escudo, "No en CONFIG"))
                if marca and marca not in CONFIG["MARCAS"]:
                    issues.append((sku, nombre, "Marca", marca, "No en CONFIG"))
            for issue in issues:
                self.config_tree.insert("", "end", values=issue)
            logging.info(f"Problemas de configuración cargados: {len(issues)} para tienda {self.store_id}")
        except Exception as e:
            logging.error(f"Error en load_config_issues para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo cargar problemas de config: {str(e)}")

    def update_config_values(self):
        try:
            logging.info(f"Botón Actualizar Seleccionados clicado para tienda {self.store_id}")
            selected = self.config_tree.selection()
            if not selected:
                messagebox.showwarning("Advertencia", "Selecciona valores para actualizar.")
                logging.warning("No se seleccionaron valores para actualizar")
                return
            cursor = DatabaseManager().get_cursor()
            updated = 0
            for item in selected:
                sku, _, campo, valor_antiguo, _ = self.config_tree.item(item)["values"]
                campo_lower = campo.lower().replace(" ", "_")
                config_dict = {
                    "nivel_educativo": CONFIG["NIVELES_EDUCATIVOS"],
                    "color": CONFIG["COLORES"],
                    "tipo_prenda": CONFIG["TIPOS_PRENDA"],
                    "tipo_pieza": CONFIG["TIPOS_PIEZA"],
                    "genero": CONFIG["GENEROS"],
                    "atributo": CONFIG["ATRIBUTOS"],
                    "ubicacion": CONFIG["UBICACIONES"],
                    "escudo": CONFIG["ESCUDOS"],
                    "marca": CONFIG["MARCAS"]
                }[campo_lower]
                new_value = tk.simpledialog.askstring("Actualizar Valor", f"Actualizar {campo} '{valor_antiguo}' a un valor de CONFIG:", initialvalue=valor_antiguo)
                if new_value and new_value in config_dict:
                    cursor.execute(f"UPDATE productos SET {campo_lower} = ? WHERE sku = ? AND store_id = ?", (new_value, sku, self.store_id))
                    updated += 1
            DatabaseManager().commit()
            self.load_config_issues()
            messagebox.showinfo("Éxito", f"{updated} valores actualizados a CONFIG.")
            logging.info(f"{updated} valores actualizados a CONFIG para tienda {self.store_id}")
        except Exception as e:
            logging.error(f"Error en update_config_values para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo actualizar los valores: {str(e)}")

    def load_backups(self):
        try:
            logging.info(f"Cargando copias de seguridad para tienda {self.store_id}")
            for item in self.backup_tree.get_children():
                self.backup_tree.delete(item)
            backups = self.backup_manager.list_backups()
            for backup_type, backup_filename, creation_time in backups:
                self.backup_tree.insert("", "end", values=(backup_type, backup_filename, creation_time))
            logging.info(f"Copias de seguridad cargadas: {len(backups)} para tienda {self.store_id}")
        except Exception as e:
            logging.error(f"Error en load_backups para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo cargar copias de seguridad: {str(e)}")

    def create_manual_backup(self):
        try:
            logging.info(f"Botón Crear Copia de Seguridad clicado para tienda {self.store_id}")
            backup_path = self.backup_manager.create_backup(reason="manual")
            if backup_path:
                messagebox.showinfo("Éxito", f"Copia de seguridad creada: {os.path.basename(backup_path)}")
                self.load_backups()
                logging.info(f"Copia de seguridad creada: {os.path.basename(backup_path)} para tienda {self.store_id}")
        except Exception as e:
            logging.error(f"Error en create_manual_backup para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo crear copia de seguridad: {str(e)}")

    def restore_backup(self):
        try:
            logging.info(f"Botón Restaurar Copia Seleccionada clicado para tienda {self.store_id}")
            selected = self.backup_tree.selection()
            if not selected:
                messagebox.showwarning("Advertencia", "Selecciona una copia de seguridad para restaurar.")
                logging.warning("No se seleccionó ninguna copia de seguridad para restaurar")
                return
            backup_type, backup_filename, _ = self.backup_tree.item(selected[0])["values"]

            if not messagebox.askyesno("Confirmar", f"¿Estás seguro de que deseas restaurar la copia de seguridad '{backup_filename}' ({backup_type})? Esto sobrescribirá la base de datos actual."):
                logging.info("Restauración cancelada por el usuario")
                return

            self.backup_manager.restore_backup(backup_type, backup_filename)
            messagebox.showinfo("Éxito", f"Base de datos restaurada desde: {backup_filename} ({backup_type})")
            self.load_backups()
            logging.info(f"Base de datos restaurada: {backup_filename} ({backup_type}) para tienda {self.store_id}")
        except Exception as e:
            logging.error(f"Error en restore_backup para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo restaurar la copia de seguridad: {str(e)}")

    def delete_backup(self):
        try:
            logging.info(f"Botón Eliminar Copia Seleccionada clicado para tienda {self.store_id}")
            selected = self.backup_tree.selection()
            if not selected:
                messagebox.showwarning("Advertencia", "Selecciona una copia de seguridad para eliminar.")
                logging.warning("No se seleccionó ninguna copia de seguridad para eliminar")
                return
            backup_type, backup_filename, _ = self.backup_tree.item(selected[0])["values"]

            if not messagebox.askyesno("Confirmar", f"¿Estás seguro de que deseas eliminar la copia de seguridad '{backup_filename}' ({backup_type})?"):
                logging.info("Eliminación de copia de seguridad cancelada por el usuario")
                return

            self.backup_manager.delete_backup(backup_type, backup_filename)
            messagebox.showinfo("Éxito", f"Copia de seguridad eliminada: {backup_filename} ({backup_type})")
            self.load_backups()
            logging.info(f"Copia de seguridad eliminada: {backup_filename} ({backup_type}) para tienda {self.store_id}")
        except Exception as e:
            logging.error(f"Error en delete_backup para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"No se pudo eliminar la copia de seguridad: {str(e)}")

def abrir_mantenimiento(app):
    try:
        logging.info(f"Ejecutando abrir_mantenimiento para tienda {getattr(app, 'store_id', 1)}")
        print(f"Ejecutando abrir_mantenimiento para tienda {getattr(app, 'store_id', 1)}")
        MaintenanceTool(app)
        logging.info("MaintenanceTool inicializado")
        print("MaintenanceTool inicializado")
    except Exception as e:
        logging.error(f"Error en abrir_mantenimiento para tienda {getattr(app, 'store_id', 1)}: {str(e)}")
        messagebox.showerror("Error", f"No se pudo abrir la ventana de mantenimiento: {str(e)}")

# Definición de fields_to_index
fields_to_index = {
    "nivel_educativo": 2,
    "color": 4,
    "tipo_prenda": 5,
    "tipo_pieza": 6,
    "genero": 7,
    "atributo": 8,
    "ubicacion": 9,
    "escudo": 10,
    "marca": 11
}