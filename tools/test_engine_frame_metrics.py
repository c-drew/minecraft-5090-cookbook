"""Regression checks for timing-window selection and incomplete-log reporting."""
import csv
from pathlib import Path
import tempfile
import unittest

from engine_frame_metrics import read_engine_frames


class EngineFrameMetricsTest(unittest.TestCase):
    def measure(self, rows, start=0.0, end=1.0):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'frames.csv'
            with path.open('w', newline='') as stream:
                writer = csv.writer(stream)
                writer.writerow(['unix_ms', 'total'])
                writer.writerows(rows)
            return read_engine_frames(path, start, end)

    def test_excludes_frames_crossing_either_window_boundary(self):
        result = self.measure([(-100, 150), (0, 100), (100, 300),
                               (400, 200), (900, 200)])
        self.assertEqual(result['frames'], 3)
        self.assertEqual(result['fps'], 5)
        self.assertAlmostEqual(result['one_percent_low'], 1000 / 300)
        self.assertEqual(result['median_ms'], 200)
        self.assertEqual(result['worst_ms'], 300)
        self.assertEqual(result['window_coverage'], 0.6)

    def test_full_window_and_budget_misses(self):
        result = self.measure([(0, 5), (5, 7), (12, 8)], end=0.020)
        self.assertEqual(result['frames'], 3)
        self.assertEqual(result['window_coverage'], 1)
        self.assertEqual(result['over_144_count'], 2)

    def test_empty_window_is_not_reported_as_zero_fps(self):
        with self.assertRaises(ValueError):
            self.measure([(2000, 5)])

    def test_rejects_invalid_windows(self):
        for start, end in [(1, 1), (2, 1), (float('nan'), 2), (0, float('inf'))]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                self.measure([(0, 5)], start, end)

    def test_rejects_corrupt_or_reordered_log(self):
        for rows in [[(0, -1)], [(0, float('nan'))], [(float('inf'), 5)],
                     [(5, 5), (0, 5)]]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.measure(rows)


if __name__ == '__main__':
    unittest.main()
