import pandas as pd
import sqlite3
import os
import logging
import customtkinter as ctk
from threading import Thread
from datetime import datetime
import unicodedata
import json
from tkinter import filedialog, messagebox
from src.core.config.config import CONFIG
from src.core.utils.tooltips import ToolTip
import platform

# Configurar logging
os.makedirs(CONFIG['LOGS_DIR'], exist_ok=True)
log_file = os.path.join(CONFIG['LOGS_DIR'], f"sync_log_{datetime.now().strftime('%Y%m%d')}.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Rutas para los archivos (relativas al directorio raíz)
SYNC_DIR = os.path.join(CONFIG['ROOT_FOLDER'], CONFIG['SYNC_REPORTS_DIR'])
os.makedirs(SYNC_DIR, exist_ok=True)
DOWNLOADS_PATH = os.path.join(SYNC_DIR, "Maximoda_Inventarios_Sync.xlsx")
LAST_EXPORT_DATA_PATH = os.path.join(SYNC_DIR, "last_export_data.json")

class Synchronizer:
    def __init__(self, parent, icons, db_manager, store_id=1):
        self.parent = parent
        self.icons = icons
        self.db_manager = db_manager
        self.store_id = store_id
        self.main_frame = ctk.CTkFrame(parent, fg_color="transparent")
        self.store_ids = self.get_store_ids()
        self.setup_ui()
        self.bind_shortcuts()

    def get_store_ids(self):
        """Obtiene los store_ids disponibles desde contador_sku."""
        try:
            conn = sqlite3.connect(CONFIG['DB_PATH'])
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT store_id FROM contador_sku")
            store_ids = [row[0] for row in cursor.fetchall()]
            conn.close()
            return store_ids if store_ids else [1]
        except sqlite3.Error as e:
            logger.error(f"Error al obtener store_ids: {e}")
            return [1]

    def get_thread_safe_connection(self):
        """Crea una conexión SQLite específica para el hilo actual."""
        return sqlite3.connect(CONFIG['DB_PATH'], check_same_thread=False)

    def setup_ui(self):
        """Configura la interfaz del módulo de sincronización."""
        # Título
        title_label = ctk.CTkLabel(
            self.main_frame, text="Sincronización con ELEventas",
            font=("Helvetica", 24, "bold"), text_color="#003087"
        )
        title_label.pack(pady=(20, 10))

        # Selección de store_id
        store_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        store_frame.pack(pady=10)
        store_label = ctk.CTkLabel(store_frame, text="Tienda:", font=("Helvetica", 14))
        store_label.pack(side="left", padx=5)
        self.store_combobox = ctk.CTkComboBox(
            store_frame, values=[str(id) for id in self.store_ids],
            command=self.update_store_id, width=100,
            font=("Helvetica", 12)
        )
        self.store_combobox.set(str(self.store_id))
        self.store_combobox.pack(side="left", padx=5)
        ToolTip(self.store_combobox, "Selecciona la tienda para sincronizar datos")

        # Botones
        button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        button_frame.pack(pady=20)

        self.export_all_button = ctk.CTkButton(
            button_frame, text="Exportar Todo", command=self.export_thread,
            fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8,
            width=200, height=40, font=("Helvetica", 14, "bold")
        )
        self.export_all_button.grid(row=0, column=0, padx=10, pady=5)
        ToolTip(self.export_all_button, "Exporta todos los productos a un archivo Excel")

        self.export_changes_button = ctk.CTkButton(
            button_frame, text="Exportar Cambios", command=self.export_changes_thread,
            fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8,
            width=200, height=40, font=("Helvetica", 14, "bold")
        )
        self.export_changes_button.grid(row=0, column=1, padx=10, pady=5)
        ToolTip(self.export_changes_button, "Exporta solo productos nuevos o modificados desde la última exportación")

        self.import_button = ctk.CTkButton(
            button_frame, text="Importar desde Excel", command=self.import_thread,
            fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8,
            width=200, height=40, font=("Helvetica", 14, "bold")
        )
        self.import_button.grid(row=0, column=2, padx=10, pady=5)
        ToolTip(self.import_button, "Importa datos de productos desde un archivo Excel")

        self.open_excel_button = ctk.CTkButton(
            button_frame, text="Abrir Excel", command=self.open_excel,
            fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8,
            width=200, height=40, font=("Helvetica", 14, "bold")
        )
        self.open_excel_button.grid(row=1, column=0, padx=10, pady=5)
        ToolTip(self.open_excel_button, "Abre el último archivo Excel exportado")

        self.open_report_button = ctk.CTkButton(
            button_frame, text="Abrir Reporte", command=self.open_report,
            fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8,
            width=200, height=40, font=("Helvetica", 14, "bold")
        )
        self.open_report_button.grid(row=1, column=1, padx=10, pady=5)
        ToolTip(self.open_report_button, "Abre el último reporte de sincronización generado")

        # Barra de progreso
        self.progress_bar = ctk.CTkProgressBar(self.main_frame, width=600, progress_color="#4A90E2")
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)

        # Etiqueta de estado
        self.status_label = ctk.CTkLabel(
            self.main_frame, text="Listo", font=("Helvetica", 12), text_color="#4B5EAA"
        )
        self.status_label.pack(pady=5)

        # Área de log
        log_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        log_frame.pack(pady=10, fill="both", expand=True)
        self.log_text = ctk.CTkTextbox(
            log_frame, height=400, width=600, font=("Helvetica", 12),
            fg_color="#E6E6E6", text_color="#000000", wrap="word"
        )
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar = ctk.CTkScrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.insert("end", "Registro de operaciones:\n")
        self.log_text.configure(state="disabled")

    def bind_shortcuts(self):
        """Asocia atajos de teclado a los botones."""
        self.parent.bind("<Control-e>", lambda event: self.export_thread())
        self.parent.bind("<Control-c>", lambda event: self.export_changes_thread())
        self.parent.bind("<Control-i>", lambda event: self.import_thread())
        self.parent.bind("<Control-x>", lambda event: self.open_excel())
        self.parent.bind("<Control-r>", lambda event: self.open_report())

    def update_store_id(self, selected_store_id):
        """Actualiza el store_id seleccionado."""
        self.store_id = int(selected_store_id)
        logger.info(f"Store_id actualizado a {self.store_id}")
        self.log_message(f"Tienda seleccionada: {self.store_id}")

    def log_message(self, message):
        """Añade un mensaje al área de log."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        self.log_text.configure(state="disabled")
        self.log_text.see("end")

    def update_status(self, message, color="#4B5EAA"):
        """Actualiza la etiqueta de estado."""
        self.status_label.configure(text=message, text_color=color)

    def open_excel(self):
        """Abre el archivo Excel generado."""
        self.update_status("Abriendo Excel...", "#4B5EAA")
        if os.path.exists(DOWNLOADS_PATH):
            if platform.system() == "Windows":
                os.startfile(DOWNLOADS_PATH)
            else:
                os.system(f"open {DOWNLOADS_PATH}")
            self.log_message(f"Abriendo Excel: {DOWNLOADS_PATH}")
            self.update_status("Excel abierto", "#00A86B")
        else:
            messagebox.showerror("Error", "El archivo Excel no existe. Realiza una exportación primero.")
            self.update_status("Error al abrir Excel", "#FF5555")

    def open_report(self):
        """Abre el último reporte generado."""
        self.update_status("Abriendo reporte...", "#4B5EAA")
        report_files = [f for f in os.listdir(SYNC_DIR) if f.startswith("Reporte_") and f.endswith(".txt")]
        if report_files:
            latest_report = max(report_files, key=lambda x: os.path.getctime(os.path.join(SYNC_DIR, x)))
            report_path = os.path.join(SYNC_DIR, latest_report)
            if platform.system() == "Windows":
                os.startfile(report_path)
            else:
                os.system(f"open {report_path}")
            self.log_message(f"Abriendo reporte: {report_path}")
            self.update_status("Reporte abierto", "#00A86B")
        else:
            messagebox.showerror("Error", "No se encontraron reportes. Realiza una exportación primero.")
            self.update_status("Error al abrir reporte", "#FF5555")

    def remove_accents(self, text):
        """Elimina acentos de un texto."""
        if not text:
            return text
        normalized = unicodedata.normalize('NFKD', text)
        return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')

    def format_price(self, price):
        """Formatea un precio al formato de ELEventas."""
        return f"$   {float(price):.2f}"

    def export_thread(self):
        """Ejecuta la exportación completa en un hilo separado."""
        Thread(target=lambda: self.export_all(incremental=False)).start()

    def export_changes_thread(self):
        """Ejecuta la exportación incremental en un hilo separado."""
        Thread(target=lambda: self.export_all(incremental=True)).start()

    def export_all(self, incremental=False):
        """Exporta productos a Excel y genera un reporte de cambios."""
        try:
            self.update_status(f"Exportando {'cambios' if incremental else 'todo'}...", "#4B5EAA")
            self.progress_bar.set(0)
            self.progress_bar.configure(progress_color="#4A90E2")
            conn = self.get_thread_safe_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Obtener última fecha de exportación
            last_export_time = None
            if incremental and os.path.exists(LAST_EXPORT_DATA_PATH):
                with open(LAST_EXPORT_DATA_PATH, 'r') as f:
                    data = json.load(f)
                    last_export_time = data.get('last_export_time')

            query = """
                SELECT p.sku, p.nombre, p.inventario, p.precio, e.nombre AS escuela_nombre,
                       COALESCE(p.last_modified, '1970-01-01 00:00:00') AS last_modified
                FROM productos p
                LEFT JOIN escuelas e ON p.escuela_id = e.id
                WHERE p.store_id = ?
            """
            params = [self.store_id]
            if incremental and last_export_time:
                query += " AND p.last_modified > ?"
                params.append(last_export_time)

            cursor.execute(query, params)
            productos_db = [dict(row) for row in cursor.fetchall()]
            total_products = len(productos_db)
            logger.info(f"Obtenidos {total_products} productos desde SQLite para store_id {self.store_id}")

            conn.close()

            last_export_data = {}
            if os.path.exists(LAST_EXPORT_DATA_PATH):
                with open(LAST_EXPORT_DATA_PATH, 'r') as f:
                    last_export_data = json.load(f)

            new_productos = []
            modified_productos = []
            current_data = {}
            for i, prod in enumerate(productos_db):
                sku = str(prod['sku'])
                current_data[sku] = {
                    'nombre': prod['nombre'],
                    'inventario': prod['inventario'],
                    'precio': prod['precio'],
                    'escuela_nombre': prod['escuela_nombre'] or 'Sin Escuela',
                    'last_modified': prod['last_modified']
                }
                if sku not in last_export_data:
                    new_productos.append(prod)
                elif any(
                    last_export_data[sku][key] != current_data[sku][key]
                    for key in ['nombre', 'inventario', 'precio', 'escuela_nombre']
                ):
                    modified_productos.append((prod, last_export_data[sku]))
                self.progress_bar.set((i + 1) / total_products / 2)

            data = []
            for i, prod in enumerate(productos_db):
                row = {
                    'Código': str(prod['sku']),
                    'Descripción': self.remove_accents(prod['nombre']),
                    'Precio Costo': self.format_price(prod['precio']),
                    'Precio Venta': self.format_price(prod['precio']),
                    'Precio Mayoreo': self.format_price(0.0),
                    'Departamento': self.remove_accents(prod['escuela_nombre'] or 'Sin Escuela'),
                    'Existencia': prod['inventario'],
                    'Inv. Mínimo': 5,
                    'Inv. Máximo': 15,
                    'Tipo de Venta': 'UNIDAD',
                    'Impuesto 1 (IVA)': 16,
                    'Impuesto 2 (Otro)': 0,
                    'Clave Producto / Servicio (CFDI 3.3)': '01010101',
                    'Unidad de Medida (CFDI 3.3)': 'EA'
                }
                data.append(row)
                self.progress_bar.set(0.5 + (i + 1) / total_products / 2)

            df = pd.DataFrame(data)
            df.to_excel(DOWNLOADS_PATH, index=False)
            logger.info(f"Exportados {len(df)} productos a {DOWNLOADS_PATH}")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_path = os.path.join(SYNC_DIR, f"Reporte_{timestamp}.txt")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"Reporte de Cambios - {timestamp}\n")
                f.write("-" * 50 + "\n")
                if new_productos:
                    f.write("Productos Nuevos:\n")
                    for prod in new_productos:
                        f.write(
                            f"SKU: {prod['sku']}, Nombre: {prod['nombre']}, "
                            f"Inventario: {prod['inventario']}, Precio: {prod['precio']}, "
                            f"Escuela: {prod['escuela_nombre'] or 'Sin Escuela'}, "
                            f"Última Modificación: {prod['last_modified']}\n"
                        )
                else:
                    f.write("Productos Nuevos: Ninguno\n")
                f.write("-" * 50 + "\n")
                if modified_productos:
                    f.write("Productos Modificados:\n")
                    for prod, old_data in modified_productos:
                        changes = []
                        if prod['nombre'] != old_data['nombre']:
                            changes.append(f"Nombre: {old_data['nombre']} → {prod['nombre']}")
                        if prod['inventario'] != old_data['inventario']:
                            changes.append(f"Inventario: {old_data['inventario']} → {prod['inventario']}")
                        if prod['precio'] != old_data['precio']:
                            changes.append(f"Precio: {old_data['precio']} → {prod['precio']}")
                        if (prod['escuela_nombre'] or 'Sin Escuela') != old_data['escuela_nombre']:
                            changes.append(f"Escuela: {old_data['escuela_nombre']} → {prod['escuela_nombre'] or 'Sin Escuela'}")
                        f.write(
                            f"SKU: {prod['sku']}, Nombre: {prod['nombre']}, "
                            f"Cambios: {'; '.join(changes)}, "
                            f"Última Modificación: {prod['last_modified']}\n"
                        )
                else:
                    f.write("Productos Modificados: Ninguno\n")

            current_data['last_export_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(LAST_EXPORT_DATA_PATH, 'w') as f:
                json.dump(current_data, f)

            self.log_message(f"Exportación {'incremental' if incremental else 'completa'} exitosa: {len(df)} productos a {DOWNLOADS_PATH}. Reporte: {report_path}")
            self.progress_bar.set(1)
            self.progress_bar.configure(progress_color="#00A86B")
            self.update_status("Exportación completada", "#00A86B")

        except Exception as e:
            logger.error(f"Error al exportar: {e}")
            self.log_message(f"Error al exportar: {str(e)}")
            self.progress_bar.set(0)
            self.progress_bar.configure(progress_color="#FF5555")
            self.update_status("Error en exportación", "#FF5555")

    def import_thread(self):
        """Ejecuta la importación en un hilo separado."""
        excel_path = filedialog.askopenfilename(
            title="Seleccionar Excel de ELEventas",
            filetypes=[("Archivos Excel", "*.xlsx *.xls")]
        )
        if excel_path:
            Thread(target=self.import_from_excel, args=(excel_path,)).start()

    def validate_import_data(self, df):
        """Valida los datos del DataFrame antes de importar."""
        errors = []
        for index, row in df.iterrows():
            if pd.isna(row['Código']) or not str(row['Código']).strip():
                errors.append(f"Fila {index + 2}: Código vacío o inválido.")
            if pd.isna(row['Descripción']) or not str(row['Descripción']).strip():
                errors.append(f"Fila {index + 2}: Descripción vacía.")
            try:
                precio = self.clean_price(row['Precio Venta'])
                if precio < 0:
                    errors.append(f"Fila {index + 2}: Precio negativo ({precio}).")
            except ValueError:
                errors.append(f"Fila {index + 2}: Precio inválido ({row['Precio Venta']}).")
            if pd.isna(row['Existencia']) or not isinstance(row['Existencia'], (int, float)) or row['Existencia'] < 0:
                errors.append(f"Fila {index + 2}: Existencia inválida ({row['Existencia']}).")
        return errors

    def import_from_excel(self, excel_path):
        """Importa productos desde un Excel de ELEventas."""
        try:
            self.update_status("Importando desde Excel...", "#4B5EAA")
            self.progress_bar.set(0)
            self.progress_bar.configure(progress_color="#4A90E2")
            df = pd.read_excel(excel_path)
            logger.info(f"Leídos {len(df)} productos desde {excel_path}")

            errors = self.validate_import_data(df)
            if errors:
                error_msg = "Errores en los datos:\n" + "\n".join(errors[:5]) + (f"\n...y {len(errors) - 5} más." if len(errors) > 5 else "")
                self.log_message(error_msg)
                messagebox.showerror("Error", error_msg)
                self.update_status("Error en importación", "#FF5555")
                self.progress_bar.set(0)
                self.progress_bar.configure(progress_color="#FF5555")
                return

            if df['Código'].duplicated().any():
                raise ValueError("Se encontraron códigos duplicados en la columna 'Código'.")

            df['Precio Venta'] = df['Precio Venta'].apply(self.clean_price)
            total_rows = len(df)

            departamentos = df['Departamento'].unique()
            escuela_mapping = {}
            cursor = self.db_manager.get_cursor()
            for i, depto in enumerate(departamentos):
                cursor.execute("SELECT id FROM escuelas WHERE nombre = ? AND store_id = ?", (depto, self.store_id))
                result = cursor.fetchone()
                if result:
                    escuela_id = result['id']
                else:
                    escuela_id = self.db_manager.add_escuela(depto, self.store_id)
                    logger.info(f"Creada escuela '{depto}' con id {escuela_id}")
                escuela_mapping[depto] = escuela_id
                self.progress_bar.set((i + 1) / len(departamentos) / 2)

            for i, row in df.iterrows():
                cursor.execute("""
                    INSERT OR REPLACE INTO productos (
                        sku, nombre, inventario, precio, store_id, escuela_id,
                        nivel_educativo, color, tipo_prenda, tipo_pieza, genero, marca, talla, atributo,
                        ubicacion, escudo, qr_path, ventas, image_path, last_modified
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(row['Código']),
                    row['Descripción'],
                    int(row['Existencia']),
                    row['Precio Venta'],
                    self.store_id,
                    escuela_mapping[row['Departamento']],
                    'N/A',
                    'N/A',
                    row['Departamento'],
                    'N/A',
                    'N/A',
                    'N/A',
                    'N/A',
                    '{}',
                    'N/A',
                    'N/A',
                    f"qrcodes/{row['Código']}.png",
                    0,
                    'N/A',
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
                self.progress_bar.set(0.5 + (i + 1) / total_rows / 2)

            max_sku = str(df['Código'].max())
            cursor.execute("UPDATE contador_sku SET ultimo_sku = ? WHERE store_id = ?", (max_sku, self.store_id))
            if cursor.rowcount == 0:
                cursor.execute("INSERT INTO contador_sku (id, ultimo_sku, store_id) VALUES (?, ?, ?)", (1, max_sku, self.store_id))
            logger.info(f"Contador SKU actualizado a {max_sku}")

            self.db_manager.commit()
            self.log_message(f"Importación exitosa: {len(df)} productos actualizados desde {excel_path}")
            self.progress_bar.set(1)
            self.progress_bar.configure(progress_color="#00A86B")
            self.update_status("Importación completada", "#00A86B")

        except Exception as e:
            logger.error(f"Error al importar: {e}")
            self.log_message(f"Error al importar: {str(e)}")
            self.progress_bar.set(0)
            self.progress_bar.configure(progress_color="#FF5555")
            self.update_status("Error en importación", "#FF5555")

    def clean_price(self, price):
        """Elimina el símbolo '$' y espacios de los precios y convierte a float."""
        if isinstance(price, str):
            return float(price.replace('$', '').strip())
        return float(price)