import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".gif"}


class _PhotoHandler(FileSystemEventHandler):
    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def on_created(self, event):
        if event.is_directory:
            return

        ext = os.path.splitext(event.src_path)[1].lower()
        if ext not in IMAGE_EXTENSIONS:
            return

        # Wait for file to finish writing
        self._wait_for_file_ready(event.src_path)
        self.callback(event.src_path)

    def _wait_for_file_ready(self, path, retries=5, delay=0.5):
        """Wait until the file is no longer being written to."""
        for _ in range(retries):
            time.sleep(delay)
            try:
                with open(path, "rb"):
                    return
            except (IOError, OSError):
                continue


def start_watching(folder_path, on_new_file, recursive=False):
    """Start watching a folder for new image files.

    Args:
        folder_path: Path to the folder to watch.
        on_new_file: Callback function called with (file_path) when a new image appears.
        recursive: If True, also watch subfolders.

    Returns:
        watchdog.observers.Observer instance (call .stop() to stop watching).
    """
    os.makedirs(folder_path, exist_ok=True)
    handler = _PhotoHandler(on_new_file)
    observer = Observer()
    observer.schedule(handler, folder_path, recursive=recursive)
    observer.start()
    return observer
