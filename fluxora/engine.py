"""Integração PySide6/yt-dlp, adaptada do motor do Fluxora 2.1."""
from __future__ import annotations
import re
import shutil
import threading
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import QThread, Signal

try: import yt_dlp
except ImportError: yt_dlp = None
try: import imageio_ffmpeg
except ImportError: imageio_ffmpeg = None

VIDEO_QUALITIES = ['Melhor disponível', '2160p', '1440p', '1080p', '720p', '480p', '360p']
AUDIO_QUALITIES = ['320 kbps', '256 kbps', '192 kbps', '128 kbps']
BROWSERS = {'Não usar cookies': None, 'Google Chrome': 'chrome', 'Microsoft Edge': 'edge',
            'Mozilla Firefox': 'firefox', 'Brave': 'brave'}
MEDIA_EXT = {'.mp4', '.mkv', '.webm', '.mp3', '.m4a', '.wav', '.opus', '.flac', '.mov'}


def javascript_runtime():
    """Localiza o Node portátil da distribuição ou uma instalação do sistema."""
    bundled = Path(__file__).resolve().parents[1] / 'runtime' / 'node.exe'
    if bundled.is_file():
        return str(bundled)
    return shutil.which('node')


def _enable_ejs(opts):
    node = javascript_runtime()
    if node:
        opts['js_runtimes'] = {'node': {'path': node}}
        # O pacote yt-dlp-ejs vai incluído na distribuição; o fallback remoto
        # permite acompanhar desafios novos sem reinstalar todo o aplicativo.
        opts['remote_components'] = ['ejs:github']


def is_valid_url(url):
    item = urlparse(url)
    return item.scheme in {'http', 'https'} and bool(item.netloc)


def is_playlist_url(url):
    item = urlparse(url)
    args = parse_qs(item.query)
    return any(args.get(key) for key in ('list', 'playlist', 'set')) or any(
        part in item.path.lower() for part in ('/playlist', '/playlists/', '/sets/'))


def format_bytes(count):
    count = float(count or 0)
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if count < 1024: return f'{count:.1f} {unit}'
        count /= 1024
    return f'{count:.1f} PB'


def thumbnail_url(info):
    """Retorna a melhor miniatura disponível em metadados normais ou flat."""
    if not isinstance(info,dict): return ''
    if info.get('thumbnail'): return str(info['thumbnail'])
    candidates=[item for item in (info.get('thumbnails') or [])
                if isinstance(item,dict) and item.get('url')]
    if candidates:
        def score(item):
            width=int(item.get('width') or 0); height=int(item.get('height') or 0)
            return (width*height,width,height)
        return str(max(candidates,key=score)['url'])
    video_id=str(info.get('id') or '')
    if re.fullmatch(r'[A-Za-z0-9_-]{6,}',video_id):
        extractor=str(info.get('extractor_key') or info.get('ie_key') or '').lower()
        if extractor=='youtube': return f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg'
    return ''


def yt_options(output, media_type='MP4', quality='Melhor disponível', browser=None,
               cookie_file=None, playlist=False, playlist_limit=0, selected=None,
               progress_hook=None, post_hook=None):
    if yt_dlp is None: raise RuntimeError('yt-dlp não está instalado. Execute instalar.bat.')
    if imageio_ffmpeg is None: raise RuntimeError('imageio-ffmpeg não está instalado. Execute instalar.bat.')
    opts = {
        'outtmpl': str(Path(output) / ('%(playlist_index)02d - %(title).180B.%(ext)s' if playlist
                                       else '%(title).180B.%(ext)s')),
        'ffmpeg_location': str(Path(imageio_ffmpeg.get_ffmpeg_exe())),
        'progress_hooks': [progress_hook] if progress_hook else [],
        'postprocessor_hooks': [post_hook] if post_hook else [],
        'noplaylist': not playlist,
        'windowsfilenames': True, 'quiet': True,
        'retries': 3, 'fragment_retries': 3,
    }
    _enable_ejs(opts)
    if browser:
        opts['user_agent'] = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                              'AppleWebKit/537.36 (KHTML, like Gecko) '
                              'Chrome/131.0.0.0 Safari/537.36') if browser != 'firefox' else None
        if not opts['user_agent']: opts.pop('user_agent')
    if cookie_file: opts['cookiefile'] = str(cookie_file)
    elif browser: opts['cookiesfrombrowser'] = (browser,)
    if playlist and playlist_limit: opts['playlistend'] = int(playlist_limit)
    if playlist and selected: opts['playlist_items'] = ','.join(map(str, selected))
    if media_type == 'MP3':
        bitrate = re.search(r'\d+', quality)
        opts.update({'format': 'bestaudio/best', 'postprocessors': [{
            'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3',
            'preferredquality': bitrate.group(0) if bitrate else '320',
        }]})
    else:
        limit_match = re.search(r'\d+', quality)
        limit = int(limit_match.group(0)) if limit_match else None
        selector = (
            f'bestvideo[height<={limit}][ext=mp4]+bestaudio[ext=m4a]/'
            f'bestvideo[height<={limit}]+bestaudio/best[height<={limit}]/best'
            if limit else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best'
        )
        opts.update({'format': selector, 'merge_output_format': 'mp4',
                     'postprocessors': [{'key': 'FFmpegVideoRemuxer', 'preferedformat': 'mp4'}]})
    return opts


