"""Fluxora 3.0: interface Qt desenhada a partir do conceito aprovado."""
from __future__ import annotations
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import Qt, QSize, QUrl, QTimer, QPoint, QRect, QItemSelectionModel, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui import QPixmap, QIcon, QDesktopServices, QCloseEvent, QColor, QPainter, QLinearGradient, QPen
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton, QHBoxLayout,
    QVBoxLayout, QGridLayout, QLineEdit, QComboBox, QProgressBar, QScrollArea,
    QStackedWidget, QFileDialog, QDialog, QFormLayout, QSpinBox, QCheckBox,
    QMessageBox, QSystemTrayIcon, QMenu, QSizePolicy, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QStyledItemDelegate,
    QStyleOptionViewItem,
)
from .theme import BG, SIDEBAR, SURFACE, SURFACE2, GREEN, TEXT, MUTED, BORDER, SUBTLE, RED
from .icons import icon
from .storage import Storage
from .converter_ui import ConverterPage
from .engine import (
    Analyzer, Downloader, ImageFetcher, VIDEO_QUALITIES, AUDIO_QUALITIES, BROWSERS,
    is_valid_url, is_playlist_url, format_bytes,
)


def column(margins=(0,0,0,0), spacing=0):
    lay = QVBoxLayout(); lay.setContentsMargins(*margins); lay.setSpacing(spacing); return lay

def row(margins=(0,0,0,0), spacing=0):
    lay = QHBoxLayout(); lay.setContentsMargins(*margins); lay.setSpacing(spacing); return lay

def text(value, name=None, wrap=False):
    lbl = QLabel(str(value)); lbl.setObjectName(name or ''); lbl.setWordWrap(wrap); return lbl

def frame(name='Card'):
    f = QFrame(); f.setObjectName(name); return f

def push(title, kind=None, name=None, color=None):
    btn = QPushButton(title)
    if kind: btn.setIcon(icon(kind, color or ('#0A1907' if name=='Primary' else '#B4C6C9'), 18))
    if name: btn.setObjectName(name)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn

def duration(seconds):
    if not seconds: return '—'
    sec = int(seconds)
    return f'{sec//3600}:{sec//60%60:02d}:{sec%60:02d}' if sec>=3600 else f'{sec//60}:{sec%60:02d}'


def thumb_placeholder(w=160, h=91):
    pix = QPixmap(w,h)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    g = QLinearGradient(0,0,w,h); g.setColorAt(0,QColor('#214038')); g.setColorAt(.7,QColor('#152B32')); g.setColorAt(1,QColor('#283D20'))
    p.fillRect(0,0,w,h,g)
    p.setPen(QColor(GREEN)); font=p.font(); font.setPointSize(23); font.setBold(True); p.setFont(font)
    p.drawText(pix.rect(),Qt.AlignmentFlag.AlignCenter,'▶')
    p.end(); return pix


class Cover(QLabel):
    def __init__(self, w=142, h=81, parent=None):
        super().__init__(parent); self.setFixedSize(w,h)
        self.original = thumb_placeholder(w,h)
        self.setPixmap(self.original)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet('border-radius:8px; background: #1B3134;')

    def set_image(self, img):
        if isinstance(img,bytes):
            pix = QPixmap()
            if not pix.loadFromData(img): return
        else: pix = img
        if pix.isNull(): return
        self.original=pix
        self._rescale()

    def _rescale(self):
        self.setPixmap(self.original.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                            Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event):
        self._rescale()
        super().resizeEvent(event)


