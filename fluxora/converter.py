"""Conversão local de mídia com FFmpeg e integração assíncrona ao Qt."""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

try:
    import imageio_ffmpeg
except ImportError:
    imageio_ffmpeg = None


VIDEO_INPUTS={'.mp4','.mkv','.avi','.mov','.webm','.m4v','.mpeg','.mpg','.wmv'}
AUDIO_INPUTS={'.mp3','.wav','.flac','.m4a','.aac','.ogg','.opus','.wma'}
SUPPORTED_INPUTS=VIDEO_INPUTS|AUDIO_INPUTS
VIDEO_OUTPUTS=('MP4','MKV','AVI','MOV','WEBM')
AUDIO_OUTPUTS=('MP3','WAV','FLAC','M4A','OGG')
QUALITY_PROFILES=('Alta qualidade','Equilibrado','Compacto')
RESOLUTIONS=('Original','1080p','720p','480p')
BITRATES=('128 kbps','192 kbps','256 kbps','320 kbps')

_log = logging.getLogger('fluxora.converter')
if not _log.handlers:
    log_dir = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share')) / 'Fluxora'
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_dir / 'fluxora.log', encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        _log.addHandler(handler); _log.setLevel(logging.INFO)
    except OSError:
        _log.addHandler(logging.NullHandler())


class ConversionError(RuntimeError):
    pass


@dataclass
class MediaInfo:
    path: str
    duration: float = 0.0
    size: int = 0
    has_video: bool = False
    has_audio: bool = False
    width: int = 0
    height: int = 0
    video_codec: str = ''
    audio_codec: str = ''
    error: str = ''


@dataclass
class ConversionSettings:
    output_format: str
    quality: str = 'Equilibrado'
    resolution: str = 'Original'
    keep_aspect: bool = True
    bitrate: str = '192 kbps'


@dataclass
class ConversionTask:
    source: str
    output_dir: str
    settings: ConversionSettings
    media: MediaInfo
    id: str = field(default_factory=lambda:uuid.uuid4().hex)
    output_path: str = ''
    temp_path: str = ''
    error: str = ''


def _creation_flags():
    return getattr(subprocess,'CREATE_NO_WINDOW',0) if os.name=='nt' else 0


def find_ffmpeg(configured: str | None = None) -> str:
    if configured and Path(configured).is_file(): return str(Path(configured).resolve())
    found=shutil.which('ffmpeg')
    if found: return str(Path(found).resolve())
    if imageio_ffmpeg is not None:
        try:
            bundled=Path(imageio_ffmpeg.get_ffmpeg_exe())
            if bundled.is_file(): return str(bundled.resolve())
        except (OSError, RuntimeError): pass
    raise ConversionError('FFmpeg não foi encontrado. Execute instalar.bat ou configure um FFmpeg válido.')


def find_ffprobe(ffmpeg_path: str | None = None, configured: str | None = None) -> str | None:
    if configured and Path(configured).is_file(): return str(Path(configured).resolve())
    found=shutil.which('ffprobe')
    if found: return str(Path(found).resolve())
    if ffmpeg_path:
        sibling=Path(ffmpeg_path).with_name('ffprobe.exe' if os.name=='nt' else 'ffprobe')
        if sibling.is_file(): return str(sibling.resolve())
    return None


def detect_encoders(ffmpeg_path: str) -> set[str]:
    try:
        result=subprocess.run([ffmpeg_path,'-hide_banner','-encoders'],capture_output=True,
                              text=True,encoding='utf-8',errors='replace',timeout=15,
                              creationflags=_creation_flags())
    except (OSError,subprocess.SubprocessError) as exc:
        raise ConversionError(f'Não foi possível consultar os encoders do FFmpeg: {exc}') from exc
    text=(result.stdout or '')+'\n'+(result.stderr or '')
    return {match.group(1) for match in re.finditer(r'^\s*[VAS][A-Z.]{5}\s+([\w-]+)\s',text,re.MULTILINE)}


def available_formats(encoders: set[str]) -> list[str]:
    requirements={
        'MP4':{'libx264','aac'}, 'MKV':{'libx264','aac'}, 'MOV':{'libx264','aac'},
        'WEBM':{'libvpx-vp9','libopus'}, 'AVI':{'mpeg4','libmp3lame'},
        'MP3':{'libmp3lame'}, 'WAV':{'pcm_s16le'}, 'FLAC':{'flac'},
        'M4A':{'aac'}, 'OGG':{'libvorbis'},
    }
    return [name for name in VIDEO_OUTPUTS+AUDIO_OUTPUTS if requirements[name].issubset(encoders)]


