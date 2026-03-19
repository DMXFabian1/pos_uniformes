import PyInstaller.__main__
import os
from src.core.paths import BASE_DIR

# Configuración de archivos y directorios a incluir
data_files = [
    (os.path.join(BASE_DIR, 'productos.db'), '.'),
    (os.path.join(BASE_DIR, 'assets', 'icons'), 'assets/icons'),
    (os.path.join(BASE_DIR, 'src', 'core', 'config', 'config.json'), 'src/core/config'),
    (os.path.join(BASE_DIR, 'Mis codigos'), 'Mis codigos')
]

# Convertir separadores para compatibilidad con PyInstaller
if os.name == 'nt':
    data_files = [(src, dest.replace('/', '\\')) for src, dest in data_files]
else:
    data_files = [(src, dest) for src, dest in data_files]

# Argumentos para PyInstaller
args = [
    '--name=Gestor_de_Inventarios',
    '--onefile',
    '--windowed',  # Evitar consola en Windows
    '--add-data=' + ';'.join([f'{src}{os.pathsep}{dest}' for src, dest in data_files]),
    '--hidden-import=customtkinter',
    '--hidden-import=PIL',
    '--hidden-import=brother_ql',
    '--hidden-import=brother_ql.backends.helpers',
    '--hidden-import=brother_ql.backends.pyusb',
    '--hidden-import=brother_ql.conversion',
    '--hidden-import=usb',
    '--hidden-import=usb.core',
    '--hidden-import=usb.util',
    '--hidden-import=usb.backend',
    '--hidden-import=usb.backend.libusb0',
    '--hidden-import=usb.backend.libusb1',
    '--hidden-import=usb.backend.openusb',
    '--hidden-import=packbits',
    '--hidden-import=attr',
    '--hidden-import=pyzbar',
    '--hidden-import=opencv-python',
    '--hidden-import=pandas',
    '--hidden-import=openpyxl',
    'main.py'
]

# Ejecutar PyInstaller
PyInstaller.__main__.run(args)
