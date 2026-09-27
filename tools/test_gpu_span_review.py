"""Reject logs that could give misleading CPU/GPU timing comparisons."""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('gpu_span_review', Path(__file__).with_name('gpu-span-review.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TimingIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.cpu = [dict(frame=i, unix_ms=1000 + i * 5, total=5, zones='') for i in range(3)]
        self.gpu = [dict(frame=i, collector_frame=i+2, cpu_unix_ms=1000+i*5,
                         total_ms=4, upload_ms=.5, world_ms=2.5, overlay_ms=.5, fuse_ms=.5,
                         calibration_deviation_ns=1000, submit_host_ns=1_000_000_000+i*5_000_000,
                         gpu_begin_host_ns=1_001_000_000+i*5_000_000,
                         gpu_end_host_ns=1_005_000_000+i*5_000_000,
                         timestamp_bits=64, timestamp_period_ns=1,
                         gpu_begin_tick=1_001_000_000+i*5_000_000,
                         gpu_end_tick=1_005_000_000+i*5_000_000) for i in range(3)]
        (self.path / 'results.json').write_text(json.dumps([
            dict(label='synthetic', engine_window=[1, 1.01500001], metrics={})]))

    def review(self):
        for name, rows in [('cpu-frames.csv', self.cpu), ('complete-gpu-frames.csv', self.gpu)]:
            with (self.path / name).open('w') as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
        return module.review(self.path)['runs'][0]

    def test_submission_envelope_is_distinct_from_completion_cadence(self):
        run = self.review()
        self.assertEqual(run['matched_frames'], 3)
        self.assertEqual(run['gpu_sections']['total_ms']['mean_ms'], 4)
        self.assertEqual(run['gpu_completion_intervals']['mean_ms'], 5)
        self.assertEqual(run['gpu_gaps_between_submissions']['mean_ms'], 1)

    def test_missing_gpu_frame(self):
        self.gpu.pop(1)
        with self.assertRaisesRegex(ValueError, 'no GPU result'):
            self.review()

    def test_stale_gpu_frame_with_same_id(self):
        self.gpu[1]['cpu_unix_ms'] -= 5
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            self.review()

    def test_duplicate_cpu_identity(self):
        self.cpu[2]['frame'] = 1
        with self.assertRaisesRegex(ValueError, 'Duplicate CPU'):
            self.review()

    def test_duplicate_gpu_identity(self):
        self.gpu.append(dict(self.gpu[1]))
        with self.assertRaisesRegex(ValueError, 'Duplicate GPU'):
            self.review()

    def test_imprecise_clock_calibration(self):
        self.gpu[1]['calibration_deviation_ns'] = 2_000_000
        with self.assertRaisesRegex(ValueError, 'clock calibration'):
            self.review()

    def test_reversed_gpu_completion(self):
        self.gpu[1]['gpu_end_tick'] = self.gpu[0]['gpu_end_tick'] - 1
        with self.assertRaisesRegex(ValueError, 'Non-increasing'):
            self.review()


if __name__ == '__main__':
    unittest.main()
