"""Rode com: python -m unittest discover -s tests"""
import json
import tempfile
import unittest
from pathlib import Path
from fluxora import storage

class StorageTests(unittest.TestCase):
    def test_save_history_and_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            previous=storage.DATA_DIR
            storage.DATA_DIR=Path(temp)
            try:
                repo=storage.Storage()
                repo.config['output_dir']=temp
                repo.save_config()
                video=Path(temp)/'video.mp4'; video.write_bytes(b'mp4')
                self.assertEqual(repo.add_files([video]),1)
                self.assertEqual(repo.add_files([video]),0)
                restored=storage.Storage()
                self.assertEqual(restored.config['output_dir'],temp)
                self.assertEqual(restored.history[0]['title'],'video')
            finally:
                storage.DATA_DIR=previous

    def test_migrates_legacy_cookie_and_caps_unlimited_playlist(self):
        with tempfile.TemporaryDirectory() as temp:
            previous=storage.DATA_DIR
            storage.DATA_DIR=Path(temp)
            try:
                cookie=Path(temp)/'youtube-cookies.txt'; cookie.write_text('cookie',encoding='utf-8')
                (Path(temp)/'config.json').write_text(json.dumps({
                    'browser':'Google Chrome', 'cookie_file':str(cookie), 'playlist_limit':'0'
                }),encoding='utf-8')
                repo=storage.Storage()
                self.assertEqual(repo.config['browser'],'Google Chrome')
                self.assertEqual(repo.config['cookie_file'],str(cookie))
                self.assertEqual(repo.config['playlist_limit'],100)
                self.assertTrue(repo.config_path.is_file())
            finally:
                storage.DATA_DIR=previous

if __name__=='__main__': unittest.main()
