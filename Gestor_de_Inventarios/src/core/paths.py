# src/core/paths.py
import os
import sys

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = get_base_dir()
DB_PATH = os.path.join(BASE_DIR, "productos.db")
ICONS_DIR = os.path.join(BASE_DIR, "assets", "icons")
CONFIG_FILE = os.path.join(BASE_DIR, "src", "core", "config", "config.json")
