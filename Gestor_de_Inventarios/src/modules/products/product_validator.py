import logging
from tkinter import messagebox
from src.core.config.config import CONFIG

logger = logging.getLogger(__name__)

class ProductValidator:
    """
    Clase que valida entradas para campos de productos, como números, campos requeridos, ubicaciones y tallas.
    """
    def __init__(self):
        """
        Inicializa el validador de productos con la lista de tallas permitidas.

        Raises:
            ValueError: Si la configuración de tallas no está definida.
        """
        self.tallas_permitidas = CONFIG.get("TALLAS", [])
        if not self.tallas_permitidas:
            logger.warning("Lista de tallas permitidas no definida en CONFIG['TALLAS']")
            self.tallas_permitidas = []
        logger.debug("ProductValidator inicializado con tallas permitidas: %s", self.tallas_permitidas)

    def _update_widget_style(self, widget, is_valid, value):
        """
        Actualiza el estilo de un widget según el resultado de la validación.

        Args:
            widget (tk.Widget): Widget a actualizar.
            is_valid (bool): Indica si la validación fue exitosa.
            value (str): Valor que se validó.
        """
        if widget is None:
            return
        try:
            if not value:
                widget.configure(fg_color="#FFFFFF", border_color="#A3BFFA")
            elif is_valid:
                widget.configure(fg_color="#FFFFFF", border_color="#A3BFFA")
            else:
                widget.configure(fg_color="#FFE6E6", border_color="#FF5555")
        except Exception as e:
            logger.warning("Error al actualizar estilo del widget: %s", str(e))

    def validate_numeric(self, value, field_name, widget=None, allow_negative=False):
        """
        Valida una entrada numérica y actualiza el widget si es necesario.

        Args:
            value (str): Valor a validar.
            field_name (str): Nombre del campo para mensajes de error.
            widget (tk.Widget, optional): Widget asociado para actualizar su estilo.
            allow_negative (bool): Si se permiten valores negativos.

        Returns:
            tuple: (bool, float or str) - (Éxito de la validación, Valor numérico o mensaje de error).
        """
        try:
            if not value or value.strip() == "":
                self._update_widget_style(widget, True, value)
                logger.debug("Valor numérico vacío para %s, considerado válido", field_name)
                return True, None

            num = float(value)
            if not allow_negative and num < 0:
                self._update_widget_style(widget, False, value)
                error_msg = f"El campo {field_name} no puede ser negativo"
                logger.warning("%s: %s", error_msg, value)
                return False, error_msg

            self._update_widget_style(widget, True, value)
            logger.debug("Validación numérica exitosa para %s: %s", field_name, num)
            return True, num
        except ValueError:
            self._update_widget_style(widget, False, value)
            error_msg = f"El campo {field_name} debe ser un número válido"
            logger.warning("%s: %s", error_msg, value)
            return False, error_msg

    def validate_required(self, value, field_name, widget=None):
        """
        Valida que un campo requerido no esté vacío.

        Args:
            value (str): Valor a validar.
            field_name (str): Nombre del campo para mensajes de error.
            widget (tk.Widget, optional): Widget asociado para actualizar su estilo.

        Returns:
            tuple: (bool, str) - (Éxito de la validación, Valor o mensaje de error).
        """
        value = value.strip() if value else ""
        if not value:
            self._update_widget_style(widget, False, value)
            error_msg = f"El campo {field_name} es obligatorio y no puede estar vacío"
            logger.warning("%s", error_msg)
            return False, error_msg

        self._update_widget_style(widget, True, value)
        logger.debug("Validación de campo requerido exitosa para %s: %s", field_name, value)
        return True, value

    def validate_ubicacion(self, value, field_name, widget=None):
        """
        Valida que el campo ubicación no sea solo números.

        Args:
            value (str): Valor a validar.
            field_name (str): Nombre del campo para mensajes de error.
            widget (tk.Widget, optional): Widget asociado para actualizar su estilo.

        Returns:
            tuple: (bool, str) - (Éxito de la validación, Valor o mensaje de error).
        """
        value = value.strip() if value else ""
        if value and value.isdigit():
            self._update_widget_style(widget, False, value)
            error_msg = f"El campo {field_name} no puede ser solo números"
            logger.warning("%s: %s", error_msg, value)
            return False, error_msg

        self._update_widget_style(widget, True, value)
        logger.debug("Validación de ubicación exitosa para %s: %s", field_name, value)
        return True, value

    def validate_talla(self, value, field_name, widget=None, custom_tallas=None):
        """
        Valida que la talla esté en la lista de tallas permitidas.

        Args:
            value (str): Valor a validar.
            field_name (str): Nombre del campo para mensajes de error.
            widget (tk.Widget, optional): Widget asociado para actualizar su estilo.
            custom_tallas (list, optional): Lista de tallas personalizadas adicionales.

        Returns:
            tuple: (bool, str) - (Éxito de la validación, Valor o mensaje de error).
        """
        value = value.strip().upper() if value else ""
        if not value:
            self._update_widget_style(widget, True, value)
            logger.debug("Talla vacía para %s, considerada válida", field_name)
            return True, None

        allowed_tallas = self.tallas_permitidas + (custom_tallas or [])
        if allowed_tallas and value not in allowed_tallas:
            self._update_widget_style(widget, False, value)
            error_msg = f"La talla '{value}' no está en la lista de tallas permitidas"
            logger.warning("%s", error_msg)
            return False, error_msg

        self._update_widget_style(widget, True, value)
        logger.debug("Validación de talla exitosa para %s: %s", field_name, value)
        return True, value