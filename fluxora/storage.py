"""Preferências e histórico local do Fluxora."""
from __future__ import annotations
import json
import os
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share')) / 'Fluxora'

class Storage:
    def __init__(self):
        self.config_path = DATA_DIR / 'config-qt.json'
        self.library_path = DATA_DIR / 'biblioteca-qt.json'
        defaults = {
            'output_dir': str(Path.home() / 'Downloads'),
            'browser': 'Não usar cookies', 'cookie_file': '',
            'playlist_limit': 100, 'close_to_tray': True,
        }
        self.config = self._read(self.config_path, defaults)
        if not self.config_path.exists():
            self._migrate_legacy_config(defaults)
        self.history = self._read(self.library_path, [])
        if not isinstance(self.history, list): self.history = []

    def _migrate_legacy_config(self, defaults):
        """Importa preferências do Fluxora 2.x uma única vez."""
        legacy = self._read(DATA_DIR / 'config.json', {})
        if not legacy:
            return
        migrated = dict(defaults)
        for key in ('output_dir', 'browser', 'cookie_file'):
            if legacy.get(key):
                migrated[key] = legacy[key]
        try:
            old_limit = int(legacy.get('playlist_limit', 100))
        except (TypeError, ValueError):
            old_limit = 100
        # Na versão antiga, zero significava milhares de itens. A 3.0 usa um
        # teto seguro para manter análise e interface responsivas.
        migrated['playlist_limit'] = min(500, max(1, old_limit or 100))
        self.config = migrated
        self.save_config()

    @staticmethod
    def _read(path, fallback):
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            return value if type(value) is type(fallback) else fallback
        except (OSError, ValueError): return fallback

    @staticmethod
    def _write(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(path)

    def save_config(self): self._write(self.config_path, self.config)

    def add_files(self, paths, source_url='', thumb_url=''):
        current = {x.get('path') for x in self.history}
        count = 0
        for path in paths:
            path = Path(path)
            if not path.exists() or str(path) in current: continue
            self.history.insert(0, {
                'path': str(path), 'title': path.stem,
                'type': 'audio' if path.suffix.lower() in {'.mp3','.m4a','.wav','.opus','.flac'} else 'video',
                'size': path.stat().st_size,
                'created_at': datetime.now().isoformat(timespec='minutes'),
                'source_url': source_url, 'thumbnail': thumb_url,
            })
            count += 1
        self.history = self.history[:500]
        if count: self._write(self.library_path, self.history)
        return count
