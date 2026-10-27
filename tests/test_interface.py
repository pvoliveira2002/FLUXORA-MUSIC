"""Testes rápidos da interface, sem rede nem downloads simulados."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
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
        for index in range(5):
            self.window._show_page(index)
            self.assertEqual(self.window.pages.currentIndex(),index)
        self.assertEqual(self.window.windowTitle(),'Fluxora 3.1 | Downloads e Conversão de Mídia')
        self.assertEqual(self.window.playlist_table.columnCount(),5)
        self.assertIn('MP3',self.window.converter_page.formats)

    def test_playlist_population_and_selection(self):
        entries=[{'index':1,'title':'Primeiro','duration':61,'thumbnail':''},
                 {'index':2,'title':'Segundo','duration':125,'thumbnail':''}]
        self.window._populate_playlist(entries)
        self.assertEqual(self.window.playlist_table.rowCount(),2)
        self.assertEqual(self.window.playlist_table.item(0,3).text(),'Primeiro')
        self.assertTrue(self.window.pl_download.isEnabled())
        self.window.select_playlist(False)
        self.assertFalse(self.window.pl_download.isEnabled())

    def _fill_playlist(self,count=30):
        entries=[{'index':number+101,'title':f'Música {number+1:03d}','duration':60,'thumbnail':''}
                 for number in range(count)]
        self.window._populate_playlist(entries); self.window._show_page(2); self.app.processEvents()
        return entries

    def _click_playlist(self,row,column=0,modifier=Qt.KeyboardModifier.NoModifier):
        table=self.window.playlist_table
        point=table.visualRect(table.model().index(row,column)).center()
        QTest.mouseClick(table.viewport(),Qt.MouseButton.LeftButton,modifier,point)
        self.app.processEvents()

    def test_playlist_checkbox_individual_and_shift_range(self):
        self._fill_playlist(30); table=self.window.playlist_table
        self.window.select_playlist(False)
        self._click_playlist(1)
        self._click_playlist(19,modifier=Qt.KeyboardModifier.ShiftModifier)
        checked=[row for row in range(30) if table.item(row,0).checkState()==Qt.CheckState.Checked]
        self.assertEqual(checked,list(range(1,20)))
        self.assertEqual(self.window.playlist_selected.text(),'19 vídeos selecionados')

    def test_playlist_shift_can_uncheck_a_range_without_changing_others(self):
        self._fill_playlist(30); table=self.window.playlist_table
        self._click_playlist(1)
        self._click_playlist(19,modifier=Qt.KeyboardModifier.ShiftModifier)
        unchecked=[row for row in range(30) if table.item(row,0).checkState()==Qt.CheckState.Unchecked]
        self.assertEqual(unchecked,list(range(1,20)))
        self.assertEqual(table.item(0,0).checkState(),Qt.CheckState.Checked)
        self.assertEqual(table.item(20,0).checkState(),Qt.CheckState.Checked)

    def test_playlist_ctrl_shift_visual_selection_and_space(self):
        self._fill_playlist(30); table=self.window.playlist_table
        self.window.select_playlist(False)
        self._click_playlist(2,3)
        self._click_playlist(6,3,Qt.KeyboardModifier.ControlModifier)
        selected={index.row() for index in table.selectionModel().selectedRows()}
        self.assertEqual(selected,{2,6})
        QTest.keyClick(table,Qt.Key.Key_Space); self.app.processEvents()
        self.assertEqual({row for row in range(30) if table.item(row,0).checkState()==Qt.CheckState.Checked},{2,6})
        QTest.keyClick(table,Qt.Key.Key_Space); self.app.processEvents()
        self.assertFalse(any(table.item(row,0).checkState()==Qt.CheckState.Checked for row in range(30)))
        self._click_playlist(10,3)
        self._click_playlist(15,3,Qt.KeyboardModifier.ShiftModifier)
        self.assertEqual({index.row() for index in table.selectionModel().selectedRows()},set(range(10,16)))

    def test_playlist_ctrl_a_marks_only_visible_rows_and_search_preserves_checks(self):
        self._fill_playlist(30); table=self.window.playlist_table
        self.window.select_playlist(False); self.window.search_playlist('Música 00')
        table.setFocus(); QTest.keyClick(table,Qt.Key.Key_A,Qt.KeyboardModifier.ControlModifier); QTest.keyClick(table,Qt.Key.Key_Space)
        self.app.processEvents()
        visible=[row for row in range(30) if not table.isRowHidden(row)]
        checked=[row for row in range(30) if table.item(row,0).checkState()==Qt.CheckState.Checked]
        self.assertEqual(checked,visible)
        self.window.search_playlist('Música 030'); self.window.search_playlist('')
        self.assertEqual([row for row in range(30) if table.item(row,0).checkState()==Qt.CheckState.Checked],visible)

    def test_playlist_shift_checkbox_uses_only_visible_filtered_rows(self):
        entries=[{'index':row+1,'title':f'{"Grupo A" if row % 2 == 0 else "Grupo B"} {row}','duration':60,'thumbnail':''}
                 for row in range(20)]
        self.window._populate_playlist(entries); self.window._show_page(2); self.window.select_playlist(False)
        self.window.search_playlist('Grupo A'); self.app.processEvents()
        self._click_playlist(2); self._click_playlist(10,modifier=Qt.KeyboardModifier.ShiftModifier)
        checked=[row for row in range(20) if self.window.playlist_table.item(row,0).checkState()==Qt.CheckState.Checked]
        self.assertEqual(checked,[2,4,6,8,10])

    def test_playlist_handles_300_items_and_preserves_original_download_indices(self):
        entries=self._fill_playlist(300); table=self.window.playlist_table
        self.assertEqual(table.rowCount(),300)
        self.window.select_playlist(False)
        for row in (1,149,299): table.item(row,0).setCheckState(Qt.CheckState.Checked)
        self.window.analyzed_info={'kind':'playlist','url':'https://example.com/list','entries':entries}
        with patch.object(self.window,'_launch_download',return_value=True) as launch:
            self.window.start_playlist_download()
        self.assertEqual([call.args[4] for call in launch.call_args_list],[[102],[250],[400]])
        self.assertEqual(self.window.playlist_selected.text(),'3 vídeos selecionados')

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

    def test_queue_starts_at_most_three_individual_downloads(self):
        def fake_start(job):
            job['card'].start()
            self.window.active_downloads[job['card']]=object()
        with patch.object(self.window,'_start_download_job',side_effect=fake_start):
            for number in range(5):
                self.window._launch_download(
                    f'https://example.com/video/{number}','MP3','320 kbps',False,None,
                    f'Faixa {number}'
                )
        self.assertEqual(len(self.window.active_downloads),3)
        self.assertEqual(len(self.window.pending_downloads),2)
        self.assertEqual(sum(card.state=='Baixando' for card in self.window.download_cards),3)
        self.assertEqual(sum(card.state=='Na fila' for card in self.window.download_cards),2)

    def test_playlist_creates_one_queue_item_per_track(self):
        self.window.change_type('MP3')
        self.window._analyzed({
            'kind':'playlist', 'url':'https://example.com/playlist?list=1',
            'title':'Playlist', 'channel':'Canal', 'count':2, 'thumbnail':'',
            'entries':[{'index':1,'title':'Faixa 1','duration':60,'thumbnail':''},
                       {'index':2,'title':'Faixa 2','duration':90,'thumbnail':''}],
        })
        with patch.object(self.window,'_process_download_queue'):
            self.window.start_playlist_download()
        self.assertEqual(len(self.window.pending_downloads),2)
        self.assertEqual([job['selected'] for job in self.window.pending_downloads],[[1],[2]])
        self.assertEqual([job['card'].title for job in self.window.pending_downloads],['Faixa 1','Faixa 2'])

    def test_cancelled_failed_and_completed_filters_update_and_remove(self):
        with patch.object(self.window,'_process_download_queue'):
            self.window._launch_download('https://example.com/one','MP3','320 kbps',False,None,'Cancelada')
            cancelled=self.window.download_cards[0]
            self.window._cancel_download_card(cancelled)
            self.assertEqual(cancelled.state,'Cancelado')
            self.assertIn('Cancelados (1)',self.window.filter_buttons['Cancelados'].text())

            self.window._launch_download('https://example.com/two','MP3','320 kbps',False,None,'Falha')
            failed=self.window.download_cards[0]
            self.window._failed_download(failed,'Erro de teste detalhado')
            self.assertEqual(failed.state,'Falhou')
            self.assertIn('Falhou (1)',self.window.filter_buttons['Falhou'].text())

            self.window._launch_download('https://example.com/three','MP3','320 kbps',False,None,'Concluída')
            completed=self.window.download_cards[0]
            self.window._finished_download(completed,{'files':[],'url':'','thumbnail':'','count':1})
            self.assertEqual(completed.state,'Concluído')
            self.assertIn('Concluídos (1)',self.window.filter_buttons['Concluídos'].text())

        self.assertFalse(self.window.filter_buttons['Pausados'].isEnabled())
        for filter_name in ('Todos','Na fila','Baixando','Concluídos','Cancelados','Falhou'):
            self.window.filter_buttons[filter_name].click(); self.app.processEvents()
            self.assertEqual(self.window.filter_state,filter_name)
        self.window.filter_buttons['Cancelados'].click(); self.app.processEvents()
        self.assertFalse(cancelled.isHidden())
        self.assertTrue(failed.isHidden()); self.assertTrue(completed.isHidden())
        self.window._remove_download_card(cancelled)
        self.assertNotIn(cancelled,self.window.download_cards)
        self.assertIn('Cancelados (0)',self.window.filter_buttons['Cancelados'].text())


if __name__=='__main__': unittest.main()
