"""Conversor de mídia do Fluxora 3.1: interface premium integrada ao FFmpeg."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QUrl, QRect
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QKeySequence, QShortcut, QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QScrollArea,
    QFileDialog, QComboBox, QCheckBox, QProgressBar, QMessageBox, QDialog,
    QFormLayout, QButtonGroup, QSizePolicy,
)

from .converter import (
    AUDIO_OUTPUTS, VIDEO_OUTPUTS, BITRATES, QUALITY_PROFILES, RESOLUTIONS,
    SUPPORTED_INPUTS, ConversionQueue, ConversionSettings, ConversionTask,
    MediaInfo, available_formats, detect_encoders, find_ffmpeg, probe_media,
)
from .engine import format_bytes
from .icons import icon
from .theme import GREEN, RED

VIDEO_INPUTS={'.mp4','.mkv','.avi','.mov','.webm','.m4v','.mpeg','.mpg','.wmv'}


def _row(margins=(0,0,0,0),spacing=0):
    layout=QHBoxLayout(); layout.setContentsMargins(*margins); layout.setSpacing(spacing); return layout


def _column(margins=(0,0,0,0),spacing=0):
    layout=QVBoxLayout(); layout.setContentsMargins(*margins); layout.setSpacing(spacing); return layout


def _label(value,name=''):
    widget=QLabel(str(value)); widget.setObjectName(name); return widget


def _button(value,image=None,name=None):
    widget=QPushButton(value)
    if image: widget.setIcon(icon(image,'#0A1907' if name in ('Primary','ConverterPrimary','ConverterAdd') else '#C4D2D5',19))
    if name: widget.setObjectName(name)
    widget.setCursor(Qt.CursorShape.PointingHandCursor); return widget


def _duration(seconds):
    value=int(seconds or 0)
    if not value: return '—'
    return f'{value//3600}:{value//60%60:02d}:{value%60:02d}' if value>=3600 else f'{value//60}:{value%60:02d}'


class ElideLabel(QLabel):
    def __init__(self,value=''):
        super().__init__(); self.full_text=str(value); self.setToolTip(self.full_text)
    def setText(self,value):
        self.full_text=str(value); self.setToolTip(self.full_text); self._update_elide()
    def resizeEvent(self,event): self._update_elide(); super().resizeEvent(event)
    def _update_elide(self): QLabel.setText(self,self.fontMetrics().elidedText(self.full_text,Qt.TextElideMode.ElideMiddle,max(30,self.width()-3)))


class ProbeThread(QThread):
    ready=Signal(str,object); failed=Signal(str,str)
    def __init__(self,path,ffmpeg,parent=None): super().__init__(parent); self.path=path; self.ffmpeg=ffmpeg
    def run(self):
        try: self.ready.emit(self.path,probe_media(self.path,self.ffmpeg))
        except Exception as exc: self.failed.emit(self.path,str(exc))


class DropArea(QFrame):
    paths_dropped=Signal(list)
    def __init__(self,parent=None):
        super().__init__(parent); self.setObjectName('ConverterDrop'); self.setAcceptDrops(True); self.setMinimumHeight(92)
        layout=_row((20,15,20,15),13); self.setLayout(layout); layout.addStretch()
        symbol=_label('⬆','UploadGlyph'); symbol.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(symbol)
        copy=_column(spacing=3); copy.addWidget(_label('Ou arraste e solte seus arquivos aqui','ConverterStrong')); copy.addWidget(_label('Vídeos, áudios e outros formatos suportados','Muted')); layout.addLayout(copy); layout.addStretch()
    def dragEnterEvent(self,event:QDragEnterEvent):
        if event.mimeData().hasUrls(): event.acceptProposedAction()
    def dropEvent(self,event:QDropEvent):
        self.paths_dropped.emit([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]); event.acceptProposedAction()


class SelectionBox(QCheckBox):
    activated=Signal(object)
    def __init__(self,parent=None):
        super().__init__(parent); self.setFixedSize(24,24); self.setCursor(Qt.CursorShape.PointingHandCursor)
    def paintEvent(self,event):
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing,True); box=QRect(2,2,20,20)
        checked=self.isChecked(); painter.setPen(QPen(QColor(GREEN if checked else '#82979D'),1.8)); painter.setBrush(QColor(GREEN if checked else '#0B171A')); painter.drawRoundedRect(box,5,5)
        if checked:
            painter.setPen(QPen(QColor('#0A1607'),2.5,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin)); painter.drawLine(7,12,11,16); painter.drawLine(11,16,18,7)
        painter.end()
    def mouseReleaseEvent(self,event):
        modifiers=event.modifiers(); super().mouseReleaseEvent(event)
        if event.button()==Qt.MouseButton.LeftButton: self.activated.emit(modifiers)
    def keyReleaseEvent(self,event):
        super().keyReleaseEvent(event)
        if event.key()==Qt.Key.Key_Space: self.activated.emit(Qt.KeyboardModifier.NoModifier)


class CardSettingsDialog(QDialog):
    def __init__(self,card,parent=None):
        super().__init__(parent); self.card=card; self.setWindowTitle(f'Opções — {Path(card.path).name}'); self.setMinimumWidth(430)
        root=_column((24,22,24,22),14); self.setLayout(root); root.addWidget(_label('Configurações individuais','Heading'))
        form=QFormLayout(); form.setVerticalSpacing(12); root.addLayout(form)
        self.quality=QComboBox(); self.quality.addItems(QUALITY_PROFILES); self.quality.setCurrentText(card.quality); form.addRow('Qualidade',self.quality)
        self.resolution=QComboBox(); self.resolution.addItems(RESOLUTIONS); self.resolution.setCurrentText(card.resolution); form.addRow('Resolução',self.resolution)
        self.bitrate=QComboBox(); self.bitrate.addItems(BITRATES); self.bitrate.setCurrentText(card.bitrate); form.addRow('Bitrate de áudio',self.bitrate)
        self.keep=QCheckBox('Manter proporção do vídeo'); self.keep.setChecked(card.keep_aspect); form.addRow('',self.keep)
        target=card.format.currentText(); self.resolution.setEnabled(target in VIDEO_OUTPUTS); self.keep.setEnabled(target in VIDEO_OUTPUTS)
        self.bitrate.setEnabled(target not in {'WAV','FLAC'}); self.quality.setEnabled(target not in {'WAV','FLAC'})
        actions=_row(spacing=9); actions.addStretch(); cancel=_button('Cancelar'); cancel.clicked.connect(self.reject); actions.addWidget(cancel)
        save=_button('Aplicar','check','Primary'); save.clicked.connect(self.accept); actions.addWidget(save); root.addLayout(actions)
    def apply(self):
        self.card.quality=self.quality.currentText(); self.card.resolution=self.resolution.currentText(); self.card.bitrate=self.bitrate.currentText(); self.card.keep_aspect=self.keep.isChecked()


class ConversionCard(QFrame):
    selection_clicked=Signal(object,object); remove_requested=Signal(str); cancel_requested=Signal(str)
    individual_requested=Signal(str); settings_requested=Signal(object); format_changed=Signal(object,str)
    def __init__(self,path,formats,parent=None):
        super().__init__(parent); self.path=str(Path(path).resolve()); self.media=None; self.state='Analisando'; self.valid_formats=list(formats)
        self.quality='Equilibrado'; self.resolution='Original'; self.bitrate='192 kbps'; self.keep_aspect=True; self.output_path=''; self.task_id=''
        self.setObjectName('ConversionCard'); self.setProperty('batchSelected',True); self.setMinimumHeight(91)
        outer=_row((12,9,12,9),10); self.setLayout(outer)
        self.select=SelectionBox(); self.select.setObjectName('BatchCheck'); self.select.setChecked(True); self.select.activated.connect(lambda modifiers:self.selection_clicked.emit(self,modifiers)); outer.addWidget(self.select)
        glyph=_label('♪' if Path(path).suffix.lower() not in VIDEO_INPUTS else '▶','MediaGlyph'); glyph.setAlignment(Qt.AlignmentFlag.AlignCenter); glyph.setFixedSize(62,62); outer.addWidget(glyph)
        info=_column(spacing=5); self.title=ElideLabel(Path(path).name); self.title.setObjectName('ConverterStrong'); self.title.setMinimumWidth(95); self.title.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred); info.addWidget(self.title)
        self.details=_label('Lendo informações do arquivo…','Muted'); self.details.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred); info.addWidget(self.details); outer.addLayout(info,2)
        target=_column(spacing=3); target.addWidget(_label('Converter para','Subtle')); self.format=QComboBox(); self.format.addItems(formats); self.format.setMinimumWidth(130)
        self.format.currentTextChanged.connect(lambda value:self.format_changed.emit(self,value)); target.addWidget(self.format); outer.addLayout(target,2)
        gear=_button('','settings','IconButton'); gear.setToolTip('Configurações individuais'); gear.clicked.connect(lambda:self.settings_requested.emit(self)); outer.addWidget(gear)
        progress=_column(spacing=6); progress.setContentsMargins(4,5,4,4); self.progress=QProgressBar(); self.progress.setRange(0,100); progress.addWidget(self.progress)
        statusline=_row(spacing=5); self.status=_label('Analisando…','Subtle'); self.status.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred); statusline.addWidget(self.status,1); self.percent=_label('','Success'); statusline.addWidget(self.percent); progress.addLayout(statusline); outer.addLayout(progress,2)
        self.run=_button('','play','RoundButton'); self.run.setToolTip('Converter somente este arquivo'); self.run.clicked.connect(lambda:self.individual_requested.emit(self.path)); outer.addWidget(self.run)
        self.remove=_button('','close','RoundButton'); self.remove.setToolTip('Remover'); self.remove.clicked.connect(self._remove_or_cancel); outer.addWidget(self.remove)
    def is_selected(self): return self.select.isChecked()
    def set_selected(self,value):
        self.select.blockSignals(True); self.select.setChecked(bool(value)); self.select.blockSignals(False); self.setProperty('batchSelected',bool(value)); self.style().unpolish(self); self.style().polish(self)
    def is_mutable(self): return self.state not in {'Na fila','Convertendo'}
    def is_eligible(self): return bool(self.media and self.format.currentText() and self.is_mutable())
    def set_media(self,media:MediaInfo,valid_formats,preferred=''):
        self.media=media; self.valid_formats=list(valid_formats); self.state='Pronto'; self.progress.setRange(0,100); self.progress.setValue(0)
        resolution=f'  •  {media.width}×{media.height}' if media.has_video and media.width else ''
        self.details.setText(f'{Path(self.path).suffix[1:].upper()}{resolution}  •  {_duration(media.duration)}  •  {format_bytes(media.size)}')
        previous=preferred or self.format.currentText(); self.format.blockSignals(True); self.format.clear(); self.format.addItems(valid_formats)
        if previous in valid_formats: self.format.setCurrentText(previous)
        self.format.blockSignals(False); self.status.setText('Aguardando'); self.status.setStyleSheet(''); self.run.setEnabled(bool(valid_formats))
    def set_failed(self,message,details=''):
        self.error_details=details or message; self.state='Falhou'; self.progress.setRange(0,100); self.progress.setValue(0); self.status.setText(message); self.status.setToolTip(self.error_details); self.status.setStyleSheet(f'color:{RED};'); self.run.setEnabled(True); self.select.setEnabled(True); self.run.setToolTip('Tentar novamente')
    def queued(self): self.state='Na fila'; self.status.setText('Na fila…'); self.status.setStyleSheet(''); self.run.setEnabled(False); self.select.setEnabled(False); self.format.setEnabled(False); self.run.setIcon(icon('play','#C4D2D5',19))
    def start(self): self.state='Convertendo'; self.status.setText('Convertendo…'); self.status.setStyleSheet(''); self.run.setEnabled(False); self.format.setEnabled(False); self.remove.setToolTip('Cancelar conversão')
    def update_progress(self,values):
        value=values.get('percent',-1)
        if value<0: self.progress.setRange(0,0); self.percent.setText('')
        else: self.progress.setRange(0,100); self.progress.setValue(value); self.percent.setText(f'{value}%')
        extras=[]
        if values.get('speed'): extras.append(values['speed'])
        if values.get('eta') is not None: extras.append(f'{_duration(values["eta"])} restante')
        self.status.setText('Convertendo'+(f'  •  {"  •  ".join(extras)}' if extras else '…'))
    def complete(self,output):
        self.state='Concluído'; self.output_path=output; self.progress.setRange(0,100); self.progress.setValue(100); self.percent.setText('✓'); self.status.setText('Concluído'); self.status.setStyleSheet(f'color:{GREEN};'); self.format.setEnabled(True); self.select.setEnabled(True); self.run.setEnabled(True); self.run.setIcon(icon('external','#C4D2D5',19)); self.run.setToolTip('Abrir arquivo convertido'); self.remove.setToolTip('Remover')
    def cancelled(self): self.state='Cancelado'; self.status.setText('Cancelado'); self.percent.setText('×'); self.format.setEnabled(True); self.select.setEnabled(True); self.run.setEnabled(True); self.run.setIcon(icon('play','#C4D2D5',19)); self.run.setToolTip('Converter novamente')
    def _remove_or_cancel(self):
        if self.state=='Convertendo': self.cancel_requested.emit(self.path)
        else: self.remove_requested.emit(self.path)


class ConverterPage(QWidget):
    conversion_completed=Signal(str,str); busy_changed=Signal(bool)
    def __init__(self,storage,parent=None):
        super().__init__(parent); self.storage=storage; self.cards={}; self.probes=[]; self.selection_anchor=None; self.completed_count=0; self.failed_count=0; self.global_format='MP3'; self.global_quality='Equilibrado'
        try:
            self.ffmpeg=find_ffmpeg(storage.config.get('ffmpeg_path')); self.encoders=detect_encoders(self.ffmpeg); self.formats=available_formats(self.encoders); self.engine_error='' if self.formats else 'O FFmpeg encontrado não possui encoders compatíveis.'
        except Exception as exc: self.ffmpeg=''; self.encoders=set(); self.formats=[]; self.engine_error=str(exc)
        self.queue=ConversionQueue(self.ffmpeg,self.encoders,self); self.queue.job_started.connect(self._job_started); self.queue.job_progress.connect(self._job_progress); self.queue.job_completed.connect(self._job_completed); self.queue.job_failed.connect(self._job_failed); self.queue.job_cancelled.connect(self._job_cancelled); self.queue.queue_finished.connect(self._queue_finished)
        self._build(); self.select_all_shortcut=QShortcut(QKeySequence.StandardKey.SelectAll,self); self.select_all_shortcut.activated.connect(self.select_all)
    def _build(self):
        root=_column(spacing=12); self.setLayout(root)
        heading=_row(spacing=12); emblem=_label('⟳','ConverterEmblem'); emblem.setAlignment(Qt.AlignmentFlag.AlignCenter); heading.addWidget(emblem)
        titles=_column(spacing=1); titles.addWidget(_label('Conversor de vídeo e áudio','ConverterTitle')); titles.addWidget(_label('Transforme seus arquivos em diferentes formatos com qualidade e praticidade.','Muted')); heading.addLayout(titles,1); root.addLayout(heading)
        imports=_row(spacing=12); add_files=_button('Adicionar arquivos\nSelecione um ou mais arquivos','plus','ConverterAdd'); add_files.clicked.connect(self.choose_files); imports.addWidget(add_files,1)
        add_folder=_button('Adicionar pasta\nConverta os arquivos da pasta','folder','ConverterImport'); add_folder.clicked.connect(self.choose_folder); imports.addWidget(add_folder,1)
        self.drop=DropArea(); self.drop.paths_dropped.connect(self.add_paths); imports.addWidget(self.drop,2); root.addLayout(imports)
        settings=QFrame(); settings.setObjectName('ConverterPanel'); setting_row=_row((13,10,13,10),14); settings.setLayout(setting_row)
        formats_box=_column(spacing=6); formats_box.addWidget(_label('Formato de saída  (aplicar aos selecionados)','ConverterStrong')); formats_line=_row(spacing=6); self.format_group=QButtonGroup(self); self.format_group.setExclusive(True); self.format_buttons={}
        for name in self.formats:
            button=_button(name,'music' if name in AUDIO_OUTPUTS else 'film','FormatChip'); button.setCheckable(True); button.clicked.connect(lambda checked=False,value=name:self.apply_global_format(value)); self.format_group.addButton(button); self.format_buttons[name]=button; formats_line.addWidget(button)
        formats_line.addStretch(); formats_box.addLayout(formats_line); setting_row.addLayout(formats_box,3)
        quality_box=_column(spacing=6); quality_box.addWidget(_label('Qualidade','ConverterStrong')); quality_line=_row(spacing=7); self.quality_group=QButtonGroup(self); self.quality_group.setExclusive(True); self.quality_buttons={}
        for quality in ('Equilibrado','Alta qualidade','Compacto'):
            button=_button(quality,'star','QualityChip'); button.setCheckable(True); button.clicked.connect(lambda checked=False,value=quality:self.apply_global_quality(value)); self.quality_group.addButton(button); self.quality_buttons[quality]=button; quality_line.addWidget(button)
        quality_box.addLayout(quality_line); setting_row.addLayout(quality_box,2); self.advanced_toggle=_button('Opções avançadas','settings'); self.advanced_toggle.setCheckable(True); self.advanced_toggle.clicked.connect(self._toggle_advanced); setting_row.addWidget(self.advanced_toggle); root.addWidget(settings)
        self.advanced=QFrame(); self.advanced.setObjectName('ConverterAdvanced'); advanced=_row((13,9,13,9),10); self.advanced.setLayout(advanced); self.resolution_label=_label('Resolução','Muted'); advanced.addWidget(self.resolution_label); self.resolution=QComboBox(); self.resolution.addItems(RESOLUTIONS); advanced.addWidget(self.resolution); self.bitrate_label=_label('Bitrate','Muted'); advanced.addWidget(self.bitrate_label); self.bitrate=QComboBox(); self.bitrate.addItems(BITRATES); advanced.addWidget(self.bitrate); self.preserve_resolution=QCheckBox('Preservar resolução original'); advanced.addWidget(self.preserve_resolution); self.keep_aspect=QCheckBox('Manter proporção'); advanced.addWidget(self.keep_aspect); advanced.addStretch(); self.advanced.hide(); root.addWidget(self.advanced)
        list_panel=QFrame(); list_panel.setObjectName('ConverterPanel'); panel=_column((9,8,9,8),8); list_panel.setLayout(panel); tools=_row(spacing=7); self.files_title=_label('Arquivos adicionados (0)','Section'); tools.addWidget(self.files_title); tools.addStretch()
        for caption,handler in [('Todos',self.select_all),('Nenhum',self.select_none),('Inverter seleção',self.invert_selection),('Remover selecionados',self.remove_selected),('Limpar lista',self.clear_list)]:
            button=_button(caption,'trash' if 'Remover' in caption or 'Limpar' in caption else 'check'); button.clicked.connect(handler); tools.addWidget(button)
        panel.addLayout(tools); self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.contents=QWidget(); self.contents.setMinimumWidth(0); self.list=_column((0,0,2,0),7); self.contents.setLayout(self.list); self.list.addStretch(); self.scroll.setWidget(self.contents); panel.addWidget(self.scroll,1); root.addWidget(list_panel,1)
        footer=_row(spacing=12); destination=QFrame(); destination.setObjectName('ConverterFooter'); d=_column((14,10,14,10),7); destination.setLayout(d); d.addWidget(_label('▰  Pasta de destino','ConverterStrong')); dline=_row(spacing=7); self.destination=_label('','DestinationPath'); dline.addWidget(self.destination,1); change=_button('Alterar…','folder'); change.clicked.connect(self.choose_destination); dline.addWidget(change); open_folder=_button('Abrir pasta','external'); open_folder.clicked.connect(self.open_destination); dline.addWidget(open_folder); d.addLayout(dline); footer.addWidget(destination,3)
        summary=QFrame(); summary.setObjectName('ConverterFooter'); s=_column((14,10,14,10),5); summary.setLayout(s); s.addWidget(_label('▤  Resumo da conversão','ConverterStrong')); self.summary=_label('Nenhum arquivo adicionado','Muted'); self.summary.setWordWrap(True); s.addWidget(self.summary); self.total_progress=QProgressBar(); self.total_progress.setRange(0,100); s.addWidget(self.total_progress); footer.addWidget(summary,2)
        action=QFrame(); action.setObjectName('ConverterAction'); a=_column((10,8,10,8),3); action.setLayout(a); self.convert=_button('Selecione os arquivos','convert','ConverterPrimary'); self.convert.clicked.connect(self.convert_all); a.addWidget(self.convert); self.cancel=_button('Cancelar fila','close'); self.cancel.clicked.connect(self.queue.cancel_all); self.cancel.hide(); a.addWidget(self.cancel); footer.addWidget(action,2); root.addLayout(footer); self._restore_settings(); self._update_summary()
    def _restore_settings(self):
        config=self.storage.config; self.global_format=config.get('converter_format','MP3'); self.global_quality=config.get('converter_quality','Equilibrado')
        if self.global_format not in self.formats: self.global_format=self.formats[0] if self.formats else ''
        if self.global_format in self.format_buttons: self.format_buttons[self.global_format].setChecked(True)
        if self.global_quality in self.quality_buttons: self.quality_buttons[self.global_quality].setChecked(True)
        self.resolution.setCurrentText(config.get('converter_resolution','Original')); self.bitrate.setCurrentText(config.get('converter_bitrate','192 kbps')); self.keep_aspect.setChecked(bool(config.get('converter_keep_aspect',True))); self.preserve_resolution.setChecked(self.resolution.currentText()=='Original'); self.resolution.setEnabled(not self.preserve_resolution.isChecked())
        self.output_dir=config.get('converter_output_dir') or config.get('output_dir') or str(Path.home()/'Videos'); self._set_destination_text(); self.resolution.currentTextChanged.connect(self._advanced_changed); self.bitrate.currentTextChanged.connect(self._advanced_changed); self.keep_aspect.toggled.connect(self._advanced_changed); self.preserve_resolution.toggled.connect(self._preserve_changed); self._update_advanced_visibility(self.global_format)
    def _save_settings(self,*_): self.storage.config.update(converter_format=self.global_format,converter_quality=self.global_quality,converter_resolution=self.resolution.currentText(),converter_bitrate=self.bitrate.currentText(),converter_keep_aspect=self.keep_aspect.isChecked(),converter_output_dir=self.output_dir); self.storage.save_config()
    def _preserve_changed(self,checked):
        if checked: self.resolution.setCurrentText('Original')
        self.resolution.setEnabled(not checked); self._advanced_changed()
    def _advanced_changed(self,*_):
        for card in self.cards.values():
            if card.is_selected() and card.is_mutable():
                card.resolution=self.resolution.currentText(); card.bitrate=self.bitrate.currentText(); card.keep_aspect=self.keep_aspect.isChecked()
        self._save_settings()
    def _update_advanced_visibility(self,value):
        video=value in VIDEO_OUTPUTS; lossless=value in {'WAV','FLAC'}
        for widget in (self.resolution_label,self.resolution,self.preserve_resolution,self.keep_aspect): widget.setVisible(video)
        self.bitrate_label.setVisible(not lossless); self.bitrate.setVisible(not lossless)
        for button in self.quality_buttons.values(): button.setEnabled(not lossless)
    def _toggle_advanced(self,checked): self.advanced.setVisible(checked)
    def choose_files(self):
        patterns=' '.join(f'*{suffix}' for suffix in sorted(SUPPORTED_INPUTS)); paths,_=QFileDialog.getOpenFileNames(self,'Adicionar mídias','',f'Mídias ({patterns});;Todos os arquivos (*.*)'); self.add_paths(paths)
    def choose_folder(self):
        folder=QFileDialog.getExistingDirectory(self,'Adicionar pasta')
        if folder: self.add_paths([str(path) for path in Path(folder).iterdir() if path.is_file()])
    def choose_destination(self):
        folder=QFileDialog.getExistingDirectory(self,'Pasta de destino',self.output_dir)
        if folder: self.output_dir=folder; self._set_destination_text(); self._save_settings()
    def _set_destination_text(self): self.destination.setText(self.output_dir); self.destination.setToolTip(self.output_dir)
    def open_destination(self):
        path=Path(self.output_dir); path.mkdir(parents=True,exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    def add_paths(self,paths):
        expanded=[]
        for raw in paths:
            path=Path(raw); expanded.extend([item for item in path.iterdir() if item.is_file()] if path.is_dir() else [path])
        unsupported=0
        for path in expanded:
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_INPUTS: unsupported+=1; continue
            key=str(path.resolve())
            if key in self.cards: continue
            card=ConversionCard(key,self.formats); card.quality=self.global_quality; card.resolution=self.resolution.currentText(); card.bitrate=self.bitrate.currentText(); card.keep_aspect=self.keep_aspect.isChecked(); card.selection_clicked.connect(self._selection_clicked); card.remove_requested.connect(self.remove_path); card.cancel_requested.connect(self.cancel_path); card.individual_requested.connect(self.convert_individual); card.settings_requested.connect(self.edit_card_settings); card.format_changed.connect(self._card_format_changed); self.cards[key]=card; self.list.insertWidget(self.list.count()-1,card); self._probe(key)
        if unsupported: QMessageBox.information(self,'Arquivos ignorados',f'{unsupported} arquivo(s) não são mídias compatíveis.')
        self._update_summary()
    def _probe(self,path):
        card=self.cards.get(path)
        if not card or not self.ffmpeg: return
        card.state='Analisando'; card.status.setText('Analisando arquivo…'); card.progress.setRange(0,0); worker=ProbeThread(path,self.ffmpeg,self); self.probes.append(worker); worker.ready.connect(self._probe_ready); worker.failed.connect(self._probe_failed); worker.finished.connect(lambda w=worker:self._probe_done(w)); worker.start()
    def _probe_done(self,worker):
        if worker in self.probes: self.probes.remove(worker)
        worker.deleteLater()
    def _probe_ready(self,path,media):
        card=self.cards.get(path)
        if not card: return
        valid=[name for name in self.formats if (name in VIDEO_OUTPUTS and media.has_video) or (name in AUDIO_OUTPUTS and media.has_audio)]
        if not valid: card.set_failed('Nenhuma conversão compatível.'); card.set_selected(False)
        else:
            preferred=self.global_format if self.global_format in valid else valid[0]; card.set_media(media,valid,preferred)
            if self.global_format not in valid: card.set_selected(False); card.status.setText(f'{self.global_format} incompatível; usando {preferred}'); card.status.setStyleSheet(f'color:{RED};')
        self._update_summary()
    def _probe_failed(self,path,message):
        card=self.cards.get(path)
        if card: card.set_failed('Não foi possível analisar o arquivo.',message); card.set_selected(False)
        self._update_summary()
    def _selection_clicked(self,card,modifiers):
        card.set_selected(card.is_selected())
        ordered=list(self.cards.values())
        if modifiers & Qt.KeyboardModifier.ShiftModifier and self.selection_anchor in ordered:
            a,b=ordered.index(self.selection_anchor),ordered.index(card); value=self.selection_anchor.is_selected()
            for item in ordered[min(a,b):max(a,b)+1]:
                if item.is_mutable() and item.media: item.set_selected(value)
        else: self.selection_anchor=card
        self._update_summary()
    def select_all(self):
        for card in self.cards.values():
            if card.media and card.is_mutable(): card.set_selected(True)
        self._update_summary()
    def select_none(self):
        for card in self.cards.values():
            if card.is_mutable(): card.set_selected(False)
        self.selection_anchor=None; self._update_summary()
    def invert_selection(self):
        for card in self.cards.values():
            if card.media and card.is_mutable(): card.set_selected(not card.is_selected())
        self._update_summary()
    def remove_selected(self):
        for card in list(self.cards.values()):
            if card.is_selected() and card.is_mutable(): self.remove_path(card.path)
    def clear_list(self):
        for card in list(self.cards.values()):
            if card.is_mutable(): self.remove_path(card.path)
    def apply_global_format(self,value):
        self.global_format=value; incompatible=0; self._update_advanced_visibility(value)
        for card in self.cards.values():
            if not card.is_selected() or not card.is_mutable(): continue
            if value in card.valid_formats: card.format.setCurrentText(value); card.status.setText('Aguardando'); card.status.setStyleSheet('')
            elif card.media: card.set_selected(False); card.status.setText(f'{value} incompatível com este arquivo'); card.status.setStyleSheet(f'color:{RED};'); incompatible+=1
        self._save_settings(); self._update_summary()
        if incompatible: self.summary.setText(self.summary.text()+f'  •  {incompatible} incompatível(is) desmarcado(s)')
    def apply_global_quality(self,value):
        self.global_quality=value
        for card in self.cards.values():
            if card.is_selected() and card.is_mutable(): card.quality=value
        self._save_settings(); self._update_summary()
    def _card_format_changed(self,card,value): card.status.setToolTip('Mantém vídeo e áudio' if value in VIDEO_OUTPUTS else 'Extrai ou converte somente o áudio'); self._update_summary()
    def edit_card_settings(self,card):
        if not card.is_mutable(): return
        dialog=CardSettingsDialog(card,self)
        if dialog.exec()==QDialog.DialogCode.Accepted: dialog.apply(); card.status.setText('Configuração individual aplicada')
    def remove_path(self,path):
        card=self.cards.get(str(Path(path).resolve()))
        if not card or card.state=='Convertendo': return
        if card.state=='Na fila': self.queue.remove_pending(card.task_id)
        self.cards.pop(card.path,None); self.list.removeWidget(card); card.deleteLater(); self._update_summary()
    def cancel_path(self,path):
        card=self.cards.get(str(Path(path).resolve()))
        if card and self.queue.current and self.queue.current.id==card.task_id: self.queue.cancel_current()
    def convert_individual(self,path):
        card=self.cards.get(str(Path(path).resolve()))
        if not card: return
        if card.state=='Concluído' and card.output_path and Path(card.output_path).is_file(): QDesktopServices.openUrl(QUrl.fromLocalFile(card.output_path)); return
        if not card.is_eligible(): return
        task=self._task_for_card(card); card.task_id=task.id; card.queued(); self.cancel.show(); self.busy_changed.emit(True); self.queue.enqueue([task]); self._update_summary()
    def convert_all(self):
        if self.queue.is_active(): return
        selected=[card for card in self.cards.values() if card.is_selected() and card.is_eligible()]
        if not selected: return
        tasks=[]
        for card in selected:
            task=self._task_for_card(card); card.task_id=task.id; card.queued(); tasks.append(task)
        self.cancel.show(); self.convert.setEnabled(False); self.busy_changed.emit(True); self.queue.enqueue(tasks); self._update_summary()
    def _task_for_card(self,card): return ConversionTask(card.path,self.output_dir,ConversionSettings(card.format.currentText(),card.quality,card.resolution,card.keep_aspect,card.bitrate),card.media)
    def _card_for_task(self,task): return self.cards.get(str(Path(task.source).resolve()))
    def _job_started(self,task):
        card=self._card_for_task(task)
        if card: card.start()
    def _job_progress(self,task,values):
        card=self._card_for_task(task)
        if card: card.update_progress(values)
        self._update_total_progress()
    def _job_completed(self,task):
        card=self._card_for_task(task)
        if card: card.complete(task.output_path)
        self.completed_count+=1; self.conversion_completed.emit(task.source,task.output_path); self._update_total_progress()
    def _job_failed(self,task,message):
        card=self._card_for_task(task)
        if card: card.set_failed(message,task.error); card.format.setEnabled(True)
        self.failed_count+=1; self._update_total_progress()
    def _job_cancelled(self,task):
        card=self._card_for_task(task)
        if card: card.cancelled()
        self._update_total_progress()
    def _queue_finished(self): self.cancel.hide(); self.busy_changed.emit(False); self._update_summary()
    def _update_total_progress(self):
        cards=list(self.cards.values()); values=[card.progress.value() for card in cards if card.progress.maximum()==100]; self.total_progress.setValue(int(sum(values)/len(cards)) if cards else 0); self._update_summary()
    def _update_summary(self):
        total=len(self.cards); selected=[card for card in self.cards.values() if card.is_selected() and card.media and card.is_mutable()]; selected_count=len(selected); destinations={card.format.currentText() for card in selected if card.format.currentText()}; waiting=sum(card.state=='Na fila' for card in self.cards.values()); running=sum(card.state=='Convertendo' for card in self.cards.values()); self.files_title.setText(f'Arquivos adicionados ({total})')
        detail=f'{total} arquivo(s) na lista\n{selected_count} selecionado(s)  •  {self.completed_count} concluído(s)  •  {self.failed_count} erro(s)'
        if running or waiting: detail+=f'\nFila: {running} convertendo, {waiting} aguardando'
        elif len(destinations)==1 and selected_count: detail+=f'\nDestino comum: {next(iter(destinations))}'
        self.summary.setText(self.engine_error or detail)
        if not selected_count: caption='Selecione os arquivos'
        elif selected_count==1 and len(destinations)==1: caption=f'Converter 1 arquivo para {next(iter(destinations))}'
        elif selected_count==total and len(destinations)==1: caption=f'Converter todos para {next(iter(destinations))}'
        elif len(destinations)==1: caption=f'Converter {selected_count} selecionados para {next(iter(destinations))}'
        elif selected_count==1: caption='Converter 1 arquivo'
        else: caption=f'Converter {selected_count} selecionados'
        self.convert.setText(caption); self.convert.setEnabled(bool(self.ffmpeg and selected_count and not self.queue.is_active()))
    def is_active(self): return self.queue.is_active() or any(worker.isRunning() for worker in self.probes)
    def shutdown(self):
        self.queue.shutdown()
        for worker in self.probes: worker.wait(2500)
