"""Validação das opções do motor sem acessar a rede."""
import tempfile
import unittest
from fluxora.engine import (DownloadCancelled, Downloader, is_playlist_url,
                            is_valid_url, thumbnail_url, yt_options)


class EngineTests(unittest.TestCase):
    def test_url_and_playlist_detection(self):
        self.assertTrue(is_valid_url('https://www.youtube.com/watch?v=abc'))
        self.assertFalse(is_valid_url('arquivo local'))
        self.assertTrue(is_playlist_url('https://www.youtube.com/playlist?list=PL123'))
        self.assertTrue(is_playlist_url('https://www.youtube.com/watch?v=abc&list=PL123'))
        self.assertFalse(is_playlist_url('https://www.youtube.com/watch?v=abc'))

    def test_mp4_selector_always_includes_audio_fallbacks(self):
        with tempfile.TemporaryDirectory() as temp:
            options=yt_options(temp,'MP4','1080p')
        self.assertIn('bestaudio',options['format'])
        self.assertEqual(options['merge_output_format'],'mp4')
        self.assertTrue(options['ffmpeg_location'])

    def test_mp3_uses_ffmpeg_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            options=yt_options(temp,'MP3','320 kbps')
        self.assertEqual(options['format'],'bestaudio/best')
        self.assertEqual(options['postprocessors'][0]['preferredcodec'],'mp3')
        self.assertEqual(options['postprocessors'][0]['preferredquality'],'320')

    def test_single_playlist_item_uses_its_own_progress(self):
        with tempfile.TemporaryDirectory() as temp:
            worker=Downloader('https://example.com/playlist',temp,'MP3','320 kbps',
                              playlist=True,selected=[25])
            updates=[]; worker.progress.connect(updates.append)
            worker.hook({'status':'downloading','total_bytes':100,'downloaded_bytes':50,
                         'info_dict':{'title':'Faixa','playlist_index':25,'playlist_count':100}})
        self.assertEqual(updates[-1]['percent'],50)

    def test_cancel_is_honoured_during_postprocessing(self):
        with tempfile.TemporaryDirectory() as temp:
            worker=Downloader('https://example.com/video',temp,'MP3','320 kbps')
            worker.cancel()
            with self.assertRaises(DownloadCancelled):
                worker.post_hook({'status':'started','info_dict':{}})

    def test_thumbnail_uses_best_flat_playlist_image(self):
        info={'id':'abc123xyz', 'thumbnails':[
            {'url':'https://img/small.jpg','width':120,'height':90},
            {'url':'https://img/large.jpg','width':480,'height':360},
        ]}
        self.assertEqual(thumbnail_url(info),'https://img/large.jpg')

    def test_thumbnail_has_youtube_id_fallback(self):
        self.assertEqual(
            thumbnail_url({'id':'x-_CkcA3u_c','ie_key':'Youtube'}),
            'https://i.ytimg.com/vi/x-_CkcA3u_c/hqdefault.jpg'
        )

    def test_thumbnail_does_not_treat_playlist_id_as_video(self):
        self.assertEqual(
            thumbnail_url({'id':'RDx-_CkcA3u_c','ie_key':'YoutubeTab','_type':'playlist'}),
            ''
        )


if __name__=='__main__': unittest.main()
