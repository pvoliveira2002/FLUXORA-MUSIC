"""Testes do conversor real com mídias locais pequenas e sem rede."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fluxora.converter import (
    AUDIO_OUTPUTS, VIDEO_OUTPUTS, ConversionError, ConversionQueue, ConversionSettings,
    ConversionTask, available_formats, build_ffmpeg_args, detect_encoders,
    find_ffmpeg, probe_media, progress_values, unique_output_path,
)


class ConverterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv[:1])
        cls.temporary = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.temporary.name)
        cls.ffmpeg = find_ffmpeg()
        cls.encoders = detect_encoders(cls.ffmpeg)
        cls.wav = cls.folder / 'áudio de teste.wav'
        cls.mp4 = cls.folder / 'vídeo de teste.mp4'
        subprocess.run([cls.ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                        '-f', 'lavfi', '-i', 'sine=frequency=700:duration=0.45',
                        '-c:a', 'pcm_s16le', str(cls.wav)], check=True)
        subprocess.run([cls.ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
                        '-f', 'lavfi', '-i', 'color=c=green:s=160x90:d=0.45',
                        '-f', 'lavfi', '-i', 'sine=frequency=500:duration=0.45',
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                        '-shortest', str(cls.mp4)], check=True)

    @classmethod
    def tearDownClass(cls): cls.temporary.cleanup()

    def _convert(self, source, target):
        media = probe_media(source, self.ffmpeg)
        task = ConversionTask(str(source), str(self.folder), ConversionSettings(target), media)
        task.temp_path = str(self.folder / f'resultado-{target.lower()}.{target.lower()}')
        args = build_ffmpeg_args(task, self.encoders)
        result = subprocess.run([self.ffmpeg, *args], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = Path(task.temp_path); self.assertTrue(output.is_file()); self.assertGreater(output.stat().st_size, 0)
        return probe_media(output, self.ffmpeg)

    def test_detects_all_required_formats(self):
        self.assertTrue({'libx264','aac','libmp3lame','pcm_s16le'}.issubset(self.encoders))
        self.assertEqual(available_formats(self.encoders), list(VIDEO_OUTPUTS + AUDIO_OUTPUTS))

    def test_probe_reads_video_audio_duration_and_unicode_path(self):
        media = probe_media(self.mp4, self.ffmpeg)
        self.assertTrue(media.has_video); self.assertTrue(media.has_audio)
        self.assertEqual((media.width, media.height), (160, 90)); self.assertGreater(media.duration, 0)

    def test_real_video_to_audio_and_video_conversions(self):
        mp3 = self._convert(self.mp4, 'MP3'); self.assertTrue(mp3.has_audio); self.assertFalse(mp3.has_video)
        mkv = self._convert(self.mp4, 'MKV'); self.assertTrue(mkv.has_video); self.assertTrue(mkv.has_audio)

    def test_resolution_profile_does_not_upscale_small_video(self):
        media = probe_media(self.mp4, self.ffmpeg)
        task = ConversionTask(str(self.mp4), str(self.folder), ConversionSettings('MP4', resolution='720p'), media,
                              temp_path=str(self.folder / 'sem ampliar.mp4'))
        result = subprocess.run([self.ffmpeg, *build_ffmpeg_args(task, self.encoders)], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        converted = probe_media(task.temp_path, self.ffmpeg)
        self.assertLessEqual(converted.height, media.height)

    def test_real_audio_conversions(self):
        mp3 = self._convert(self.wav, 'MP3'); self.assertTrue(mp3.has_audio)
        wav = self._convert(Path(self.folder / 'resultado-mp3.mp3'), 'WAV'); self.assertTrue(wav.has_audio)

    def test_audio_cannot_become_video_without_visual_source(self):
        media = probe_media(self.wav, self.ffmpeg)
        task = ConversionTask(str(self.wav), str(self.folder), ConversionSettings('MP4'), media,
                              temp_path=str(self.folder / 'inválido.mp4'))
        with self.assertRaises(ConversionError): build_ffmpeg_args(task, self.encoders)

    def test_output_never_overwrites_source_or_existing_file(self):
        first = unique_output_path(self.mp4, self.folder, 'MP4'); first.touch()
        second = unique_output_path(self.mp4, self.folder, 'MP4')
        self.assertNotEqual(first, second); self.assertNotEqual(second.resolve(), self.mp4.resolve())

    def test_progress_and_safe_argument_list(self):
        values = progress_values({'out_time_us':'5000000','speed':'2.0x'}, 10, 2.5)
        self.assertEqual(values['percent'], 50); self.assertEqual(values['eta'], 2.5)
        media = probe_media(self.mp4, self.ffmpeg)
        task = ConversionTask(str(self.mp4), str(self.folder), ConversionSettings('MP3'), media,
                              temp_path=str(self.folder / 'argumento seguro.mp3'))
        args = build_ffmpeg_args(task, self.encoders)
        self.assertIsInstance(args, list); self.assertIn(str(self.mp4), args); self.assertNotIn('shell=True', args)

    def test_queue_converts_multiple_files_sequentially(self):
        media = probe_media(self.wav, self.ffmpeg)
        tasks = [ConversionTask(str(self.wav), str(self.folder), ConversionSettings('MP3'), media) for _ in range(2)]
        queue = ConversionQueue(self.ffmpeg, self.encoders); completed = []; loop = QEventLoop()
        queue.job_completed.connect(lambda task: completed.append(task.output_path))
        queue.queue_finished.connect(loop.quit); QTimer.singleShot(30000, loop.quit)
        queue.enqueue(tasks); loop.exec()
        self.assertFalse(queue.is_active()); self.assertEqual(len(completed), 2)
        self.assertNotEqual(completed[0], completed[1]); self.assertTrue(all(Path(path).is_file() for path in completed))

    def test_cancel_current_continues_with_next_file(self):
        media = probe_media(self.mp4, self.ffmpeg)
        tasks = [ConversionTask(str(self.mp4), str(self.folder), ConversionSettings('WEBM'), media),
                 ConversionTask(str(self.wav), str(self.folder), ConversionSettings('MP3'), probe_media(self.wav, self.ffmpeg))]
        queue = ConversionQueue(self.ffmpeg, self.encoders); cancelled = []; completed = []; loop = QEventLoop()
        queue.job_started.connect(lambda task: QTimer.singleShot(0, queue.cancel_current) if task.id == tasks[0].id else None)
        queue.job_cancelled.connect(lambda task: cancelled.append(task.id)); queue.job_completed.connect(lambda task: completed.append(task.id))
        queue.queue_finished.connect(loop.quit); QTimer.singleShot(30000, loop.quit)
        queue.enqueue(tasks); loop.exec()
        self.assertIn(tasks[0].id, cancelled); self.assertIn(tasks[1].id, completed); self.assertFalse(queue.is_active())


if __name__ == '__main__': unittest.main()
