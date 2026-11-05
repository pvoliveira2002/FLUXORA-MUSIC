"""Página do gravador de tela do Fluxora."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from .icons import icon
from .screen_recorder import ScreenRecorder, ScreenRecorderError, ScreenRecordingSettings
from .theme import GREEN, MUTED


def _label(value: str, name: str = '', wrap: bool = False) -> QLabel:
    widget = QLabel(value); widget.setObjectName(name); widget.setWordWrap(wrap); return widget


def _button(value: str, icon_name: str = '', name: str = '') -> QPushButton:
    widget = QPushButton(value)
    if icon_name:
        widget.setIcon(icon(icon_name, '#0A1907' if name == 'Primary' else '#B4C6C9', 18))
    widget.setObjectName(name); widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def format_elapsed(seconds: int) -> str:
    seconds = max(0, int(seconds))
    return f'{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}'


class ScreenRecorderPage(QWidget):
    recording_completed = Signal(str)
    status_message = Signal(str)

    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage
        self.last_output = ''
        self.recorder = ScreenRecorder(self)
        self.recorder.started.connect(self._recording_started)
        self.recorder.elapsed.connect(lambda value: self.timer.setText(format_elapsed(value)))
        self.recorder.completed.connect(self._recording_completed)
        self.recorder.failed.connect(self._recording_failed)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(17)
        heading = QHBoxLayout(); heading.setSpacing(12)
        emblem = _label('●', 'RecorderEmblem'); heading.addWidget(emblem)
        titles = QVBoxLayout(); titles.setSpacing(2)
        titles.addWidget(_label('Gravador de tela', 'Heading'))
        titles.addWidget(_label('Grave sua área de trabalho em MP4, diretamente no computador.', 'Muted'))
        heading.addLayout(titles); heading.addStretch(); root.addLayout(heading)

        hero = QFrame(); hero.setObjectName('RecorderHero')
        hero_layout = QVBoxLayout(hero); hero_layout.setContentsMargins(26, 26, 26, 26); hero_layout.setSpacing(12)
        monitor = QLabel(); monitor.setPixmap(icon('monitor', GREEN, 66).pixmap(66, 66))
        monitor.setAlignment(Qt.AlignmentFlag.AlignCenter); hero_layout.addWidget(monitor)
        self.state = _label('Pronto para gravar', 'Section'); self.state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(self.state)
        self.timer = _label('00:00:00', 'RecorderTimer'); self.timer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_layout.addWidget(self.timer)
        self.detail = _label('O vídeo será salvo em MP4 (H.264).', 'Muted', True)
        self.detail.setAlignment(Qt.AlignmentFlag.AlignCenter); hero_layout.addWidget(self.detail)
        root.addWidget(hero, 1)

        settings = QFrame(); settings.setObjectName('Panel')
        grid = QGridLayout(settings); grid.setContentsMargins(18, 16, 18, 16); grid.setHorizontalSpacing(13); grid.setVerticalSpacing(10)
        grid.addWidget(_label('Tela', 'Muted'), 0, 0)
        grid.addWidget(_label('Taxa de quadros', 'Muted'), 0, 1)
        grid.addWidget(_label('Qualidade', 'Muted'), 0, 2)
        self.screen = QComboBox(); self._populate_screens(); grid.addWidget(self.screen, 1, 0)
        self.fps = QComboBox(); self.fps.addItems(['24 FPS', '30 FPS', '60 FPS']); self.fps.setCurrentText('30 FPS'); grid.addWidget(self.fps, 1, 1)
        self.quality = QComboBox(); self.quality.addItems(['Alta', 'Equilibrada', 'Compacta']); self.quality.setCurrentText('Equilibrada'); grid.addWidget(self.quality, 1, 2)
        self.cursor = QCheckBox('Mostrar o cursor do mouse'); self.cursor.setChecked(True); grid.addWidget(self.cursor, 2, 0)
        self.minimize = QCheckBox('Minimizar o Fluxora ao iniciar'); self.minimize.setChecked(True); grid.addWidget(self.minimize, 2, 1, 1, 2)
        root.addWidget(settings)

        destination = QFrame(); destination.setObjectName('Panel')
        dest_layout = QVBoxLayout(destination); dest_layout.setContentsMargins(18, 14, 18, 14); dest_layout.setSpacing(8)
        dest_layout.addWidget(_label('Pasta de destino', 'Muted'))
        dest_row = QHBoxLayout(); dest_row.setSpacing(8)
        default_dir = str(Path.home() / 'Videos' / 'Fluxora' / 'Gravacoes')
        self.destination = QLineEdit(self.storage.config.get('screen_recording_dir', default_dir))
        dest_row.addWidget(self.destination, 1)
        choose = _button('Alterar', 'folder'); choose.clicked.connect(self._choose_folder); dest_row.addWidget(choose)
        self.open_folder = _button('Abrir pasta', 'external'); self.open_folder.clicked.connect(self._open_destination); dest_row.addWidget(self.open_folder)
        dest_layout.addLayout(dest_row)
        note = _label('Áudio não é incluído nesta versão do gravador. A captura de som do Windows exige configuração de dispositivo própria.', 'Subtle', True)
        dest_layout.addWidget(note); root.addWidget(destination)

        actions = QHBoxLayout(); actions.setSpacing(10); actions.addStretch()
        self.open_file = _button('Abrir última gravação', 'external'); self.open_file.setEnabled(False)
        self.open_file.clicked.connect(self._open_last_file); actions.addWidget(self.open_file)
        self.stop_button = _button('Parar e salvar', 'close', 'Danger'); self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop); actions.addWidget(self.stop_button)
        self.start_button = _button('Iniciar gravação', 'play', 'Primary'); self.start_button.setMinimumHeight(45)
        self.start_button.clicked.connect(self.start); actions.addWidget(self.start_button)
        root.addLayout(actions)

    def _populate_screens(self) -> None:
        self.screen.clear(); self.screen.addItem('Área de trabalho inteira', None)
        for number, screen in enumerate(QGuiApplication.screens(), 1):
            geometry = screen.geometry(); ratio = float(screen.devicePixelRatio())
            data = (round(geometry.x() * ratio), round(geometry.y() * ratio),
                    round(geometry.width() * ratio), round(geometry.height() * ratio))
            primary = ' (principal)' if screen is QGuiApplication.primaryScreen() else ''
            self.screen.addItem(f'Tela {number}{primary} — {data[2]} × {data[3]}', data)

    def _settings(self) -> ScreenRecordingSettings:
        destination = self.destination.text().strip()
        if not destination:
            raise ScreenRecorderError('Escolha uma pasta de destino.')
        area = self.screen.currentData()
        values = {'x': None, 'y': None, 'width': None, 'height': None}
        if area:
            values.update(zip(('x', 'y', 'width', 'height'), area))
        return ScreenRecordingSettings(
            output_dir=destination,
            fps=int(self.fps.currentText().split()[0]),
            quality=self.quality.currentText(),
            draw_cursor=self.cursor.isChecked(),
            **values,
        )

    def start(self) -> None:
        if sys.platform != 'win32':
            QMessageBox.warning(self, 'Recurso indisponível', 'O gravador de tela está disponível somente no Windows.')
            return
        try:
            settings = self._settings()
            self.storage.config['screen_recording_dir'] = settings.output_dir
            self.storage.save_config()
            self.recorder.start(settings)
        except ScreenRecorderError as exc:
            QMessageBox.warning(self, 'Não foi possível iniciar', str(exc))

    def stop(self) -> None:
        if self.recorder.is_active():
            self.state.setText('Finalizando o arquivo...')
            self.detail.setText('Aguarde enquanto o MP4 é fechado corretamente.')
            self.stop_button.setEnabled(False)
            self.recorder.stop()

    def is_active(self) -> bool:
        return self.recorder.is_active()

    def shutdown(self) -> bool:
        return self.recorder.shutdown()

    def _recording_started(self, path: str) -> None:
        self.last_output = path
        self.state.setText('Gravando a tela')
        self.detail.setText(f'Salvando em: {path}')
        self.start_button.setEnabled(False); self.stop_button.setEnabled(True)
        self._set_controls_enabled(False)
        self.status_message.emit('Gravação de tela em andamento')
        if self.minimize.isChecked():
            self.window().showMinimized()

    def _recording_completed(self, path: str) -> None:
        self.last_output = path
        self.state.setText('Gravação concluída')
        self.detail.setText(path); self.timer.setText('00:00:00')
        self.open_file.setEnabled(True); self._reset_controls()
        self.status_message.emit('Gravação de tela concluída')
        self.recording_completed.emit(path)

    def _recording_failed(self, message: str) -> None:
        self.state.setText('Falha na gravação')
        self.detail.setText(message); self.timer.setText('00:00:00')
        self._reset_controls(); self.status_message.emit('Falha na gravação de tela')
        QMessageBox.warning(self, 'Não foi possível gravar', message)

    def _reset_controls(self) -> None:
        self.start_button.setEnabled(True); self.stop_button.setEnabled(False)
        self._set_controls_enabled(True)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for widget in (self.screen, self.fps, self.quality, self.cursor, self.minimize, self.destination):
            widget.setEnabled(enabled)

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, 'Pasta das gravações', self.destination.text())
        if folder:
            self.destination.setText(folder)

    def _open_destination(self) -> None:
        path = Path(self.destination.text().strip()).expanduser()
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, 'Pasta indisponível', str(exc)); return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_last_file(self) -> None:
        if self.last_output and Path(self.last_output).is_file():
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.last_output))
