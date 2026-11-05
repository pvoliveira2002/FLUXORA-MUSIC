from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from fluxora.screen_recorder import (
    ScreenRecorderError, ScreenRecordingSettings, build_screen_recording_args,
    unique_recording_path,
)
from fluxora.screen_recorder_ui import format_elapsed


class ScreenRecorderTests(unittest.TestCase):
    def test_builds_full_desktop_mp4_command(self):
        settings = ScreenRecordingSettings('C:/Videos', fps=30, quality='Equilibrada', draw_cursor=True)
        args = build_screen_recording_args(settings, 'C:/Videos/teste.mp4', platform='win32')
        self.assertIn('gdigrab', args)
        self.assertIn('desktop', args)
        self.assertIn('libx264', args)
        self.assertIn('yuv420p', args)
        self.assertIn('pad=ceil(iw/2)*2:ceil(ih/2)*2', args)
        self.assertEqual(args[args.index('-draw_mouse') + 1], '1')
        self.assertNotIn('-video_size', args)
        self.assertEqual(args[-1], 'C:/Videos/teste.mp4')

    def test_builds_selected_monitor_area_with_even_dimensions(self):
        settings = ScreenRecordingSettings('C:/Videos', fps=60, quality='Alta', draw_cursor=False,
                                           x=-1920, y=0, width=1919, height=1079)
        args = build_screen_recording_args(settings, 'saida.mp4', platform='win32')
        self.assertEqual(args[args.index('-offset_x') + 1], '-1920')
        self.assertEqual(args[args.index('-video_size') + 1], '1918x1078')
        self.assertEqual(args[args.index('-draw_mouse') + 1], '0')

    def test_rejects_invalid_configuration_and_non_windows(self):
        with self.assertRaises(ScreenRecorderError):
            build_screen_recording_args(ScreenRecordingSettings('.', fps=25), 'saida.mp4', platform='win32')
        with self.assertRaises(ScreenRecorderError):
            build_screen_recording_args(ScreenRecordingSettings('.'), 'saida.mp4', platform='linux')

    def test_unique_name_does_not_overwrite_existing_recording(self):
        with tempfile.TemporaryDirectory() as folder:
            moment = datetime(2026, 11, 5, 14, 30, 0)
            first = unique_recording_path(folder, moment)
            first.touch()
            second = unique_recording_path(folder, moment)
            self.assertEqual(second.name, 'Gravacao Fluxora 2026-11-05 14-30-00 (2).mp4')

    def test_elapsed_clock_format(self):
        self.assertEqual(format_elapsed(0), '00:00:00')
        self.assertEqual(format_elapsed(3661), '01:01:01')


if __name__ == '__main__':
    unittest.main()