def _seconds(value: str) -> float:
    try:
        hours,minutes,seconds=value.split(':')
        return int(hours)*3600+int(minutes)*60+float(seconds)
    except (ValueError,AttributeError): return 0.0


def probe_media(path: str | Path, ffmpeg_path: str | None = None,
                ffprobe_path: str | None = None) -> MediaInfo:
    source=Path(path)
    if not source.is_file(): raise ConversionError('O arquivo selecionado não existe.')
    ffmpeg_path=ffmpeg_path or find_ffmpeg()
    ffprobe_path=ffprobe_path or find_ffprobe(ffmpeg_path)
    if ffprobe_path:
        try:
            result=subprocess.run([ffprobe_path,'-v','error','-show_format','-show_streams',
                                   '-of','json',str(source)],capture_output=True,text=True,
                                  encoding='utf-8',errors='replace',timeout=20,
                                  creationflags=_creation_flags())
            data=json.loads(result.stdout or '{}') if result.returncode==0 else {}
            streams=data.get('streams') or []
            video=next((x for x in streams if x.get('codec_type')=='video'),{})
            audio=next((x for x in streams if x.get('codec_type')=='audio'),{})
            duration=float((data.get('format') or {}).get('duration') or 0)
            if streams:
                return MediaInfo(str(source),duration,source.stat().st_size,bool(video),bool(audio),
                                 int(video.get('width') or 0),int(video.get('height') or 0),
                                 str(video.get('codec_name') or ''),str(audio.get('codec_name') or ''))
        except (OSError,ValueError,subprocess.SubprocessError): pass
    try:
        result=subprocess.run([ffmpeg_path,'-hide_banner','-i',str(source)],capture_output=True,
                              text=True,encoding='utf-8',errors='replace',timeout=20,
                              creationflags=_creation_flags())
    except (OSError,subprocess.SubprocessError) as exc:
        raise ConversionError(f'Não foi possível ler o arquivo: {exc}') from exc
    details=(result.stderr or '')+'\n'+(result.stdout or '')
    duration_match=re.search(r'Duration:\s*(\d+:\d+:\d+(?:\.\d+)?)',details)
    video_match=re.search(r'Video:\s*([^,\s]+).*?\b(\d{2,5})x(\d{2,5})\b',details)
    audio_match=re.search(r'Audio:\s*([^,\s]+)',details)
    if not video_match and not audio_match:
        raise ConversionError('O arquivo não contém streams de vídeo ou áudio reconhecíveis.')
    return MediaInfo(str(source),_seconds(duration_match.group(1)) if duration_match else 0,
                     source.stat().st_size,bool(video_match),bool(audio_match),
                     int(video_match.group(2)) if video_match else 0,
                     int(video_match.group(3)) if video_match else 0,
                     video_match.group(1) if video_match else '',audio_match.group(1) if audio_match else '')


def unique_output_path(source: str | Path, output_dir: str | Path, output_format: str) -> Path:
    source=Path(source); directory=Path(output_dir); extension='.'+output_format.lower()
    candidate=directory/f'{source.stem} (convertido){extension}'
    number=2
    while candidate.exists() or candidate.resolve()==source.resolve():
        candidate=directory/f'{source.stem} (convertido {number}){extension}'; number += 1
    return candidate


def _bitrate_value(value: str) -> str:
    match=re.search(r'\d+',value or '')
    return (match.group(0) if match else '192')+'k'


