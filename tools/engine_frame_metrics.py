#!/usr/bin/env python3
"""Measure complete acquire-to-acquire engine intervals in an explicit time window.

These are render-thread wall intervals, including GPU/presentation waits and Java
work. They do not prove that the compositor or physical display delivered frames.
Read the log after the game exits so buffered rows are complete.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics


def read_engine_frames(path, start_s, end_s):
    if not math.isfinite(start_s) or not math.isfinite(end_s) or end_s <= start_s:
        raise ValueError('Expected a finite, increasing window in Unix seconds')
    frames = []
    previous_start = -math.inf
    with Path(path).open() as f:
        for row in csv.DictReader(f):
            start_ms, duration = float(row['unix_ms']), float(row['total'])
            if not math.isfinite(start_ms) or not math.isfinite(duration) or duration < 0:
                raise ValueError('Invalid engine timestamp or duration')
            if start_ms < previous_start:
                raise ValueError('Engine wall clock moved backward; window alignment is invalid')
            previous_start = start_ms
            # Exclude intervals crossing either measurement boundary.
            if start_ms >= start_s * 1000 and start_ms + duration <= end_s * 1000 and duration > 0:
                frames.append(duration)
    if not frames:
        raise ValueError('No complete engine frames within the requested window')
    ordered = sorted(frames)
    worst = ordered[-max(1, len(frames) // 100):]
    covered = sum(frames) / 1000
    over = sum(t > 1000 / 144 for t in frames)
    return {
        'scope': 'engine acquire-to-acquire wall interval; not display delivery',
        'frames': len(frames), 'seconds': covered,
        'window_seconds': end_s - start_s,
        'window_coverage': covered / (end_s - start_s),
        'fps': 1000 / statistics.mean(frames),
        'one_percent_low': 1000 / statistics.mean(worst),
        'median_ms': statistics.median(frames),
        'p99_ms': ordered[int(len(frames) * .99)], 'worst_ms': max(frames),
        'over_144_count': over, 'over_144_percent': 100 * over / len(frames),
    }


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv', type=Path)
    p.add_argument('--start', type=float, required=True)
    p.add_argument('--end', type=float, required=True)
    a = p.parse_args()
    print(json.dumps(read_engine_frames(a.csv, a.start, a.end), indent=2))
