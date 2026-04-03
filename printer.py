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


def print_grid_2x2(file_paths, printer_name, margin=40):
    """Print exactly 4 images as a 2x2 grid on a single page.

    Args:
        file_paths: List of 4 image file paths.
        printer_name: Name of the target printer.
        margin: Pixel gap between cells and edges.
    """
    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)

    hdc.StartDoc("Photobooth 2x2 Grid")
    hdc.StartPage()

    page_w = hdc.GetDeviceCaps(8)   # HORZRES
    page_h = hdc.GetDeviceCaps(10)  # VERTRES

    # Each cell size (half page minus margins)
    cell_w = (page_w - margin * 3) // 2
    cell_h = (page_h - margin * 3) // 2

    # Grid positions: top-left corner of each cell
    positions = [
        (margin, margin),                          # top-left
        (margin * 2 + cell_w, margin),             # top-right
        (margin, margin * 2 + cell_h),             # bottom-left
        (margin * 2 + cell_w, margin * 2 + cell_h),  # bottom-right
    ]

    for i, file_path in enumerate(file_paths[:4]):
        img = Image.open(file_path)
        img_w, img_h = img.size

        # Scale to fit cell while keeping aspect ratio
        scale = min(cell_w / img_w, cell_h / img_h)
        new_w = int(img_w * scale)
        new_h = int(img_h * scale)

        # Center within cell
        cx, cy = positions[i]
        x = cx + (cell_w - new_w) // 2
        y = cy + (cell_h - new_h) // 2

        dib = ImageWin.Dib(img)
        dib.draw(hdc.GetHandleOutput(), (x, y, x + new_w, y + new_h))

    hdc.EndPage()
    hdc.EndDoc()
    hdc.DeleteDC()


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
