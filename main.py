from __future__ import annotations
import ctypes
import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication, QIcon
from fluxora.theme import QSS
from fluxora.ui import FluxoraWindow


def main():
    if sys.platform == 'win32':
        try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('Fluxora.Desktop.3')
        except (AttributeError, OSError): pass
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName('Fluxora')
    app.setApplicationDisplayName('Fluxora')
    app.setOrganizationName('Fluxora')
    app.setStyle('Fusion')
    app.setQuitOnLastWindowClosed(False)
    ico = Path(__file__).parent/'assets'/'Fluxora.ico'
    if ico.is_file(): app.setWindowIcon(QIcon(str(ico)))
    app.setStyleSheet(QSS)
    window = FluxoraWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__': main()