def info_options(browser=None, cookie_file=None, playlist=False, limit=100):
    if yt_dlp is None: raise RuntimeError('Instale yt-dlp para analisar links.')
    opts = {'quiet': True, 'skip_download': True, 'noplaylist': not playlist}
    _enable_ejs(opts)
    if cookie_file: opts['cookiefile'] = cookie_file
    elif browser: opts['cookiesfrombrowser'] = (browser,)
    if playlist:
        opts['extract_flat'] = 'in_playlist'
        opts['playlistend'] = max(1, int(limit))
    return opts


class Analyzer(QThread):
    analyzed = Signal(object)
    failed = Signal(str)
    def __init__(self, url, browser=None, cookies=None, playlist=False, limit=100, parent=None):
        super().__init__(parent)
        self.url, self.browser, self.cookies = url, browser, cookies
        self.playlist, self.limit = playlist, limit

    def run(self):
        try:
            if not is_valid_url(self.url): raise ValueError('Informe um link HTTP ou HTTPS válido.')
            with yt_dlp.YoutubeDL(info_options(self.browser, self.cookies, self.playlist, self.limit)) as ydl:
                info = ydl.extract_info(self.url, download=False) or {}
            if self.playlist:
                entries = []
                for number, item in enumerate(info.get('entries') or [], 1):
                    if not item: continue
                    entries.append({'index': int(item.get('playlist_index') or number),
                                    'title': item.get('title') or f'Vídeo {number}',
                                    'duration': item.get('duration'),
                                    'thumbnail': thumbnail_url(item),
                                    'url': item.get('webpage_url') or item.get('url', '')})
                self.analyzed.emit({'kind': 'playlist', 'url': self.url,
                                    'title': info.get('title', 'Playlist'),
                                    'channel': info.get('uploader', ''),
                                    'count': info.get('playlist_count') or info.get('n_entries'),
                                    'entries': entries,
                                    'thumbnail': thumbnail_url(info)})
            else:
                formats = info.get('formats', [])
                heights = sorted({int(f.get('height')) for f in formats
                                  if f.get('height') and f.get('vcodec') != 'none'}, reverse=True)
                video_formats = {}
                for item in formats:
                    if not item.get('height') or item.get('vcodec') == 'none': continue
                    height = int(item['height'])
                    width = int(item.get('width') or 0)
                    if width > video_formats.get(height, {}).get('width', 0):
                        video_formats[height] = {'width': width, 'height': height,
                                                 'ext': item.get('ext') or ''}
                self.analyzed.emit({'kind': 'video', 'url': self.url,
                                    'title': info.get('title') or 'Mídia',
                                    'channel': info.get('uploader') or info.get('channel') or '',
                                    'duration': info.get('duration'),
                                    'view_count': info.get('view_count'),
                                    'thumbnail': thumbnail_url(info),
                                    'heights': heights, 'video_formats': video_formats})
        except Exception as exc:
            self.failed.emit(str(exc).replace('ERROR: ', '').strip())


class DownloadCancelled(Exception): pass


