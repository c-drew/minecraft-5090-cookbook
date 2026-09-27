#!/usr/bin/env python3
"""Join completed CPU/GPU logs by frame identity within recorded bench windows.

GPU spans include scheduling inside the timestamp envelope. Submission-to-start
delay includes queued work, semaphore waits and scheduling; it is not a measured
driver-only cost. Neither timeline proves physical display delivery.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics

from engine_frame_metrics import read_engine_frames


def distribution(values):
    if not values:
        raise ValueError('Empty timing distribution')
    if not all(math.isfinite(v) for v in values):
        raise ValueError('Non-finite timing')
    ordered = sorted(values)
    return {'count': len(values), 'mean_ms': statistics.mean(values),
            'median_ms': statistics.median(values), 'p99_ms': ordered[int(len(values) * .99)],
            'maximum_ms': max(values), 'minimum_ms': min(values),
            'over_6_944_ms': sum(v > 1000 / 144 for v in values)}


def review(directory):
    directory = Path(directory)
    with (directory / 'cpu-frames.csv').open() as f:
        cpu_rows = list(csv.DictReader(f))
    cpu = {}
    for row in cpu_rows:
        frame = int(row['frame'])
        if frame in cpu:
            raise ValueError(f'Duplicate CPU frame identity {frame}')
        cpu[frame] = row
    with (directory / 'complete-gpu-frames.csv').open() as f:
        rows = list(csv.DictReader(f))
    gpu = {}
    collected = {}
    for row in rows:
        frame = int(row['frame'])
        if frame == 2**64 - 1:
            continue  # Initial native context predates the first JNI acquire.
        if frame in gpu:
            raise ValueError(f'Duplicate GPU frame identity {frame}')
        gpu[frame] = row
        collected.setdefault(int(row['collector_frame']), []).append(frame)
    results = []
    for record in json.loads((directory / 'results.json').read_text()):
        start, end = record['engine_window']
        engine = read_engine_frames(directory / 'cpu-frames.csv', start, end)
        if not .98 <= engine['window_coverage'] <= 1.01:
            raise ValueError('Incomplete engine window')
        frames = [n for n, c in cpu.items() if float(c['unix_ms']) >= start * 1000
                  and float(c['unix_ms']) + float(c['total']) <= end * 1000 and float(c['total']) > 0]
        if any(n not in gpu for n in frames):
            raise ValueError('A measured CPU frame has no GPU result')
        spans = []
        for n in frames:
            c, g = cpu[n], gpu[n]
            if abs(float(c['unix_ms']) - float(g['cpu_unix_ms'])) > .002:
                raise ValueError(f'CPU/GPU identity mismatch at frame {n}')
            fields = {k: float(g[k]) for k in ('total_ms', 'upload_ms', 'world_ms', 'overlay_ms', 'fuse_ms')}
            if any(not math.isfinite(v) or v < 0 or v > 1000 for v in fields.values()):
                raise ValueError(f'Invalid GPU interval at frame {n}')
            if abs(sum(fields[k] for k in ('upload_ms', 'world_ms', 'overlay_ms', 'fuse_ms')) - fields['total_ms']) > .00001:
                raise ValueError('GPU section durations do not sum to the envelope')
            deviation = int(g['calibration_deviation_ns'])
            begin_host, end_host = float(g['gpu_begin_host_ns']), float(g['gpu_end_host_ns'])
            if begin_host < 0 or end_host < begin_host or not 0 < deviation < 1000000:
                raise ValueError('Missing or too imprecise GPU/CPU clock calibration')
            delay = (begin_host - int(g['submit_host_ns'])) / 1e6
            if delay < -deviation / 1e6:
                raise ValueError('GPU begins before submission beyond calibration error')
            spans.append(fields | {'frame': n, 'queue_delay_ms': delay, 'calibration_deviation_ns': deviation})
        by_frame = {r['frame']: r for r in spans}
        completion_intervals, gpu_gaps = [], []
        for n in frames:
            if n - 1 not in by_frame:
                continue
            current, previous = gpu[n], gpu[n - 1]
            if int(current['timestamp_bits']) != 64:
                raise ValueError('Cross-submission diagnostic requires the calibrated 64-bit timeline')
            period_ms = float(current['timestamp_period_ns']) / 1e6
            completion_intervals.append((int(current['gpu_end_tick']) - int(previous['gpu_end_tick'])) * period_ms)
            gpu_gaps.append((int(current['gpu_begin_tick']) - int(previous['gpu_end_tick'])) * period_ms)
        if not completion_intervals:
            raise ValueError('No adjacent GPU submissions in the measurement window')
        if min(completion_intervals) <= 0:
            raise ValueError('Non-increasing GPU completion timeline')
        slow = []
        for n in sorted(frames, key=lambda n: float(cpu[n]['total']), reverse=True)[:12]:
            zones = {}
            for item in cpu[n]['zones'].split(';'):
                if '=' in item:
                    k, v = item.rsplit('=', 1)
                    zones[k] = float(v)
            previous_slots = []
            for previous in collected.get(n, []):
                g = gpu[previous]
                previous_slots.append({'frame': previous, 'gpu_total_ms': float(g['total_ms']),
                                       'queue_delay_ms': (float(g['gpu_begin_host_ns']) - int(g['submit_host_ns'])) / 1e6})
            slow.append({'frame': n, 'cpu_total_ms': float(cpu[n]['total']),
                         'zones': zones, 'own_gpu': by_frame[n], 'slot_collected_after_fence': previous_slots})
        results.append({'label': record['label'], 'engine_window': record['engine_window'],
                        'engine_metrics': engine, 'mango_metrics': record['metrics'],
                        'movement_validated': record.get('movement', {}).get('validated') if record.get('movement') else None,
                        'matched_frames': len(frames), 'gpu_sections': {k: distribution([r[k] for r in spans])
                        for k in ('total_ms', 'upload_ms', 'world_ms', 'overlay_ms', 'fuse_ms', 'queue_delay_ms')},
                        'gpu_completion_intervals': distribution(completion_intervals),
                        'gpu_gaps_between_submissions': distribution(gpu_gaps),
                        'gpu_cadence_scope': 'Adjacent submissions whose corresponding complete CPU intervals both fall inside the window; GPU timestamps, not physical display delivery.',
                        'max_calibration_deviation_ns': max(r['calibration_deviation_ns'] for r in spans),
                        'slowest_engine_frames': slow})
    return {'scope': __doc__, 'runs': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    data = review(args.directory)
    (args.directory / 'analysis.json').write_text(json.dumps(data, indent=2) + '\n')
    for r in data['runs']:
        print(json.dumps({k: v for k, v in r.items() if k != 'slowest_engine_frames'}))
