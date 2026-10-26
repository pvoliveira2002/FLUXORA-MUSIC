"""Validação das opções do motor sem acessar a rede."""
import tempfile
import unittest
from fluxora.engine import is_playlist_url, is_valid_url, yt_options


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


if __name__=='__main__': unittest.main()
