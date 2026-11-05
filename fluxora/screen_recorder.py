"""Gravação real da área de trabalho do Windows usando o FFmpeg."""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QElapsedTimer, QObject, QProcess, QTimer, Signal

from .converter import ConversionError, find_ffmpeg


class ScreenRecorderError(RuntimeError):
    """Erro legível apresentado pela tela do gravador."""


@dataclass(frozen=True)
class ScreenRecordingSettings:
    output_dir: str
    fps: int = 30
    quality: str = 'Equilibrada'
    draw_cursor: bool = True
    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None


QUALITY_PROFILES = {
    'Alta': ('veryfast', '18'),
    'Equilibrada': ('veryfast', '23'),
    'Compacta': ('faster', '28'),
}


def unique_recording_path(output_dir: str, now: datetime | None = None) -> Path:
    """Cria um nome previsível sem substituir uma gravação anterior."""
    folder = Path(output_dir).expanduser()
    stamp = (now or datetime.now()).strftime('%Y-%m-%d %H-%M-%S')
    candidate = folder / f'Gravacao Fluxora {stamp}.mp4'
    suffix = 2
    while candidate.exists():
        candidate = folder / f'Gravacao Fluxora {stamp} ({suffix}).mp4'
        suffix += 1
    return candidate


def build_screen_recording_args(settings: ScreenRecordingSettings, output_path: str,
                                platform: str | None = None) -> list[str]:
    """Monta os argumentos sem shell, evitando problemas com espaços nos caminhos."""
    current_platform = platform or sys.platform
    if current_platform != 'win32':
        raise ScreenRecorderError('A gravação de tela desta versão está disponível somente no Windows.')
    if settings.fps not in (24, 30, 60):
        raise ScreenRecorderError('A taxa de quadros deve ser 24, 30 ou 60 FPS.')
    if settings.quality not in QUALITY_PROFILES:
        raise ScreenRecorderError('Perfil de qualidade inválido.')

    preset, crf = QUALITY_PROFILES[settings.quality]
    args = [
        '-hide_banner', '-loglevel', 'warning', '-y',
        '-thread_queue_size', '1024', '-f', 'gdigrab',
        '-framerate', str(settings.fps),
        '-draw_mouse', '1' if settings.draw_cursor else '0',
    ]
    area = (settings.x, settings.y, settings.width, settings.height)
    if any(value is not None for value in area):
        if not all(value is not None for value in area):
            raise ScreenRecorderError('A área da tela está incompleta.')
        width = int(settings.width) // 2 * 2
        height = int(settings.height) // 2 * 2
        if width < 2 or height < 2:
            raise ScreenRecorderError('A área selecionada é pequena demais para gravar.')
        args += ['-offset_x', str(int(settings.x)), '-offset_y', str(int(settings.y)),
                 '-video_size', f'{width}x{height}']
    args += [
        '-i', 'desktop', '-an', '-c:v', 'libx264', '-preset', preset,
        '-crf', crf, '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart', output_path,
    ]
    return args


class ScreenRecorder(QObject):
    """Controla um único FFmpeg e finaliza o MP4 de forma segura ao parar."""
    started = Signal(str)
    elapsed = Signal(int)
    completed = Signal(str)
    failed = Signal(str)
    state_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process: QProcess | None = None
        self.output_path = ''
        self._errors = bytearray()
        self._stopping = False
        self._reported = False
        self._clock = QElapsedTimer()
        self._ticker = QTimer(self)
        self._ticker.setInterval(500)
        self._ticker.timeout.connect(self._emit_elapsed)

    def is_active(self) -> bool:
        return bool(self.process and self.process.state() != QProcess.ProcessState.NotRunning)

    def start(self, settings: ScreenRecordingSettings) -> str:
        if self.is_active():
            raise ScreenRecorderError('Já existe uma gravação em andamento.')
        try:
            ffmpeg = find_ffmpeg()
        except ConversionError as exc:
            raise ScreenRecorderError(str(exc)) from exc
        folder = Path(settings.output_dir).expanduser()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ScreenRecorderError(f'Não foi possível criar a pasta de destino: {exc}') from exc
        if not os.access(folder, os.W_OK):
            raise ScreenRecorderError('A pasta escolhida não permite salvar arquivos.')

        self.output_path = str(unique_recording_path(str(folder)))
        arguments = build_screen_recording_args(settings, self.output_path)
        self._errors.clear(); self._stopping = False; self._reported = False
        process = QProcess(self)
        process.setProgram(ffmpeg)
        process.setArguments(arguments)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        process.readyReadStandardError.connect(self._read_errors)
        process.started.connect(self._process_started)
        process.errorOccurred.connect(self._process_error)
        process.finished.connect(self._process_finished)
        self.process = process
        process.start()
        return self.output_path

    def stop(self) -> None:
        if not self.is_active() or self._stopping:
            return
        self._stopping = True
        self.process.write(b'q\n')
        self.process.waitForBytesWritten(500)
        QTimer.singleShot(5000, self._force_stop_if_needed)

    def shutdown(self) -> bool:
        """Usado ao sair do aplicativo; tenta preservar o vídeo antes de forçar."""
        if not self.is_active():
            return True
        self._stopping = True
        self.process.write(b'q\n')
        self.process.waitForBytesWritten(500)
        if self.process.waitForFinished(4500):
            return True
        self.process.terminate()
        if self.process.waitForFinished(1500):
            return True
        self.process.kill()
        return self.process.waitForFinished(1500)

    def _process_started(self) -> None:
        self._clock.start(); self._ticker.start()
        self.state_changed.emit(True); self.started.emit(self.output_path)

    def _emit_elapsed(self) -> None:
        if self._clock.isValid():
            self.elapsed.emit(max(0, self._clock.elapsed() // 1000))

    def _read_errors(self) -> None:
        if not self.process:
            return
        self._errors.extend(bytes(self.process.readAllStandardError()))
        if len(self._errors) > 12000:
            del self._errors[:-12000]

    def _process_error(self, error) -> None:
        if self.process:
            self._read_errors()
        if error == QProcess.ProcessError.FailedToStart:
            self._ticker.stop(); self.state_changed.emit(False)
            details = self._errors.decode('utf-8', errors='replace').strip()
            self._report_failure(details or 'O processo do FFmpeg não pôde ser iniciado.')
            process = self.process; self.process = None
            if process:
                process.deleteLater()

    def _process_finished(self, exit_code: int, _status) -> None:
        self._read_errors(); self._ticker.stop(); self.elapsed.emit(0)
        path = Path(self.output_path)
        valid = path.is_file() and path.stat().st_size > 1024
        details = self._errors.decode('utf-8', errors='replace').strip()
        self.state_changed.emit(False)
        if valid and exit_code == 0:
            self.completed.emit(str(path))
        else:
            path.unlink(missing_ok=True)
            message = details.splitlines()[-1] if details else f'O FFmpeg encerrou com o código {exit_code}.'
            self._report_failure(f'Não foi possível gravar a tela. {message}')
        process = self.process
        self.process = None
        self._stopping = False
        if process:
            process.deleteLater()

    def _report_failure(self, message: str) -> None:
        if self._reported:
            return
        self._reported = True
        self.failed.emit(message)

    def _force_stop_if_needed(self) -> None:
        if self.is_active():
            self.process.terminate()
            QTimer.singleShot(1500, self._kill_if_needed)

    def _kill_if_needed(self) -> None:
        if self.is_active():
            self.process.kill()