class Downloader(QThread):
    progress = Signal(object)
    completed = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    thumbnail = Signal(str)
    def __init__(self, url, output, media_type, quality, browser=None, cookies=None,
                 playlist=False, playlist_limit=100, selected=None, parent=None):
        super().__init__(parent)
        self.url = url
        self.output = Path(output)
        self.media_type, self.quality = media_type, quality
        self.browser, self.cookies = browser, cookies
        self.playlist, self.playlist_limit, self.selected = playlist, playlist_limit, selected
        self.stop_flag = threading.Event()
        self.seen_thumbnail = ''
        self.produced_files = set()

    def cancel(self): self.stop_flag.set()

    def hook(self, data):
        if self.stop_flag.is_set(): raise DownloadCancelled()
        info = data.get('info_dict') or {}
        thumb = thumbnail_url(info)
        if thumb and thumb != self.seen_thumbnail:
            self.seen_thumbnail = thumb
            self.thumbnail.emit(thumb)
        if data.get('status') == 'downloading':
            total = data.get('total_bytes') or data.get('total_bytes_estimate') or 0
            received = data.get('downloaded_bytes') or 0
            percent = int(received / total * 100) if total else 0
            idx, count = info.get('playlist_index'), info.get('playlist_count') or info.get('n_entries')
            full_percent = (percent if self.selected and len(self.selected)==1 else
                            int(((idx - 1) + percent / 100) * 100 / count) if idx and count else percent)
            self.progress.emit({'percent': min(100, full_percent),
                                'item_percent': percent,
                                'title': info.get('title') or 'Mídia',
                                'speed': format_bytes(data.get('speed'))+'/s' if data.get('speed') else '',
                                'eta': data.get('eta'), 'stage': 'Baixando'})
        elif data.get('status') == 'finished':
            filename=data.get('filename') or info.get('filepath') or info.get('_filename')
            if filename: self.produced_files.add(str(filename))
            self.progress.emit({'percent': 99, 'title': info.get('title') or 'Mídia',
                                'stage': 'Convertendo / finalizando'})

    def post_hook(self, data):
        if self.stop_flag.is_set(): raise DownloadCancelled()
        info=data.get('info_dict') or {}
        filename=info.get('filepath') or data.get('filepath') or info.get('_filename')
        if filename: self.produced_files.add(str(filename))

    def run(self):
        try:
            if not is_valid_url(self.url): raise ValueError('Endereço de vídeo inválido.')
            self.output.mkdir(parents=True, exist_ok=True)
            before = {str(p) for p in self.output.iterdir() if p.is_file()}
            opts = yt_options(self.output, self.media_type, self.quality,
                              self.browser, self.cookies, self.playlist, self.playlist_limit,
                              self.selected, self.hook, self.post_hook)
            with yt_dlp.YoutubeDL(opts) as ydl:
                data = ydl.extract_info(self.url, download=True) or {}
            after=[]
            for value in self.produced_files:
                candidate=Path(value)
                if candidate.is_file() and candidate.suffix.lower() in MEDIA_EXT: after.append(candidate)
                elif self.media_type=='MP3':
                    converted=candidate.with_suffix('.mp3')
                    if converted.is_file(): after.append(converted)
            if not after:
                after = [p for p in self.output.iterdir() if p.is_file()
                         and str(p) not in before and p.suffix.lower() in MEDIA_EXT]
            after=list(dict.fromkeys(after))
            if not after and data.get('_type') != 'playlist':
                # O arquivo pode já existir. O yt-dlp não precisa baixar novamente.
                title = str(data.get('title') or '')
                if title:
                    after = [p for p in self.output.iterdir()
                             if p.is_file() and p.suffix.lower() in MEDIA_EXT
                             and title[:20].lower() in p.stem.lower()]
            self.completed.emit({'title': data.get('title') or 'Download concluído',
                                 'files': [str(p) for p in after],
                                 'url': self.url, 'thumbnail': self.seen_thumbnail,
                                 'count': len(after)})
        except Exception as exc:
            if self.stop_flag.is_set() or isinstance(exc, DownloadCancelled):
                self.cancelled.emit()
            else:
                message = str(exc).replace('ERROR: ', '').strip()
                if 'DPAPI' in message: message += '\nExperimente cookies.txt ou Mozilla Firefox.'
                self.failed.emit(message)


class ImageFetcher(QThread):
    loaded = Signal(str, bytes)
    def __init__(self, url, parent=None): super().__init__(parent); self.url = url
    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=9) as response:
                if response.headers.get('Content-Length') and int(response.headers.get('Content-Length')) > 3_000_000:
                    return
                data = response.read(3_000_000)
            if data: self.loaded.emit(self.url, data)
        except Exception: pass
