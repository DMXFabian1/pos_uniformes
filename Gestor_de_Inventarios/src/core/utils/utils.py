# utils.utils
import tkinter as tk
from tkinter import messagebox
import pyperclip
import io
import win32clipboard
from PIL import Image
import os
import shutil
import logging

def validate_path(path, write_access=True):
    parent_dir = os.path.dirname(path) if os.path.isfile(path) else path
    if not os.path.exists(parent_dir):
        raise FileNotFoundError(f"El directorio {parent_dir} no existe")
    if write_access and not os.access(parent_dir, os.W_OK):
        raise PermissionError(f"No hay permisos de escritura en {parent_dir}")

def check_disk_space(path, min_space_mb=100, critical_space_mb=10):
    total, used, free = shutil.disk_usage(path)
    free_mb = free // (2**20)  # Convertir a MB
    if free_mb < min_space_mb:
        logging.warning(f"Espacio libre bajo: {free_mb} MB disponibles")
        messagebox.showwarning("Advertencia", f"Espacio libre bajo: {free_mb} MB disponibles")
        if free_mb < critical_space_mb:
            logging.error("Espacio en disco críticamente bajo. Cerrando aplicación.")
            messagebox.showerror("Error", "Espacio en disco insuficiente para continuar. La aplicación se cerrará.")
            raise SystemExit("Espacio en disco insuficiente")

def copy_to_clipboard(text):
    try:
        if text:
            pyperclip.copy(text.upper())
            messagebox.showinfo("Éxito", f"Texto '{text.upper()}' copiado al portapapeles.")
            return True
        else:
            messagebox.showerror("Error", "No hay texto para copiar.")
            return False
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo copiar el texto: {str(e)}")
        return False

def copy_image_to_clipboard(image_path):
    try:
        imagen = Image.open(image_path)
        output = io.BytesIO()
        imagen.convert('RGB').save(output, 'BMP')
        data = output.getvalue()[14:]  # Quitar cabecera BMP
        output.close()
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()
        messagebox.showinfo("Éxito", "Imagen copiada al portapapeles.")
        return True
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo copiar la imagen: {str(e)}")
        return False

def sanitize_filename(filename):
    invalid_chars = r'<>:"/\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename