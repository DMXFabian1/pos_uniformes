import tkinter as tk
import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
from src.core.config.config import CONFIG, exportar_configuraciones
from src.core.config.controller import Controller
from src.modules.maintenance.maintenance import abrir_mantenimiento
from src.core.utils.tooltips import ToolTip
from src.ui.ui_components import create_field, validate_string, validate_numeric_entry, create_check_combobox
from src.core.utils.utils import validate_path, check_disk_space
import os
import platform
from pathlib import Path
import shutil
from datetime import datetime
import re
from src.core.config.db_manager import DatabaseManager
import logging
import json

class GeneradorCodigos:
    def __init__(self, parent, icons=None, db_manager=None, store_id=1):
        self.parent = parent
        self.icons = icons or {}
        self.store_id = store_id
        logging.info(f"Iniciando GeneradorCodigos para tienda {self.store_id}")
        print("Iniciando GeneradorCodigos")
        
        self.root_folder = CONFIG["ROOT_FOLDER"]
        self.image_folder = os.path.join(self.root_folder, CONFIG["IMAGES_DIR"])
        self.qr_folder = os.path.join(self.root_folder, CONFIG["QR_DIR"])
        self.db_path = os.path.join(self.root_folder, CONFIG["DB_NAME"])
        self.plantillas_file = os.path.join(self.root_folder, "plantillas_productos.json")
        
        config_path = os.path.join(self.root_folder, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    if "COLORES" in loaded_config:
                        CONFIG["COLORES"] = loaded_config["COLORES"]
                        logging.info(f"Colores cargados desde config.json: {CONFIG['COLORES']}")
            except Exception as e:
                logging.error(f"Error al cargar config.json: {str(e)}")
        
        self.db_manager = db_manager or DatabaseManager()
        
        self.controller = Controller(self)
        self.talla_vars = {talla: tk.BooleanVar() for talla in CONFIG["TALLAS"]}
        self.color_vars = {color: tk.BooleanVar() for color in CONFIG["COLORES"]}
        self.tallas_personalizadas = []
        self.tallas_numericas_personalizadas = []
        self.colores_personalizados = []
        self.image_path = None
        self.image_preview = None
        
        self.all_tallas_numericas = sorted(set([t for t in CONFIG["TALLAS"] if t.isdigit()]), key=int)
        self.all_colores = sorted(set(CONFIG["COLORES"]))
        self.tallas_americanas = ["XS", "S", "M", "L", "XL", "XXL", "XXXL", "XXXXL"]
        self.tallas_españolas = ["CH", "MD", "GD", "EXG"]
        self.tallas_especiales = ["Uni", "ESP", "NT"]
        self.tallas_malla_calceta = ["0-0", "0-2", "3-5", "6-8", "9-12", "13-18", "CH-MD", "GD-EXG", "Dama"]
        self.all_escuelas = sorted([escuela['nombre'] for escuela in self.db_manager.get_escuelas(self.store_id)])
        
        self.main_frame = ctk.CTkFrame(self.parent, fg_color="#FFFFFF", corner_radius=10, border_width=1, border_color="#A3BFFA")
        
        logging.info("Antes de setup_ui")
        print("Antes de setup_ui")
        self.setup_ui()
        logging.info(f"GeneradorCodigos inicializado para tienda {self.store_id}")
        print("GeneradorCodigos inicializado")

    def remove_duplicates(self, items):
        return sorted(set(items))

    def blink_button(self, button, original_color="#4A90E2", blink_color="#00FF00", duration=100, cycles=3):
        def blink_step(count):
            if count <= 0:
                button.configure(fg_color=original_color)
                return
            button.configure(fg_color=blink_color if count % 2 == 0 else original_color)
            self.parent.after(duration, lambda: blink_step(count - 1))
        
        blink_step(cycles * 2)

    def show_action_message(self, label, message, color="#00A86B", duration=2000):
        label.configure(text=message, text_color=color)
        self.parent.after(duration, lambda: label.configure(text=""))

    def validate_field(self, value, widget):
        try:
            logging.info("Validando campo de nombre")
            return validate_string(widget, "Nombre")
        except Exception as e:
            logging.error(f"Error en validate_field para tienda {self.store_id}: {str(e)}")
            return False

    def validate_price(self, value):
        try:
            logging.info("Validando precio")
            if not value:
                self.entry_precio.configure(fg_color="#FFFFFF", border_color="#A3BFFA")
                return True
            if value == ".":
                self.entry_precio.configure(fg_color="#FFFFFF", border_color="#A3BFFA")
                return True
            if value.endswith(".") or value.startswith("."):
                self.entry_precio.configure(fg_color="#FFFFFF", border_color="#A3BFFA")
                return True
            num = float(value)
            if num < 0:
                self.entry_precio.configure(fg_color="#FFE6E6", border_color="#FF5555")
                return False
            self.entry_precio.configure(fg_color="#FFFFFF", border_color="#A3BFFA")
            return True
        except ValueError:
            self.entry_precio.configure(fg_color="#FFE6E6", border_color="#FF5555")
            return False
        except Exception as e:
            logging.error(f"Error en validate_price para tienda {self.store_id}: {str(e)}")
            self.entry_precio.configure(fg_color="#FFE6E6", border_color="#FF5555")
            return False

    def validate_price_final(self):
        try:
            logging.info("Validando precio final")
            value = self.entry_precio.get().strip()
            if not value:
                self.entry_precio.configure(fg_color="#FFFFFF", border_color="#A3BFFA")
                return True
            num = float(value)
            if num < 0:
                self.entry_precio.configure(fg_color="#FFE6E6", border_color="#FF5555")
                messagebox.showwarning("Advertencia", "El campo Precio no puede ser negativo.")
                return False
            self.entry_precio.configure(fg_color="#FFFFFF", border_color="#A3BFFA")
            return True
        except ValueError:
            self.entry_precio.configure(fg_color="#FFE6E6", border_color="#FF5555")
            messagebox.showwarning("Advertencia", "El campo Precio debe ser un número válido.")
            return False
        except Exception as e:
            logging.error(f"Error en validate_price_final para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"Error al validar precio: {str(e)}")
            return False

    def select_image(self):
        try:
            logging.info("Botón Seleccionar Imagen clicado")
            file_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.gif *.bmp")])
            if file_path:
                validate_path(self.image_folder)
                check_disk_space(self.root_folder)
                os.makedirs(self.image_folder, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_extension = os.path.splitext(file_path)[1]
                new_filename = f"product_image_{timestamp}{file_extension}"
                new_file_path = os.path.join(self.image_folder, new_filename)
                shutil.copy(file_path, new_file_path)
                self.image_path = os.path.join("ProductImages", new_filename)
                img = Image.open(new_file_path)
                img = img.resize((150, 150), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.image_label.configure(image=photo, text="")
                self.image_label.image = photo
                logging.info(f"Imagen seleccionada: {new_filename} para tienda {self.store_id}")
            else:
                self.image_path = None
                self.image_label.configure(image=None, text="Sin imagen seleccionada")
                logging.info("Selección de imagen cancelada")
        except PermissionError:
            messagebox.showerror("Error de permisos", "No tienes permisos para guardar la imagen en la carpeta ProductImages.")
            self.image_path = None
            self.image_label.configure(image=None, text="Vista previa no disponible")
            logging.error(f"Error de permisos al guardar imagen para tienda {self.store_id}")
        except OSError as e:
            messagebox.showerror("Error del sistema", f"No se pudo copiar la imagen: {str(e)}.")
            self.image_path = None
            self.image_label.configure(image=None, text="Vista previa no disponible")
            logging.error(f"Error del sistema al copiar imagen para tienda {self.store_id}: {str(e)}")
        except (IOError, Image.UnidentifiedImageError):
            messagebox.showerror("Error de imagen", "La imagen seleccionada está corrupta o no es un formato válido.")
            self.image_path = None
            self.image_label.configure(image=None, text="Vista previa no disponible")
            logging.error(f"Imagen corrupta o formato inválido para tienda {self.store_id}")
        except Exception as e:
            messagebox.showerror("Error inesperado", f"Ocurrió un error inesperado al cargar la imagen: {str(e)}")
            self.image_path = None
            self.image_label.configure(image=None, text="Vista previa no disponible")
            logging.error(f"Error inesperado en select_image para tienda {self.store_id}: {str(e)}")

    def update_name(self, event=None):
        try:
            logging.info("Actualizando nombre del producto")
            print("update_name called")
            tipo_pieza = self.combo_tipo_pieza.get() if not self.controller.omitir_tipo_pieza_var.get() else ""
            marca = self.combo_marca.get() if not self.controller.omitir_marca_var.get() else ""
            atributo = self.combo_atributo.get() if not self.controller.omitir_atributo_var.get() else ""
            genero = self.combo_genero.get() if not self.controller.omitir_genero_var.get() else ""
            genero_abreviatura = ""
            if genero:
                if genero.lower() == "hombre":
                    genero_abreviatura = "H"
                elif genero.lower() == "mujer":
                    genero_abreviatura = "M"
                elif genero.lower() == "unisex":
                    genero_abreviatura = "U"
            name_parts = [part for part in [tipo_pieza, marca, atributo, genero_abreviatura] if part]
            generated_name = " ".join(name_parts)
            print(f"Generated name: {generated_name}")
            self.entry_nombre.delete(0, "end")
            self.entry_nombre.insert(0, generated_name)
            
            self.blink_button(self.btn_generar_nombre)
            self.show_action_message(self.message_label_action, "Nombre generado")
            
            logging.info(f"Nombre generado: {generated_name} para tienda {self.store_id}")
        except Exception as e:
            logging.error(f"Error en update_name para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"Error al actualizar nombre: {str(e)}")

    def get_selected_tallas(self):
        try:
            logging.info("Obteniendo tallas seleccionadas")
            selected = [talla for talla, var in self.talla_vars.items() if var.get()]
            logging.info(f"Tallas seleccionadas: {selected} para tienda {self.store_id}")
            return selected
        except Exception as e:
            logging.error(f"Error en get_selected_tallas para tienda {self.store_id}: {str(e)}")
            return []

    def get_selected_colors(self):
        try:
            logging.info("Obteniendo colores seleccionados")
            selected = [color for color, var in self.color_vars.items() if var.get()]
            logging.info(f"Colores seleccionados: {selected} para tienda {self.store_id}")
            return selected
        except Exception as e:
            logging.error(f"Error en get_selected_colors para tienda {self.store_id}: {str(e)}")
            return []

    def get_selected_escuelas(self):
        try:
            logging.info("Obteniendo escuelas seleccionadas")
            selected = self.combo_escuela.get_selected()
            logging.info(f"Escuelas seleccionadas: {selected} para tienda {self.store_id}")
            return selected
        except Exception as e:
            logging.error(f"Error en get_selected_escuelas para tienda {self.store_id}: {str(e)}")
            return []

    def añadir_talla_personalizada(self):
        try:
            logging.info("Botón Añadir Talla Personalizada clicado")
            talla = self.talla_personalizada_entry.get().strip()
            if not talla:
                messagebox.showwarning("Advertencia", "La talla personalizada no puede estar vacía.")
                logging.warning(f"Talla personalizada vacía para tienda {self.store_id}")
                return
            if not re.match(r'^[\w-\/]+$', talla):
                messagebox.showwarning("Advertencia", "La talla solo puede contener letras, números, '-' y '/'.")
                logging.warning(f"Talla personalizada inválida: {talla} para tienda {self.store_id}")
                return
            if len(talla) > 10:
                messagebox.showwarning("Advertencia", "La talla no puede tener más de 10 caracteres.")
                logging.warning(f"Talla personalizada demasiado larga: {talla} para tienda {self.store_id}")
                return
            talla_lower = talla.lower()
            if talla_lower in [t.lower() for t in self.talla_vars.keys()]:
                messagebox.showwarning("Advertencia", f"La talla '{talla}' ya existe.")
                logging.warning(f"Talla personalizada ya existe: {talla} para tienda {self.store_id}")
                return
            self.talla_vars[talla] = tk.BooleanVar()
            self.tallas_personalizadas.append(talla)
            
            CONFIG["TALLAS"] = self.remove_duplicates(CONFIG["TALLAS"])
            if talla not in CONFIG["TALLAS"]:
                CONFIG["TALLAS"].append(talla)
                CONFIG["TALLAS"] = self.remove_duplicates(CONFIG["TALLAS"])
                exportar_configuraciones(CONFIG, os.path.join(CONFIG["ROOT_FOLDER"], "config.json"))
                logging.info(f"Talla '{talla}' añadida a CONFIG['TALLAS'] y guardada en config.json para tienda {self.store_id}")

            for widget in self.tallas_personalizadas_inner_frame.winfo_children():
                widget.destroy()
            self.tallas_personalizadas_inner_frame.grid_forget()

            combined_tallas = self.tallas_personalizadas
            tallas_personalizadas_no_numericas = self.remove_duplicates([talla for talla in combined_tallas if not talla.isdigit()])
            num_rows = (len(tallas_personalizadas_no_numericas) + 4) // 5
            self.tallas_personalizadas_inner_frame.configure(height=num_rows * 40)

            self.tallas_personalizadas_inner_frame.grid(row=0, column=0, sticky="w")
            for i, talla_item in enumerate(tallas_personalizadas_no_numericas):
                if talla_item not in self.talla_vars:
                    self.talla_vars[talla_item] = tk.BooleanVar()
                cb = ctk.CTkCheckBox(self.tallas_personalizadas_inner_frame, text=talla_item, variable=self.talla_vars[talla_item], 
                                     fg_color="#4A90E2", border_color="#A3BFFA", hover_color="#E6F0FA", text_color="#4B5EAA")
                cb.grid(row=i // 5, column=i % 5, padx=10, pady=5, sticky="w")

            self.tallas_personalizadas_inner_frame.update_idletasks()
            self.canvas_tallas.configure(scrollregion=self.canvas_tallas.bbox("all"))

            self.talla_personalizada_entry.delete(0, tk.END)
            messagebox.showinfo("Éxito", f"Talla personalizada '{talla}' añadida y guardada.")
            logging.info(f"Talla personalizada '{talla}' añadida para tienda {self.store_id}")
        except Exception as e:
            messagebox.showerror("Error", f"Error al añadir talla personalizada: {str(e)}")
            logging.error(f"Error en añadir_talla_personalizada para tienda {self.store_id}: {str(e)}")

    def añadir_talla_numerica_personalizada(self):
        try:
            logging.info("Botón Añadir Talla Numérica Personalizada clicado")
            talla = self.talla_numerica_personalizada_entry.get().strip()
            if not talla:
                messagebox.showwarning("Advertencia", "La talla numérica no puede estar vacía.")
                logging.warning(f"Talla numérica vacía para tienda {self.store_id}")
                return
            try:
                talla_num = int(talla)
                if talla_num <= 0:
                    messagebox.showwarning("Advertencia", "La talla debe ser un número entero positivo.")
                    logging.warning(f"Talla numérica inválida (no positiva): {talla} para tienda {self.store_id}")
                    return
            except ValueError:
                messagebox.showwarning("Advertencia", "La talla debe ser un número entero válido.")
                logging.warning(f"Talla numérica inválida (no numérica): {talla} para tienda {self.store_id}")
                return
            if len(talla) > 10:
                messagebox.showwarning("Advertencia", "La talla no puede tener más de 10 caracteres.")
                logging.warning(f"Talla numérica demasiado larga: {talla} para tienda {self.store_id}")
                return
            existing_tallas = [t for t in self.talla_vars.keys()]
            if talla in existing_tallas:
                messagebox.showwarning("Advertencia", f"La talla '{talla}' ya existe.")
                logging.warning(f"Talla numérica ya existe: {talla} para tienda {self.store_id}")
                return
            self.talla_vars[talla] = tk.BooleanVar()
            self.tallas_numericas_personalizadas.append(talla)

            CONFIG["TALLAS"] = self.remove_duplicates(CONFIG["TALLAS"])
            if talla not in CONFIG["TALLAS"]:
                CONFIG["TALLAS"].append(talla)
                CONFIG["TALLAS"] = self.remove_duplicates(CONFIG["TALLAS"])
                exportar_configuraciones(CONFIG, os.path.join(CONFIG["ROOT_FOLDER"], "config.json"))
                logging.info(f"Talla numérica '{talla}' añadida a CONFIG['TALLAS'] y guardada en config.json para tienda {self.store_id}")

            for widget in self.tallas_numericas_inner_frame.winfo_children():
                widget.destroy()
            self.tallas_numericas_inner_frame.grid_forget()

            combined_tallas = [t for t in CONFIG["TALLAS"] if t.isdigit()] + self.tallas_numericas_personalizadas
            self.all_tallas_numericas = self.remove_duplicates(combined_tallas)
            self.all_tallas_numericas = sorted(self.all_tallas_numericas, key=int)
            num_rows = (len(self.all_tallas_numericas) + 4) // 5
            self.tallas_numericas_inner_frame.configure(height=num_rows * 40)

            self.tallas_numericas_inner_frame.grid(row=0, column=0, sticky="w")
            for i, talla_item in enumerate(self.all_tallas_numericas):
                if talla_item not in self.talla_vars:
                    self.talla_vars[talla_item] = tk.BooleanVar()
                cb = ctk.CTkCheckBox(self.tallas_numericas_inner_frame, text=talla_item, variable=self.talla_vars[talla_item], 
                                     fg_color="#4A90E2", border_color="#A3BFFA", hover_color="#E6F0FA", text_color="#4B5EAA")
                cb.grid(row=i // 5, column=i % 5, padx=10, pady=5, sticky="w")

            self.tallas_numericas_inner_frame.update_idletasks()
            self.canvas_tallas.configure(scrollregion=self.canvas_tallas.bbox("all"))

            self.talla_numerica_personalizada_entry.delete(0, tk.END)
            messagebox.showinfo("Éxito", f"Talla numérica '{talla}' añadida y guardada.")
            logging.info(f"Talla numérica '{talla}' añadida para tienda {self.store_id}")
        except Exception as e:
            messagebox.showerror("Error", f"Error al añadir talla numérica: {str(e)}")
            logging.error(f"Error en añadir_talla_numerica_personalizada para tienda {self.store_id}: {str(e)}")

    def añadir_color_personalizado(self):
        try:
            logging.info("Botón Añadir Color Personalizado clicado")
            color = self.color_personalizado_entry.get().strip()
            if not color:
                messagebox.showwarning("Advertencia", "El color personalizado no puede estar vacío.")
                logging.warning(f"Color personalizado vacío para tienda {self.store_id}")
                return
            if not re.match(r'^[\w\s-]+$', color):
                messagebox.showwarning("Advertencia", "El color solo puede contener letras, números, espacios, '-' y '/'.")
                logging.warning(f"Color personalizado inválido: {color} para tienda {self.store_id}")
                return
            if len(color) > 20:
                messagebox.showwarning("Advertencia", "El color no puede tener más de 20 caracteres.")
                logging.warning(f"Color personalizado demasiado largo: {color} para tienda {self.store_id}")
                return
            color_lower = color.lower()
            if color_lower in [c.lower() for c in self.color_vars.keys()]:
                messagebox.showwarning("Advertencia", f"El color '{color}' ya existe.")
                logging.warning(f"Color personalizado ya existe: {color} para tienda {self.store_id}")
                return
            color = color.capitalize()
            self.color_vars[color] = tk.BooleanVar()
            self.colores_personalizados.append(color)

            CONFIG["COLORES"] = self.remove_duplicates(CONFIG["COLORES"])
            if color not in CONFIG["COLORES"]:
                CONFIG["COLORES"].append(color)
                CONFIG["COLORES"] = self.remove_duplicates(CONFIG["COLORES"])
                exportar_configuraciones(CONFIG, os.path.join(CONFIG["ROOT_FOLDER"], "config.json"))
                logging.info(f"Color '{color}' añadido a CONFIG['COLORES'] y guardado en config.json para tienda {self.store_id}")

            for widget in self.colores_inner_frame.winfo_children():
                widget.destroy()
            self.colores_inner_frame.grid_forget()

            combined_colores = CONFIG["COLORES"] + self.colores_personalizados
            self.all_colores = self.remove_duplicates(combined_colores)
            num_rows = (len(self.all_colores) + 3) // 4
            self.colores_inner_frame.configure(height=num_rows * 40)

            self.colores_inner_frame.grid(row=0, column=1, sticky="w")
            for i, color_item in enumerate(self.all_colores):
                if color_item not in self.color_vars:
                    self.color_vars[color_item] = tk.BooleanVar()
                cb = ctk.CTkCheckBox(self.colores_inner_frame, text=color_item, variable=self.color_vars[color_item], 
                                     fg_color="#4A90E2", border_color="#A3BFFA", hover_color="#E6F0FA", text_color="#4B5EAA",
                                     command=self.update_name)
                cb.grid(row=i // 4, column=i % 4, padx=10, pady=5, sticky="w")
                ToolTip(cb, f"Seleccionar el color {color_item}")

            self.colores_inner_frame.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

            self.color_personalizado_entry.delete(0, tk.END)
            messagebox.showinfo("Éxito", f"Color personalizado '{color}' añadido y guardado.")
            logging.info(f"Color personalizado '{color}' añadido para tienda {self.store_id}")
        except Exception as e:
            messagebox.showerror("Error", f"Error al añadir color personalizado: {str(e)}")
            logging.error(f"Error en añadir_color_personalizado para tienda {self.store_id}: {str(e)}")

    def añadir_escuela_personalizada(self):
        try:
            logging.info("Botón Añadir Escuela Personalizada clicado")
            escuela = self.escuela_entry.get().strip()
            if not escuela:
                messagebox.showwarning("Advertencia", "El nombre de la escuela no puede estar vacío.")
                logging.warning(f"Escuela vacía para tienda {self.store_id}")
                return
            if not re.match(r'^[\w\s\-\'"]+$', escuela):
                messagebox.showwarning("Advertencia", "El nombre de la escuela solo puede contener letras, números, espacios, guiones, comillas y apóstrofes.")
                logging.warning(f"Escuela inválida: {escuela} para tienda {self.store_id}")
                return
            if len(escuela) > 100:
                messagebox.showwarning("Advertencia", "El nombre de la escuela no puede tener más de 100 caracteres.")
                logging.warning(f"Escuela demasiado larga: {escuela} para tienda {self.store_id}")
                return
            escuela_lower = escuela.lower()
            if escuela_lower in [e.lower() for e in self.all_escuelas]:
                messagebox.showwarning("Advertencia", f"La escuela '{escuela}' ya existe.")
                logging.warning(f"Escuela ya existe: {escuela} para tienda {self.store_id}")
                return
            escuela_id = self.db_manager.add_escuela(escuela, self.store_id)
            self.all_escuelas = sorted([esc['nombre'] for esc in self.db_manager.get_escuelas(self.store_id)])
            self.combo_escuela.configure(values=self.all_escuelas)
            self.combo_escuela.set([escuela])
            self.escuela_entry.delete(0, tk.END)
            messagebox.showinfo("Éxito", f"Escuela '{escuela}' añadida con ID {escuela_id}.")
            logging.info(f"Escuela '{escuela}' añadida con ID {escuela_id} para tienda {self.store_id}")
        except Exception as e:
            messagebox.showerror("Error", f"Error al añadir escuela: {str(e)}")
            logging.error(f"Error en añadir_escuela_personalizada para tienda {self.store_id}: {str(e)}")

    def seleccionar_tallas(self, tallas_a_seleccionar):
        try:
            logging.info(f"Seleccionando tallas: {tallas_a_seleccionar} para tienda {self.store_id}")
            for var in self.talla_vars.values():
                var.set(False)
            for talla in tallas_a_seleccionar:
                if talla in self.talla_vars:
                    self.talla_vars[talla].set(True)
            logging.info(f"Tallas seleccionadas: {tallas_a_seleccionar} para tienda {self.store_id}")
        except Exception as e:
            logging.error(f"Error en seleccionar_tallas para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"Error al seleccionar tallas: {str(e)}")

    def seleccionar_tallas_pants(self):
        try:
            logging.info("Botón Tallas Pants clicado")
            tallas_pants = ["16", "CH", "MD", "GD", "EXG"]
            self.seleccionar_tallas(tallas_pants)
        except Exception as e:
            logging.error(f"Error en seleccionar_tallas_pants para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"Error al seleccionar tallas pants: {str(e)}")

    def seleccionar_tallas_mallas(self):
        try:
            logging.info("Botón Tallas Mallas clicado")
            tallas_mallas = ["0-0", "0-2", "3-5", "6-8", "9-12", "13-18", "CH-MD", "GD-EXG", "Dama"]
            self.seleccionar_tallas(tallas_mallas)
        except Exception as e:
            logging.error(f"Error en seleccionar_tallas_mallas para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"Error al seleccionar tallas mallas: {str(e)}")

    def seleccionar_tallas_basicas(self):
        try:
            logging.info("Botón Tallas Básicas clicado")
            tallas_basicas = ["2", "4", "6", "8", "10", "12", "14", "16"]
            self.seleccionar_tallas(tallas_basicas)
        except Exception as e:
            logging.error(f"Error en seleccionar_tallas_basicas para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"Error al seleccionar tallas básicas: {str(e)}")

    def actualizar_plantillas_combo(self):
        try:
            if os.path.exists(self.plantillas_file):
                with open(self.plantillas_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                nombres_plantillas = [p["nombre_plantilla"] for p in data["plantillas"]]
                self.combo_plantillas.configure(values=nombres_plantillas)
                if nombres_plantillas:
                    self.combo_plantillas.set(nombres_plantillas[0])
                else:
                    self.combo_plantillas.set("")
            else:
                self.combo_plantillas.configure(values=[""])
                self.combo_plantillas.set("")
        except Exception as e:
            logging.error(f"Error al actualizar combo de plantillas para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"Error al cargar plantillas: {str(e)}")

    def setup_ui(self):
        try:
            logging.info("Iniciando setup_ui")
            print("Iniciando setup_ui")
            top_bar = ctk.CTkFrame(self.main_frame, fg_color="#003087", corner_radius=0)
            top_bar.pack(fill="x")
            ctk.CTkLabel(top_bar, text="Generador de Códigos", font=("Helvetica", 18, "bold"), text_color="#FFFFFF").pack(side="left", padx=15, pady=10)
            action_frame = ctk.CTkFrame(top_bar, fg_color="transparent")
            action_frame.pack(side="right", padx=15)
            ctk.CTkButton(action_frame, text="🛠 Mantenimiento", command=lambda: abrir_mantenimiento(self), fg_color="#4A90E2", hover_color="#2A6EBB", width=120, corner_radius=8, font=("Helvetica", 12)).pack(side="left", padx=5)

            content_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
            content_frame.pack(fill="both", expand=True)
            content_frame.grid_rowconfigure(0, weight=1)
            content_frame.grid_columnconfigure(0, weight=1)
            content_frame.grid_columnconfigure(1, weight=1)
            content_frame.grid_columnconfigure(2, weight=1)

            left_frame = ctk.CTkFrame(content_frame, fg_color="#F5F7FA", corner_radius=10, border_width=1, border_color="#A3BFFA")
            left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
            ctk.CTkLabel(left_frame, text="Datos del Producto", font=("Helvetica", 16, "bold"), text_color="#1A2E5A").pack(pady=10)

            canvas = tk.Canvas(left_frame, bg="#F5F7FA", highlightthickness=0)
            scrollbar = ctk.CTkScrollbar(left_frame, orientation="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True, padx=15, pady=5)
            scrollbar.pack(side="right", fill="y")
            self.canvas = canvas

            data_inner_frame = ctk.CTkFrame(canvas, fg_color="transparent")
            canvas.create_window((0, 0), window=data_inner_frame, anchor="nw")

            nombre_frame = ctk.CTkFrame(data_inner_frame, fg_color="transparent")
            nombre_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=3, pady=3)
            ctk.CTkLabel(nombre_frame, text="Nombre:", font=("Helvetica", 12, "bold"), text_color="#1A2E5A", width=120).grid(row=0, column=0, sticky="e", padx=3, pady=3)
            nombre_inner_frame = ctk.CTkFrame(nombre_frame, fg_color="transparent")
            nombre_inner_frame.grid(row=0, column=1, sticky="w")
            self.entry_nombre = ctk.CTkEntry(nombre_inner_frame, width=300, border_color="#A3BFFA", fg_color="#FFFFFF")
            self.entry_nombre.pack(side="left", padx=3, pady=3)
            self.entry_nombre.focus_set()
            ToolTip(self.entry_nombre, "Nombre del producto (se genera automáticamente o puedes editarlo manualmente)")

            tipo_prenda_field = create_field(data_inner_frame, "Tipo de Prenda:", sorted(CONFIG["TIPOS_PRENDA"]), 1, self.controller.omitir_tipo_prenda_var, self.controller.toggle_field, 
                                            lambda: self.controller.añadir_valor("Tipo de Prenda", self.combo_tipo_prenda, "TIPOS_PRENDA"), update_callback=self.update_name)
            self.combo_tipo_prenda = tipo_prenda_field["combo"]
            ToolTip(self.combo_tipo_prenda, "Categoría general de la prenda (ej. Deportivo)")
            ToolTip(tipo_prenda_field["checkbox"], "Omitir este campo si no aplica")
            if tipo_prenda_field["add_button"]:
                ToolTip(tipo_prenda_field["add_button"], "Añadir un nuevo tipo de prenda")

            tipo_pieza_field = create_field(data_inner_frame, "Tipo de Pieza:", sorted(CONFIG["TIPOS_PIEZA"]), 3, self.controller.omitir_tipo_pieza_var, self.controller.toggle_field, 
                                           lambda: self.controller.añadir_valor("Tipo de Pieza", self.combo_tipo_pieza, "TIPOS_PIEZA"), update_callback=self.update_name)
            self.combo_tipo_pieza = tipo_pieza_field["combo"]
            ToolTip(self.combo_tipo_pieza, "Tipo específico de prenda (ej. Camisa)")
            ToolTip(tipo_pieza_field["checkbox"], "Omitir este campo si no aplica")
            if tipo_pieza_field["add_button"]:
                ToolTip(tipo_pieza_field["add_button"], "Añadir un nuevo tipo de pieza")

            marca_field = create_field(data_inner_frame, "Marca:", sorted(CONFIG["MARCAS"]), 5, self.controller.omitir_marca_var, self.controller.toggle_field, 
                                      lambda: self.controller.añadir_valor("Marca", self.combo_marca, "MARCAS", "ULTIMA_MARCA"), CONFIG.get("ULTIMA_MARCA", ""), update_callback=self.update_name)
            self.combo_marca = marca_field["combo"]
            ToolTip(self.combo_marca, "Marca del producto (ej. Lobito)")
            ToolTip(marca_field["checkbox"], "Omitir este campo si no aplica")
            if marca_field["add_button"]:
                ToolTip(marca_field["add_button"], "Añadir una nueva marca")

            colores_frame = ctk.CTkFrame(data_inner_frame, fg_color="transparent")
            colores_frame.grid(row=7, column=0, columnspan=2, sticky="ew", padx=3, pady=3)
            ctk.CTkLabel(colores_frame, text="Colores:", font=("Helvetica", 12, "bold"), text_color="#1A2E5A", width=120).grid(row=0, column=0, sticky="e", padx=3, pady=3)
            colores_inner_frame = ctk.CTkFrame(colores_frame, fg_color="transparent", width=500)
            colores_inner_frame.grid(row=0, column=1, sticky="w")
            colores_inner_frame.grid_propagate(False)
            self.colores_inner_frame = colores_inner_frame
            num_rows = (len(self.all_colores) + 3) // 4
            colores_inner_frame.configure(height=num_rows * 40)
            for i, color in enumerate(self.all_colores):
                if color not in self.color_vars:
                    self.color_vars[color] = tk.BooleanVar()
                cb = ctk.CTkCheckBox(colores_inner_frame, text=color, variable=self.color_vars[color], 
                                     fg_color="#4A90E2", border_color="#A3BFFA", hover_color="#E6F0FA", text_color="#4B5EAA",
                                     command=self.update_name)
                cb.grid(row=i // 4, column=i % 4, padx=10, pady=5, sticky="w")
                ToolTip(cb, f"Seleccionar el color {color}")
            checkbox_colores = ctk.CTkCheckBox(colores_frame, text="Omitir Colores", variable=self.controller.omitir_color_var, 
                                               command=lambda: self.controller.toggle_field(self.controller.omitir_color_var, colores_inner_frame),
                                               fg_color="#4A90E2", text_color="#4B5EAA")
            checkbox_colores.grid(row=1, column=1, sticky="w", padx=3, pady=3)
            ToolTip(checkbox_colores, "Omitir la selección de colores si no aplica")
            colores_personalizados_frame = ctk.CTkFrame(colores_frame, fg_color="transparent")
            colores_personalizados_frame.grid(row=2, column=1, sticky="w", pady=5)
            ctk.CTkLabel(colores_personalizados_frame, text="Color Personalizado:", font=("Helvetica", 12, "bold"), text_color="#1A2E5A").pack(side="left", padx=5)
            self.color_personalizado_entry = ctk.CTkEntry(colores_personalizados_frame, width=100)
            self.color_personalizado_entry.pack(side="left", padx=5)
            ctk.CTkButton(colores_personalizados_frame, text="Añadir Color", 
                          command=self.añadir_color_personalizado, 
                          fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=100, font=("Helvetica", 12)).pack(side="left", padx=5)
            ToolTip(self.color_personalizado_entry, "Ingresa un color personalizado para añadirlo")

            atributo_field = create_field(data_inner_frame, "Atributo:", sorted(CONFIG["ATRIBUTOS"]), 9, self.controller.omitir_atributo_var, self.controller.toggle_field, 
                                         lambda: self.controller.añadir_valor("Atributo", self.combo_atributo, "ATRIBUTOS"), update_callback=self.update_name)
            self.combo_atributo = atributo_field["combo"]
            ToolTip(self.combo_atributo, "Característica adicional del producto (ej. Manga Corta)")
            ToolTip(atributo_field["checkbox"], "Omitir este campo si no aplica")
            if atributo_field["add_button"]:
                ToolTip(atributo_field["add_button"], "Añadir un nuevo atributo")

            genero_field = create_field(data_inner_frame, "Género:", sorted(CONFIG["GENEROS"]), 11, self.controller.omitir_genero_var, self.controller.toggle_field, update_callback=self.update_name)
            self.combo_genero = genero_field["combo"]
            ToolTip(self.combo_genero, "Género del producto (Mujer, Hombre, Unisex)")
            ToolTip(genero_field["checkbox"], "Omitir este campo si no aplica")

            nivel_educativo_field = create_field(data_inner_frame, "Nivel Educativo:", sorted(CONFIG["NIVELES_EDUCATIVOS"]), 13, self.controller.omitir_nivel_var, self.controller.toggle_field, 
                                                lambda: self.controller.añadir_valor("Nivel Educativo", self.combo_nivel_educativo, "NIVELES_EDUCATIVOS"), update_callback=self.update_name)
            self.combo_nivel_educativo = nivel_educativo_field["combo"]
            ToolTip(self.combo_nivel_educativo, "Selecciona el nivel educativo asociado al producto (ej. Primaria)")
            ToolTip(nivel_educativo_field["checkbox"], "Omitir este campo si no aplica")
            if nivel_educativo_field["add_button"]:
                ToolTip(nivel_educativo_field["add_button"], "Añadir un nuevo nivel educativo")

            escuela_frame = ctk.CTkFrame(data_inner_frame, fg_color="transparent")
            escuela_frame.grid(row=15, column=0, columnspan=2, sticky="ew", padx=3, pady=3)
            ctk.CTkLabel(escuela_frame, text="Escuela:", font=("Helvetica", 12, "bold"), text_color="#1A2E5A", width=120).grid(row=0, column=0, sticky="e", padx=3, pady=3)
            escuela_inner_frame = ctk.CTkFrame(escuela_frame, fg_color="transparent")
            escuela_inner_frame.grid(row=0, column=1, sticky="w")
            self.combo_escuela = create_check_combobox(escuela_inner_frame, "Escuelas", self.all_escuelas, width=300, command=lambda selected: self.update_name())
            self.combo_escuela.pack(side="left", padx=3, pady=3)
            ToolTip(self.combo_escuela, "Selecciona una o más escuelas asociadas al producto")

            checkbox_escuela = ctk.CTkCheckBox(escuela_frame, text="Omitir Escuelas", variable=self.controller.omitir_escuela_var, 
                                            command=lambda: self.controller.toggle_field(self.controller.omitir_escuela_var, self.combo_escuela), 
                                            fg_color="#4A90E2", text_color="#4B5EAA")
            checkbox_escuela.grid(row=1, column=1, sticky="w", padx=3, pady=3)
            ToolTip(checkbox_escuela, "Omitir la selección de escuelas si no aplica")

            escuela_personalizada_frame = ctk.CTkFrame(escuela_frame, fg_color="transparent")
            escuela_personalizada_frame.grid(row=2, column=1, sticky="w", pady=5)
            ctk.CTkLabel(escuela_personalizada_frame, text="Nueva Escuela:", font=("Helvetica", 12, "bold"), text_color="#1A2E5A").pack(side="left", padx=5)
            self.escuela_entry = ctk.CTkEntry(escuela_personalizada_frame, width=150, placeholder_text="Nueva escuela")
            self.escuela_entry.pack(side="left", padx=3)
            ToolTip(self.escuela_entry, "Ingresa una nueva escuela para añadirla")
            ctk.CTkButton(escuela_personalizada_frame, text="Añadir Escuela", command=self.añadir_escuela_personalizada, 
                        fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=100, font=("Helvetica", 12)).pack(side="left", padx=3)
            ToolTip(self.escuela_entry, "Añade una nueva escuela a la base de datos")

            ubicacion_field = create_field(data_inner_frame, "Ubicación:", sorted(CONFIG["UBICACIONES"]), 17, self.controller.omitir_ubicacion_var, self.controller.toggle_field, 
                                          lambda: self.controller.añadir_valor("Ubicación", self.combo_ubicacion, "UBICACIONES"), update_callback=self.update_name)
            self.combo_ubicacion = ubicacion_field["combo"]
            ToolTip(self.combo_ubicacion, "Ubicación o sucursal (ej. San Felipe)")
            ToolTip(ubicacion_field["checkbox"], "Omitir este campo si no aplica")
            if ubicacion_field["add_button"]:
                ToolTip(ubicacion_field["add_button"], "Añadir una nueva ubicación")

            escudo_field = create_field(data_inner_frame, "Escudo:", sorted(CONFIG["ESCUDOS"]), 19, self.controller.omitir_escudo_var, self.controller.toggle_field, update_callback=self.update_name)
            self.combo_escudo = escudo_field["combo"]
            ToolTip(self.combo_escudo, "Indica si el producto lleva escudo")
            ToolTip(escudo_field["checkbox"], "Omitir este campo si no aplica")

            precio_frame = ctk.CTkFrame(data_inner_frame, fg_color="transparent")
            precio_frame.grid(row=21, column=0, columnspan=2, sticky="ew", padx=3, pady=3)
            ctk.CTkLabel(precio_frame, text="Precio:", font=("Helvetica", 12, "bold"), text_color="#1A2E5A", width=120).grid(row=0, column=0, sticky="e", padx=3, pady=3)
            precio_inner_frame = ctk.CTkFrame(precio_frame, fg_color="transparent")
            precio_inner_frame.grid(row=0, column=1, sticky="w")
            self.entry_precio = ctk.CTkEntry(precio_inner_frame, width=300, placeholder_text="Ej. 150.00", border_color="#A3BFFA", fg_color="#FFFFFF")
            self.entry_precio.pack(side="left", padx=3, pady=3)
            self.entry_precio.configure(validate="key", validatecommand=(self.parent.register(self.validate_price), '%P'))
            self.entry_precio.bind("<FocusOut>", lambda event: self.validate_price_final())
            ToolTip(self.entry_precio, "Precio del producto (ej. 150.00)")

            codigo_frame = ctk.CTkFrame(data_inner_frame, fg_color="transparent")
            codigo_frame.grid(row=23, column=0, columnspan=2, sticky="ew", padx=3, pady=3)
            ctk.CTkLabel(codigo_frame, text="Código Preimpreso:", font=("Helvetica", 12, "bold"), text_color="#1A2E5A", width=120).grid(row=0, column=0, sticky="e", padx=3, pady=3)
            codigo_inner_frame = ctk.CTkFrame(codigo_frame, fg_color="transparent")
            codigo_inner_frame.grid(row=0, column=1, sticky="w")
            self.entry_nomenclatura = ctk.CTkEntry(codigo_inner_frame, width=300, border_color="#A3BFFA", fg_color="#FFFFFF")
            self.entry_nomenclatura.pack(side="left", padx=3, pady=3)
            self.entry_nomenclatura.bind("<KeyPress>", self.controller.barcode_scanned)
            codigo_checkbox = ctk.CTkCheckBox(codigo_frame, text="Usar código preimpreso", variable=self.controller.usar_codigo_preimpreso_var, fg_color="#4A90E2", text_color="#4B5EAA")
            codigo_checkbox.grid(row=1, column=1, sticky="w", padx=3, pady=3)
            ToolTip(self.entry_nomenclatura, "Código preimpreso para etiquetas (si aplica)")
            ToolTip(codigo_checkbox, "Activar para usar un código preimpreso")

            image_frame = ctk.CTkFrame(data_inner_frame, fg_color="transparent")
            image_frame.grid(row=25, column=0, columnspan=2, sticky="ew", padx=3, pady=3)
            ctk.CTkLabel(image_frame, text="Imagen:", font=("Helvetica", 12, "bold"), text_color="#1A2E5A", width=120).grid(row=0, column=0, sticky="e", padx=3, pady=3)
            image_inner_frame = ctk.CTkFrame(image_frame, fg_color="transparent")
            image_inner_frame.grid(row=0, column=1, sticky="w")
            btn_select_image = ctk.CTkButton(image_inner_frame, text="Seleccionar Imagen", command=self.select_image, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12))
            btn_select_image.pack(side="left", padx=3, pady=3)
            ToolTip(btn_select_image, "Selecciona una imagen para el producto")
            self.image_label = ctk.CTkLabel(image_inner_frame, text="Sin imagen seleccionada", width=150, height=150)
            self.image_label.pack(side="left", padx=3, pady=3)

            data_inner_frame.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))

            def on_mouse_scroll(event):
                if canvas.winfo_exists() and canvas.winfo_containing(event.x_root, event.y_root) == canvas:
                    canvas.yview_scroll(int(-event.delta / 120), "units")

            canvas.bind("<MouseWheel>", on_mouse_scroll)

            center_frame = ctk.CTkFrame(content_frame, fg_color="#F5F7FA", corner_radius=10, border_width=1, border_color="#A3BFFA", height=800)
            center_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=0)
            center_frame.grid_propagate(False)
            ctk.CTkLabel(center_frame, text="Tallas", font=("Helvetica", 16, "bold"), text_color="#1A2E5A").pack(pady=10)

            canvas_tallas = tk.Canvas(center_frame, bg="#F5F7FA", highlightthickness=0, height=700)
            scrollbar_tallas = ctk.CTkScrollbar(center_frame, orientation="vertical", command=canvas_tallas.yview)
            canvas_tallas.configure(yscrollcommand=scrollbar_tallas.set)
            canvas_tallas.pack(side="left", fill="both", expand=True, padx=15, pady=5)
            scrollbar_tallas.pack(side="right", fill="y")
            self.canvas_tallas = canvas_tallas

            tallas_inner_frame = ctk.CTkFrame(canvas_tallas, fg_color="transparent")
            canvas_tallas.create_window((0, 0), window=tallas_inner_frame, anchor="nw", tags="inner_frame")

            def adjust_canvas_width(event):
                canvas_width = event.width - 4
                self.canvas_tallas.itemconfig("inner_frame", width=canvas_width)
                tallas_inner_frame.update_idletasks()
                self.canvas_tallas.configure(scrollregion=self.canvas_tallas.bbox("all"))

            canvas_tallas.bind("<Configure>", adjust_canvas_width)

            def agregar_tallas(titulo, lista_tallas, frame, is_numeric=False, is_personalized=False):
                category_frame = ctk.CTkFrame(frame, fg_color="#F5F7FA", border_width=1, border_color="#A3BFFA")
                category_frame.pack(fill="x", padx=5, pady=2, expand=True)
                ctk.CTkLabel(category_frame, text=titulo, font=("Helvetica", 12, "bold"), text_color="#1A2E5A").pack(anchor="w", pady=5)
                sub_frame = ctk.CTkFrame(category_frame, fg_color="transparent")
                sub_frame.pack(fill="x", expand=True)
                sub_frame.grid_propagate(False)
                if is_numeric:
                    self.tallas_numericas_inner_frame = sub_frame
                if is_personalized:
                    self.tallas_personalizadas_inner_frame = sub_frame
                num_rows = (len(lista_tallas) + 4) // 5
                sub_frame.configure(height=num_rows * 40)
                for i, talla in enumerate(lista_tallas):
                    if talla in self.talla_vars:
                        cb = ctk.CTkCheckBox(sub_frame, text=talla, variable=self.talla_vars[talla], 
                                             fg_color="#4A90E2", border_color="#A3BFFA", hover_color="#E6F0FA", text_color="#4B5EAA")
                        cb.grid(row=i // 5, column=i % 5, padx=10, pady=5, sticky="w")

            agregar_tallas("Tallas Numéricas", self.all_tallas_numericas, tallas_inner_frame, is_numeric=True)
            
            tallas_numericas_personalizadas_frame = ctk.CTkFrame(tallas_inner_frame, fg_color="transparent")
            tallas_numericas_personalizadas_frame.pack(fill="x", pady=5, expand=True)
            ctk.CTkLabel(tallas_numericas_personalizadas_frame, text="Talla Numérica Personalizada:", font=("Helvetica", 12, "bold"), text_color="#1A2E5A").pack(side="left", padx=5)
            self.talla_numerica_personalizada_entry = ctk.CTkEntry(tallas_numericas_personalizadas_frame, width=100)
            self.talla_numerica_personalizada_entry.pack(side="left", padx=5)
            ctk.CTkButton(tallas_numericas_personalizadas_frame, text="Añadir Talla Numérica", command=self.añadir_talla_numerica_personalizada, 
                          fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=100, font=("Helvetica", 12)).pack(side="left", padx=5)

            agregar_tallas("Tallas Americanas", self.tallas_americanas, tallas_inner_frame)
            agregar_tallas("Tallas Españolas", self.tallas_españolas, tallas_inner_frame)
            agregar_tallas("Tallas Malla y Calceta", self.tallas_malla_calceta, tallas_inner_frame)
            agregar_tallas("Tallas Especiales", self.tallas_especiales, tallas_inner_frame)
            tallas_personalizadas_no_numericas = self.remove_duplicates([talla for talla in self.tallas_personalizadas if not talla.isdigit()])
            agregar_tallas("Tallas Personalizadas", tallas_personalizadas_no_numericas, tallas_inner_frame, is_personalized=True)

            talla_personalizada_frame = ctk.CTkFrame(tallas_inner_frame, fg_color="transparent")
            talla_personalizada_frame.pack(fill="x", pady=5, expand=True)
            ctk.CTkLabel(talla_personalizada_frame, text="Talla Personalizada:", font=("Helvetica", 12, "bold"), text_color="#1A2E5A").pack(side="left", padx=5)
            self.talla_personalizada_entry = ctk.CTkEntry(talla_personalizada_frame, width=100)
            self.talla_personalizada_entry.pack(side="left", padx=5)
            ctk.CTkButton(talla_personalizada_frame, text="Añadir Talla", command=self.añadir_talla_personalizada, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=100, font=("Helvetica", 12)).pack(side="left", padx=5)

            tallas_buttons_frame = ctk.CTkFrame(tallas_inner_frame, fg_color="transparent")
            tallas_buttons_frame.pack(pady=10, expand=True)
            btn_todas = ctk.CTkButton(tallas_buttons_frame, text="✓ Todas", command=self.controller.seleccionar_todas, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=100, font=("Helvetica", 12))
            btn_todas.grid(row=0, column=0, padx=5, pady=2)
            ToolTip(btn_todas, "Selecciona todas las tallas disponibles")
            btn_ninguna = ctk.CTkButton(tallas_buttons_frame, text="✗ Ninguna", command=self.controller.deseleccionar_todas, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=100, font=("Helvetica", 12))
            btn_ninguna.grid(row=0, column=1, padx=5, pady=2)
            ToolTip(btn_ninguna, "Deselecciona todas las tallas")
            btn_pares = ctk.CTkButton(tallas_buttons_frame, text="⚖ Pares", command=self.controller.seleccionar_pares, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=100, font=("Helvetica", 12))
            btn_pares.grid(row=0, column=2, padx=5, pady=2)
            ToolTip(btn_pares, "Selecciona tallas numéricas pares")
            btn_pants = ctk.CTkButton(tallas_buttons_frame, text="👖 Tallas Pants", command=self.seleccionar_tallas_pants, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=100, font=("Helvetica", 12))
            btn_pants.grid(row=1, column=0, padx=5, pady=2)
            ToolTip(btn_pants, "Selecciona: 16, CH, MD, GD, EXG")
            btn_mallas = ctk.CTkButton(tallas_buttons_frame, text="🧦 Tallas Mallas", command=self.seleccionar_tallas_mallas, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=100, font=("Helvetica", 12))
            btn_mallas.grid(row=1, column=1, padx=5, pady=2)
            ToolTip(btn_mallas, "Selecciona: 0-0, 0-2, 3-5, 6-8, 9-12, 13-18, CH-MD, GD-EXG, Dama")
            btn_basicas = ctk.CTkButton(tallas_buttons_frame, text="👕 Tallas Básicas", command=self.seleccionar_tallas_basicas, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=100, font=("Helvetica", 12))
            btn_basicas.grid(row=1, column=2, padx=5, pady=2)
            ToolTip(btn_basicas, "Selecciona: 2, 4, 6, 8, 10, 12, 14, 16")

            ctk.CTkLabel(tallas_inner_frame, text="", height=20).pack()

            tallas_inner_frame.update_idletasks()
            canvas_tallas.configure(scrollregion=canvas_tallas.bbox("all"))

            def on_mouse_scroll_tallas(event):
                if canvas_tallas.winfo_exists() and canvas_tallas.winfo_containing(event.x_root, event.y_root) == canvas_tallas:
                    canvas_tallas.yview_scroll(int(-event.delta / 120), "units")

            canvas_tallas.bind("<MouseWheel>", on_mouse_scroll_tallas)

            right_frame = ctk.CTkFrame(content_frame, fg_color="#F5F7FA", corner_radius=10, border_width=1, border_color="#A3BFFA")
            right_frame.grid(row=0, column=2, sticky="nsew", padx=(10, 0), pady=0)
            ctk.CTkLabel(right_frame, text="Generar", font=("Helvetica", 16, "bold"), text_color="#1A2E5A").pack(pady=10)

            generar_inner_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
            generar_inner_frame.pack(fill="both", expand=True, padx=15, pady=5)

            self.preview_label = ctk.CTkLabel(generar_inner_frame, text="Previsualización: Ninguna", font=("Helvetica", 12), wraplength=300, text_color="#4B5EAA")
            self.preview_label.pack(pady=10, expand=True)

            resumen_frame = ctk.CTkFrame(generar_inner_frame, fg_color="transparent")
            resumen_frame.pack(fill="both", expand=True, pady=10)
            self.resumen_textbox = ctk.CTkTextbox(resumen_frame, height=150, wrap="word", font=("Helvetica", 12), fg_color="#FFFFFF", text_color="#4B5EAA")
            self.resumen_textbox.pack(side="left", fill="both", expand=True)
            scrollbar_resumen = ctk.CTkScrollbar(resumen_frame, command=self.resumen_textbox.yview)
            scrollbar_resumen.pack(side="right", fill="y")
            self.resumen_textbox.configure(yscrollcommand=scrollbar_resumen.set)
            self.resumen_textbox.insert("end", "Presiona 'Revisar' para ver los datos")
            self.resumen_textbox.configure(state="disabled")

            plantillas_frame = ctk.CTkFrame(generar_inner_frame, fg_color="transparent")
            plantillas_frame.pack(fill="x", pady=5)
            ctk.CTkLabel(plantillas_frame, text="Plantilla:", font=("Helvetica", 12, "bold"), text_color="#1A2E5A").pack(side="left", padx=5)
            self.combo_plantillas = ctk.CTkComboBox(plantillas_frame, width=150, values=[""], command=self.controller.cargar_plantilla)
            self.combo_plantillas.pack(side="left", padx=5)
            ToolTip(self.combo_plantillas, "Selecciona una plantilla para cargar los datos")
            self.actualizar_plantillas_combo()

            buttons_frame = ctk.CTkFrame(generar_inner_frame, fg_color="transparent")
            buttons_frame.pack(pady=10)
            
            self.btn_generar_nombre = ctk.CTkButton(buttons_frame, text="Generar Nombre", command=self.update_name, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12))
            self.btn_generar_nombre.pack(side="top", pady=5)
            ToolTip(self.btn_generar_nombre, "Genera un nombre basado en los campos seleccionados")
            
            self.btn_revisar = ctk.CTkButton(buttons_frame, text="🔍 Revisar", command=self.controller.revisar_datos, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12))
            self.btn_revisar.pack(side="top", pady=5)
            ToolTip(self.btn_revisar, "Revisa los datos ingresados antes de generar")
            
            self.btn_generar = ctk.CTkButton(buttons_frame, text="✔ Generar", command=self.controller.generar_codigo, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12))
            self.btn_generar.pack(side="top", pady=5)
            ToolTip(self.btn_generar, "Genera los códigos QR y etiquetas")
            
            btn_capturar = ctk.CTkButton(buttons_frame, text="📋 Capturar Datos", command=self.controller.capturar_datos_formulario, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12))
            btn_capturar.pack(side="top", pady=5)
            ToolTip(btn_capturar, "Captura los datos del formulario para crear una plantilla")
            
            btn_limpiar = ctk.CTkButton(buttons_frame, text="↻ Limpiar", command=self.controller.limpiar_formulario, fg_color="#4A90E2", hover_color="#2A6EBB", corner_radius=8, width=120, font=("Helvetica", 12))
            btn_limpiar.pack(side="top", pady=5)
            ToolTip(btn_limpiar, "Limpia todos los campos del formulario")

            self.message_label_action = ctk.CTkLabel(buttons_frame, text="", font=("Helvetica", 10))
            self.message_label_action.pack(side="top", pady=5)

            self.controller.btn_revisar = self.btn_revisar
            self.controller.btn_generar = self.btn_generar
            self.controller.btn_generar_nombre = self.btn_generar_nombre
            self.controller.message_label_action = self.message_label_action
            self.controller.blink_button = self.blink_button
            self.controller.show_action_message = self.show_action_message

            self.message_label = ctk.CTkLabel(generar_inner_frame, text="", text_color="#00A86B", font=("Helvetica", 12))
            self.message_label.pack(pady=10, expand=True)
            self.controller.message_label = self.message_label
            logging.info("setup_ui completado")
        except Exception as e:
            logging.error(f"Error en setup_ui para tienda {self.store_id}: {str(e)}")
            messagebox.showerror("Error", f"Error al configurar la interfaz: {str(e)}")

if __name__ == "__main__":
    root = ctk.CTk()
    root.title("Generador de Códigos")
    app = GeneradorCodigos(root, icons={})
    app.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
    root.mainloop()