def build_ffmpeg_args(task: ConversionTask, encoders: set[str]) -> list[str]:
    source=Path(task.source); settings=task.settings; target=settings.output_format.upper()
    if not source.is_file(): raise ConversionError('O arquivo de origem não existe mais.')
    if target not in VIDEO_OUTPUTS+AUDIO_OUTPUTS: raise ConversionError('Formato de saída não suportado.')
    if target in VIDEO_OUTPUTS and not task.media.has_video:
        raise ConversionError('Não é possível criar vídeo a partir de um arquivo somente de áudio sem uma fonte visual.')
    if target in AUDIO_OUTPUTS and not task.media.has_audio:
        raise ConversionError('O arquivo não possui uma faixa de áudio para extrair ou converter.')
    required={
        'MP4':('libx264','aac'),'MKV':('libx264','aac'),'MOV':('libx264','aac'),
        'WEBM':('libvpx-vp9','libopus'),'AVI':('mpeg4','libmp3lame'),
        'MP3':('libmp3lame',),'WAV':('pcm_s16le',),'FLAC':('flac',),
        'M4A':('aac',),'OGG':('libvorbis',),
    }[target]
    missing=[codec for codec in required if codec not in encoders]
    if missing: raise ConversionError('O codec necessário não está disponível: '+', '.join(missing))
    args=['-hide_banner','-nostdin','-y','-i',str(source)]
    quality=settings.quality if settings.quality in QUALITY_PROFILES else 'Equilibrado'
    bitrate=_bitrate_value(settings.bitrate)
    if target in VIDEO_OUTPUTS:
        args += ['-map','0:v:0','-map','0:a:0?']
        if settings.resolution!='Original':
            height={'1080p':1080,'720p':720,'480p':480}.get(settings.resolution)
            if height:
                if settings.keep_aspect: args += ['-vf',f'scale=-2:min({height}\\,ih)']
                else: args += ['-vf',f'scale={height*16//9}:{height}']
        if target in ('MP4','MKV','MOV'):
            crf={'Alta qualidade':'18','Equilibrado':'23','Compacto':'28'}[quality]
            args += ['-c:v','libx264','-preset','medium','-crf',crf,'-c:a','aac','-b:a',bitrate]
            if target in ('MP4','MOV'): args += ['-movflags','+faststart']
        elif target=='WEBM':
            crf={'Alta qualidade':'24','Equilibrado':'32','Compacto':'38'}[quality]
            args += ['-c:v','libvpx-vp9','-crf',crf,'-b:v','0','-c:a','libopus','-b:a',bitrate]
        else:
            scale={'Alta qualidade':'2','Equilibrado':'5','Compacto':'8'}[quality]
            args += ['-c:v','mpeg4','-q:v',scale,'-c:a','libmp3lame','-b:a',bitrate]
    else:
        args += ['-map','0:a:0','-vn']
        if target=='MP3': args += ['-c:a','libmp3lame','-b:a',bitrate]
        elif target=='WAV': args += ['-c:a','pcm_s16le']
        elif target=='FLAC': args += ['-c:a','flac']
        elif target=='M4A': args += ['-c:a','aac','-b:a',bitrate]
        elif target=='OGG': args += ['-c:a','libvorbis','-b:a',bitrate]
    args += ['-progress','pipe:1','-nostats',task.temp_path]
    return args


def progress_values(fields: dict[str,str], duration: float, elapsed: float) -> dict:
    processed=0.0
    if fields.get('out_time_us'):
        try: processed=float(fields['out_time_us'])/1_000_000
        except ValueError: pass
    elif fields.get('out_time'):
        processed=_seconds(fields['out_time'])
    percent=min(99,max(0,int(processed/duration*100))) if duration>0 else -1
    eta=(elapsed*(100-percent)/percent) if percent>0 else None
    return {'percent':percent,'processed':processed,'elapsed':elapsed,
            'speed':fields.get('speed',''),'eta':eta}


