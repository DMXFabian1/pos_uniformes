import qrcode
import logging
import os
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

def validate_string(arg, name, allow_empty=False):
    """
    Valida que el argumento sea una cadena. Si es None, lo convierte a una cadena vacía.

    Args:
        arg (Any): Valor a validar.
        name (str): Nombre del argumento para mensajes de error.
        allow_empty (bool): Si se permiten cadenas vacías.

    Returns:
        str: Cadena validada.

    Raises:
        ValueError: Si el argumento no es una cadena válida o está vacío cuando no se permite.
    """
    if arg is None:
        arg = ""
        logger.debug(f"Argumento '{name}' era None, convertido a cadena vacía")
    if not isinstance(arg, str):
        logger.error("Argumento '%s' no es una cadena: %s", name, type(arg))
        raise ValueError(f"El argumento '{name}' debe ser una cadena")
    if not allow_empty and not arg.strip():
        logger.error("Argumento '%s' está vacío", name)
        raise ValueError(f"El argumento '{name}' no puede estar vacío")
    return arg.strip()

def generar_qr(data, output_path, tipo_pieza=None):
    """
    Genera un código QR con el ícono del tipo_pieza en el centro (si se proporciona) y lo guarda en la ruta especificada.
    El ícono se coloca dentro de un fondo cuadrado blanco con borde negro.

    Args:
        data (str): Datos para el QR.
        output_path (str): Ruta donde guardar el QR.
        tipo_pieza (str, optional): Tipo de pieza del producto para seleccionar el ícono. Default es None.

    Returns:
        bool: True si se generó correctamente.

    Raises:
        ValueError: Si los argumentos son inválidos.
        IOError: Si hay un error al guardar el archivo.
    """
    try:
        data = validate_string(data, "data")
        output_path = validate_string(output_path, "output_path")
        tipo_pieza = validate_string(tipo_pieza, "tipo_pieza", allow_empty=True)

        if os.path.exists(output_path):
            os.remove(output_path)
            logger.debug("Archivo existente eliminado: %s", output_path)

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=6,
            border=4
        )
        qr.add_data(data)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

        if tipo_pieza:
            qr_size = qr_img.size[0]
            icon_size = int(qr_size * 0.20)
            square_size = int(icon_size * 1.2)

            tipo_pieza_icons = {
                'Bata': 'bata.png',
                'Boina': 'boina.png',
                'Calceta': 'calceta.png',
                'Camisa': 'camisa.png',
                'Chaleco': 'chaleco.png',
                'Chamarra': 'chamarra.png',
                'Corbata': 'corbata.png',
                'Corbatín': 'corbatin.png',
                'Falda': 'falda.png',
                'Guante': 'guante.png',
                'Jumper': 'jumper.png',
                'Malla': 'malla.png',
                'Moño': 'moño.png',
                'Pantalón': 'pantalon.png',
                'Pants 2pz': 'pants_2pz.png',
                'Pants 3pz': 'pants_3pz.png',
                'Pants Suelto': 'pants_suelto.png',
                'Playera': 'playera.png',
                'Suéter': 'sueter.png'
            }
            default_icon = 'default.png'
            icon_folder = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'assets', 'icons', 'tipos_pieza')

            logger.debug(f"Valor de tipo_pieza recibido: '{tipo_pieza}'")
            icon_filename = tipo_pieza_icons.get(tipo_pieza, default_icon)
            icon_path = os.path.join(icon_folder, icon_filename)
            logger.debug(f"Buscando ícono en: {icon_path}")

            if os.path.exists(icon_path):
                logger.debug(f"Ícono encontrado para tipo_pieza '{tipo_pieza}': {icon_path}")
                icon = Image.open(icon_path).convert('RGBA')
                icon = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)

                square_img = Image.new('RGBA', (square_size, square_size), (0, 0, 0, 0))
                draw_square = ImageDraw.Draw(square_img)
                draw_square.rectangle(
                    [0, 0, square_size - 1, square_size - 1],
                    fill=(255, 255, 255, 255),
                    outline=(0, 0, 0, 255),
                    width=2
                )

                icon_x_square = (square_size - icon_size) // 2
                icon_y_square = (square_size - icon_size) // 2
                square_img.paste(icon, (icon_x_square, icon_y_square), mask=icon.split()[3])

                square_x = (qr_size - square_size) // 2
                square_y = (qr_size - square_size) // 2
                qr_img.paste(square_img, (square_x, square_y), mask=square_img.split()[3])
            else:
                logger.warning(f"Ícono no encontrado para tipo_pieza '{tipo_pieza}': {icon_path}")
                default_icon_path = os.path.join(icon_folder, default_icon)
                if os.path.exists(default_icon_path):
                    logger.debug(f"Usando ícono por defecto: {default_icon_path}")
                    icon = Image.open(default_icon_path).convert('RGBA')
                    icon = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                    square_img = Image.new('RGBA', (square_size, square_size), (0, 0, 0, 0))
                    draw_square = ImageDraw.Draw(square_img)
                    draw_square.rectangle(
                        [0, 0, square_size - 1, square_size - 1],
                        fill=(255, 255, 255, 255),
                        outline=(0, 0, 0, 255),
                        width=2
                    )
                    icon_x_square = (square_size - icon_size) // 2
                    icon_y_square = (square_size - icon_size) // 2
                    square_img.paste(icon, (icon_x_square, icon_y_square), mask=icon.split()[3])
                    square_x = (qr_size - square_size) // 2
                    square_y = (qr_size - square_size) // 2
                    qr_img.paste(square_img, (square_x, square_y), mask=square_img.split()[3])
                else:
                    logger.warning(f"Ícono por defecto no encontrado: {default_icon_path}")

        qr_img.save(output_path)
        logger.info("QR generado y guardado en: %s", output_path)
        return True
    except Exception as e:
        logger.error(f"Error al generar QR: {str(e)}")
        raise