class PlaylistCheckDelegate(QStyledItemDelegate):
    """Desenha indicadores checkable grandes e consistentes no tema escuro."""
    SIZE = 21

    def checkbox_rect(self, option):
        rect=QRect(0,0,self.SIZE,self.SIZE); rect.moveCenter(option.rect.center()); return rect

    def paint(self,painter,option,index):
        if index.column()!=0:
            super().paint(painter,option,index); return
        clean=QStyleOptionViewItem(option)
        clean.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
        super().paint(painter,clean,index)
        box=self.checkbox_rect(option); state=index.data(Qt.ItemDataRole.CheckStateRole)
        checked=state in (Qt.CheckState.Checked,Qt.CheckState.Checked.value)
        painter.save(); painter.setRenderHint(QPainter.RenderHint.Antialiasing,True)
        painter.setPen(QPen(QColor(GREEN if checked else '#A9BBC0'),1.6))
        painter.setBrush(QColor(GREEN if checked else '#101B1F'))
        painter.drawRoundedRect(box,4,4)
        if checked:
            painter.setPen(QPen(QColor('#0A1607'),2.6,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
            painter.drawLine(box.left()+5,box.center().y(),box.left()+9,box.bottom()-5)
            painter.drawLine(box.left()+9,box.bottom()-5,box.right()-4,box.top()+5)
        painter.restore()

    def editorEvent(self,event,model,option,index):
        return False


class PlaylistTable(QTableWidget):
    """Tabela com seleção de linhas no padrão Windows e marcação em lote."""
    checks_changed=Signal()

    def __init__(self,rows,columns,parent=None):
        super().__init__(rows,columns,parent)
        self.check_delegate=PlaylistCheckDelegate(self); self.setItemDelegateForColumn(0,self.check_delegate)
        self.check_anchor=None; self.selection_anchor=None

    def reset_anchors(self):
        self.check_anchor=None; self.selection_anchor=None; self.clearSelection()

    def visible_rows(self):
        return [row for row in range(self.rowCount()) if not self.isRowHidden(row)]

    def _between_visible(self,first,last):
        visible=self.visible_rows()
        if first not in visible or last not in visible: return [last]
        a,b=visible.index(first),visible.index(last)
        return visible[min(a,b):max(a,b)+1]

    def _set_checked(self,rows,state):
        self.blockSignals(True)
        for row in rows:
            item=self.item(row,0)
            if item: item.setCheckState(state)
        self.blockSignals(False); self.viewport().update(); self.checks_changed.emit()

    def _select_rows(self,rows,clear=True):
        selection=self.selectionModel()
        if clear: selection.clearSelection()
        flags=QItemSelectionModel.SelectionFlag.Select|QItemSelectionModel.SelectionFlag.Rows
        for row in rows: selection.select(self.model().index(row,0),flags)

    def select_visible_rows(self):
        self._select_rows(self.visible_rows(),True)

    def mousePressEvent(self,event):
        index=self.indexAt(event.position().toPoint())
        modifiers=event.modifiers()
        if index.isValid() and index.column()==0:
            option=QStyleOptionViewItem(); option.rect=self.visualRect(index)
            if self.check_delegate.checkbox_rect(option).contains(event.position().toPoint()):
                row=index.row()
                if (modifiers & Qt.KeyboardModifier.ShiftModifier and self.check_anchor is not None
                        and self.check_anchor in self.visible_rows()):
                    rows=self._between_visible(self.check_anchor,row)
                    anchor_item=self.item(self.check_anchor,0)
                    state=anchor_item.checkState() if anchor_item else Qt.CheckState.Checked
                    self._set_checked(rows,state); self._select_rows(rows,False)
                else:
                    item=self.item(row,0)
                    state=Qt.CheckState.Unchecked if item.checkState()==Qt.CheckState.Checked else Qt.CheckState.Checked
                    self._set_checked([row],state); self.check_anchor=row
                event.accept(); return
        if index.isValid() and modifiers & Qt.KeyboardModifier.ShiftModifier:
            anchor=self.selection_anchor if self.selection_anchor in self.visible_rows() else index.row()
            rows=self._between_visible(anchor,index.row())
            self._select_rows(rows,not bool(modifiers & Qt.KeyboardModifier.ControlModifier))
            self.selection_anchor=anchor; self.setCurrentIndex(index); event.accept(); return
        if index.isValid(): self.selection_anchor=index.row()
        super().mousePressEvent(event)

    def keyPressEvent(self,event):
        if event.key()==Qt.Key.Key_A and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.select_visible_rows(); event.accept(); return
        if event.key()==Qt.Key.Key_Space:
            rows=sorted({index.row() for index in self.selectionModel().selectedRows() if not self.isRowHidden(index.row())})
            if rows:
                all_checked=all(self.item(row,0).checkState()==Qt.CheckState.Checked for row in rows)
                self._set_checked(rows,Qt.CheckState.Unchecked if all_checked else Qt.CheckState.Checked)
                self.check_anchor=rows[0]
                event.accept(); return
        super().keyPressEvent(event)


class DownloadCard(QFrame):
    """Uma tarefa visível durante toda a sessão do aplicativo."""
    def __init__(self, title, media, quality, cancel=None, remove=None):
        super().__init__(); self.setObjectName('Card')
        self.setMinimumHeight(112)
        self.state = 'Na fila'; self.title = title
        outer=row((11,10,11,10),12); self.setLayout(outer)
        self.cover=Cover(144,84); outer.addWidget(self.cover)
        middle=column(spacing=5); outer.addLayout(middle,1)
        self.label=text(title); self.label.setStyleSheet('font-weight:700; font-size:13px;');
        self.label.setMaximumHeight(21); middle.addWidget(self.label)
        tags=row(spacing=6)
        for item in [media,quality]:
            tag=text(item,'Tag'); tags.addWidget(tag)
        tags.addStretch(1); middle.addLayout(tags)
        self.progress=QProgressBar(); self.progress.setRange(0,100); self.progress.setValue(0); middle.addWidget(self.progress)
        self.progress_animation=QPropertyAnimation(self.progress,b'value',self)
        self.progress_animation.setDuration(220)
        self.progress_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.detail=text('Aguardando na fila...','Muted'); middle.addWidget(self.detail)
        controls=column(spacing=8); controls.addStretch(1)
        self.percent=text('0%','Success'); self.percent.setAlignment(Qt.AlignmentFlag.AlignRight); controls.addWidget(self.percent)
        self.cancel_btn=push('','close', 'IconButton'); self.cancel_btn.setToolTip('Cancelar download')
        if cancel: self.cancel_btn.clicked.connect(cancel)
        else: self.cancel_btn.setEnabled(False)
        controls.addWidget(self.cancel_btn)
        self.remove_btn=push('','close','IconButton'); self.remove_btn.setToolTip('Remover da lista desta sessão')
        if remove: self.remove_btn.clicked.connect(remove)
        else: self.remove_btn.setEnabled(False)
        self.remove_btn.setVisible(False); controls.addWidget(self.remove_btn)
        controls.addStretch(1)
        outer.addLayout(controls)

    def start(self):
        self.state='Baixando'; self.detail.setText('Preparando download...')
        self.cancel_btn.setEnabled(True)

    def update_progress(self,data):
        self.state='Baixando'
        if data.get('title') and (self.title.startswith('Preparando') or self.title.startswith('Novo download')):
            self.title=data['title']; self.label.setText(self.title)
        percent = int(data.get('percent',0))
        self.progress_animation.stop()
        self.progress_animation.setStartValue(self.progress.value())
        self.progress_animation.setEndValue(percent)
        self.progress_animation.start()
        self.percent.setText(f'{percent}%')
        detail=data.get('stage') or 'Baixando'
        if data.get('speed'): detail += '  •  '+data['speed']
        if data.get('eta') is not None: detail += f'  •  Restam {duration(data["eta"])}'
        self.detail.setText(detail)

    def finalize(self, state, message=''):
        self.state=state
        self.progress_animation.stop()
        self.cancel_btn.setEnabled(False); self.cancel_btn.setVisible(False)
        self.remove_btn.setVisible(True); self.remove_btn.setEnabled(True)
        self.detail.setText(message or state)
        if state=='Concluído':
            self.progress.setValue(100); self.percent.setText('✓')
            self.percent.setStyleSheet(f'color:{GREEN}; font-size:19px; font-weight:700;')
        elif state=='Falhou': self.percent.setText('!'); self.percent.setStyleSheet(f'color:{RED}; font-weight:800;')
        elif state=='Cancelado': self.percent.setText('×'); self.percent.setStyleSheet(f'color:{MUTED}; font-weight:800;')


class SettingsDialog(QDialog):
    def __init__(self, storage, parent=None):
        super().__init__(parent); self.storage=storage
        self.setWindowTitle('Configurações do Fluxora'); self.setMinimumWidth(540)
        v=column((27,25,27,25),16); self.setLayout(v)
        heading=text('Configurações','Heading'); v.addWidget(heading)
        v.addWidget(text('Downloads, sessões do navegador e playlists.','Muted'))
        form=QFormLayout(); form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form.setHorizontalSpacing(16); form.setVerticalSpacing(15)
        v.addLayout(form)
        folder=row(spacing=8); self.dest=QLineEdit(storage.config.get('output_dir',str(Path.home()/'Downloads')))
        browse=push('Escolher','folder'); browse.clicked.connect(self._choose_folder)
        folder.addWidget(self.dest,1); folder.addWidget(browse)
        form.addRow('Salvar em',self._wrap(folder))
        self.browser=QComboBox(); self.browser.addItems(BROWSERS)
        self.browser.setCurrentText(storage.config.get('browser','Não usar cookies'))
        form.addRow('Sessão do navegador',self.browser)
        cookies=row(spacing=8); self.cookie=QLineEdit(storage.config.get('cookie_file',''))
        choose=push('Arquivo…','folder'); choose.clicked.connect(self._choose_cookies)
        cookies.addWidget(self.cookie,1); cookies.addWidget(choose)
        form.addRow('cookies.txt',self._wrap(cookies))
        self.limit=QSpinBox(); self.limit.setRange(1,500); self.limit.setValue(int(storage.config.get('playlist_limit',100)))
        self.limit.setToolTip('Quantidade máxima analisada numa playlist; pode aumentar até 500.')
        form.addRow('Itens por playlist',self.limit)
        self.tray=QCheckBox('Minimizar para a bandeja ao fechar')
        self.tray.setChecked(bool(storage.config.get('close_to_tray',True)))
        v.addWidget(self.tray)
        hint=text('Usar cookies é opcional. Se a fonte exigir login, escolha um navegador ou um arquivo cookies.txt.','Muted',True)
        v.addWidget(hint)
        buttons=row(spacing=10); buttons.addStretch()
        cancel=push('Cancelar'); cancel.clicked.connect(self.reject); buttons.addWidget(cancel)
        save=push('Salvar alterações','check','Primary'); save.clicked.connect(self._save); buttons.addWidget(save)
        v.addLayout(buttons)

    def _wrap(self,layout):
        w=QWidget(); w.setLayout(layout); return w
    def _choose_folder(self):
        p=QFileDialog.getExistingDirectory(self,'Pasta de downloads',self.dest.text())
        if p: self.dest.setText(p)
    def _choose_cookies(self):
        p,_=QFileDialog.getOpenFileName(self,'Arquivo de cookies','','Textos (*.txt);;Todos (*.*)')
        if p: self.cookie.setText(p)
    def _save(self):
        path=Path(self.dest.text().strip())
        if not self.dest.text().strip(): QMessageBox.warning(self,'Pasta inválida','Escolha uma pasta de downloads.'); return
        cookie=self.cookie.text().strip()
        if cookie and not Path(cookie).is_file(): QMessageBox.warning(self,'Arquivo não encontrado','O arquivo cookies.txt não existe.'); return
        self.storage.config.update(output_dir=str(path),browser=self.browser.currentText(),
                                   cookie_file=cookie,playlist_limit=self.limit.value(),
                                   close_to_tray=self.tray.isChecked())
        self.storage.save_config(); self.accept()


class FluxoraWindow(QMainWindow):
    def __init__(self):
        super().__init__(); self.setWindowTitle('Fluxora 3.1 | Downloads e Conversão de Mídia')
        self.resize(1330,825); self.setMinimumSize(1050,670)
        self.storage=Storage()
        self.active_analyzer=None
        self.max_parallel_downloads=3
        self.active_downloads={}; self.pending_downloads=[]; self.queued_download_keys=set()
        self.shutting_down=False
        self.download_cards=[]; self.fetchers=[]; self.images={}; self.image_waiters={}; self.analyzed_info=None
        self.playlist_covers={}; self.playlist_thumbs_loaded=set()
        self.filter_state='Todos'; self.library_filter='video'
        self.library_columns=0
        self.library_resize_timer=QTimer(self); self.library_resize_timer.setSingleShot(True)
        self.library_resize_timer.timeout.connect(self._refresh_library_if_columns_changed)
        ico=Path(__file__).resolve().parents[1]/'assets'/'Fluxora.ico'
        if ico.is_file(): self.setWindowIcon(QIcon(str(ico)))
        self._create_ui(); self._create_tray(); self._refresh_space(); self._refresh_library()

    def _create_ui(self):
        root=QWidget(); root.setObjectName('Root'); self.setCentralWidget(root)
        overall=row(spacing=0); root.setLayout(overall)
        self.sidebar=frame('Sidebar'); self.sidebar.setFixedWidth(224); overall.addWidget(self.sidebar)
        self._build_sidebar()
        content=QWidget(); content.setObjectName('Body'); overall.addWidget(content,1)
        body=column((25,23,25,14),17); content.setLayout(body)
        self.url_bar=frame('FormPanel'); bar=row((10,9,10,9),8); self.url_bar.setLayout(bar)
        self.url_entry=QLineEdit(); self.url_entry.setPlaceholderText('Cole o link do vídeo ou playlist aqui...')
        self.url_entry.setClearButtonEnabled(True); self.url_entry.returnPressed.connect(self.analyze)
        bar.addWidget(self.url_entry,1)
        paste=push('Colar','paste'); paste.clicked.connect(self.paste_link); bar.addWidget(paste)
        self.analyze_button=push('Analisar','search'); self.analyze_button.clicked.connect(self.analyze); bar.addWidget(self.analyze_button)
        self.download_button=push('Baixar','download','Primary'); self.download_button.clicked.connect(self.start_download); bar.addWidget(self.download_button)
        body.addWidget(self.url_bar)
        self.pages=QStackedWidget(); body.addWidget(self.pages,1)
        self.downloads_page=self._build_download_page(); self.pages.addWidget(self.downloads_page)
        self.video_page=self._build_preview_page(); self.pages.addWidget(self.video_page)
        self.playlist_page=self._build_playlist_page(); self.pages.addWidget(self.playlist_page)
        self.library_page=self._build_library_page(); self.pages.addWidget(self.library_page)
        self.converter_page=ConverterPage(self.storage,self); self.pages.addWidget(self.converter_page)
        self.converter_page.conversion_completed.connect(self._conversion_completed)
        footer=QWidget(); foot=row(spacing=7); footer.setLayout(foot)
        self.status_dot=text('●','Success'); foot.addWidget(self.status_dot)
        self.status_label=text('Sistema pronto para baixar','Muted'); foot.addWidget(self.status_label)
        foot.addStretch(); foot.addWidget(text('FLUXORA 3.1  •  PYSIDE6 + FFMPEG','Subtle'))
        body.addWidget(footer)
        self._show_page(0)

    def _build_sidebar(self):
        side=column((13,22,13,18),10); self.sidebar.setLayout(side)
        header=row((7,0,0,8),8)
        logo=QLabel(); logo_file=Path(__file__).resolve().parents[1]/'assets'/'fluxora-logo.png'
        if logo_file.is_file(): logo.setPixmap(QPixmap(str(logo_file)).scaled(38,38,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        header.addWidget(logo)
        header.addWidget(text('FLUXORA','Brand'),1)
        side.addLayout(header); side.addSpacing(17)
        self.nav_buttons={}
        for title,ic,index in [('Downloads','download',0),('Biblioteca','library',3)]:
            b=push(title,ic,'Nav'); b.setIconSize(QSize(21,21))
            b.clicked.connect(lambda checked=False, p=index: self._show_page(p)); side.addWidget(b)
            self.nav_buttons[index]=b
        side.addSpacing(4)
        side.addWidget(text('FERRAMENTAS','Eyebrow'))
        converter=push('Conversor','convert','Nav'); converter.setIconSize(QSize(21,21))
        converter.clicked.connect(lambda checked=False:self._show_page(4)); side.addWidget(converter); self.nav_buttons[4]=converter
        for title,ic in [('Gravador de tela','monitor'),('Gravador de áudio','mic'),('Captura de dispositivo','phone')]:
            b=push(title,ic,'Nav'); b.setEnabled(False)
            b.setToolTip('Módulo ainda não integrado.'); side.addWidget(b)
        side.addStretch(1)
        for title,ic,action in [('Histórico','history',lambda: self._show_page(3)),
                                ('Configurações','settings',self.settings_dialog)]:
            b=push(title,ic,'Nav'); b.clicked.connect(action); side.addWidget(b)
        storage=frame('InfoBox'); s=column((13,12,13,12),8); storage.setLayout(s)
        s.addWidget(text('ARMAZENAMENTO','Eyebrow'))
        self.disk_label=text('Verificando espaço...','Muted'); s.addWidget(self.disk_label)
        self.disk_bar=QProgressBar(); self.disk_bar.setRange(0,100); self.disk_bar.setValue(0)
        s.addWidget(self.disk_bar); side.addWidget(storage)

    def _build_download_page(self):
        page=QWidget(); v=column(spacing=16); page.setLayout(v)
        types=row(spacing=9)
        self.type_chips=[]
        for title,ic,media in [('Vídeo','film','MP4'),('Playlist','list','PLAYLIST'),('Áudio','music','MP3'),('Legendas','subtitles','SUBTITLE')]:
            b=push(title,ic,'Chip'); b.setCheckable(True)
            if media=='SUBTITLE': b.setEnabled(False); b.setToolTip('Legendas: em desenvolvimento')
            else: b.clicked.connect(lambda checked=False, m=media: self.change_type(m))
            types.addWidget(b); self.type_chips.append((b,media))
        types.addStretch(); v.addLayout(types)
        control=frame('FormPanel'); c=row((17,13,14,13),12); control.setLayout(c)
        c.addWidget(text('Formato','Muted'))
        self.format_combo=QComboBox(); self.format_combo.addItems(['MP4 (vídeo)','MP3 (áudio)'])
        self.format_combo.setMinimumWidth(160); self.format_combo.currentTextChanged.connect(self._quality_changed)
        c.addWidget(self.format_combo)
        c.addSpacing(10); c.addWidget(text('Qualidade','Muted'))
        self.quality_combo=QComboBox(); self.quality_combo.addItems(VIDEO_QUALITIES)
        self.quality_combo.setMinimumWidth(180); c.addWidget(self.quality_combo)
        c.addStretch(); gear=push('','settings','IconButton'); gear.clicked.connect(self.settings_dialog)
        gear.setToolTip('Preferências de download'); c.addWidget(gear); v.addWidget(control)
        top=row(spacing=8); top.addWidget(text('Seus downloads','Section')); top.addStretch()
        self.current_folder=push('Abrir pasta','folder'); self.current_folder.clicked.connect(self.open_folder)
        top.addWidget(self.current_folder); v.addLayout(top)
        filters=row(spacing=7); self.filter_buttons={}
        for title in ['Todos','Na fila','Baixando','Concluídos','Cancelados','Pausados','Falhou']:
            b=push(title,'','Chip'); b.setCheckable(True)
            if title=='Pausados': b.setEnabled(False); b.setToolTip('Pausar downloads ainda não é suportado pelo motor atual')
            else: b.clicked.connect(lambda checked=False, t=title: self.set_filter(t))
            filters.addWidget(b); self.filter_buttons[title]=b
        filters.addStretch(); v.addLayout(filters)
        scroll=QScrollArea(); scroll.setWidgetResizable(True)
        self.download_contents=QWidget(); self.download_list=column((1,1,1,1),10)
        self.download_contents.setLayout(self.download_list)
        self.download_list.addStretch(1)
        scroll.setWidget(self.download_contents); v.addWidget(scroll,1)
        self.empty_downloads=frame('InfoBox')
        e=column((24,34,24,32),13)
        e.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_downloads.setLayout(e)
        symbol=text('↓'); symbol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        symbol.setStyleSheet(f'font-size:38px; color:{GREEN}; font-weight:800;'); e.addWidget(symbol)
        headline=text('Seus downloads aparecem aqui','Section'); headline.setAlignment(Qt.AlignmentFlag.AlignCenter); e.addWidget(headline)
        hint=text('Cole um link acima e clique em Baixar ou Analisar.','Muted'); hint.setAlignment(Qt.AlignmentFlag.AlignCenter); e.addWidget(hint)
        self.download_list.insertWidget(0,self.empty_downloads)
        self.set_filter('Todos'); self.change_type('MP4')
        return page

    def _build_preview_page(self):
        scroller=QScrollArea(); scroller.setWidgetResizable(True)
        page=QWidget(); v=column((1,1,7,1),15); page.setLayout(v)
        scroller.setWidget(page)
        head=row(spacing=10); head.addWidget(text('Prévia do vídeo','Heading')); head.addStretch()
        back=push('Voltar para downloads'); back.clicked.connect(lambda:self._show_page(0)); head.addWidget(back)
        v.addLayout(head)
        preview=frame('Panel'); p=row((16,16,16,16),17); preview.setLayout(p)
        self.preview_cover=Cover(336,190); p.addWidget(self.preview_cover)
        description=column(spacing=11); p.addLayout(description,1)
        self.preview_title=text('Analise um link para visualizar o vídeo.','Section',True)
        description.addWidget(self.preview_title)
        self.preview_channel=text('','Muted'); description.addWidget(self.preview_channel)
        self.preview_metadata=text('','Muted'); description.addWidget(self.preview_metadata)
        desc_tags=row(spacing=7)
        for label in ['VÍDEO','MP4 / MP3','QUALIDADE DISPONÍVEL']:
            desc_tags.addWidget(text(label,'Tag'))
        desc_tags.addStretch(); description.addLayout(desc_tags)
        description.addStretch(); p.addStretch(0)
        v.addWidget(preview)
        rowtitle=row(); rowtitle.addWidget(text('Formatos disponíveis','Section')); rowtitle.addStretch()
        v.addLayout(rowtitle)
        format_panel=frame('Panel'); fl=column((14,13,14,13),9); format_panel.setLayout(fl)
        frow=row(spacing=8)
        fl.addLayout(frow)
        self.preview_media_chips=[]
        for mode in ['Vídeo','Áudio']:
            b=push(mode,None,'Chip'); b.setCheckable(True)
            b.clicked.connect(lambda checked=False,m=mode: self.set_preview_media(m))
            frow.addWidget(b); self.preview_media_chips.append(b)
        frow.addStretch()
        self.preview_qualities=column(spacing=7); fl.addLayout(self.preview_qualities)
        v.addWidget(format_panel)
        bottom=row(spacing=12); bottom.addStretch()
        self.preview_download=push('Baixar agora','download','Primary')
        self.preview_download.clicked.connect(self.start_download)
        self.preview_download.setMinimumHeight(46); bottom.addWidget(self.preview_download)
        v.addLayout(bottom); v.addStretch(1)
        self.set_preview_media('Vídeo'); return scroller

    def _build_playlist_page(self):
        page=QWidget(); v=column(spacing=15); page.setLayout(v)
        heading=row(spacing=10); heading.addWidget(text('Playlist','Heading')); heading.addStretch()
        back=push('Voltar para downloads'); back.clicked.connect(lambda:self._show_page(0)); heading.addWidget(back)
        v.addLayout(heading)
        hero=frame('Panel'); h=row((18,16,18,16),18); hero.setLayout(h)
        self.playlist_cover=Cover(142,120); h.addWidget(self.playlist_cover)
        meta=column(spacing=9); h.addLayout(meta,1)
        self.playlist_title=text('Carregue uma playlist para escolher os vídeos.','Section',True)
        meta.addWidget(self.playlist_title)
        self.playlist_meta=text('','Muted'); meta.addWidget(self.playlist_meta)
        self.playlist_selected=text('0 vídeos selecionados','Success'); meta.addWidget(self.playlist_selected)
        actions=row(spacing=9)
        self.pl_download=push('Baixar selecionados','download','Primary')
        self.pl_download.clicked.connect(self.start_playlist_download); actions.addWidget(self.pl_download)
        all_btn=push('Selecionar todos','check'); all_btn.clicked.connect(lambda:self.select_playlist(True)); actions.addWidget(all_btn)
        none_btn=push('Limpar seleção','close'); none_btn.clicked.connect(lambda:self.select_playlist(False)); actions.addWidget(none_btn)
        actions.addStretch(); meta.addLayout(actions)
        v.addWidget(hero)
        searchbar=row(spacing=9)
        self.playlist_search=QLineEdit(); self.playlist_search.setPlaceholderText('Pesquisar dentro da playlist...')
        self.playlist_search.textChanged.connect(self.search_playlist)
        searchbar.addWidget(self.playlist_search,1)
        searchbar.addWidget(text('Formato','Muted')); self.pl_media=QComboBox()
        self.pl_media.addItems(['MP4','MP3']); self.pl_media.currentTextChanged.connect(self._playlist_quality_change)
        searchbar.addWidget(self.pl_media)
        searchbar.addWidget(text('Qualidade','Muted')); self.pl_quality=QComboBox(); self.pl_quality.addItems(VIDEO_QUALITIES)
        searchbar.addWidget(self.pl_quality); v.addLayout(searchbar)
        self.playlist_table=PlaylistTable(0,5)
        self.playlist_table.setHorizontalHeaderLabels(['','Nº','Miniatura','Título','Duração'])
        self.playlist_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.playlist_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.playlist_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.playlist_table.setAlternatingRowColors(True)
        self.playlist_table.verticalHeader().setVisible(False)
        self.playlist_table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch)
        self.playlist_table.setColumnWidth(0,49); self.playlist_table.setColumnWidth(1,55)
        self.playlist_table.setColumnWidth(2,112); self.playlist_table.setColumnWidth(4,85)
        self.playlist_table.itemChanged.connect(self.update_selected_count)
        self.playlist_table.checks_changed.connect(self.update_selected_count)
        self.playlist_table.verticalScrollBar().valueChanged.connect(
            lambda _value: QTimer.singleShot(80,self._load_visible_playlist_thumbnails)
        )
        v.addWidget(self.playlist_table,1)
        self.playlist_notice=text('A análise exibe até o limite definido nas Configurações.','Subtle'); v.addWidget(self.playlist_notice)
        self.pl_download.setEnabled(False)
        return page

    def _build_library_page(self):
        page=QWidget(); v=column(spacing=17); page.setLayout(v)
        v.addWidget(text('Minha biblioteca','Heading'))
        v.addWidget(text('Seus vídeos e músicas baixados, tudo em um só lugar.','Muted'))
        controls=row(spacing=8)
        self.library_tabs={}
        for label,key,ic in [('Vídeos','video','film'),('Músicas','audio','music')]:
            b=push(label,ic,'Chip'); b.setCheckable(True)
            b.clicked.connect(lambda checked=False,k=key:self.set_library_filter(k))
            controls.addWidget(b); self.library_tabs[key]=b
        controls.addStretch(); v.addLayout(controls)
        find=row(spacing=9); self.library_search=QLineEdit(); self.library_search.setPlaceholderText('Buscar arquivos...')
        self.library_search.textChanged.connect(self._refresh_library)
        find.addWidget(self.library_search,1); refresh=push('Atualizar','history')
        refresh.clicked.connect(self._refresh_library); find.addWidget(refresh)
        locate=push('Abrir pasta','folder'); locate.clicked.connect(self.open_folder); find.addWidget(locate)
        v.addLayout(find)
        self.library_scroll=QScrollArea(); self.library_scroll.setWidgetResizable(True)
        self.library_content=QWidget(); self.library_grid=QGridLayout(self.library_content)
        self.library_grid.setContentsMargins(2,4,5,4); self.library_grid.setHorizontalSpacing(13); self.library_grid.setVerticalSpacing(14)
        self.library_scroll.setWidget(self.library_content); v.addWidget(self.library_scroll,1)
        self.set_library_filter('video'); return page

    def _create_tray(self):
        self.tray=None
        if not QSystemTrayIcon.isSystemTrayAvailable(): return
        self.tray=QSystemTrayIcon(self.windowIcon(),self)
        menu=QMenu(self)
        open_action=menu.addAction('Abrir Fluxora'); open_action.triggered.connect(self.show_from_tray)
        exit_action=menu.addAction('Sair'); exit_action.triggered.connect(self.exit_app)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda reason:self.show_from_tray() if reason==QSystemTrayIcon.ActivationReason.DoubleClick else None)
        self.tray.show()

    def show_from_tray(self): self.showNormal(); self.raise_(); self.activateWindow()
    def exit_app(self):
        self.storage.save_config()
        if self.active_analyzer and self.active_analyzer.isRunning():
            QMessageBox.information(self,'Análise em andamento','Aguarde a análise terminar antes de encerrar o Fluxora.')
            return
        self.shutting_down=True
        for job in self.pending_downloads:
            job['card'].finalize('Cancelado','Aplicativo encerrado antes de iniciar')
            self.queued_download_keys.discard(job['key'])
        self.pending_downloads.clear()
        running=[worker for worker in self.active_downloads.values() if worker.isRunning()]
        for worker in running: worker.cancel()
        if any(not worker.wait(2500) for worker in running):
            self.shutting_down=False
            QMessageBox.information(self,'Downloads em andamento','Alguns downloads ainda estão finalizando. Aguarde antes de encerrar.')
            return
        if hasattr(self,'converter_page'):
            self.converter_page.shutdown()
        QApplication.instance().quit()
    def closeEvent(self,event:QCloseEvent):
        if self.tray and self.storage.config.get('close_to_tray',True):
            self.hide(); self.tray.showMessage('Fluxora','O aplicativo continua aberto na bandeja.',QSystemTrayIcon.MessageIcon.Information,2200)
            event.ignore()
        else:
            if self.active_analyzer and self.active_analyzer.isRunning():
                QMessageBox.information(self,'Análise em andamento','Aguarde a análise terminar antes de fechar o Fluxora.')
                event.ignore(); return
            if self.active_downloads or self.pending_downloads:
                QMessageBox.information(self,'Downloads em andamento','Cancele ou aguarde a fila terminar antes de fechar o Fluxora.')
                event.ignore(); return
            if hasattr(self,'converter_page') and self.converter_page.is_active():
                QMessageBox.information(self,'Conversão em andamento','Cancele ou aguarde a conversão terminar antes de fechar o Fluxora.')
                event.ignore(); return
            event.accept(); QApplication.instance().quit()

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'library_resize_timer'):
            self.library_resize_timer.start(160)

    def _show_page(self,index):
        self.pages.setCurrentIndex(index)
        for k,b in self.nav_buttons.items():
            active = 3 if index==3 else (4 if index==4 else 0)
            b.setProperty('active','true' if k==active else 'false')
            b.style().unpolish(b); b.style().polish(b)
        self.url_bar.setVisible(index in (0,1,2))
        self.download_button.setVisible(index==0)
        self.analyze_button.setVisible(index in (0,1,2))
        if index==3: self._refresh_library()
        self._refresh_space()

    def _refresh_space(self):
        output=self.storage.config.get('output_dir',str(Path.home()/'Downloads'))
        path=Path(output)
        while not path.exists() and path != path.parent: path=path.parent
        try:
            _,used,free=shutil.disk_usage(path)
            self.disk_bar.setValue(int(used/(used+free)*100))
            self.disk_label.setText(f'{format_bytes(free)} livres')
        except OSError: self.disk_label.setText('Espaço não disponível')

    def status(self,msg): self.status_label.setText(msg)

    def settings_dialog(self):
        if SettingsDialog(self.storage,self).exec()==QDialog.DialogCode.Accepted:
            self._refresh_space(); self.status('Configurações salvas')

    def paste_link(self):
        content=QApplication.clipboard().text().strip()
        if content: self.url_entry.setText(content)
        else: self.status('A área de transferência está vazia.')

    def change_type(self,media):
        for b,k in self.type_chips: b.setChecked(media==k)
        if media=='MP3': self.format_combo.setCurrentText('MP3 (áudio)')
        elif media=='MP4': self.format_combo.setCurrentText('MP4 (vídeo)')
        elif media=='PLAYLIST':
            self.status('Cole a URL da playlist e clique em Analisar para escolher os itens.')
        self.mode=media

    def _selected_media_type(self):
        return 'MP3' if self.format_combo.currentText().startswith('MP3') else 'MP4'

    def _quality_changed(self,_val):
        current='MP3' if self.format_combo.currentText().startswith('MP3') else 'MP4'
        desired=self.quality_combo.currentText()
        self.quality_combo.blockSignals(True); self.quality_combo.clear()
        self.quality_combo.addItems(AUDIO_QUALITIES if current=='MP3' else VIDEO_QUALITIES)
        if desired in (AUDIO_QUALITIES if current=='MP3' else VIDEO_QUALITIES):
            self.quality_combo.setCurrentText(desired)
        self.quality_combo.blockSignals(False)
        for b,key in self.type_chips:
            if key in ('MP3','MP4'): b.setChecked(key==current)

    def set_filter(self,name):
        self.filter_state=name
        counts = {
            'Todos': len(self.download_cards),
            'Na fila': sum(x.state=='Na fila' for x in self.download_cards),
            'Baixando': sum(x.state=='Baixando' for x in self.download_cards),
            'Concluídos': sum(x.state=='Concluído' for x in self.download_cards),
            'Cancelados': sum(x.state=='Cancelado' for x in self.download_cards),
            'Pausados': 0,
            'Falhou': sum(x.state=='Falhou' for x in self.download_cards),
        }
        for key,btn in self.filter_buttons.items():
            btn.setChecked(key==name)
            btn.setText(f'{key} ({counts[key]})')
        number_visible=0
        for card in self.download_cards:
            show=(name=='Todos' or (name=='Baixando' and card.state=='Baixando') or
                  (name=='Na fila' and card.state=='Na fila') or
                  (name=='Concluídos' and card.state=='Concluído') or
                  (name=='Cancelados' and card.state=='Cancelado') or
                  (name=='Falhou' and card.state=='Falhou'))
            card.setVisible(show)
            if show: number_visible += 1
        self.empty_downloads.setVisible(number_visible==0)

    def set_preview_media(self,media):
        for b in self.preview_media_chips: b.setChecked(b.text()==media)
        self.preview_media=media
        self.format_combo.setCurrentText('MP3 (áudio)' if media=='Áudio' else 'MP4 (vídeo)')
        self._clear_layout(self.preview_qualities)
        all_heights=(self.analyzed_info or {}).get('heights') or []
        if media=='Vídeo':
            options=['Melhor disponível']+[f'{x}p' for x in all_heights if f'{x}p' in VIDEO_QUALITIES]
            if len(options)==1: options=VIDEO_QUALITIES
        else: options=AUDIO_QUALITIES
        self.preview_option_buttons=[]
        for i,quality in enumerate(options):
            b=push(self._preview_option_label(quality,i==0),None,'Chip'); b.setCheckable(True)
            b.setStyleSheet('text-align:left;')
            b.clicked.connect(lambda checked=False,q=quality:self.set_preview_quality(q))
            self.preview_qualities.addWidget(b); self.preview_option_buttons.append((b,quality))
        if options: self.set_preview_quality(options[0])

    def _preview_option_label(self,quality,selected=False):
        marker='●' if selected else '○'
        if self.preview_media=='Áudio':
            detail=f'MP3  •  {quality}'
        elif quality=='Melhor disponível':
            detail='MP4  •  Melhor combinação de vídeo e áudio'
        else:
            try: height=int(quality.removesuffix('p'))
            except ValueError: height=0
            found=(self.analyzed_info or {}).get('video_formats',{}).get(height,{})
            resolution=f'{found.get("width")}×{height}' if found.get('width') else quality
            detail=f'MP4 {quality}  •  {resolution}'
        return f'{marker}    {detail}'

    def set_preview_quality(self,quality):
        self.preview_quality=quality
        for b,q in self.preview_option_buttons:
            b.setChecked(q==quality); b.setText(self._preview_option_label(q,q==quality))

    def _playlist_quality_change(self,value):
        self.format_combo.setCurrentText('MP3 (áudio)' if value=='MP3' else 'MP4 (vídeo)')
        self.pl_quality.clear(); self.pl_quality.addItems(AUDIO_QUALITIES if value=='MP3' else VIDEO_QUALITIES)

    def analyze(self):
        url=self.url_entry.text().strip()
        if not is_valid_url(url): QMessageBox.warning(self,'URL inválida','Cole um link completo começando com https://'); return
        if self.active_analyzer and self.active_analyzer.isRunning():
            self.status('Uma análise já está em andamento.'); return
        playlist=(self.mode=='PLAYLIST' or is_playlist_url(url))
        self._show_page(2 if playlist else 1)
        self.status('Analisando playlist...' if playlist else 'Buscando dados do vídeo...')
        self.analyze_button.setEnabled(False); self.analyze_button.setText('Analisando...')
        selected_browser=BROWSERS.get(self.storage.config.get('browser','Não usar cookies'))
        cookies=self.storage.config.get('cookie_file') or None
        self.active_analyzer=Analyzer(url,selected_browser,cookies,playlist,
                                       int(self.storage.config.get('playlist_limit',100)),self)
        worker=self.active_analyzer
        worker.analyzed.connect(self._analyzed)
        worker.failed.connect(lambda error: (self.status('Falha na análise'),QMessageBox.warning(self,'Análise indisponível',error)))
        worker.finished.connect(lambda: (self.analyze_button.setEnabled(True),self.analyze_button.setText('Analisar')))
        worker.start()

    def _analyzed(self,info):
        self.analyzed_info=info
        self.status('Análise concluída')
        requested_media=self._selected_media_type()
        if info['kind']=='video':
            self.preview_title.setText(info['title'])
            self.preview_channel.setText(info['channel'])
            views=info.get('view_count')
            self.preview_metadata.setText(f'{duration(info.get("duration"))}  •  '+(f'{views:,} visualizações' if views is not None else 'Qualidade disponível após análise'))
            self.set_preview_media('Áudio' if requested_media=='MP3' else 'Vídeo')
            self._show_page(1)
            self._request_image(info.get('thumbnail'),self.preview_cover)
        else:
            self.pl_media.setCurrentText(requested_media)
            self.playlist_title.setText(info['title'])
            count=info.get('count') or len(info.get('entries') or [])
            self.playlist_meta.setText(f'{info.get("channel") or "Playlist"}  •  {count} vídeos')
            self._populate_playlist(info.get('entries',[]))
            first_thumb=next((item.get('thumbnail') for item in info.get('entries',[]) if item.get('thumbnail')),'')
            self._request_image(info.get('thumbnail') or first_thumb,self.playlist_cover)
            self._show_page(2)

    def _populate_playlist(self,entries):
        table=self.playlist_table
        table.blockSignals(True); table.setRowCount(0)
        table.reset_anchors()
        self.playlist_covers.clear(); self.playlist_thumbs_loaded.clear()
        for ix,item in enumerate(entries):
            table.insertRow(ix); table.setRowHeight(ix,62)
            check=QTableWidgetItem(); check.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsSelectable|Qt.ItemFlag.ItemIsUserCheckable)
            check.setCheckState(Qt.CheckState.Checked); table.setItem(ix,0,check)
            number=QTableWidgetItem(str(item.get('index',ix+1))); number.setData(Qt.ItemDataRole.UserRole,item.get('index',ix+1))
            table.setItem(ix,1,number)
            cover=Cover(96,54); table.setCellWidget(ix,2,cover)
            self.playlist_covers[ix]=(cover,item.get('thumbnail',''))
            table.setItem(ix,3,QTableWidgetItem(item.get('title','Sem título')))
            table.setItem(ix,4,QTableWidgetItem(duration(item.get('duration'))))
        table.blockSignals(False)
        self.update_selected_count()
        self.playlist_notice.setText(f'{len(entries)} itens carregados. Se houver mais vídeos, aumente o limite nas Configurações.')
        QTimer.singleShot(0,self._load_visible_playlist_thumbnails)

    def _load_visible_playlist_thumbnails(self):
        if not self.playlist_table.rowCount(): return
        viewport=self.playlist_table.viewport()
        first=self.playlist_table.indexAt(QPoint(0,0)).row()
        last=self.playlist_table.indexAt(QPoint(0,max(0,viewport.height()-1))).row()
        if first < 0: first=0
        if last < 0: last=min(self.playlist_table.rowCount()-1,first+12)
        for row_number in range(first,min(last+2,self.playlist_table.rowCount())):
            if row_number in self.playlist_thumbs_loaded: continue
            cover,url=self.playlist_covers.get(row_number,(None,''))
            self.playlist_thumbs_loaded.add(row_number)
            if cover and url: self._request_image(url,cover)

    def update_selected_count(self,*_):
        count=sum(self.playlist_table.item(i,0).checkState()==Qt.CheckState.Checked
                  for i in range(self.playlist_table.rowCount()))
        self.playlist_selected.setText(f'{count} vídeos selecionados')
        self.pl_download.setEnabled(count>0)

    def select_playlist(self,value):
        self.playlist_table.check_anchor=None; self.playlist_table.selection_anchor=None
        self.playlist_table.blockSignals(True)
        for i in range(self.playlist_table.rowCount()):
            self.playlist_table.item(i,0).setCheckState(Qt.CheckState.Checked if value else Qt.CheckState.Unchecked)
        self.playlist_table.blockSignals(False)
        if value: self.playlist_table.select_visible_rows()
        else: self.playlist_table.clearSelection()
        self.playlist_table.viewport().update(); self.update_selected_count()

    def search_playlist(self,needle):
        needle=needle.strip().lower()
        for i in range(self.playlist_table.rowCount()):
            title=self.playlist_table.item(i,3).text().lower()
            self.playlist_table.setRowHidden(i,needle not in title)
        QTimer.singleShot(0,self._load_visible_playlist_thumbnails)

    def start_playlist_download(self):
        if not self.analyzed_info or self.analyzed_info.get('kind')!='playlist':
            QMessageBox.information(self,'Playlist','Analise uma playlist antes de baixar.'); return
        selected_rows=[i for i in range(self.playlist_table.rowCount())
                       if self.playlist_table.item(i,0).checkState()==Qt.CheckState.Checked]
        if not selected_rows: QMessageBox.information(self,'Playlist','Selecione pelo menos um vídeo.'); return
        entries={int(item.get('index',position+1)):item
                 for position,item in enumerate(self.analyzed_info.get('entries',[]))}
        added=0
        for table_row in selected_rows:
            index=int(self.playlist_table.item(table_row,1).data(Qt.ItemDataRole.UserRole))
            item=entries.get(index,{})
            if self._launch_download(self.analyzed_info['url'],self.pl_media.currentText(),
                                     self.pl_quality.currentText(),True,[index],
                                     item.get('title') or self.playlist_table.item(table_row,3).text(),
                                     item.get('thumbnail','')):
                added += 1
        self._show_page(0)
        self.status(f'{added} música(s) adicionada(s) à fila' if added else 'Os itens selecionados já estão na fila')

    def start_download(self):
        url=self.url_entry.text().strip()
        if not is_valid_url(url): QMessageBox.warning(self,'URL inválida','Cole uma URL antes de baixar.'); return
        if is_playlist_url(url) or self.mode=='PLAYLIST':
            if self.analyzed_info and self.analyzed_info.get('kind')=='playlist' and self.analyzed_info.get('url')==url:
                self.start_playlist_download()
            else: self.analyze()
            return
        if self.pages.currentIndex()==1 and self.analyzed_info and self.analyzed_info.get('kind')=='video' and self.analyzed_info['url']==url:
            media='MP3' if self.preview_media=='Áudio' else 'MP4'; quality=self.preview_quality
        else:
            media=self._selected_media_type(); quality=self.quality_combo.currentText()
        self._launch_download(url,media,quality,False,None)

    def _launch_download(self,url,media,quality,playlist,selected,title=None,thumbnail=''):
        selected_tuple=tuple(selected or ())
        job_key=(url,media,quality,playlist,selected_tuple)
        if job_key in self.queued_download_keys: return False
        self.queued_download_keys.add(job_key)
        fallback=(self.analyzed_info.get('title') if self.analyzed_info and self.analyzed_info.get('url')==url else 'Novo download')
        card=None
        card=DownloadCard(title or fallback,media,quality,
                          cancel=lambda:self._cancel_download_card(card),
                          remove=lambda:self._remove_download_card(card))
        if thumbnail: self._request_image(thumbnail,card.cover)
        self.download_cards.insert(0,card); self.download_list.insertWidget(0,card)
        self.pending_downloads.append({'key':job_key,'card':card,'url':url,'media':media,
                                       'quality':quality,'playlist':playlist,'selected':list(selected_tuple) or None})
        self.set_filter('Todos'); self._show_page(0)
        self.status('Download adicionado à fila')
        self._process_download_queue()
        return True

    def _process_download_queue(self):
        if self.shutting_down: return
        while self.pending_downloads and len(self.active_downloads)<self.max_parallel_downloads:
            job=self.pending_downloads.pop(0)
            card=job['card']
            if card.state=='Cancelado':
                self.queued_download_keys.discard(job['key']); continue
            self._start_download_job(job)

    def _start_download_job(self,job):
        card=job['card']; card.start()
        browser=BROWSERS.get(self.storage.config.get('browser','Não usar cookies'))
        cookies=self.storage.config.get('cookie_file') or None
        output=self.storage.config.get('output_dir',str(Path.home()/'Downloads'))
        worker=Downloader(job['url'],output,job['media'],job['quality'],browser,cookies,job['playlist'],
                          int(self.storage.config.get('playlist_limit',100)),job['selected'],self)
        self.active_downloads[card]=worker
        self.set_filter(self.filter_state)
        self.status('Iniciando transferência...')
        worker.progress.connect(card.update_progress)
        worker.progress.connect(lambda data:self.status(data.get('stage','Baixando...')))
        worker.thumbnail.connect(lambda url:self._request_image(url,card.cover))
        worker.completed.connect(lambda data:self._finished_download(card,data))
        worker.failed.connect(lambda message:self._failed_download(card,message))
        worker.cancelled.connect(lambda:self._cancelled_download(card))
        worker.finished.connect(lambda:self._worker_stopped(card,worker,job['key']))
        worker.start()

    def _finished_download(self,card,result):
        count=self.storage.add_files(result.get('files',[]),result.get('url',''),result.get('thumbnail',''))
        card.finalize('Concluído', f'{result.get("count",0)} arquivo(s) processado(s) • Concluído')
        self.status('Download concluído' if count else 'Download concluído — consulte a pasta de destino')
        if self.tray: self.tray.showMessage('Fluxora','Download concluído.',QSystemTrayIcon.MessageIcon.Information,2800)
        self._refresh_library(); self.set_filter(self.filter_state)

    def _failed_download(self,card,error):
        summary=(error.splitlines()[0] if error else 'Falha no download')[:180]
        card.finalize('Falhou',summary); card.detail.setToolTip(error)
        self.status('Falha no download'); self.set_filter(self.filter_state)
        if self.tray: self.tray.showMessage('Fluxora','Um download falhou. Consulte a aba Falhou.',QSystemTrayIcon.MessageIcon.Warning,3200)

    def _cancelled_download(self,card):
        card.finalize('Cancelado','Transferência cancelada'); self.status('Download cancelado'); self.set_filter(self.filter_state)

    def _worker_stopped(self,card,worker,job_key):
        if self.active_downloads.get(card) is worker: self.active_downloads.pop(card,None)
        self.queued_download_keys.discard(job_key)
        worker.deleteLater()
        selected=any(self.playlist_table.item(i,0).checkState()==Qt.CheckState.Checked
                     for i in range(self.playlist_table.rowCount()))
        self.pl_download.setEnabled(selected)
        self.set_filter(self.filter_state); self._refresh_space(); self._process_download_queue()

    def _cancel_download_card(self,card):
        worker=self.active_downloads.get(card)
        if worker and worker.isRunning():
            card.cancel_btn.setEnabled(False); card.detail.setText('Cancelando transferência...')
            worker.cancel(); return
        for position,job in enumerate(self.pending_downloads):
            if job['card'] is card:
                self.pending_downloads.pop(position); self.queued_download_keys.discard(job['key'])
                card.finalize('Cancelado','Removido da fila antes de iniciar')
                self.set_filter(self.filter_state); return

    def _remove_download_card(self,card):
        if card in self.active_downloads or card.state in ('Na fila','Baixando'): return
        if card in self.download_cards: self.download_cards.remove(card)
        self.download_list.removeWidget(card); card.deleteLater(); self.set_filter(self.filter_state)

    def _request_image(self,url,cover):
        if not url: return
        if url in self.images:
            try: cover.set_image(self.images[url])
            except RuntimeError: pass
            return
        if url in self.image_waiters:
            if cover not in self.image_waiters[url]: self.image_waiters[url].append(cover)
            return
        self.image_waiters[url]=[cover]
        fetch=ImageFetcher(url,self)
        # reter referência até a thread terminar
        self.fetchers.append(fetch)
        def on_loaded(_url,data):
            self.images[_url]=data
            for target in self.image_waiters.get(_url,[]):
                try: target.set_image(data)
                except RuntimeError: pass
        fetch.loaded.connect(on_loaded)
        def on_finished():
            self.image_waiters.pop(url,None)
            if fetch in self.fetchers: self.fetchers.remove(fetch)
        fetch.finished.connect(on_finished)
        fetch.start()

    def set_library_filter(self,media):
        self.library_filter=media
        for key,button in self.library_tabs.items(): button.setChecked(key==media)
        self._refresh_library()

    def _desired_library_columns(self):
        width=self.library_scroll.viewport().width() if hasattr(self,'library_scroll') else self.width()-280
        if width >= 980: return 4
        if width >= 720: return 3
        if width >= 470: return 2
        return 1

    def _refresh_library_if_columns_changed(self):
        if not hasattr(self,'library_scroll'): return
        desired=self._desired_library_columns()
        if desired != self.library_columns:
            self._refresh_library()

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            child=layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            elif child.layout(): FluxoraWindow._clear_layout(child.layout())

    def _refresh_library(self,*_):
        if not hasattr(self,'library_grid'): return
        self._clear_layout(self.library_grid)
        for index in range(self.library_grid.rowCount()+1): self.library_grid.setRowStretch(index,0)
        for index in range(self.library_grid.columnCount()+1): self.library_grid.setColumnStretch(index,0)
        columns=self._desired_library_columns(); self.library_columns=columns
        search=self.library_search.text().casefold() if hasattr(self,'library_search') else ''
        matches=[x for x in self.storage.history if x.get('type')==self.library_filter
                 and search in x.get('title','').casefold() and Path(x.get('path','')).is_file()]
        if not matches:
            empty=frame('InfoBox'); v=column((26,44,26,44),12); v.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setLayout(v); label=text('▧'); label.setStyleSheet(f'font-size:35px;color:{GREEN};'); v.addWidget(label)
            v.addWidget(text('Nenhum arquivo encontrado','Section'))
            v.addWidget(text('Os downloads concluídos aparecerão aqui.','Muted'))
            self.library_grid.addWidget(empty,0,0,1,columns)
        else:
            for i, entry in enumerate(matches):
                tile=frame('Card'); tile.setMinimumHeight(246)
                content=column((10,10,10,10),9); tile.setLayout(content)
                cover=Cover(218,124); cover.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
                cover.setMinimumWidth(180); cover.setMaximumWidth(16777215); cover.setFixedHeight(124)
                content.addWidget(cover)
                self._request_image(entry.get('thumbnail',''),cover)
                title=text(entry.get('title','Arquivo'),wrap=False); title.setToolTip(entry.get('title',''))
                title.setStyleSheet('font-size:12px;font-weight:650;')
                title.setMaximumHeight(19); content.addWidget(title)
                note=text(f'{format_bytes(entry.get("size"))}  •  {entry.get("created_at","")[:10]}','Muted')
                content.addWidget(note)
                actions=row(spacing=7)
                b=push('Abrir arquivo','external'); b.clicked.connect(lambda _,p=entry['path']:self.open_path(p))
                actions.addWidget(b,1)
                folder=push('','folder','IconButton'); folder.setToolTip('Abrir pasta do arquivo')
                folder.clicked.connect(lambda _,p=entry['path']:self.open_containing_folder(p))
                actions.addWidget(folder); content.addLayout(actions)
                reconvert=push('Converter novamente','convert')
                reconvert.clicked.connect(lambda _,p=entry['path']:self._open_in_converter(p))
                content.addWidget(reconvert)
                self.library_grid.addWidget(tile,i//columns,i%columns)
        self.library_grid.setRowStretch((len(matches)+columns-1)//columns,1)

    def _conversion_completed(self, source_path, output_path):
        if self.storage.add_files([output_path], source_path=source_path, origin='conversion'):
            self._refresh_library()
        self.status(f'Conversão concluída: {Path(output_path).name}')

    def _open_in_converter(self, path):
        self.converter_page.add_paths([path])
        self._show_page(4)

    def open_path(self,path):
        path=Path(path)
        if not path.exists(): QMessageBox.warning(self,'Não encontrado',f'Arquivo indisponível:\n{path}'); return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def open_containing_folder(self,path):
        path=Path(path)
        directory=path.parent
        if not directory.is_dir(): QMessageBox.warning(self,'Não encontrado',f'Pasta indisponível:\n{directory}'); return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))

    def open_folder(self):
        directory=Path(self.storage.config.get('output_dir',str(Path.home()/'Downloads')))
        directory.mkdir(parents=True,exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))