class ConversionQueue(QObject):
    job_started=Signal(object)
    job_progress=Signal(object,object)
    job_completed=Signal(object)
    job_failed=Signal(object,str)
    job_cancelled=Signal(object)
    queue_changed=Signal()
    queue_finished=Signal()

    def __init__(self, ffmpeg_path: str, encoders: set[str], parent=None):
        super().__init__(parent); self.ffmpeg_path=ffmpeg_path; self.encoders=encoders
        self.pending=[]; self.current=None; self.process=None; self.cancelled=False; self.stop_after_cancel=False
        self._stdout=''; self._stderr=''; self._fields={}; self._started=0.0

    def enqueue(self,tasks):
        self.pending.extend(tasks); self.queue_changed.emit(); self._start_next()

    def remove_pending(self,task_id):
        for index,task in enumerate(self.pending):
            if task.id==task_id:
                self.pending.pop(index); self.job_cancelled.emit(task); self.queue_changed.emit(); return True
        return False

    def cancel_all(self):
        for task in self.pending: self.job_cancelled.emit(task)
        self.pending.clear(); self.cancelled=True; self.stop_after_cancel=True; self.queue_changed.emit()
        if self.process and self.process.state()!=QProcess.ProcessState.NotRunning:
            self.process.terminate(); QTimer.singleShot(1800,self._kill_if_running)
        elif not self.current: self.queue_finished.emit()

    def cancel_current(self):
        if not self.current or not self.process: return False
        self.cancelled=True; self.stop_after_cancel=False
        if self.process.state()!=QProcess.ProcessState.NotRunning:
            self.process.terminate(); QTimer.singleShot(1800,self._kill_if_running)
        return True

    def _kill_if_running(self):
        if self.process and self.process.state()!=QProcess.ProcessState.NotRunning: self.process.kill()

    def _start_next(self):
        if self.current or not self.pending:
            if not self.current and not self.pending: self.queue_finished.emit()
            return
        self.cancelled=False; self.stop_after_cancel=False; self.current=self.pending.pop(0); task=self.current
        try:
            source=Path(task.source); output_dir=Path(task.output_dir)
            output_dir.mkdir(parents=True,exist_ok=True)
            if not os.access(output_dir,os.W_OK): raise ConversionError('A pasta de destino não permite gravação.')
            free=shutil.disk_usage(output_dir).free
            if free < max(source.stat().st_size*2,20*1024*1024):
                raise ConversionError('Não há espaço livre suficiente para realizar a conversão com segurança.')
            output=unique_output_path(source,output_dir,task.settings.output_format)
            temp=output.with_name(f'.{output.stem}.fluxora-{uuid.uuid4().hex[:8]}{output.suffix}')
            task.output_path=str(output); task.temp_path=str(temp)
            args=build_ffmpeg_args(task,self.encoders)
        except Exception as exc:
            self.current=None; task.error=str(exc); self.job_failed.emit(task,str(exc)); self.queue_changed.emit()
            QTimer.singleShot(0,self._start_next); return
        self._stdout=''; self._stderr=''; self._fields={}; self._started=time.monotonic()
        process=QProcess(self); self.process=process
        process.setProgram(self.ffmpeg_path); process.setArguments(args)
        process.readyReadStandardOutput.connect(self._read_stdout)
        process.readyReadStandardError.connect(self._read_stderr)
        process.finished.connect(self._finished)
        process.errorOccurred.connect(self._process_error)
        _log.info('Iniciando conversão: %s -> %s', task.source, task.settings.output_format)
        self.job_started.emit(task); self.queue_changed.emit(); process.start()

    def _read_stdout(self):
        self._stdout += bytes(self.process.readAllStandardOutput()).decode('utf-8','replace')
        while '\n' in self._stdout:
            line,self._stdout=self._stdout.split('\n',1); line=line.strip()
            if '=' not in line: continue
            key,value=line.split('=',1); self._fields[key]=value
            if key in ('out_time_us','out_time','progress'):
                values=progress_values(self._fields,self.current.media.duration,time.monotonic()-self._started)
                self.job_progress.emit(self.current,values)

    def _read_stderr(self):
        self._stderr += bytes(self.process.readAllStandardError()).decode('utf-8','replace')
        if len(self._stderr)>120_000: self._stderr=self._stderr[-120_000:]

    def _process_error(self,error):
        if error==QProcess.ProcessError.FailedToStart and self.current:
            self._stderr='O processo FFmpeg não pôde ser iniciado.'
            if self.process and self.process.state()==QProcess.ProcessState.NotRunning:
                QTimer.singleShot(0,lambda:self._finished(-1,QProcess.ExitStatus.CrashExit) if self.current else None)

    def _finished(self,exit_code,_exit_status):
        task=self.current; self.current=None
        if not task: return
        temp=Path(task.temp_path)
        if self.cancelled:
            try: temp.unlink(missing_ok=True)
            except OSError: pass
            self.job_cancelled.emit(task)
            _log.info('Conversão cancelada: %s', task.source)
        elif exit_code==0 and temp.is_file() and temp.stat().st_size>0:
            try:
                destination=Path(task.output_path)
                if destination.exists(): destination=unique_output_path(task.source,task.output_dir,task.settings.output_format)
                os.replace(temp,destination); task.output_path=str(destination)
                self.job_progress.emit(task,{'percent':100,'processed':task.media.duration,
                                             'elapsed':time.monotonic()-self._started,'speed':'','eta':0})
                self.job_completed.emit(task)
                _log.info('Conversão concluída: %s', task.output_path)
            except OSError as exc:
                task.error=f'Não foi possível finalizar o arquivo: {exc}'; self.job_failed.emit(task,task.error)
        else:
            try: temp.unlink(missing_ok=True)
            except OSError: pass
            technical=self._stderr.strip() or f'FFmpeg encerrou com código {exit_code}.'
            task.error=technical
            _log.error('Falha na conversão de %s: %s', task.source, technical)
            self.job_failed.emit(task,'Não foi possível converter o arquivo. Consulte os detalhes técnicos.')
        if self.process: self.process.deleteLater()
        self.process=None; self.queue_changed.emit()
        if self.cancelled and self.stop_after_cancel:
            self.cancelled=False; self.stop_after_cancel=False; self.queue_finished.emit()
        else:
            self.cancelled=False; QTimer.singleShot(0,self._start_next)

    def is_active(self):
        return bool(self.current or self.pending)

    def shutdown(self):
        self.cancel_all()
        if self.process and self.process.state()!=QProcess.ProcessState.NotRunning:
            self.process.kill(); return self.process.waitForFinished(2500)
        return True
