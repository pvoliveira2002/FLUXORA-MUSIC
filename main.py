from __future__ import annotations
import ctypes
import faulthandler
import os
import sys
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QGuiApplication, QIcon
from fluxora.theme import QSS
from fluxora.ui import FluxoraWindow


_fault_log_handle = None
_instance_mutex = None


def acquire_single_instance():
    """Mantém somente um Fluxora ativo para não duplicar filas e bandejas."""
    global _instance_mutex
    if sys.platform != 'win32':
        return True
    from ctypes import wintypes
    kernel32=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel32.CreateMutexW.argtypes=(wintypes.LPVOID,wintypes.BOOL,wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype=wintypes.HANDLE
    kernel32.CloseHandle.argtypes=(wintypes.HANDLE,)
    ctypes.set_last_error(0)
    handle=kernel32.CreateMutexW(None,False,'Local\\Fluxora.Desktop.SingleInstance')
    if not handle:
        return True
    if ctypes.get_last_error()==183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        return False
    _instance_mutex=handle
    return True


def enable_native_crash_log():
    """Registra a pilha das threads se Python/Qt sofrer uma falha nativa."""
    global _fault_log_handle
    try:
        log_dir = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'Fluxora'
        log_dir.mkdir(parents=True, exist_ok=True)
        _fault_log_handle = (log_dir / 'fluxora-crash.log').open('a', encoding='utf-8')
        _fault_log_handle.write(
            f'\n--- Fluxora iniciado em {datetime.now().isoformat(timespec="seconds")} '
            f'com Python {sys.version.split()[0]} ({sys.executable}) ---\n'
        )
        _fault_log_handle.flush()
        faulthandler.enable(_fault_log_handle, all_threads=True)
    except (OSError, RuntimeError):
        _fault_log_handle = None


def main():
    enable_native_crash_log()
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
    if not acquire_single_instance():
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(None,'Fluxora já está aberto','Já existe uma instância do Fluxora em execução. Verifique a janela ou o ícone próximo ao relógio do Windows.')
        return
    window = FluxoraWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__': main()
