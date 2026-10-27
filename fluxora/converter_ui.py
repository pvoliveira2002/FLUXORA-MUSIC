"""Tela do conversor local do Fluxora 3.1."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QScrollArea,
    QFileDialog, QComboBox, QCheckBox, QProgressBar, QMessageBox, QSizePolicy,
)

from .converter import (
    AUDIO_OUTPUTS, VIDEO_OUTPUTS, BITRATES, QUALITY_PROFILES, RESOLUTIONS,
    SUPPORTED_INPUTS, ConversionQueue, ConversionSettings, ConversionTask,
    MediaInfo, available_formats, detect_encoders, find_ffmpeg, probe_media,
)
from .engine import format_bytes
from .icons import icon
from .theme import GREEN, MUTED, RED


def _row(margins=(0, 0, 0, 0), spacing=0):
    layout = QHBoxLayout(); layout.setContentsMargins(*margins); layout.setSpacing(spacing); return layout


def _column(margins=(0, 0, 0, 0), spacing=0):
    layout = QVBoxLayout(); layout.setContentsMargins(*margins); layout.setSpacing(spacing); return layout


def _label(value, name=''):
    widget = QLabel(str(value)); widget.setObjectName(name); return widget


def _button(value, image=None, name=None):
    widget = QPushButton(value)
    if image: widget.setIcon(icon(image, '#0A1907' if name == 'Primary' else '#B4C6C9', 18))
    if name: widget.setObjectName(name)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def _duration(seconds):
    value = int(seconds or 0)
    return f'{value // 60}:{value % 60:02d}' if value else '—'


class ProbeThread(QThread):
    ready = Signal(str, object)
    failed = Signal(str, str)

    def __init__(self, path, ffmpeg, parent=None):
        super().__init__(parent); self.path = path; self.ffmpeg = ffmpeg

    def run(self):
        try: self.ready.emit(self.path, probe_media(self.path, self.ffmpeg))
        except Exception as exc: self.failed.emit(self.path, str(exc))


class DropArea(QFrame):
    paths_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent); self.setObjectName('InfoBox'); self.setAcceptDrops(True)
        self.setMinimumHeight(92)
        layout = _column((18, 15, 18, 15), 5); layout.setAlignment(Qt.AlignmentFlag.AlignCenter); self.setLayout(layout)
        title = _label('Arraste seus arquivos para cá', 'Section'); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note = _label('Ou clique em Adicionar arquivos para começar.', 'Muted'); note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title); layout.addWidget(note)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        self.paths_dropped.emit([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()


class ConversionCard(QFrame):
    remove_requested = Signal(str)
    cancel_requested = Signal(str)
    retry_requested = Signal(str)
    format_changed = Signal(str)

    def __init__(self, path, formats, parent=None):
        super().__init__(parent); self.path = str(Path(path)); self.media = None; self.state = 'Analisando'
        self.setObjectName('Card'); self.setMinimumHeight(104)
        outer = _row((13, 11, 13, 11), 12); self.setLayout(outer)
        glyph = _label('♪' if Path(path).suffix.lower() not in {'.mp4','.mkv','.avi','.mov','.webm','.m4v','.mpeg','.mpg','.wmv'} else '▶')
        glyph.setAlignment(Qt.AlignmentFlag.AlignCenter); glyph.setFixedSize(64, 64)
        glyph.setStyleSheet(f'background:#19302C;border-radius:8px;color:{GREEN};font-size:26px;font-weight:800;')
        outer.addWidget(glyph)
        content = _column(spacing=5); outer.addLayout(content, 1)
        top = _row(spacing=7); self.title = _label(Path(path).name); self.title.setStyleSheet('font-weight:700;font-size:13px;')
        self.title.setToolTip(self.path); top.addWidget(self.title, 1)
        self.format = QComboBox(); self.format.addItems(formats); self.format.setMinimumWidth(90)
        self.format.currentTextChanged.connect(self.format_changed); top.addWidget(self.format); content.addLayout(top)
        self.details = _label('Lendo informações do arquivo…', 'Muted'); content.addWidget(self.details)
        self.progress = QProgressBar(); self.progress.setRange(0, 0); content.addWidget(self.progress)
        self.status = _label('Analisando', 'Subtle'); content.addWidget(self.status)
        controls = _column(spacing=5); self.percent = _label('', 'Success'); self.percent.setAlignment(Qt.AlignmentFlag.AlignRight)
        controls.addWidget(self.percent)
        self.remove = _button('', 'close', 'IconButton'); self.remove.setToolTip('Remover da fila')
        self.remove.clicked.connect(self._remove_or_cancel); controls.addWidget(self.remove)
        self.retry = _button('Tentar novamente'); self.retry.clicked.connect(lambda: self.retry_requested.emit(self.path)); self.retry.hide(); controls.addWidget(self.retry)
        self.error_details = ''; self.details_button = _button('Detalhes'); self.details_button.clicked.connect(self._show_error); self.details_button.hide(); controls.addWidget(self.details_button)
        controls.addStretch(); outer.addLayout(controls)

    def set_media(self, media: MediaInfo, valid_formats):
        self.media = media; self.state = 'Pronto'; self.progress.setRange(0, 100); self.progress.setValue(0)
        self.details.setText(f'{Path(self.path).suffix[1:].upper()}  •  {_duration(media.duration)}  •  {format_bytes(media.size)}')
        previous = self.format.currentText(); self.format.blockSignals(True); self.format.clear(); self.format.addItems(valid_formats)
        if previous in valid_formats: self.format.setCurrentText(previous)
        self.format.blockSignals(False); self.status.setText('Pronto para converter')

    def set_failed(self, message, details=''):
        self.error_details = details or message
        self.state = 'Falhou'; self.progress.setRange(0, 100); self.progress.setValue(0); self.status.setText(message)
        self.status.setToolTip(message); self.status.setStyleSheet(f'color:{RED};'); self.retry.show(); self.details_button.show(); self.remove.show()

    def start(self):
        self.state = 'Convertendo'; self.progress.setRange(0, 100); self.status.setStyleSheet(''); self.status.setText('Convertendo…')
        self.remove.show(); self.remove.setToolTip('Cancelar esta conversão'); self.retry.hide(); self.details_button.hide()

    def update_progress(self, values):
        value = values.get('percent', -1)
        if value < 0: self.progress.setRange(0, 0); self.percent.setText('')
        else: self.progress.setRange(0, 100); self.progress.setValue(value); self.percent.setText(f'{value}%')
        extras = []
        if values.get('speed'): extras.append(values['speed'])
        if values.get('elapsed') is not None: extras.append(f'decorrido {_duration(values["elapsed"])}')
        if values.get('eta') is not None: extras.append(f'restam {_duration(values["eta"])}')
        self.status.setText('Convertendo' + (f'  •  {"  •  ".join(extras)}' if extras else '…'))

    def complete(self, output):
        self.state = 'Concluído'; self.progress.setRange(0, 100); self.progress.setValue(100); self.percent.setText('✓')
        self.status.setText(f'Concluído: {Path(output).name}'); self.status.setStyleSheet(f'color:{GREEN};'); self.remove.show()

    def cancelled(self):
        self.state = 'Cancelado'; self.progress.setRange(0, 100); self.status.setText('Conversão cancelada'); self.percent.setText('×'); self.remove.show()

    def _remove_or_cancel(self):
        if self.state == 'Convertendo': self.cancel_requested.emit(self.path)
        else: self.remove_requested.emit(self.path)

    def _show_error(self):
        QMessageBox.critical(self, 'Detalhes técnicos', self.error_details or 'Nenhum detalhe disponível.')


class ConverterPage(QWidget):
    conversion_completed = Signal(str, str)
    busy_changed = Signal(bool)

    def __init__(self, storage, parent=None):
        super().__init__(parent); self.storage = storage; self.cards = {}; self.probes = []
        self.completed_count = 0; self.failed_count = 0
        try:
            self.ffmpeg = find_ffmpeg(self.storage.config.get('ffmpeg_path')); self.encoders = detect_encoders(self.ffmpeg); self.formats = available_formats(self.encoders)
            self.engine_error = '' if self.formats else 'O FFmpeg encontrado não possui encoders compatíveis.'
        except Exception as exc:
            self.ffmpeg = ''; self.encoders = set(); self.formats = []; self.engine_error = str(exc)
        self.queue = ConversionQueue(self.ffmpeg, self.encoders, self)
        self.queue.job_started.connect(self._job_started); self.queue.job_progress.connect(self._job_progress)
        self.queue.job_completed.connect(self._job_completed); self.queue.job_failed.connect(self._job_failed)
        self.queue.job_cancelled.connect(self._job_cancelled); self.queue.queue_finished.connect(self._queue_finished)
        self._build()

    def _build(self):
        root = _column(spacing=13); self.setLayout(root)
        heading = _row(spacing=9); titles = _column(spacing=3); titles.addWidget(_label('Conversor de vídeo e áudio', 'Heading'))
        titles.addWidget(_label('Transforme seus arquivos em diferentes formatos com qualidade e praticidade.', 'Muted')); heading.addLayout(titles, 1)
        add_files = _button('Adicionar arquivos', 'film', 'Primary'); add_files.clicked.connect(self.choose_files); heading.addWidget(add_files)
        add_folder = _button('Adicionar pasta', 'folder'); add_folder.clicked.connect(self.choose_folder); heading.addWidget(add_folder); root.addLayout(heading)
        self.drop = DropArea(); self.drop.paths_dropped.connect(self.add_paths); root.addWidget(self.drop)
        settings = QFrame(); settings.setObjectName('FormPanel'); settings_layout = _column((14, 10, 14, 10), 8); settings.setLayout(settings_layout)
        form = _row(spacing=9); settings_layout.addLayout(form)
        form.addWidget(_label('Formato', 'Muted')); self.output_format = QComboBox(); self.output_format.addItems(self.formats); form.addWidget(self.output_format)
        form.addWidget(_label('Qualidade', 'Muted')); self.quality = QComboBox(); self.quality.addItems(QUALITY_PROFILES); form.addWidget(self.quality)
        form.addWidget(_label('Resolução', 'Muted')); self.resolution = QComboBox(); self.resolution.addItems(RESOLUTIONS); form.addWidget(self.resolution)
        form.addWidget(_label('Áudio', 'Muted')); self.bitrate = QComboBox(); self.bitrate.addItems(BITRATES); form.addWidget(self.bitrate)
        form.addStretch()
        options = _row(spacing=13); settings_layout.addLayout(options)
        self.preserve_resolution = QCheckBox('Preservar resolução original'); options.addWidget(self.preserve_resolution)
        self.keep_aspect = QCheckBox('Manter proporção'); options.addWidget(self.keep_aspect)
        self.batch = QCheckBox('Conversão em lote'); options.addWidget(self.batch)
        self.apply_all = QCheckBox('Aplicar formato a todos'); options.addWidget(self.apply_all)
        options.addStretch(); destination = _button('Destino…', 'folder'); destination.clicked.connect(self.choose_destination); options.addWidget(destination)
        self.destination = _label('', 'Subtle'); options.addWidget(self.destination)
        self.loss_note = _label('', 'Subtle'); settings_layout.addWidget(self.loss_note); root.addWidget(settings)
        self._restore_settings()
        self.output_format.currentTextChanged.connect(self._global_format_changed)
        for widget in (self.output_format, self.quality, self.resolution, self.bitrate): widget.currentTextChanged.connect(self._save_settings)
        self.keep_aspect.toggled.connect(self._save_settings)
        self.preserve_resolution.toggled.connect(self._preserve_resolution_changed)
        self.batch.toggled.connect(self._save_settings); self.apply_all.toggled.connect(self._save_settings)
        self._format_note(self.output_format.currentText())
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); contents = QWidget(); self.list = _column((1, 1, 5, 1), 9)
        contents.setLayout(self.list); self.list.addStretch(); self.scroll.setWidget(contents); root.addWidget(self.scroll, 1)
        footer = QFrame(); footer.setObjectName('FormPanel'); line = _row((14, 11, 14, 11), 10); footer.setLayout(line)
        self.summary = _label('Nenhum arquivo adicionado', 'Muted'); line.addWidget(self.summary, 1)
        self.total_progress = QProgressBar(); self.total_progress.setRange(0, 100); self.total_progress.setFixedWidth(180); line.addWidget(self.total_progress)
        self.cancel = _button('Cancelar conversão', 'close'); self.cancel.clicked.connect(self.queue.cancel_all); self.cancel.setEnabled(False); line.addWidget(self.cancel)
        self.convert = _button('Converter tudo', 'convert', 'Primary'); self.convert.clicked.connect(self.convert_all); self.convert.setEnabled(False); line.addWidget(self.convert)
        root.addWidget(footer)
        if self.engine_error: self.summary.setText(self.engine_error)

    def _restore_settings(self):
        config = self.storage.config
        values = ((self.output_format, config.get('converter_format', 'MP3')),
                  (self.quality, config.get('converter_quality', 'Equilibrado')),
                  (self.resolution, config.get('converter_resolution', 'Original')),
                  (self.bitrate, config.get('converter_bitrate', '192 kbps')))
        for combo, value in values:
            if combo.findText(value) >= 0: combo.setCurrentText(value)
        self.keep_aspect.setChecked(bool(config.get('converter_keep_aspect', True)))
        self.preserve_resolution.setChecked(config.get('converter_resolution', 'Original') == 'Original')
        self.resolution.setEnabled(not self.preserve_resolution.isChecked())
        self.batch.setChecked(bool(config.get('converter_batch', True)))
        self.apply_all.setChecked(bool(config.get('converter_apply_all', True)))
        self.output_dir = config.get('converter_output_dir') or config.get('output_dir') or str(Path.home() / 'Videos')
        self.destination.setText(f'Destino: {self.output_dir}')

    def _save_settings(self, *_):
        self.storage.config.update(converter_format=self.output_format.currentText(), converter_quality=self.quality.currentText(),
            converter_resolution=self.resolution.currentText(), converter_bitrate=self.bitrate.currentText(),
            converter_keep_aspect=self.keep_aspect.isChecked(), converter_output_dir=self.output_dir,
            converter_batch=self.batch.isChecked(), converter_apply_all=self.apply_all.isChecked())
        self.storage.save_config()

    def choose_files(self):
        patterns = ' '.join(f'*{suffix}' for suffix in sorted(SUPPORTED_INPUTS))
        paths, _ = QFileDialog.getOpenFileNames(self, 'Adicionar mídias', '', f'Mídias ({patterns});;Todos os arquivos (*.*)')
        self.add_paths(paths)

    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, 'Adicionar pasta')
        if folder: self.add_paths([str(path) for path in Path(folder).iterdir() if path.is_file()])

    def choose_destination(self):
        folder = QFileDialog.getExistingDirectory(self, 'Pasta de destino', self.output_dir)
        if folder: self.output_dir = folder; self.destination.setText(f'Destino: {folder}'); self._save_settings()

    def add_paths(self, paths):
        unsupported = 0
        for raw in paths:
            path = Path(raw)
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_INPUTS: unsupported += 1; continue
            key = str(path.resolve())
            if key in self.cards: continue
            card = ConversionCard(key, self.formats); card.remove_requested.connect(self.remove_path); card.cancel_requested.connect(self.cancel_path); card.retry_requested.connect(self.retry_path)
            card.format_changed.connect(lambda value, c=card: self._card_format_changed(c, value))
            self.cards[key] = card; self.list.insertWidget(self.list.count() - 1, card); self._probe(key)
        if unsupported: QMessageBox.information(self, 'Arquivos ignorados', f'{unsupported} arquivo(s) não são mídias compatíveis.')
        self._update_summary()

    def _probe(self, path):
        card = self.cards.get(path)
        if not card or not self.ffmpeg: return
        card.state = 'Analisando'; card.progress.setRange(0, 0); card.status.setText('Analisando arquivo…'); card.retry.hide()
        worker = ProbeThread(path, self.ffmpeg, self); self.probes.append(worker)
        worker.ready.connect(self._probe_ready); worker.failed.connect(self._probe_failed)
        worker.finished.connect(lambda w=worker: self._probe_done(w)); worker.start()

    def _probe_done(self, worker):
        if worker in self.probes: self.probes.remove(worker)
        worker.deleteLater()

    def _probe_ready(self, path, media):
        card = self.cards.get(path)
        if not card: return
        valid = [name for name in self.formats if media.has_video or name in AUDIO_OUTPUTS]
        card.set_media(media, valid)
        if self.apply_all.isChecked() and self.output_format.currentText() in valid:
            card.format.setCurrentText(self.output_format.currentText())
        self._card_format_changed(card, card.format.currentText()); self._update_summary()

    def _probe_failed(self, path, message):
        card = self.cards.get(path)
        if card: card.set_failed(message)
        self._update_summary()

    def remove_path(self, path):
        card = self.cards.get(path)
        if not card or card.state == 'Convertendo': return
        self.queue.remove_pending(getattr(card, 'task_id', '')); self.cards.pop(path, None); self.list.removeWidget(card); card.deleteLater(); self._update_summary()

    def cancel_path(self, path):
        card = self.cards.get(path)
        if card and self.queue.current and self.queue.current.id == getattr(card, 'task_id', ''):
            self.queue.cancel_current()

    def retry_path(self, path):
        card = self.cards.get(path)
        if not card: return
        if not card.media:
            self._probe(path); return
        task = self._task_for_card(card); card.task_id = task.id
        self.cancel.setEnabled(True); self.convert.setEnabled(False); self.busy_changed.emit(True); self.queue.enqueue([task])

    def _global_format_changed(self, value):
        if self.apply_all.isChecked():
            for card in self.cards.values():
                if card.format.findText(value) >= 0: card.format.setCurrentText(value)
        self._format_note(value)
        self._save_settings()

    def _format_note(self, value):
        lossless = value in {'WAV','FLAC'}
        self.bitrate.setEnabled(not lossless); self.quality.setEnabled(not lossless)
        self.loss_note.setText('Conversão sem perdas: bitrate e perfil de qualidade não se aplicam.' if lossless else
                               'Formato com compressão: a qualidade final nunca será superior à mídia original.')

    def _preserve_resolution_changed(self, checked):
        if checked: self.resolution.setCurrentText('Original')
        self.resolution.setEnabled(not checked); self._save_settings()

    def _card_format_changed(self, card, value):
        is_video = value in VIDEO_OUTPUTS
        card.format.setToolTip('Mantém vídeo e áudio' if is_video else 'Extrai/converte somente o áudio')

    def convert_all(self):
        if self.queue.is_active(): return
        if not self.output_dir: return
        tasks = []
        for card in self.cards.values():
            if card.media and card.state in {'Pronto', 'Falhou', 'Cancelado'} and card.format.currentText():
                task = self._task_for_card(card); card.task_id = task.id; tasks.append(task)
                if not self.batch.isChecked(): break
        if not tasks: QMessageBox.information(self, 'Nada para converter', 'Adicione ao menos um arquivo válido.'); return
        self.completed_count = self.failed_count = 0; self.total_progress.setValue(0); self.cancel.setEnabled(True); self.convert.setEnabled(False)
        self.busy_changed.emit(True); self.queue.enqueue(tasks); self._update_summary()

    def _task_for_card(self, card):
        settings = ConversionSettings(card.format.currentText(), self.quality.currentText(), self.resolution.currentText(),
                                      self.keep_aspect.isChecked(), self.bitrate.currentText())
        return ConversionTask(card.path, self.output_dir, settings, card.media)

    def _card_for_task(self, task): return self.cards.get(str(Path(task.source).resolve()))
    def _job_started(self, task):
        card = self._card_for_task(task)
        if card: card.start()
    def _job_progress(self, task, values):
        card = self._card_for_task(task)
        if card: card.update_progress(values)
        self._update_total_progress()
    def _job_completed(self, task):
        card = self._card_for_task(task)
        if card: card.complete(task.output_path)
        self.completed_count += 1; self.conversion_completed.emit(task.source, task.output_path); self._update_total_progress()
    def _job_failed(self, task, message):
        card = self._card_for_task(task)
        if card: card.set_failed(message, task.error)
        self.failed_count += 1; self._update_total_progress()
    def _job_cancelled(self, task):
        card = self._card_for_task(task)
        if card: card.cancelled()
        self._update_total_progress()
    def _queue_finished(self):
        self.cancel.setEnabled(False); self.busy_changed.emit(False); self._update_summary()

    def _update_total_progress(self):
        cards = list(self.cards.values()); values = [card.progress.value() for card in cards if card.progress.maximum() == 100]
        self.total_progress.setValue(int(sum(values) / len(cards)) if cards else 0); self._update_summary()

    def _update_summary(self):
        total = len(self.cards); ready = sum(card.state in {'Pronto','Falhou','Cancelado'} for card in self.cards.values())
        self.summary.setText(f'{total} arquivo(s)  •  {self.completed_count} concluído(s)  •  {self.failed_count} falha(s)')
        self.convert.setEnabled(bool(self.ffmpeg and ready and not self.queue.is_active()))

    def is_active(self): return self.queue.is_active() or any(worker.isRunning() for worker in self.probes)
    def shutdown(self):
        self.queue.shutdown()
        for worker in self.probes: worker.wait(2500)

