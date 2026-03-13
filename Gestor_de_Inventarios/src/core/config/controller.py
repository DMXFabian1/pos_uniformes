import os
import sqlite3
import shutil
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from src.core.config.config import CONFIG, exportar_configuraciones
from src.modules.products import generar_qr, generar_etiqueta
from src.core.config.db_manager import DatabaseManager
from src.core.utils.utils import sanitize_filename
from src.core.utils.tooltips import ToolTip
import logging
import json
from datetime import datetime

class Controller:
    def __init__(self, app):
        self.app = app
        self.store_id = getattr(app, 'store_id', 1)
        self.omitir_nivel_var = tk.BooleanVar()
        self.omitir_escuela_var = tk.BooleanVar()
        self.omitir_color_var = tk.BooleanVar()
        self.omitir_tipo_prenda_var = tk.BooleanVar()
        self.omitir_tipo_pieza_var = tk.BooleanVar()
        self.omitir_genero_var = tk.BooleanVar()
        self.omitir_atributo_var = tk.BooleanVar()
        self.omitir_ubicacion_var = tk.BooleanVar()
        self.omitir_escudo_var = tk.BooleanVar()
        self.omitir_marca_var = tk.BooleanVar()
        self.usar_codigo_preimpreso_var = tk.BooleanVar(value=False)
        self.message_label = None
        self.btn_revisar = None
        self.message_label_action = None
        self.btn_generar = None
        self.btn_generar_nombre = None
        self.blink_button = None
        self.show_action_message = None
        self.plantillas_file = os.path.join(CONFIG["ROOT_FOLDER"], "plantillas_productos.json")
        logging.info(f"Controlador inicializado para tienda {self.store_id}")

    def toggle_field(self, variable, widget):
        try:
            logging.info(f"Cambiando estado del campo para tienda {self.store_id}, omitir: {variable.get()}")
            widget.configure(state="disabled" if variable.get() else "normal")
        except Exception as e:
            logging.error(f"Error en toggle_field para tienda {self.store_id}: {str(e)}")
            self.show_message(f"Error al cambiar estado del campo: {str(e)}", "red")

    def show_message(self, text, color="green"):
        try:
            if self.message_label:
                self.message_label.configure(text=text, text_color=color)
                logging.info(f"Mensaje mostrado para tienda {self.store_id}: {text} (color: {color})")
        except Exception as e:
            logging.error(f"Error en show_message para tienda {self.store_id}: {str(e)}")

    def show_success_dialog(self, message, title="Éxito"):
        try:
            logging.info(f"Mostrando diálogo de éxito para tienda {self.store_id}: {title} - {message}")
            ventana = ctk.CTkToplevel(self.app.parent)
            ventana.title(title)
            ventana.geometry("300x150")
            ventana.configure(fg_color="#E6F0FA")
            ventana.transient(self.app.parent)
            ventana.grab_set()

            frame = ctk.CTkFrame(ventana, fg_color="#FFFFFF", corner_radius=10, border_width=2, border_color="#003087")
            frame.pack(padx=20, pady=20, fill="both", expand=True)

            ctk.CTkLabel(frame, text=message, font=("Helvetica", 12), text_color="green").pack(pady=20)

            button_frame = ctk.CTkFrame(frame, fg_color="transparent")
            button_frame.pack(pady=10)

            ctk.CTkButton(button_frame, text="Cerrar", command=ventana.destroy, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8).pack(pady=5)
        except Exception as e:
            logging.error(f"Error en show_success_dialog para tienda {self.store_id}: {str(e)}")
            self.show_message(f"Error al mostrar diálogo de éxito: {str(e)}", "red")

    def añadir_valor(self, tipo_valor, combobox, config_key, config_subkey=None):
        try:
            logging.info(f"Botón [+] clicado para añadir valor a {tipo_valor} en tienda {self.store_id}")
            print(f"Añadiendo valor para {tipo_valor}")
            ventana = ctk.CTkToplevel(self.app.parent)
            ventana.title(f"Añadir {tipo_valor}")
            ventana.geometry("300x150")
            ventana.configure(fg_color="#E6F0FA")
            ventana.transient(self.app.parent)
            ventana.grab_set()

            frame = ctk.CTkFrame(ventana, fg_color="#FFFFFF", corner_radius=10, border_width=2, border_color="#003087")
            frame.pack(padx=20, pady=20, fill="both", expand=True)

            ctk.CTkLabel(frame, text=f"Nuevo {tipo_valor}:", font=("Helvetica", 12)).pack(pady=5)
            entry = ctk.CTkEntry(frame, placeholder_text=f"Escribe el {tipo_valor.lower()}")
            entry.pack(pady=5)

            button_frame = ctk.CTkFrame(frame, fg_color="transparent")
            button_frame.pack(pady=10)

            def guardar():
                try:
                    valor = entry.get().strip()
                    if not valor:
                        messagebox.showwarning("Advertencia", f"El {tipo_valor.lower()} no puede estar vacío.")
                        return
                    valor = valor.capitalize()
                    if valor.lower() in [v.lower() for v in CONFIG[config_key]]:
                        messagebox.showwarning("Advertencia", f"El {tipo_valor.lower()} '{valor}' ya existe.")
                        return
                    CONFIG[config_key].append(valor)
                    if config_subkey:
                        CONFIG[config_subkey] = valor
                    exportar_configuraciones(CONFIG, os.path.join(CONFIG["ROOT_FOLDER"], "config.json"))
                    combobox.configure(values=sorted(CONFIG[config_key]))
                    combobox.set(valor)
                    combobox.update()
                    messagebox.showinfo("Éxito", f"{tipo_valor} '{valor}' añadido.")
                    logging.info(f"Valor '{valor}' añadido a {tipo_valor} en tienda {self.store_id}")
                    ventana.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"No se pudo añadir el {tipo_valor.lower()}: {str(e)}")
                    logging.error(f"Error en añadir_valor ({tipo_valor}) para tienda {self.store_id}: {str(e)}")

            ctk.CTkButton(button_frame, text="Guardar", command=guardar, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8).pack(side="left", padx=5)
            ctk.CTkButton(button_frame, text="Cancelar", command=ventana.destroy, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8).pack(side="left", padx=5)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el diálogo para añadir {tipo_valor.lower()}: {str(e)}")
            logging.error(f"Error en añadir_valor (inicialización) para tienda {self.store_id}: {str(e)}")

    def barcode_scanned(self, event):
        try:
            logging.info(f"Evento de escaneo de código de barras detectado en tienda {self.store_id}")
            if event.keysym == "Return" and self.usar_codigo_preimpreso_var.get():
                nomenclatura = self.app.entry_nomenclatura.get().strip()
                if nomenclatura:
                    self.show_message("Código escaneado con éxito", "green")
                else:
                    self.show_message("Error: Escanea un código válido", "red")
        except Exception as e:
            self.show_message(f"Error al procesar el código de barras: {str(e)}", "red")
            logging.error(f"Error en barcode_scanned para tienda {self.store_id}: {str(e)}")

    def manage_sku(self, increment=False):
        try:
            logging.info(f"Gestionando SKU para tienda {self.store_id}, incrementar: {increment}")
            cursor = DatabaseManager().get_cursor()
            cursor.execute("SELECT ultimo_sku FROM contador_sku WHERE store_id = ? LIMIT 1", (self.store_id,))
            ultimo_sku = cursor.fetchone()
            if ultimo_sku is None:
                cursor.execute("INSERT INTO contador_sku (ultimo_sku, store_id) VALUES ('000000', ?)", (self.store_id,))
                numero = 0
            else:
                numero = int(ultimo_sku[0])
            if increment:
                nuevo_numero = numero + 1
                if nuevo_numero > 1000000:
                    self.show_message("Error: Se ha alcanzado el límite de 1 millón de SKUs.", "red")
                    raise ValueError("Se ha alcanzado el límite de 1 millón de SKUs.")
                nuevo_sku = f"SKU{str(nuevo_numero).zfill(6)}"
                cursor.execute("UPDATE contador_sku SET ultimo_sku = ? WHERE store_id = ?", (str(nuevo_numero).zfill(6), self.store_id))
                DatabaseManager().commit()
                logging.info(f"Nuevo SKU generado para tienda {self.store_id}: {nuevo_sku}")
                return nuevo_sku
            return numero
        except sqlite3.Error as e:
            self.show_message(f"Error en la base de datos: {str(e)}", "red")
            logging.error(f"Error en manage_sku (sqlite3) para tienda {self.store_id}: {str(e)}")
            raise
        except Exception as e:
            self.show_message(f"Error al gestionar SKU: {str(e)}", "red")
            logging.error(f"Error en manage_sku para tienda {self.store_id}: {str(e)}")
            raise

    def validate_fields(self, nombre, tallas, colores, tipo_prenda, tipo_pieza, nomenclatura, precio_str, escuelas):
        try:
            logging.info(f"Validando campos del formulario para tienda {self.store_id}")
            if not nombre or not tallas:
                self.show_message("Error: Completa Nombre y selecciona al menos una talla.", "red")
                return False, None

            if not self.omitir_color_var.get() and not colores:
                self.show_message("Error: Selecciona al menos un color o marca 'Omitir Colores'.", "red")
                return False, None

            if not self.omitir_escuela_var.get() and not escuelas:
                self.show_message("Error: Selecciona al menos una escuela o marca 'Omitir Escuelas'.", "red")
                return False, None

            fields = [
                ("Tipo de Prenda", self.omitir_tipo_prenda_var, tipo_prenda),
                ("Tipo de Pieza", self.omitir_tipo_pieza_var, tipo_pieza)
            ]
            for field_name, omit_var, value in fields:
                if not omit_var.get() and not value:
                    self.show_message(f"Error: Selecciona un {field_name.lower()} o marca 'Omitir {field_name}'.", "red")
                    return False, None

            if self.usar_codigo_preimpreso_var.get() and not nomenclatura:
                self.show_message("Error: Ingresa un código preimpreso válido.", "red")
                return False, None

            precio = 0.0
            if precio_str:
                try:
                    precio = float(precio_str)
                    if precio < 0:
                        self.show_message("Error: El precio no puede ser negativo.", "red")
                        return False, None
                except ValueError:
                    self.show_message("Error: El precio debe ser un número válido.", "red")
                    return False, None

            logging.info(f"Campos validados exitosamente para tienda {self.store_id}")
            return True, precio
        except Exception as e:
            self.show_message(f"Error al validar campos: {str(e)}", "red")
            logging.error(f"Error en validate_fields para tienda {self.store_id}: {str(e)}")
            return False, None

    def get_escuela_id(self, nombres_escuelas):
        try:
            escuelas = self.app.db_manager.get_escuelas(self.store_id)
            result = []
            for nombre in nombres_escuelas:
                for escuela in escuelas:
                    if escuela['nombre'].lower() == nombre.lower():
                        result.append((nombre, escuela['id']))
                        break
                else:
                    result.append((nombre, None))
            return result
        except Exception as e:
            logging.error(f"Error al obtener IDs de escuelas '{nombres_escuelas}' para tienda {self.store_id}: {str(e)}")
            return [(nombre, None) for nombre in nombres_escuelas]

    def check_duplicate_product(self, nombre_base, nivel_educativo, escuela_id, tipo_prenda, tipo_pieza, genero, talla, color, escudo, marca):
        try:
            logging.info(f"Verificando productos duplicados para tienda {self.store_id}, escuela_id={escuela_id}")
            cursor = DatabaseManager().get_cursor()
            query = """
                SELECT nombre FROM productos 
                WHERE UPPER(nivel_educativo) = UPPER(?) 
                AND escuela_id = ? 
                AND UPPER(tipo_prenda) = UPPER(?) 
                AND UPPER(tipo_pieza) = UPPER(?) 
                AND UPPER(genero) = UPPER(?) 
                AND UPPER(talla) = UPPER(?)
                AND UPPER(color) = UPPER(?) 
                AND UPPER(escudo) = UPPER(?) 
                AND UPPER(marca) = UPPER(?)
                AND store_id = ?
            """
            params = (nivel_educativo or "", escuela_id if escuela_id is not None else None, 
                      tipo_prenda or "", tipo_pieza or "", genero or "", talla, color, 
                      escudo or "", marca or "", self.store_id)
            cursor.execute(query, params)
            duplicados = []
            for row in cursor.fetchall():
                nombre_db = row[0]
                nombre_con_talla_color = f"{nombre_base} {color} Talla {talla}" if color else f"{nombre_base} Talla {talla}"
                if nombre_db.lower() == nombre_con_talla_color.lower():
                    escuela_nombre = next((e['nombre'] for e in self.app.db_manager.get_escuelas(self.store_id) if e['id'] == escuela_id), "Sin escuela")
                    duplicados.append(f"{nombre_con_talla_color} (Escuela: {escuela_nombre}, Marca: {marca}, Nivel: {nivel_educativo}, Escudo: {escudo})")
            logging.info(f"Duplicados encontrados para tienda {self.store_id}: {len(duplicados)}")
            return duplicados
        except sqlite3.Error as e:
            logging.error(f"Error al verificar duplicados (sqlite3) para tienda {self.store_id}: {str(e)}")
            return []
        except Exception as e:
            logging.error(f"Error en check_duplicate_product para tienda {self.store_id}: {str(e)}")
            return []

    def generar_codigo(self, show_message=True):
        try:
            logging.info(f"Botón Generar clicado para tienda {self.store_id}")
            nombre_base = self.app.entry_nombre.get().strip()
            nivel_educativo = self.app.combo_nivel_educativo.get() if not self.omitir_nivel_var.get() else ""
            escuelas = self.app.get_selected_escuelas() if not self.omitir_escuela_var.get() else []
            escuelas_info = self.get_escuela_id(escuelas)
            colores = self.app.get_selected_colors() if not self.omitir_color_var.get() else [""]
            tipo_prenda = self.app.combo_tipo_prenda.get() if not self.omitir_tipo_prenda_var.get() else ""
            tipo_pieza = self.app.combo_tipo_pieza.get() if not self.omitir_tipo_pieza_var.get() else ""
            genero = self.app.combo_genero.get() if not self.omitir_genero_var.get() else ""
            atributo = self.app.combo_atributo.get() if not self.omitir_atributo_var.get() else ""
            ubicacion = self.app.combo_ubicacion.get() if not self.omitir_ubicacion_var.get() else ""
            escudo = self.app.combo_escudo.get() if not self.omitir_escudo_var.get() else ""
            marca = self.app.combo_marca.get() if not self.omitir_marca_var.get() else ""
            nomenclatura = self.app.entry_nomenclatura.get().strip() if self.usar_codigo_preimpreso_var.get() else ""
            precio_str = self.app.entry_precio.get().strip()
            tallas = [talla for talla, var in self.app.talla_vars.items() if var.get()]
            image_path = self.app.image_path

            if not nombre_base:
                self.show_message("Error: El campo Nombre no puede estar vacío.", "red")
                return

            nombre_base_lower = nombre_base.lower()
            nombre_palabras = nombre_base_lower.split()
            for talla in tallas:
                talla_lower = talla.lower()
                if talla_lower in nombre_palabras:
                    self.show_message(f"Error: El nombre '{nombre_base}' contiene la talla '{talla}'.", "red")
                    return
            if tipo_pieza not in ["Pants 3pz", "Pants 2pz"]:
                for color in colores:
                    if color and color.lower() in nombre_palabras:
                        self.show_message(f"Error: El nombre '{nombre_base}' contiene el color '{color}'.", "red")
                        return

            valid, precio = self.validate_fields(nombre_base, tallas, colores, tipo_prenda, tipo_pieza, nomenclatura, precio_str, escuelas)
            if not valid:
                return

            base_dir = self.app.qr_folder
            os.makedirs(base_dir, exist_ok=True)
            folder_name = f"{nombre_base}_{tipo_prenda}_{tipo_pieza}"
            folder_path = os.path.join(base_dir, folder_name.replace("/", "_").replace("\\", "_"))

            cursor = DatabaseManager().get_cursor()
            productos = []
            duplicados_totales = []

            if tipo_pieza in ["Pants 3pz", "Pants 2pz"] and escuelas:
                colores = [""]

            for talla in tallas:
                for color in colores:
                    for escuela_nombre, escuela_id in escuelas_info:
                        duplicados = self.check_duplicate_product(nombre_base, nivel_educativo, escuela_id, tipo_prenda, tipo_pieza, genero, talla, color, escudo, marca)
                        if duplicados:
                            duplicados_totales.extend(duplicados)

            if duplicados_totales:
                message = "Se encontraron productos duplicados:\n" + "\n".join(duplicados_totales) + "\n¿Deseas sobrescribirlos?"
                if not messagebox.askyesno("Confirmar", message):
                    self.show_message("Operación cancelada: Productos duplicados detectados.", "red")
                    return
                for talla in tallas:
                    for color in colores:
                        for _, escuela_id in escuelas_info:
                            cursor.execute("""
                                DELETE FROM productos 
                                WHERE UPPER(nivel_educativo) = UPPER(?) 
                                AND escuela_id = ? 
                                AND UPPER(tipo_prenda) = UPPER(?) 
                                AND UPPER(tipo_pieza) = UPPER(?) 
                                AND UPPER(genero) = UPPER(?) 
                                AND UPPER(talla) = UPPER(?)
                                AND UPPER(color) = UPPER(?) 
                                AND UPPER(escudo) = UPPER(?) 
                                AND UPPER(marca) = UPPER(?)
                                AND store_id = ?
                            """, (nivel_educativo or "", escuela_id if escuela_id is not None else None, 
                                  tipo_prenda or "", tipo_pieza or "", genero or "", talla, color, 
                                  escudo or "", marca or "", self.store_id))

            if os.path.exists(folder_path):
                logging.info(f"Eliminando directorio existente para tienda {self.store_id}: {folder_path}")
                shutil.rmtree(folder_path)

            logging.info(f"Creando directorio para tienda {self.store_id}: {folder_path}")
            os.makedirs(folder_path, exist_ok=True)

            if not os.path.exists(folder_path):
                logging.error(f"El directorio {folder_path} no se creó correctamente para tienda {self.store_id}")
                self.show_message(f"Error: No se pudo crear el directorio {folder_path}.", "red")
                return

            for talla in tallas:
                for color in colores:
                    if tipo_pieza in ["Pants 3pz", "Pants 2pz"] and escuelas:
                        for escuela_nombre, escuela_id in escuelas_info:
                            sku = nomenclatura if self.usar_codigo_preimpreso_var.get() else self.manage_sku(increment=True)
                            talla_folder = os.path.join(folder_path, sanitize_filename(talla) if talla else "SinTalla")
                            os.makedirs(talla_folder, exist_ok=True)

                            nombre_con_talla_color = f"{nombre_base} {escuela_nombre} Talla {talla}"
                            qr_file_path = os.path.join(talla_folder, f"{sku}_{nombre_base}_{sanitize_filename(talla)}_qr.png")
                            label_file_path = os.path.join(talla_folder, f"{sku}_{nombre_base}_{sanitize_filename(talla)}_label.png")

                            generar_qr(sku, qr_file_path, tipo_pieza)
                            generar_etiqueta(sku, escuela_nombre, nivel_educativo, nombre_con_talla_color, talla, genero, tipo_pieza, qr_file_path, label_file_path)

                            qr_path_relative = os.path.relpath(label_file_path, self.app.root_folder)

                            data = {
                                "sku": sku,
                                "nombre": nombre_con_talla_color,
                                "nivel_educativo": nivel_educativo,
                                "escuela_id": escuela_id,
                                "color": "",
                                "tipo_prenda": tipo_prenda,
                                "tipo_pieza": tipo_pieza,
                                "genero": genero,
                                "atributo": atributo,
                                "ubicacion": ubicacion,
                                "escudo": escudo,
                                "marca": marca,
                                "talla": talla,
                                "qr_path": qr_path_relative,
                                "inventario": 0,
                                "ventas": 0,
                                "precio": precio,
                                "image_path": image_path,
                                "store_id": self.store_id,
                                "last_modified": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            productos.append(data)
                            cursor.execute("""
                                INSERT OR REPLACE INTO productos (
                                    sku, nombre, nivel_educativo, escuela_id, color, tipo_prenda, tipo_pieza, 
                                    genero, atributo, ubicacion, escudo, marca, talla, qr_path, 
                                    inventario, ventas, precio, image_path, store_id, last_modified
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (sku, nombre_con_talla_color, nivel_educativo, escuela_id, "", tipo_prenda, tipo_pieza, 
                                  genero, atributo, ubicacion, escudo, marca, talla, qr_path_relative, 
                                  0, 0, precio, image_path, self.store_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                    else:
                        for escuela_nombre, escuela_id in escuelas_info if escuelas else [(None, None)]:
                            sku = nomenclatura if self.usar_codigo_preimpreso_var.get() else self.manage_sku(increment=True)
                            talla_folder = os.path.join(folder_path, sanitize_filename(talla) if talla else "SinTalla")
                            os.makedirs(talla_folder, exist_ok=True)

                            nombre_con_talla_color = f"{nombre_base} {color} Talla {talla}" if color else f"{nombre_base} Talla {talla}"
                            qr_file_path = os.path.join(talla_folder, f"{sku}_{nombre_base}_{sanitize_filename(talla)}_{sanitize_filename(color)}_qr.png")
                            label_file_path = os.path.join(talla_folder, f"{sku}_{nombre_base}_{sanitize_filename(talla)}_{sanitize_filename(color)}_label.png")

                            generar_qr(sku, qr_file_path, tipo_pieza)
                            generar_etiqueta(sku, escuela_nombre or "", nivel_educativo, nombre_con_talla_color, talla, genero, tipo_pieza, qr_file_path, label_file_path)

                            qr_path_relative = os.path.relpath(label_file_path, self.app.root_folder)

                            data = {
                                "sku": sku,
                                "nombre": nombre_con_talla_color,
                                "nivel_educativo": nivel_educativo,
                                "escuela_id": escuela_id,
                                "color": color,
                                "tipo_prenda": tipo_prenda,
                                "tipo_pieza": tipo_pieza,
                                "genero": genero,
                                "atributo": atributo,
                                "ubicacion": ubicacion,
                                "escudo": escudo,
                                "marca": marca,
                                "talla": talla,
                                "qr_path": qr_path_relative,
                                "inventario": 0,
                                "ventas": 0,
                                "precio": precio,
                                "image_path": image_path,
                                "store_id": self.store_id,
                                "last_modified": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            }
                            productos.append(data)
                            cursor.execute("""
                                INSERT OR REPLACE INTO productos (
                                    sku, nombre, nivel_educativo, escuela_id, color, tipo_prenda, tipo_pieza, 
                                    genero, atributo, ubicacion, escudo, marca, talla, qr_path, 
                                    inventario, ventas, precio, image_path, store_id, last_modified
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (sku, nombre_con_talla_color, nivel_educativo, escuela_id, color, tipo_prenda, tipo_pieza, 
                                  genero, atributo, ubicacion, escudo, marca, talla, qr_path_relative, 
                                  0, 0, precio, image_path, self.store_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            DatabaseManager().commit()
            if show_message:
                self.mostrar_ventana_exito()
                if self.blink_button and self.show_action_message:
                    self.blink_button(self.btn_generar)
                    self.show_action_message(self.message_label_action, "Códigos generados")
            logging.info(f"Códigos generados exitosamente para {len(productos)} productos en tienda {self.store_id}")
        except sqlite3.Error as e:
            if show_message:
                self.show_message(f"Error en la base de datos: {str(e)}", "red")
            logging.error(f"Error en generar_codigo (sqlite3) para tienda {self.store_id}: {str(e)}")
        except OSError as e:
            if show_message:
                self.show_message(f"Error al manejar archivos: {str(e)}", "red")
            logging.error(f"Error en generar_codigo (OSError) para tienda {self.store_id}: {str(e)}")
        except Exception as e:
            if show_message:
                self.show_message(f"Error inesperado: {str(e)}", "red")
            logging.error(f"Error en generar_codigo para tienda {self.store_id}: {str(e)}")

    def limpiar_formulario(self):
        try:
            logging.info(f"Botón Limpiar clicado para tienda {self.store_id}")
            self.app.entry_nombre.delete(0, tk.END)
            self.app.combo_escuela.set([])
            self.app.entry_nomenclatura.delete(0, tk.END)
            self.app.entry_precio.delete(0, tk.END)
            self.app.talla_personalizada_entry.delete(0, tk.END)
            self.app.talla_numerica_personalizada_entry.delete(0, tk.END)
            self.app.color_personalizado_entry.delete(0, tk.END)
            self.app.escuela_entry.delete(0, tk.END)
            for talla in self.app.tallas_personalizadas:
                if talla in self.app.talla_vars:
                    del self.app.talla_vars[talla]
            self.app.tallas_personalizadas.clear()
            for color in self.app.color_vars:
                self.app.color_vars[color].set(False)
            for widget in self.app.tallas_personalizadas_inner_frame.winfo_children():
                widget.destroy()
            for widget in self.app.tallas_numericas_inner_frame.winfo_children():
                widget.destroy()
            self.app.all_tallas_numericas = sorted([t for t in CONFIG["TALLAS"] if t.isdigit()], key=int)
            num_rows = (len(self.app.all_tallas_numericas) + 4) // 5
            self.app.tallas_numericas_inner_frame.configure(height=num_rows * 40)
            for i, talla_item in enumerate(self.app.all_tallas_numericas):
                if talla_item in self.app.talla_vars:
                    cb = ctk.CTkCheckBox(self.app.tallas_numericas_inner_frame, text=talla_item, variable=self.app.talla_vars[talla_item], 
                                         fg_color="#4A90E2", border_color="#A3BFFA", hover_color="#E6F0FA", text_color="#4B5EAA")
                    cb.grid(row=i // 5, column=i % 5, padx=10, pady=5, sticky="w")
            self.app.tallas_numericas_inner_frame.update_idletasks()
            self.app.canvas_tallas.configure(scrollregion=self.app.canvas_tallas.bbox("all"))
            for widget in self.app.colores_inner_frame.winfo_children():
                widget.destroy()
            all_colors = sorted(set(CONFIG["COLORES"] + self.app.colores_personalizados))
            num_rows = (len(all_colors) + 3) // 4
            self.app.colores_inner_frame.configure(height=num_rows * 40)
            for i, color in enumerate(all_colors):
                if color not in self.app.color_vars:
                    self.app.color_vars[color] = tk.BooleanVar()
                cb = ctk.CTkCheckBox(self.app.colores_inner_frame, text=color, variable=self.app.color_vars[color], 
                                     fg_color="#4A90E2", border_color="#A3BFFA", hover_color="#E6F0FA", text_color="#4B5EAA",
                                     command=self.app.update_name, state="normal")
                cb.grid(row=i // 4, column=i % 4, padx=10, pady=5, sticky="w")
                ToolTip(cb, f"Seleccionar el color {color}")
            self.app.colores_inner_frame.update_idletasks()
            self.app.canvas.configure(scrollregion=self.app.canvas.bbox("all"))
            fields = [
                (self.omitir_nivel_var, self.app.combo_nivel_educativo),
                (self.omitir_escuela_var, self.app.combo_escuela),
                (self.omitir_color_var, None),
                (self.omitir_tipo_prenda_var, self.app.combo_tipo_prenda),
                (self.omitir_tipo_pieza_var, self.app.combo_tipo_pieza),
                (self.omitir_genero_var, self.app.combo_genero),
                (self.omitir_atributo_var, self.app.combo_atributo),
                (self.omitir_ubicacion_var, self.app.combo_ubicacion),
                (self.omitir_escudo_var, self.app.combo_escudo),
                (self.omitir_marca_var, self.app.combo_marca),
            ]
            for omit_var, widget in fields:
                omit_var.set(False)
                if widget:
                    widget.configure(state="normal")
                    if isinstance(widget, ctk.CTkComboBox):
                        widget.set("")
                    elif hasattr(widget, 'set'):
                        widget.set([])
                    else:
                        widget.delete(0, tk.END)
            for widget in self.app.colores_inner_frame.winfo_children():
                if isinstance(widget, ctk.CTkCheckBox):
                    widget.configure(state="normal")
            self.usar_codigo_preimpreso_var.set(False)
            for var in self.app.talla_vars.values():
                var.set(False)
            self.app.image_path = None
            self.app.image_label.configure(image=None, text="Sin imagen seleccionada")
            self.app.resumen_textbox.configure(state="normal")
            self.app.resumen_textbox.delete("1.0", "end")
            self.app.resumen_textbox.insert("end", "Presiona 'Revisar' para ver los datos")
            self.app.resumen_textbox.configure(state="disabled")
            self.app.preview_label.configure(text="Previsualización: Ninguna")
            self.show_message("")
            logging.info(f"Formulario limpiado exitosamente para tienda {self.store_id}")
        except Exception as e:
            self.show_message(f"Error al limpiar el formulario: {str(e)}", "red")
            logging.error(f"Error en limpiar_formulario para tienda {self.store_id}: {str(e)}")

    def revisar_datos(self):
        try:
            logging.info(f"Botón Revisar clicado para tienda {self.store_id}")
            fields = {
                "Nombre": (None, self.app.entry_nombre.get().strip()),
                "Nivel Educativo": (self.omitir_nivel_var, self.app.combo_nivel_educativo.get()),
                "Escuelas": (self.omitir_escuela_var, self.app.get_selected_escuelas()),
                "Colores": (self.omitir_color_var, self.app.get_selected_colors()),
                "Tipo de Prenda": (self.omitir_tipo_prenda_var, self.app.combo_tipo_prenda.get()),
                "Tipo de Pieza": (self.omitir_tipo_pieza_var, self.app.combo_tipo_pieza.get()),
                "Género": (self.omitir_genero_var, self.app.combo_genero.get()),
                "Atributo": (self.omitir_atributo_var, self.app.combo_atributo.get()),
                "Ubicación": (self.omitir_ubicacion_var, self.app.combo_ubicacion.get()),
                "Escudo": (self.omitir_escudo_var, self.app.combo_escudo.get()),
                "Marca": (self.omitir_marca_var, self.app.combo_marca.get()),
            }
            nomenclatura = self.app.entry_nomenclatura.get().strip() if self.usar_codigo_preimpreso_var.get() else ""
            precio_str = self.app.entry_precio.get().strip()
            tallas = [talla for talla, var in self.app.talla_vars.items() if var.get()]
            colores = self.app.get_selected_colors() if not self.omitir_color_var.get() else [""]
            escuelas = self.app.get_selected_escuelas() if not self.omitir_escuela_var.get() else []
            image_path = self.app.image_path

            if not fields["Nombre"][1]:
                self.show_message("Error: El campo Nombre no puede estar vacío.", "red")
                logging.warning(f"Revisión fallida para tienda {self.store_id}: Nombre vacío")
                return

            campos_faltantes = []
            for field_name, (omit_var, value) in fields.items():
                if field_name == "Nombre":
                    continue
                if field_name in ["Colores", "Escuelas"]:
                    if not omit_var.get() and not value:
                        campos_faltantes.append(field_name)
                    continue
                if not omit_var.get() and not value:
                    campos_faltantes.append(field_name)

            if campos_faltantes:
                dialog = ctk.CTkToplevel(self.app.parent)
                dialog.title("Campos Faltantes")
                dialog.geometry("400x200")
                dialog.configure(fg_color="#E6F0FA")
                dialog.transient(self.app.parent)
                dialog.grab_set()
                frame = ctk.CTkFrame(dialog, fg_color="#FFFFFF", corner_radius=10, border_width=1, border_color="#A3BFFA")
                frame.pack(padx=20, pady=20, fill="both", expand=True)
                ctk.CTkLabel(frame, text="Faltan los siguientes campos:", font=("Helvetica", 14, "bold"), text_color="#1A2E5A").pack(pady=5)
                ctk.CTkLabel(frame, text="\n".join(f"- {campo}" for campo in campos_faltantes), font=("Helvetica", 12), text_color="#4B5EAA").pack(pady=5)
                button_frame = ctk.CTkFrame(frame, fg_color="transparent")
                button_frame.pack(pady=10)

                def omitir_faltantes():
                    try:
                        for field_name in campos_faltantes:
                            if field_name == "Nivel Educativo":
                                self.omitir_nivel_var.set(True)
                                self.app.combo_nivel_educativo.configure(state="disabled")
                            elif field_name == "Escuelas":
                                self.omitir_escuela_var.set(True)
                                self.app.combo_escuela.configure(state="disabled")
                            elif field_name == "Colores":
                                self.omitir_color_var.set(True)
                                for widget in self.app.colores_inner_frame.winfo_children():
                                    if isinstance(widget, ctk.CTkCheckBox):
                                        widget.configure(state="disabled")
                            elif field_name == "Tipo de Prenda":
                                self.omitir_tipo_prenda_var.set(True)
                                self.app.combo_tipo_prenda.configure(state="disabled")
                            elif field_name == "Tipo de Pieza":
                                self.omitir_tipo_pieza_var.set(True)
                                self.app.combo_tipo_pieza.configure(state="disabled")
                            elif field_name == "Género":
                                self.omitir_genero_var.set(True)
                                self.app.combo_genero.configure(state="disabled")
                            elif field_name == "Atributo":
                                self.omitir_atributo_var.set(True)
                                self.app.combo_atributo.configure(state="disabled")
                            elif field_name == "Ubicación":
                                self.omitir_ubicacion_var.set(True)
                                self.app.combo_ubicacion.configure(state="disabled")
                            elif field_name == "Escudo":
                                self.omitir_escudo_var.set(True)
                                self.app.combo_escudo.configure(state="disabled")
                            elif field_name == "Marca":
                                self.omitir_marca_var.set(True)
                                self.app.combo_marca.configure(state="disabled")
                        dialog.destroy()
                        self.revisar_datos()
                        logging.info(f"Campos faltantes omitidos exitosamente para tienda {self.store_id}")
                    except Exception as e:
                        self.show_message(f"Error al omitir campos faltantes: {str(e)}", "red")
                        logging.error(f"Error en omitir_faltantes para tienda {self.store_id}: {str(e)}")

                ctk.CTkButton(button_frame, text="Omitir Faltantes", command=omitir_faltantes, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120).pack(side="left", padx=5)
                ctk.CTkButton(button_frame, text="Cancelar", command=dialog.destroy, fg_color="#A9A9A9", hover_color="#8B8B8B", corner_radius=8, width=120).pack(side="left", padx=5)
                logging.info(f"Campos faltantes detectados para tienda {self.store_id}: {campos_faltantes}")
                return

            valid, precio = self.validate_fields(fields["Nombre"][1], tallas, fields["Colores"][1], fields["Tipo de Prenda"][1], fields["Tipo de Pieza"][1], nomenclatura, precio_str, fields["Escuelas"][1])
            if not valid:
                return

            total_productos = len(tallas) * len(colores) * (len(escuelas) if fields["Tipo de Pieza"][1] in ["Pants 3pz", "Pants 2pz"] and escuelas else 1)
            logging.info(f"Total productos a previsualizar para tienda {self.store_id}: {total_productos}")

            last_number = self.manage_sku(increment=False)
            logging.info(f"Último SKU antes de previsualización para tienda {self.store_id}: SKU{last_number:06d}")

            start_sku = last_number + 1
            end_sku = start_sku + total_productos - 1
            start_sku_str = f"SKU{start_sku:06d}"
            end_sku_str = f"SKU{end_sku:06d}"

            self.app.preview_label.configure(text=f"Previsualización: {start_sku_str} - {end_sku_str}")
            logging.info(f"Previsualización mostrada para tienda {self.store_id}: {start_sku_str} - {end_sku_str}")

            self.app.resumen_textbox.configure(state="normal")
            self.app.resumen_textbox.delete("1.0", "end")
            nombre_generico = fields["Nombre"][1]
            self.app.resumen_textbox.insert("end", f"Nombre del Producto: {nombre_generico}\n")
            self.app.resumen_textbox.insert("end", f"Total de productos: {total_productos}\n")
            self.app.resumen_textbox.insert("end", f"Tallas seleccionadas: {', '.join(tallas)}\n")
            self.app.resumen_textbox.insert("end", f"Colores seleccionados: {', '.join(colores) if colores != [''] else 'Ninguno'}\n")
            self.app.resumen_textbox.insert("end", f"Escuelas seleccionadas: {', '.join(escuelas) if escuelas else 'Ninguna'}\n")
            for field_name, (_, value) in fields.items():
                if field_name in ["Nombre", "Colores", "Escuelas"]:
                    continue
                if value:
                    self.app.resumen_textbox.insert("end", f"{field_name}: {value}\n")
            self.app.resumen_textbox.insert("end", f"Precio: {precio:.2f}\n")
            self.app.resumen_textbox.insert("end", f"Imagen: {'Seleccionada' if image_path else 'No seleccionada'}")
            self.app.resumen_textbox.configure(state="disabled")
            self.show_message("Revisa los datos antes de generar.", "green")
            if self.blink_button and self.show_action_message:
                self.blink_button(self.btn_revisar)
                self.show_action_message(self.message_label_action, "Datos revisados")
            new_last_number = self.manage_sku(increment=False)
            logging.info(f"Último SKU después de previsualización para tienda {self.store_id}: SKU{new_last_number:06d}")
        except Exception as e:
            self.show_message(f"Error al revisar datos: {str(e)}", "red")
            logging.error(f"Error en revisar_datos para tienda {self.store_id}: {str(e)}")

    def seleccionar_todas(self):
        try:
            logging.info(f"Botón Seleccionar Todas clicado para tienda {self.store_id}")
            for var in self.app.talla_vars.values():
                var.set(True)
        except Exception as e:
            self.show_message(f"Error al seleccionar todas las tallas: {str(e)}", "red")
            logging.error(f"Error en seleccionar_todas para tienda {self.store_id}: {str(e)}")

    def deseleccionar_todas(self):
        try:
            logging.info(f"Botón Deseleccionar Todas clicado para tienda {self.store_id}")
            for var in self.app.talla_vars.values():
                var.set(False)
        except Exception as e:
            self.show_message(f"Error al deseleccionar todas las tallas: {str(e)}", "red")
            logging.error(f"Error en deseleccionar_todas para tienda {self.store_id}: {str(e)}")

    def seleccionar_pares(self):
        try:
            logging.info(f"Botón Seleccionar Pares clicado para tienda {self.store_id}")
            for talla, var in self.app.talla_vars.items():
                if talla.isdigit() and int(talla) % 2 == 0:
                    var.set(True)
                else:
                    var.set(False)
        except Exception as e:
            self.show_message(f"Error al seleccionar tallas pares: {str(e)}", "red")
            logging.error(f"Error en seleccionar_pares para tienda {self.store_id}: {str(e)}")

    def mostrar_ventana_exito(self):
        try:
            logging.info(f"Mostrando ventana de éxito para generación de códigos en tienda {self.store_id}")
            self.show_success_dialog("¡Códigos generados con éxito en Mis códigos!")
        except Exception as e:
            self.show_message(f"Error al mostrar ventana de éxito: {str(e)}", "red")
            logging.error(f"Error en mostrar_ventana_exito para tienda {self.store_id}: {str(e)}")

    def capturar_datos_formulario(self):
        try:
            logging.info("Capturando datos del formulario para plantilla")
            ventana_nombre = ctk.CTkToplevel(self.app.parent)
            ventana_nombre.title("Nombre de la Plantilla")
            ventana_nombre.geometry("300x150")
            ventana_nombre.configure(fg_color="#E6F0FA")
            ventana_nombre.transient(self.app.parent)
            ventana_nombre.grab_set()

            frame_nombre = ctk.CTkFrame(ventana_nombre, fg_color="#FFFFFF", corner_radius=10, border_width=2, border_color="#003087")
            frame_nombre.pack(padx=20, pady=20, fill="both", expand=True)

            ctk.CTkLabel(frame_nombre, text="Nombre de la Plantilla:", font=("Helvetica", 12)).pack(pady=5)
            entry_nombre = ctk.CTkEntry(frame_nombre, placeholder_text="Ej. Camisa Escolar Hombre")
            entry_nombre.pack(pady=5)

            button_frame_nombre = ctk.CTkFrame(frame_nombre, fg_color="transparent")
            button_frame_nombre.pack(pady=10)

            def continuar():
                nombre_plantilla = entry_nombre.get().strip()
                if not nombre_plantilla:
                    messagebox.showwarning("Advertencia", "El nombre de la plantilla no puede estar vacío.")
                    return
                ventana_nombre.destroy()
                
                escuelas = self.app.get_selected_escuelas() if not self.omitir_escuela_var.get() else []
                escuelas_info = self.get_escuela_id(escuelas)
                escuelas_ids = [escuela_id for _, escuela_id in escuelas_info]
                datos = {
                    "nombre_plantilla": nombre_plantilla,
                    "tipo_prenda": self.app.combo_tipo_prenda.get() if not self.omitir_tipo_prenda_var.get() else "",
                    "tipo_pieza": self.app.combo_tipo_pieza.get() if not self.omitir_tipo_pieza_var.get() else "",
                    "marca": self.app.combo_marca.get() if not self.omitir_marca_var.get() else "",
                    "atributo": self.app.combo_atributo.get() if not self.omitir_atributo_var.get() else "",
                    "genero": self.app.combo_genero.get() if not self.omitir_genero_var.get() else "",
                    "nivel_educativo": self.app.combo_nivel_educativo.get() if not self.omitir_nivel_var.get() else "",
                    "escuelas": escuelas,
                    "escuelas_ids": escuelas_ids,
                    "ubicacion": self.app.combo_ubicacion.get() if not self.omitir_ubicacion_var.get() else "",
                    "escudo": self.app.combo_escudo.get() if not self.omitir_escudo_var.get() else "",
                    "precio": self.app.entry_precio.get().strip(),
                    "tallas": self.app.get_selected_tallas(),
                    "colores": self.app.get_selected_colors() if not self.omitir_color_var.get() else [],
                    "omitir": {
                        "tipo_prenda": self.omitir_tipo_prenda_var.get(),
                        "tipo_pieza": self.omitir_tipo_pieza_var.get(),
                        "marca": self.omitir_marca_var.get(),
                        "atributo": self.omitir_atributo_var.get(),
                        "genero": self.omitir_genero_var.get(),
                        "nivel_educativo": self.omitir_nivel_var.get(),
                        "escuela": self.omitir_escuela_var.get(),
                        "ubicacion": self.omitir_ubicacion_var.get(),
                        "escudo": self.omitir_escudo_var.get(),
                        "colores": self.omitir_color_var.get()
                    }
                }

                if os.path.exists(self.plantillas_file):
                    with open(self.plantillas_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                else:
                    data = {"plantillas": []}

                for p in data["plantillas"]:
                    if p["nombre_plantilla"].lower() == nombre_plantilla.lower():
                        messagebox.showwarning("Advertencia", f"Ya existe una plantilla con el nombre '{nombre_plantilla}'.")
                        return

                data["plantillas"].append(datos)
                with open(self.plantillas_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

                self.app.actualizar_plantillas_combo()

                ventana = ctk.CTkToplevel(self.app.parent)
                ventana.title("Datos Capturados")
                ventana.geometry("500x400")
                ventana.configure(fg_color="#E6F0FA")
                ventana.transient(self.app.parent)
                ventana.grab_set()

                frame = ctk.CTkFrame(ventana, fg_color="#FFFFFF", corner_radius=10, border_width=2, border_color="#003087")
                frame.pack(padx=20, pady=20, fill="both", expand=True)

                ctk.CTkLabel(frame, text=f"Plantilla '{nombre_plantilla}' guardada. Datos (JSON):", font=("Helvetica", 12, "bold")).pack(pady=5)
                texto = ctk.CTkTextbox(frame, height=200, wrap="word", font=("Helvetica", 12))
                texto.pack(pady=5, fill="both", expand=True)
                texto.insert("end", json.dumps(datos, indent=2, ensure_ascii=False))
                texto.configure(state="disabled")

                button_frame = ctk.CTkFrame(frame, fg_color="transparent")
                button_frame.pack(pady=10)

                def copiar_al_portapapeles():
                    self.app.parent.clipboard_clear()
                    self.app.parent.clipboard_append(json.dumps(datos, indent=2, ensure_ascii=False))
                    messagebox.showinfo("Éxito", "Datos copiados al portapapeles.")

                ctk.CTkButton(button_frame, text="Copiar JSON", command=copiar_al_portapapeles, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8).pack(side="left", padx=5)
                ctk.CTkButton(button_frame, text="Cerrar", command=ventana.destroy, fg_color="#A9A9A9", hover_color="#8B8B8B", corner_radius=8).pack(side="left", padx=5)

                logging.info(f"Plantilla '{nombre_plantilla}' guardada y datos capturados correctamente")

            ctk.CTkButton(button_frame_nombre, text="Continuar", command=continuar, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8).pack(side="left", padx=5)
            ctk.CTkButton(button_frame_nombre, text="Cancelar", command=ventana_nombre.destroy, fg_color="#A9A9A9", hover_color="#8B8B8B", corner_radius=8).pack(side="left", padx=5)

        except Exception as e:
            self.show_message(f"Error al capturar datos: {str(e)}", "red")
            logging.error(f"Error en capturar_datos_formulario para tienda {self.store_id}: {str(e)}")

    def cargar_plantilla(self, nombre_plantilla):
        try:
            logging.info(f"Cargando plantilla '{nombre_plantilla}' para tienda {self.store_id}")
            if not os.path.exists(self.plantillas_file):
                self.show_message("No se encontraron plantillas guardadas.", "red")
                return
            with open(self.plantillas_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            plantilla = None
            for p in data["plantillas"]:
                if p["nombre_plantilla"] == nombre_plantilla:
                    plantilla = p
                    break
            if not plantilla:
                self.show_message(f"No se encontró la plantilla '{nombre_plantilla}'.", "red")
                return
            self.limpiar_formulario()
            self.app.entry_nombre.insert(0, plantilla["nombre_plantilla"])
            if plantilla["tipo_prenda"]:
                self.app.combo_tipo_prenda.set(plantilla["tipo_prenda"])
            if plantilla["tipo_pieza"]:
                self.app.combo_tipo_pieza.set(plantilla["tipo_pieza"])
            if plantilla["marca"]:
                self.app.combo_marca.set(plantilla["marca"])
            if plantilla["atributo"]:
                self.app.combo_atributo.set(plantilla["atributo"])
            if plantilla["genero"]:
                self.app.combo_genero.set(plantilla["genero"])
            if plantilla["nivel_educativo"]:
                self.app.combo_nivel_educativo.set(plantilla["nivel_educativo"])
            if plantilla.get("escuelas", []):
                self.app.combo_escuela.set(plantilla["escuelas"])
            if plantilla["ubicacion"]:
                self.app.combo_ubicacion.set(plantilla["ubicacion"])
            if plantilla["escudo"]:
                self.app.combo_escudo.set(plantilla["escudo"])
            if plantilla["precio"]:
                self.app.entry_precio.insert(0, plantilla["precio"])
            for talla in plantilla["tallas"]:
                if talla in self.app.talla_vars:
                    self.app.talla_vars[talla].set(True)
            for color in plantilla["colores"]:
                if color in self.app.color_vars:
                    self.app.color_vars[color].set(True)
            self.omitir_tipo_prenda_var.set(plantilla["omitir"]["tipo_prenda"])
            self.app.combo_tipo_prenda.configure(state="disabled" if plantilla["omitir"]["tipo_prenda"] else "normal")
            self.omitir_tipo_pieza_var.set(plantilla["omitir"]["tipo_pieza"])
            self.app.combo_tipo_pieza.configure(state="disabled" if plantilla["omitir"]["tipo_pieza"] else "normal")
            self.omitir_marca_var.set(plantilla["omitir"]["marca"])
            self.app.combo_marca.configure(state="disabled" if plantilla["omitir"]["marca"] else "normal")
            self.omitir_atributo_var.set(plantilla["omitir"]["atributo"])
            self.app.combo_atributo.configure(state="disabled" if plantilla["omitir"]["atributo"] else "normal")
            self.omitir_genero_var.set(plantilla["omitir"]["genero"])
            self.app.combo_genero.configure(state="disabled" if plantilla["omitir"]["genero"] else "normal")
            self.omitir_nivel_var.set(plantilla["omitir"]["nivel_educativo"])
            self.app.combo_nivel_educativo.configure(state="disabled" if plantilla["omitir"]["nivel_educativo"] else "normal")
            self.omitir_escuela_var.set(plantilla["omitir"]["escuela"])
            self.app.combo_escuela.configure(state="disabled" if plantilla["omitir"]["escuela"] else "normal")
            self.omitir_ubicacion_var.set(plantilla["omitir"]["ubicacion"])
            self.app.combo_ubicacion.configure(state="disabled" if plantilla["omitir"]["ubicacion"] else "normal")
            self.omitir_escudo_var.set(plantilla["omitir"]["escudo"])
            self.app.combo_escudo.configure(state="disabled" if plantilla["omitir"]["escudo"] else "normal")
            self.omitir_color_var.set(plantilla["omitir"]["colores"])
            for widget in self.app.colores_inner_frame.winfo_children():
                if isinstance(widget, ctk.CTkCheckBox):
                    widget.configure(state="disabled" if plantilla["omitir"]["colores"] else "normal")
            self.show_message(f"Plantilla '{nombre_plantilla}' cargada correctamente.", "green")
            logging.info(f"Plantilla '{nombre_plantilla}' cargada para tienda {self.store_id}")
        except Exception as e:
            self.show_message(f"Error al cargar plantilla: {str(e)}", "red")
            logging.error(f"Error en cargar_plantilla para tienda {self.store_id}: {str(e)}")