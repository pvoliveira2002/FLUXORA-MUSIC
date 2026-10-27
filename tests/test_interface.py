"""Testes rápidos da interface, sem rede nem downloads simulados."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from fluxora.theme import QSS
from fluxora.ui import FluxoraWindow


class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication(sys.argv[:1])
        cls.app.setStyle('Fusion')
        cls.app.setStyleSheet(QSS)

    def setUp(self):
        self.window=FluxoraWindow()
        self.window.storage.config['close_to_tray']=False
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        if self.window.tray: self.window.tray.hide()
        self.window.hide(); self.window.deleteLater(); self.app.processEvents()

    def test_navigation_and_main_controls(self):
        for index in range(4):
            self.window._show_page(index)
            self.assertEqual(self.window.pages.currentIndex(),index)
        self.assertEqual(self.window.windowTitle(),'Fluxora 3.0 | Media Downloader')
        self.assertEqual(self.window.playlist_table.columnCount(),5)

    def test_playlist_population_and_selection(self):
        entries=[{'index':1,'title':'Primeiro','duration':61,'thumbnail':''},
                 {'index':2,'title':'Segundo','duration':125,'thumbnail':''}]
        self.window._populate_playlist(entries)
        self.assertEqual(self.window.playlist_table.rowCount(),2)
        self.assertEqual(self.window.playlist_table.item(0,3).text(),'Primeiro')
        self.assertTrue(self.window.pl_download.isEnabled())
        self.window.select_playlist(False)
        self.assertFalse(self.window.pl_download.isEnabled())

    def test_audio_choice_survives_video_analysis(self):
        self.window.change_type('MP3')
        self.window._analyzed({
            'kind':'video', 'url':'https://example.com/video', 'title':'Vídeo',
            'channel':'Canal', 'duration':60, 'view_count':1, 'thumbnail':'',
            'heights':[1080], 'video_formats':{1080:{'width':1920}},
        })
        self.assertEqual(self.window.preview_media,'Áudio')
        self.assertEqual(self.window.preview_quality,'320 kbps')
        self.assertTrue(self.window.format_combo.currentText().startswith('MP3'))

    def test_audio_choice_survives_playlist_analysis(self):
        self.window.change_type('MP3')
        self.window._analyzed({
            'kind':'playlist', 'url':'https://example.com/playlist?list=1',
            'title':'Playlist', 'channel':'Canal', 'count':1, 'thumbnail':'',
            'entries':[{'index':1,'title':'Faixa','duration':60,'thumbnail':''}],
        })
        self.assertEqual(self.window.pl_media.currentText(),'MP3')
        self.assertEqual(self.window.pl_quality.currentText(),'320 kbps')

    def test_direct_audio_download_launches_as_mp3(self):
        self.window.url_entry.setText('https://example.com/video')
        self.window.change_type('MP3')
        with patch.object(self.window,'_launch_download') as launch:
            self.window.start_download()
        launch.assert_called_once_with(
            'https://example.com/video','MP3','320 kbps',False,None
        )


if __name__=='__main__': unittest.main()
