import win32print
import win32ui
from PIL import Image, ImageWin


_VIRTUAL_PRINTERS = {
    "microsoft print to pdf",
    "microsoft xps document writer",
    "send to onenote",
    "onenote for windows 10",
    "onenote",
    "fax",
}


def list_printers():
    """Return a list of available physical printer names (virtual printers filtered out)."""
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    printers = win32print.EnumPrinters(flags, None, 1)
    return [
        p[2] for p in printers
        if p[2].lower() not in _VIRTUAL_PRINTERS
        and "onenote" not in p[2].lower()
        and "xps" not in p[2].lower()
        and "fax" not in p[2].lower()
    ]


def get_default_printer():
    """Return the name of the default printer."""
    return win32print.GetDefaultPrinter()


def print_image(file_path, printer_name):
    """Print an image file to the specified printer.

    The image is scaled to fit the printable area while maintaining
    its aspect ratio and centered on the page.

    Args:
        file_path: Path to the image file (JPG, PNG, etc.).
        printer_name: Name of the target printer.

    Raises:
        Exception: If printing fails.
    """
    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)

    hdc.StartDoc(file_path)
    hdc.StartPage()

    # Printable area in pixels
    printable_w = hdc.GetDeviceCaps(8)   # HORZRES
    printable_h = hdc.GetDeviceCaps(10)  # VERTRES

    img = Image.open(file_path)

    # Scale image to fit printable area while keeping aspect ratio
    img_w, img_h = img.size
    scale = min(printable_w / img_w, printable_h / img_h)
    new_w = int(img_w * scale)
    new_h = int(img_h * scale)

    # Center on page
    x = (printable_w - new_w) // 2
    y = (printable_h - new_h) // 2

    dib = ImageWin.Dib(img)
    dib.draw(hdc.GetHandleOutput(), (x, y, x + new_w, y + new_h))

    hdc.EndPage()
    hdc.EndDoc()
    hdc.DeleteDC()
