"""Interações do redesign do conversor, sem rede."""
import subprocess
import sys
import tempfile
import time
import unittest
import shutil
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from fluxora.converter import find_ffmpeg
from fluxora.converter_ui import ConverterPage
from fluxora.theme import QSS


class MemoryStorage:
    def __init__(self,folder):
        self.config={'converter_format':'MP3','converter_quality':'Equilibrado','converter_resolution':'Original',
                     'converter_bitrate':'192 kbps','converter_keep_aspect':True,'converter_output_dir':str(folder)}
    def save_config(self): pass


class ConverterUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication(sys.argv[:1]); cls.app.setStyle('Fusion'); cls.app.setStyleSheet(QSS)
        cls.temp=tempfile.TemporaryDirectory(); cls.folder=Path(cls.temp.name); cls.ffmpeg=find_ffmpeg()
        cls.audio=cls.folder/'áudio teste.wav'; cls.video=cls.folder/'vídeo teste.mp4'
        subprocess.run([cls.ffmpeg,'-hide_banner','-loglevel','error','-y','-f','lavfi','-i','sine=frequency=500:duration=0.35','-c:a','pcm_s16le',str(cls.audio)],check=True)
        subprocess.run([cls.ffmpeg,'-hide_banner','-loglevel','error','-y','-f','lavfi','-i','color=c=blue:s=160x90:d=0.35','-f','lavfi','-i','sine=frequency=600:duration=0.35','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(cls.video)],check=True)
    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()
    def setUp(self):
        self.page=ConverterPage(MemoryStorage(self.folder)); self.page.resize(1100,680); self.page.show(); self.app.processEvents()
        self.page.add_paths([str(self.video),str(self.audio)]); deadline=time.monotonic()+6
        while self.page.probes and time.monotonic()<deadline: self.app.processEvents(); time.sleep(.02)
        self.app.processEvents(); self.cards=list(self.page.cards.values())
    def tearDown(self): self.page.shutdown(); self.page.hide(); self.page.deleteLater(); self.app.processEvents()

    def test_adds_multiple_formats_and_updates_smart_button(self):
        self.assertEqual(len(self.cards),2); self.assertTrue(all(card.is_selected() for card in self.cards))
        self.assertTrue(all(card.format.currentText()=='MP3' for card in self.cards))
        self.assertEqual(self.page.convert.text(),'Converter todos para MP3')

    def test_global_format_affects_only_selected_items(self):
        video,audio=self.cards; audio.set_selected(False); self.page.apply_global_format('MKV')
        self.assertEqual(video.format.currentText(),'MKV'); self.assertEqual(audio.format.currentText(),'MP3')
        self.assertEqual(self.page.convert.text(),'Converter 1 arquivo')

    def test_incompatible_audio_to_video_is_unselected(self):
        video,audio=self.cards; video.set_selected(False); audio.set_selected(True); self.page.apply_global_format('MP4')
        self.assertFalse(audio.is_selected()); self.assertIn('incompatível',audio.status.text()); self.assertFalse(self.page.convert.isEnabled())

    def test_selection_controls_and_shift_interval(self):
        self.page.select_none(); self.assertFalse(any(card.is_selected() for card in self.cards))
        first,second=self.cards; first.set_selected(True); self.page._selection_clicked(first,Qt.KeyboardModifier.NoModifier)
        second.set_selected(True); self.page._selection_clicked(second,Qt.KeyboardModifier.ShiftModifier)
        self.assertTrue(all(card.is_selected() for card in self.cards))
        self.page.invert_selection(); self.assertFalse(any(card.is_selected() for card in self.cards))
        first.select.setFocus(); QTest.keyClick(first.select,Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier); self.app.processEvents()
        self.assertTrue(all(card.is_selected() for card in self.cards))

    def test_advanced_options_apply_only_to_selected_cards(self):
        first,second=self.cards; second.set_selected(False); self.page.resolution.setCurrentText('720p'); self.page.bitrate.setCurrentText('256 kbps')
        self.assertEqual(first.resolution,'Original'); self.assertEqual(first.bitrate,'192 kbps')
        self.page.apply_pending_settings()
        self.assertEqual(first.resolution,'720p'); self.assertEqual(first.bitrate,'256 kbps')
        self.assertEqual(second.resolution,'Original'); self.assertEqual(second.bitrate,'192 kbps')

    def test_side_panel_waits_for_explicit_apply(self):
        first,second=self.cards; second.set_selected(False)
        self.page.video_category.click(); self.page.global_format_combo.setCurrentText('MKV')
        self.assertEqual(first.format.currentText(),'MP3')
        self.assertEqual(second.format.currentText(),'MP3')
        self.page.apply_settings.click()
        self.assertEqual(first.format.currentText(),'MKV')
        self.assertEqual(second.format.currentText(),'MP3')
        self.assertIn('Aplicado a 1',self.page.apply_feedback.text())

    def test_individual_destination_is_used_by_task(self):
        card=self.cards[0]; custom=self.folder/'destino individual'; card.output_dir=str(custom)
        self.assertEqual(self.page._task_for_card(card).output_dir,str(custom))

    def test_narrow_layout_collapses_settings_without_hiding_main_action(self):
        self.page.resize(850,670); self.app.processEvents()
        self.assertEqual(self.page.workspace.orientation(),Qt.Orientation.Vertical)
        self.assertTrue(self.page.compact_settings_toggle.isVisible())
        self.assertFalse(self.page.settings_panel.isVisible())
        self.assertTrue(self.page.convert.isVisible())
        self.page.compact_settings_toggle.click(); self.app.processEvents()
        self.assertTrue(self.page.settings_panel.isVisible())
        self.page.resize(1366,768); self.app.processEvents()
        self.assertEqual(self.page.workspace.orientation(),Qt.Orientation.Horizontal)
        self.assertTrue(self.page.settings_panel.isVisible())

    def test_twenty_files_remain_compact_and_scrollable(self):
        paths=[]
        for number in range(20):
            path=self.folder/f'lote_{number:02d}.wav'; shutil.copyfile(self.audio,path); paths.append(str(path))
        self.page.add_paths(paths); deadline=time.monotonic()+10
        while self.page.probes and time.monotonic()<deadline: self.app.processEvents(); time.sleep(.02)
        self.app.processEvents()
        self.assertEqual(len(self.page.cards),22)
        self.assertTrue(all(card.maximumHeight()<=82 for card in self.page.cards.values()))
        self.assertTrue(self.page.scroll.verticalScrollBar().maximum()>0)
        for path in paths: Path(path).unlink(missing_ok=True)

    def test_mixed_individual_formats_do_not_claim_common_destination(self):
        video,audio=self.cards; video.format.setCurrentText('MKV'); audio.format.setCurrentText('FLAC'); self.page._update_summary()
        self.assertEqual(self.page.convert.text(),'Converter 2 selecionados')

    def test_batch_queues_only_checked_cards(self):
        self.cards[1].set_selected(False); captured=[]
        with patch.object(self.page.queue,'enqueue',side_effect=lambda tasks:captured.extend(tasks)):
            self.page.convert_all()
        self.assertEqual(len(captured),1); self.assertEqual(captured[0].source,self.cards[0].path)

    def test_individual_conversion_works_when_unchecked(self):
        card=self.cards[0]; card.set_selected(False); captured=[]
        with patch.object(self.page.queue,'enqueue',side_effect=lambda tasks:captured.extend(tasks)):
            self.page.convert_individual(card.path)
        self.assertEqual(len(captured),1); self.assertEqual(captured[0].source,card.path)

    def test_redesigned_page_executes_real_ffmpeg_and_emits_library_signal(self):
        audio=next(card for card in self.cards if Path(card.path).suffix.lower()=='.wav')
        completed=[]; self.page.conversion_completed.connect(lambda source,output:completed.append((source,output)))
        self.page.convert_individual(audio.path); deadline=time.monotonic()+15
        while self.page.queue.is_active() and time.monotonic()<deadline: self.app.processEvents(); time.sleep(.02)
        self.app.processEvents()
        self.assertEqual(audio.state,'Concluído'); self.assertTrue(Path(audio.output_path).is_file())
        self.assertEqual(completed[0][0],audio.path); self.assertEqual(completed[0][1],audio.output_path)

    def test_redesigned_page_executes_real_mixed_source_batch(self):
        self.page.convert_all(); deadline=time.monotonic()+20
        while self.page.queue.is_active() and time.monotonic()<deadline: self.app.processEvents(); time.sleep(.02)
        self.app.processEvents()
        self.assertTrue(all(card.state=='Concluído' for card in self.cards))
        self.assertTrue(all(Path(card.output_path).is_file() for card in self.cards))
        self.assertFalse(self.page.cancel.isVisible())

    def test_folder_import_does_not_duplicate_existing_files(self):
        self.page.add_paths([str(self.folder)])
        deadline=time.monotonic()+3
        while self.page.probes and time.monotonic()<deadline: self.app.processEvents(); time.sleep(.02)
        self.assertEqual(len(self.page.cards),2)


if __name__=='__main__': unittest.main()
