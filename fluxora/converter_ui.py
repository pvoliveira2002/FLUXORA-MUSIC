"""Conversor de mídia Fluxora 3.2: interface clean integrada ao FFmpeg."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QUrl, QRect
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDragLeaveEvent, QDropEvent, QKeySequence, QShortcut, QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QScrollArea,
    QFileDialog, QComboBox, QCheckBox, QProgressBar, QMessageBox, QDialog,
    QFormLayout, QButtonGroup, QSizePolicy, QSplitter, QLayout,
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
    if image: widget.setIcon(icon(image,'#0A1907' if name in ('Primary','ConverterPrimary','ConverterAdd','ConverterApply') else '#C4D2D5',18))
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
    def __init__(self,card,default_output,parent=None):
        super().__init__(parent); self.card=card; self.default_output=default_output; self.output_dir=card.output_dir
        self.setWindowTitle(f'Opções — {Path(card.path).name}'); self.setMinimumWidth(450)
        root=_column((24,22,24,22),14); self.setLayout(root); root.addWidget(_label('Configurações individuais','Heading'))
        form=QFormLayout(); form.setVerticalSpacing(12); root.addLayout(form)
        self.quality=QComboBox(); self.quality.addItems(QUALITY_PROFILES); self.quality.setCurrentText(card.quality); form.addRow('Qualidade',self.quality)
        self.resolution=QComboBox(); self.resolution.addItems(RESOLUTIONS); self.resolution.setCurrentText(card.resolution); form.addRow('Resolução',self.resolution)
        self.bitrate=QComboBox(); self.bitrate.addItems(BITRATES); self.bitrate.setCurrentText(card.bitrate); form.addRow('Bitrate de áudio',self.bitrate)
        self.keep=QCheckBox('Manter proporção do vídeo'); self.keep.setChecked(card.keep_aspect); form.addRow('',self.keep)
        destination=_row(spacing=7); self.destination=ElideLabel(self.output_dir or f'Padrão: {default_output}'); destination.addWidget(self.destination,1)
        choose=_button('Alterar…','folder'); choose.clicked.connect(self.choose_destination); destination.addWidget(choose); form.addRow('Pasta exclusiva',destination)
        target=card.format.currentText(); self.resolution.setEnabled(target in VIDEO_OUTPUTS); self.keep.setEnabled(target in VIDEO_OUTPUTS)
        self.bitrate.setEnabled(target not in {'WAV','FLAC'}); self.quality.setEnabled(target not in {'WAV','FLAC'})
        actions=_row(spacing=9); actions.addStretch(); cancel=_button('Cancelar'); cancel.clicked.connect(self.reject); actions.addWidget(cancel)
        save=_button('Aplicar','check','Primary'); save.clicked.connect(self.accept); actions.addWidget(save); root.addLayout(actions)
    def choose_destination(self):
        folder=QFileDialog.getExistingDirectory(self,'Pasta deste arquivo',self.output_dir or self.default_output)
        if folder: self.output_dir=folder; self.destination.setText(folder)
    def apply(self):
        self.card.quality=self.quality.currentText(); self.card.resolution=self.resolution.currentText(); self.card.bitrate=self.bitrate.currentText(); self.card.keep_aspect=self.keep.isChecked(); self.card.output_dir=self.output_dir


class ConversionCard(QFrame):
    selection_clicked=Signal(object,object); remove_requested=Signal(str); cancel_requested=Signal(str)
    individual_requested=Signal(str); settings_requested=Signal(object); format_changed=Signal(object,str)
    def __init__(self,path,formats,parent=None):
        super().__init__(parent); self.path=str(Path(path).resolve()); self.media=None; self.state='Analisando'; self.valid_formats=list(formats)
        self.quality='Equilibrado'; self.resolution='Original'; self.bitrate='192 kbps'; self.keep_aspect=True; self.output_path=''; self.output_dir=''; self.task_id=''
        self.setObjectName('ConversionCard'); self.setProperty('batchSelected',True); self.setMinimumHeight(76); self.setMaximumHeight(82)
        outer=_row((10,7,10,7),8); self.setLayout(outer)
        self.select=SelectionBox(); self.select.setObjectName('BatchCheck'); self.select.setChecked(True); self.select.activated.connect(lambda modifiers:self.selection_clicked.emit(self,modifiers)); outer.addWidget(self.select)
        glyph=_label('♫' if Path(path).suffix.lower() not in VIDEO_INPUTS else '▶','MediaGlyph'); glyph.setAlignment(Qt.AlignmentFlag.AlignCenter); glyph.setFixedSize(48,48); outer.addWidget(glyph)
        info=_column(spacing=3); self.title=ElideLabel(Path(path).name); self.title.setObjectName('ConverterStrong'); self.title.setMinimumWidth(110); self.title.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred); info.addWidget(self.title)
        self.details=_label('Lendo informações do arquivo…','Muted'); self.details.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred); info.addWidget(self.details); outer.addLayout(info,4)
        target=_column(spacing=2); target.addWidget(_label('Destino','Subtle')); self.format=QComboBox(); self.format.addItems(formats); self.format.setMinimumWidth(92); self.format.setMaximumWidth(125)
        self.format.currentTextChanged.connect(lambda value:self.format_changed.emit(self,value)); target.addWidget(self.format); outer.addLayout(target,1)
        status_box=_column(spacing=3); self.status=_label('Analisando…','Subtle'); self.status.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred); status_box.addWidget(self.status)
        self.progress=QProgressBar(); self.progress.setRange(0,100); self.progress.hide(); status_box.addWidget(self.progress); self.percent=_label('','Success'); status_box.addWidget(self.percent); outer.addLayout(status_box,2)
        gear=_button('','settings','CompactIcon'); gear.setToolTip('Configurações individuais'); gear.clicked.connect(lambda:self.settings_requested.emit(self)); outer.addWidget(gear)
        self.run=_button('','play','CompactIcon'); self.run.setToolTip('Converter somente este arquivo'); self.run.clicked.connect(lambda:self.individual_requested.emit(self.path)); outer.addWidget(self.run)
        self.remove=_button('','close','CompactIcon'); self.remove.setToolTip('Remover'); self.remove.clicked.connect(self._remove_or_cancel); outer.addWidget(self.remove)
    def is_selected(self): return self.select.isChecked()
    def set_selected(self,value):
        self.select.blockSignals(True); self.select.setChecked(bool(value)); self.select.blockSignals(False); self.setProperty('batchSelected',bool(value)); self.style().unpolish(self); self.style().polish(self)
    def is_mutable(self): return self.state not in {'Na fila','Convertendo'}
    def is_eligible(self): return bool(self.media and self.format.currentText() and self.is_mutable())
    def set_media(self,media:MediaInfo,valid_formats,preferred=''):
        self.media=media; self.valid_formats=list(valid_formats); self.state='Pronto'; self.progress.setRange(0,100); self.progress.setValue(0); self.progress.hide(); self.percent.setText('')
        resolution=f' · {media.width}×{media.height}' if media.has_video and media.width else ''
        self.details.setText(f'{Path(self.path).suffix[1:].upper()}{resolution} · {_duration(media.duration)} · {format_bytes(media.size)}')
        previous=preferred or self.format.currentText(); self.format.blockSignals(True); self.format.clear(); self.format.addItems(valid_formats)
        if previous in valid_formats: self.format.setCurrentText(previous)
        self.format.blockSignals(False); self.status.setText('Aguardando'); self.status.setStyleSheet(''); self.run.setEnabled(bool(valid_formats))
    def set_failed(self,message,details=''):
        self.error_details=details or message; self.state='Falhou'; self.progress.hide(); self.percent.setText(''); self.status.setText(message); self.status.setToolTip(self.error_details); self.status.setStyleSheet(f'color:{RED};'); self.run.setEnabled(True); self.select.setEnabled(True); self.run.setToolTip('Tentar novamente')
    def queued(self):
        self.state='Na fila'; self.status.setText('Na fila'); self.status.setStyleSheet(''); self.progress.hide(); self.percent.setText(''); self.run.setEnabled(False); self.select.setEnabled(False); self.format.setEnabled(False); self.run.setIcon(icon('play','#C4D2D5',18))
    def start(self):
        self.state='Convertendo'; self.status.setText('Convertendo'); self.status.setStyleSheet(''); self.progress.show(); self.run.setEnabled(False); self.format.setEnabled(False); self.remove.setToolTip('Cancelar conversão')
    def update_progress(self,values):
        self.progress.show(); value=values.get('percent',-1)
        if value<0: self.progress.setRange(0,0); self.percent.setText('Convertendo')
        else: self.progress.setRange(0,100); self.progress.setValue(value); self.percent.setText(f'Convertendo · {value}%')
        extras=[]
        if values.get('speed'): extras.append(values['speed'])
        if values.get('eta') is not None: extras.append(f'{_duration(values["eta"])} restante')
        self.status.setText(' · '.join(extras) if extras else 'Em processamento')
    def complete(self,output):
        self.state='Concluído'; self.output_path=output; self.progress.hide(); self.percent.setText(''); self.status.setText('Concluído'); self.status.setStyleSheet(f'color:{GREEN};'); self.format.setEnabled(True); self.select.setEnabled(True); self.run.setEnabled(True); self.run.setIcon(icon('external','#C4D2D5',18)); self.run.setToolTip('Abrir arquivo convertido'); self.remove.setToolTip('Remover')
    def cancelled(self):
        self.state='Cancelado'; self.progress.hide(); self.percent.setText(''); self.status.setText('Cancelado'); self.format.setEnabled(True); self.select.setEnabled(True); self.run.setEnabled(True); self.run.setIcon(icon('play','#C4D2D5',18)); self.run.setToolTip('Converter novamente')
    def _remove_or_cancel(self):
        if self.state=='Convertendo': self.cancel_requested.emit(self.path)
        else: self.remove_requested.emit(self.path)


class ConverterPage(QWidget):
    conversion_completed=Signal(str,str); busy_changed=Signal(bool)
    def __init__(self,storage,parent=None):
        super().__init__(parent); self.storage=storage; self.cards={}; self.probes=[]; self.selection_anchor=None; self.completed_count=0; self.failed_count=0; self.global_format='MP3'; self.global_quality='Equilibrado'; self.setAcceptDrops(True)
        try:
            self.ffmpeg=find_ffmpeg(storage.config.get('ffmpeg_path')); self.encoders=detect_encoders(self.ffmpeg); self.formats=available_formats(self.encoders); self.engine_error='' if self.formats else 'O FFmpeg encontrado não possui encoders compatíveis.'
        except Exception as exc: self.ffmpeg=''; self.encoders=set(); self.formats=[]; self.engine_error=str(exc)
        self.queue=ConversionQueue(self.ffmpeg,self.encoders,self); self.queue.job_started.connect(self._job_started); self.queue.job_progress.connect(self._job_progress); self.queue.job_completed.connect(self._job_completed); self.queue.job_failed.connect(self._job_failed); self.queue.job_cancelled.connect(self._job_cancelled); self.queue.queue_finished.connect(self._queue_finished)
        self._build(); self.select_all_shortcut=QShortcut(QKeySequence.StandardKey.SelectAll,self); self.select_all_shortcut.activated.connect(self.select_all)
    def _build(self):
        root=_column(spacing=10); root.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint); self.setLayout(root); self.setMinimumSize(0,0)
        heading=_row(spacing=9); emblem=_label('⟳','ConverterEmblem'); emblem.setAlignment(Qt.AlignmentFlag.AlignCenter); heading.addWidget(emblem)
        titles=_column(spacing=0); titles.addWidget(_label('Conversor de mídia','ConverterTitle')); titles.addWidget(_label('Converta vídeos e áudios de forma simples.','Muted')); heading.addLayout(titles,1); root.addLayout(heading)
        imports=_row(spacing=10); add_files=_button('Adicionar arquivos','plus','ConverterAdd'); add_files.clicked.connect(self.choose_files); imports.addWidget(add_files,1)
        add_folder=_button('Adicionar pasta','folder','ConverterImport'); add_folder.clicked.connect(self.choose_folder); imports.addWidget(add_folder,1); root.addLayout(imports)
        self.drop_feedback=_label('Solte os arquivos para adicioná-los','ConverterDropFeedback'); self.drop_feedback.setAlignment(Qt.AlignmentFlag.AlignCenter); self.drop_feedback.hide(); root.addWidget(self.drop_feedback)
        self.compact_settings_toggle=_button('Configurações: MP3 · Equilibrado','settings','CompactSettingsToggle'); self.compact_settings_toggle.clicked.connect(self._toggle_compact_settings); self.compact_settings_toggle.hide(); root.addWidget(self.compact_settings_toggle)
        self.workspace=QSplitter(Qt.Orientation.Horizontal); self.workspace.setObjectName('ConverterWorkspace'); self.workspace.setChildrenCollapsible(False)
        list_panel=QFrame(); list_panel.setObjectName('ConverterListPanel'); list_panel.setMinimumWidth(280); panel=_column((10,9,10,9),7); list_panel.setLayout(panel)
        tools=_row(spacing=5); self.files_title=_label('Arquivos adicionados (0)','Section'); tools.addWidget(self.files_title); tools.addStretch()
        for caption,handler in [('Todos',self.select_all),('Nenhum',self.select_none),('Inverter',self.invert_selection),('Remover',self.remove_selected),('Limpar',self.clear_list)]:
            button=_button(caption,'trash' if caption in ('Remover','Limpar') else 'check','ConverterTool'); button.clicked.connect(handler); tools.addWidget(button)
        panel.addLayout(tools); self.scroll=QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.contents=QWidget(); self.contents.setMinimumWidth(0); self.list=_column((0,0,2,0),6); self.contents.setLayout(self.list)
        self.empty=_label('Adicione arquivos ou uma pasta para começar.\nVocê também pode arrastar mídias para esta tela.','ConverterEmpty'); self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter); self.list.addWidget(self.empty,1); self.list.addStretch()
        self.scroll.setWidget(self.contents); panel.addWidget(self.scroll,1); self.workspace.addWidget(list_panel)
        self.settings_panel=QFrame(); self.settings_panel.setObjectName('ConverterSettings'); self.settings_panel.setMinimumWidth(245); settings=_column((14,13,14,13),9); self.settings_panel.setLayout(settings)
        settings.addWidget(_label('Configurações de conversão','Section')); settings.addWidget(_label('Tipo de saída','Subtle'))
        categories=_row(spacing=6); self.category_group=QButtonGroup(self); self.category_group.setExclusive(True)
        self.audio_category=_button('Áudio','music','CategoryChoice'); self.video_category=_button('Vídeo','film','CategoryChoice')
        for button,value in ((self.audio_category,'audio'),(self.video_category,'video')):
            button.setCheckable(True); button.clicked.connect(lambda checked=False,kind=value:self._category_changed(kind)); self.category_group.addButton(button); categories.addWidget(button)
        settings.addLayout(categories); settings.addWidget(_label('Formato de saída','Subtle')); self.global_format_combo=QComboBox(); self.global_format_combo.setObjectName('ConverterFormatSelect'); self.global_format_combo.currentTextChanged.connect(self._pending_changed); settings.addWidget(self.global_format_combo)
        settings.addWidget(_label('Qualidade','Subtle')); self.global_quality_combo=QComboBox(); self.global_quality_combo.addItems(QUALITY_PROFILES); self.global_quality_combo.currentTextChanged.connect(self._pending_changed); settings.addWidget(self.global_quality_combo)
        self.quality_help=_label('Perfil equilibrado para uso geral.','Muted'); self.quality_help.setWordWrap(True); settings.addWidget(self.quality_help)
        self.advanced_toggle=_button('Opções avançadas','settings','ConverterAdvancedToggle'); self.advanced_toggle.setCheckable(True); self.advanced_toggle.clicked.connect(self._toggle_advanced); settings.addWidget(self.advanced_toggle)
        self.advanced=QFrame(); self.advanced.setObjectName('ConverterAdvanced'); advanced=_column((10,9,10,9),7); self.advanced.setLayout(advanced)
        self.resolution_label=_label('Resolução','Muted'); advanced.addWidget(self.resolution_label); self.resolution=QComboBox(); self.resolution.addItems(RESOLUTIONS); self.resolution.currentTextChanged.connect(self._pending_changed); advanced.addWidget(self.resolution)
        self.bitrate_label=_label('Bitrate de áudio','Muted'); advanced.addWidget(self.bitrate_label); self.bitrate=QComboBox(); self.bitrate.addItems(BITRATES); self.bitrate.currentTextChanged.connect(self._pending_changed); advanced.addWidget(self.bitrate)
        self.preserve_resolution=QCheckBox('Preservar resolução original'); self.preserve_resolution.toggled.connect(self._preserve_changed); advanced.addWidget(self.preserve_resolution)
        self.keep_aspect=QCheckBox('Manter proporção'); self.keep_aspect.toggled.connect(self._pending_changed); advanced.addWidget(self.keep_aspect); self.advanced.hide(); settings.addWidget(self.advanced)
        settings.addStretch(); self.apply_feedback=_label('','Success'); self.apply_feedback.setAlignment(Qt.AlignmentFlag.AlignCenter); settings.addWidget(self.apply_feedback)
        self.apply_settings=_button('Aplicar aos selecionados','check','ConverterApply'); self.apply_settings.clicked.connect(self.apply_pending_settings); settings.addWidget(self.apply_settings)
        self.workspace.addWidget(self.settings_panel); self.workspace.setStretchFactor(0,2); self.workspace.setStretchFactor(1,1); self.workspace.setSizes([700,340]); root.addWidget(self.workspace,1)
        footer=QFrame(); footer.setObjectName('ConverterFixedFooter'); footer_row=_row((12,9,12,9),12); footer.setLayout(footer_row)
        destination=_column(spacing=4); destination.addWidget(_label('Pasta de destino','ConverterStrong')); dline=_row(spacing=6); self.destination=ElideLabel(''); self.destination.setObjectName('DestinationPath'); dline.addWidget(self.destination,1)
        change=_button('Alterar…','folder','FooterButton'); change.clicked.connect(self.choose_destination); dline.addWidget(change); open_folder=_button('Abrir','external','FooterButton'); open_folder.clicked.connect(self.open_destination); dline.addWidget(open_folder); destination.addLayout(dline); footer_row.addLayout(destination,3)
        summary_box=_column(spacing=4); summary_box.addWidget(_label('Resumo','ConverterStrong')); self.summary=_label('Nenhum arquivo adicionado','Muted'); self.summary.setWordWrap(True); summary_box.addWidget(self.summary); self.total_progress=QProgressBar(); self.total_progress.setRange(0,100); self.total_progress.hide(); summary_box.addWidget(self.total_progress); footer_row.addLayout(summary_box,2)
        actions=_column(spacing=4); self.convert=_button('Selecione os arquivos','convert','ConverterPrimary'); self.convert.clicked.connect(self.convert_all); actions.addWidget(self.convert); self.cancel=_button('Cancelar fila','close','FooterButton'); self.cancel.clicked.connect(self.queue.cancel_all); self.cancel.hide(); actions.addWidget(self.cancel); footer_row.addLayout(actions,2); root.addWidget(footer)
        self._restore_settings(); self._update_summary()
    def _restore_settings(self):
        config=self.storage.config; self.global_format=config.get('converter_format','MP3'); self.global_quality=config.get('converter_quality','Equilibrado')
        if self.global_format not in self.formats: self.global_format=self.formats[0] if self.formats else ''
        self.resolution.setCurrentText(config.get('converter_resolution','Original')); self.bitrate.setCurrentText(config.get('converter_bitrate','192 kbps')); self.keep_aspect.setChecked(bool(config.get('converter_keep_aspect',True))); self.preserve_resolution.setChecked(self.resolution.currentText()=='Original'); self.resolution.setEnabled(not self.preserve_resolution.isChecked())
        category='video' if self.global_format in VIDEO_OUTPUTS else 'audio'; (self.video_category if category=='video' else self.audio_category).setChecked(True); self._populate_format_combo(category,self.global_format)
        self.global_quality_combo.setCurrentText(self.global_quality); self._update_quality_help(); self._update_advanced_visibility(self.global_format)
        self.output_dir=config.get('converter_output_dir') or config.get('output_dir') or str(Path.home()/'Videos'); self._set_destination_text()
    def _save_settings(self):
        self.storage.config.update(converter_format=self.global_format,converter_quality=self.global_quality,converter_resolution=self.resolution.currentText(),converter_bitrate=self.bitrate.currentText(),converter_keep_aspect=self.keep_aspect.isChecked(),converter_output_dir=self.output_dir); self.storage.save_config()
    def _populate_format_combo(self,category,preferred=''):
        options=[name for name in self.formats if name in (AUDIO_OUTPUTS if category=='audio' else VIDEO_OUTPUTS)]; self.global_format_combo.blockSignals(True); self.global_format_combo.clear(); self.global_format_combo.addItems(options)
        if preferred in options: self.global_format_combo.setCurrentText(preferred)
        self.global_format_combo.blockSignals(False)
    def _category_changed(self,category): self._populate_format_combo(category); self._pending_changed()
    def _pending_changed(self,*_):
        value=self.global_format_combo.currentText(); self._update_advanced_visibility(value); self._update_quality_help(); self.apply_feedback.clear(); self.compact_settings_toggle.setText(f'Configurações: {value or "—"} · {self.global_quality_combo.currentText()}'); self._update_summary()
    def _update_quality_help(self):
        descriptions={'Equilibrado':'Bom equilíbrio entre qualidade e tamanho.','Alta qualidade':'Mais definição e arquivo maior.','Compacto':'Menor tamanho para compartilhar.'}; self.quality_help.setText(descriptions.get(self.global_quality_combo.currentText(),''))
    def _preserve_changed(self,checked):
        if checked: self.resolution.setCurrentText('Original')
        self.resolution.setEnabled(not checked); self._pending_changed()
    def _update_advanced_visibility(self,value):
        video=value in VIDEO_OUTPUTS; lossless=value in {'WAV','FLAC'}
        for widget in (self.resolution_label,self.resolution,self.preserve_resolution,self.keep_aspect): widget.setVisible(video)
        self.bitrate_label.setVisible(not lossless); self.bitrate.setVisible(not lossless); self.global_quality_combo.setEnabled(not lossless)
    def _toggle_advanced(self,checked): self.advanced.setVisible(checked)
    def _toggle_compact_settings(self):
        self.settings_panel.setVisible(not self.settings_panel.isVisible())
        self.compact_settings_toggle.setProperty('expanded',self.settings_panel.isVisible()); self.compact_settings_toggle.style().unpolish(self.compact_settings_toggle); self.compact_settings_toggle.style().polish(self.compact_settings_toggle)
    def apply_pending_settings(self):
        selected=[card for card in self.cards.values() if card.is_selected() and card.is_mutable() and card.media]
        if not selected: return
        value=self.global_format_combo.currentText(); quality=self.global_quality_combo.currentText(); incompatible=0; applied=0; self.global_format=value; self.global_quality=quality
        for card in selected:
            if value not in card.valid_formats:
                card.set_selected(False); card.status.setText(f'{value} incompatível com este arquivo'); card.status.setStyleSheet(f'color:{RED};'); incompatible+=1; continue
            card.format.setCurrentText(value); card.quality=quality; card.resolution=self.resolution.currentText(); card.bitrate=self.bitrate.currentText(); card.keep_aspect=self.keep_aspect.isChecked(); card.status.setText('Configuração aplicada'); card.status.setStyleSheet(''); applied+=1
        self.apply_feedback.setText(f'Aplicado a {applied} arquivo(s).'+(f' {incompatible} incompatível(is).' if incompatible else '')); self._save_settings(); self._update_summary()
        if self.width()<900: self.settings_panel.hide(); self.compact_settings_toggle.setProperty('expanded',False)
    def apply_global_format(self,value):
        category='video' if value in VIDEO_OUTPUTS else 'audio'; (self.video_category if category=='video' else self.audio_category).setChecked(True); self._populate_format_combo(category,value); self.global_format=value; self.apply_pending_settings()
    def apply_global_quality(self,value):
        self.global_quality_combo.setCurrentText(value); self.global_quality=value
        for card in self.cards.values():
            if card.is_selected() and card.is_mutable(): card.quality=value
        self._save_settings(); self._update_summary()
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
    def dragEnterEvent(self,event:QDragEnterEvent):
        if event.mimeData().hasUrls(): self.drop_feedback.show(); event.acceptProposedAction()
    def dragLeaveEvent(self,event:QDragLeaveEvent): self.drop_feedback.hide(); event.accept()
    def dropEvent(self,event:QDropEvent):
        self.drop_feedback.hide(); self.add_paths([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]); event.acceptProposedAction()
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
        card.state='Analisando'; card.status.setText('Analisando arquivo…'); worker=ProbeThread(path,self.ffmpeg,self); self.probes.append(worker); worker.ready.connect(self._probe_ready); worker.failed.connect(self._probe_failed); worker.finished.connect(lambda w=worker:self._probe_done(w)); worker.start()
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
        card.set_selected(card.is_selected()); ordered=list(self.cards.values())
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
    def _card_format_changed(self,card,value): card.status.setToolTip('Mantém vídeo e áudio' if value in VIDEO_OUTPUTS else 'Extrai ou converte somente o áudio'); self._update_summary()
    def edit_card_settings(self,card):
        if not card.is_mutable(): return
        dialog=CardSettingsDialog(card,self.output_dir,self)
        if dialog.exec()==QDialog.DialogCode.Accepted: dialog.apply(); card.status.setText('Configuração individual aplicada'); self._update_summary()
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
        task=self._task_for_card(card); card.task_id=task.id; card.queued(); self.cancel.show(); self.total_progress.show(); self.busy_changed.emit(True); self.queue.enqueue([task]); self._update_summary()
    def convert_all(self):
        if self.queue.is_active(): return
        selected=[card for card in self.cards.values() if card.is_selected() and card.is_eligible()]
        if not selected: return
        tasks=[]
        for card in selected:
            task=self._task_for_card(card); card.task_id=task.id; card.queued(); tasks.append(task)
        self.cancel.show(); self.total_progress.show(); self.convert.setEnabled(False); self.busy_changed.emit(True); self.queue.enqueue(tasks); self._update_summary()
    def _task_for_card(self,card): return ConversionTask(card.path,card.output_dir or self.output_dir,ConversionSettings(card.format.currentText(),card.quality,card.resolution,card.keep_aspect,card.bitrate),card.media)
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
    def _queue_finished(self): self.cancel.hide(); self.total_progress.hide(); self.busy_changed.emit(False); self._update_summary()
    def _update_total_progress(self):
        active=[card for card in self.cards.values() if card.state in {'Na fila','Convertendo','Concluído','Falhou'}]; values=[card.progress.value() if card.state=='Convertendo' else (100 if card.state=='Concluído' else 0) for card in active]; self.total_progress.setValue(int(sum(values)/len(values)) if values else 0); self._update_summary()
    def _update_summary(self):
        total=len(self.cards); selected=[card for card in self.cards.values() if card.is_selected() and card.media and card.is_mutable()]; selected_count=len(selected); destinations={card.format.currentText() for card in selected if card.format.currentText()}; waiting=sum(card.state=='Na fila' for card in self.cards.values()); running=sum(card.state=='Convertendo' for card in self.cards.values()); self.files_title.setText(f'Arquivos adicionados ({total})'); self.empty.setVisible(not total)
        detail=f'{self.completed_count} concluído(s) · {self.failed_count} erro(s) · {running+waiting} na fila' if running or waiting else f'{total} arquivo(s) · {selected_count} selecionado(s)'
        self.summary.setText(self.engine_error or detail); self.apply_settings.setText(f'Aplicar aos {selected_count} selecionados' if selected_count else 'Aplicar aos selecionados'); self.apply_settings.setEnabled(bool(selected_count and self.global_format_combo.currentText()))
        if not selected_count: caption='Selecione os arquivos'
        elif selected_count==1: caption='Converter 1 arquivo'
        elif selected_count==total and len(destinations)==1: caption=f'Converter todos para {next(iter(destinations))}'
        else: caption=f'Converter {selected_count} selecionados'
        self.convert.setText(caption); self.convert.setEnabled(bool(self.ffmpeg and selected_count and not self.queue.is_active()))
    def resizeEvent(self,event):
        orientation=Qt.Orientation.Vertical if self.width()<900 else Qt.Orientation.Horizontal
        if self.workspace.orientation()!=orientation:
            self.workspace.setOrientation(orientation)
            if orientation==Qt.Orientation.Vertical:
                self.compact_settings_toggle.show(); self.settings_panel.hide(); self.workspace.setSizes([max(400,self.height()-200),260])
            else:
                self.compact_settings_toggle.hide(); self.settings_panel.show(); self.workspace.setSizes([max(560,self.width()*2//3),320])
        super().resizeEvent(event)
    def is_active(self): return self.queue.is_active() or any(worker.isRunning() for worker in self.probes)
    def shutdown(self):
        self.queue.shutdown()
        for worker in self.probes: worker.wait(2500)
