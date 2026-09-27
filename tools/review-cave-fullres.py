#!/usr/bin/env python3
"""Measure localized settling error at native capture resolution.

Uses already-reviewed turn ends. No new motion detector or artifact classifier.
Whole-crop RMS, pixel quantiles and 32px tile RMS are differences from a settled
reference, not ground-truth quality. Shared brightness masks come from control.
"""
from pathlib import Path
import argparse
import json
import subprocess
import tempfile
import numpy as np


def load_selected(directory, events, storage):
    indices = sorted({i for e in events for i in
                      [*[s['frame'] for s in e['samples']], *range(e['motion_end_frame'] + 120, e['motion_end_frame'] + 156)]})
    ranges = []
    for n in indices:
        if ranges and n == ranges[-1][1] + 1:
            ranges[-1][1] = n
        else:
            ranges.append([n, n])
    select = '+'.join(f'eq(n,{a})' if a == b else f'between(n,{a},{b})' for a, b in ranges)
    with storage.open('wb') as output:
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(directory / 'fast-turns.mp4'),
                        '-vf', f"fps=60,select='{select}'", '-fps_mode', 'passthrough',
                        '-pix_fmt', 'gray', '-f', 'rawvideo', '-'], stdout=output, check=True)
    assert storage.stat().st_size == len(indices) * 2560 * 1440
    data = np.memmap(storage, dtype='u1', mode='r', shape=(len(indices), 1440, 2560))
    return data, {n: i for i, n in enumerate(indices)}


def settled(data, lookup, event, crop):
    x0, y0, x1, y1 = crop
    result = np.zeros((y1-y0, x1-x0), np.float32)
    for n in range(event['motion_end_frame'] + 120, event['motion_end_frame'] + 156):
        result += data[lookup[n], y0:y1, x0:x1]
    return result / 36


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('control', type=Path)
parser.add_argument('candidate', type=Path)
args = parser.parse_args()
events = [json.loads((p / 'convergence.json').read_text())['events'] for p in (args.control, args.candidate)]
with tempfile.TemporaryDirectory(prefix='fullres-cave-review-') as tmp:
    loaded = [load_selected(p, ev, Path(tmp) / f'{i}.gray')
              for i, (p, ev) in enumerate(zip((args.control, args.candidate), events))]
    results = []
    for i, (data, lookup) in enumerate(loaded):
        records = []
        for index, event in enumerate(events[i]):
            crop = [v * 4 for v in event['crop_at_640x360']]
            x0, y0, x1, y1 = crop
            target = settled(data, lookup, event, crop)
            reference = settled(*loaded[0], events[0][index], crop)
            mask = (reference > 15) & (reference < 225)
            target_mean = float(target[mask].mean())
            samples = []
            for sample in event['samples']:
                frame = data[lookup[sample['frame']], y0:y1, x0:x1].astype(np.float32)
                gain = target_mean / max(float(frame[mask].mean()), 1)
                residual = frame * gain - target
                absolute = np.abs(residual[mask])
                bh, bw = target.shape[0] // 32, target.shape[1] // 32
                roi = residual[:bh*32, :bw*32]
                tile_mask = mask[:bh*32, :bw*32].reshape(bh, 32, bw, 32).mean((1, 3)) > .99
                tile_rms = np.sqrt((roi * roi).reshape(bh, 32, bw, 32).mean((1, 3)))[tile_mask]
                samples.append({'delay_s': sample['delay_s'], 'frame': sample['frame'], 'gain': gain,
                    'relative_rms': float(np.sqrt((absolute * absolute).mean()) / target_mean),
                    'absolute_error_quantiles': {str(q): float(np.percentile(absolute, q)) for q in [50, 90, 95, 99, 99.9]},
                    'tile_32_rms_quantiles': {str(q): float(np.percentile(tile_rms, q)) for q in [50, 90, 95, 99, 100]}})
            records.append({'event': index, 'crop': crop, 'target_mean': target_mean, 'samples': samples})
        result = {'directory': str((args.control, args.candidate)[i]), 'resolution': [2560, 1440], 'events': records}
        results.append(result)
        ((args.control, args.candidate)[i] / 'fullres-convergence.json').write_text(json.dumps(result, indent=2) + '\n')
    for row in results:
        print(json.dumps({'directory': row['directory'], 'means': {
            str(delay): {'relative_rms': float(np.mean([next(s['relative_rms'] for s in e['samples'] if s['delay_s'] == delay) for e in row['events']])),
                        'tile_95_rms': float(np.mean([next(s['tile_32_rms_quantiles']['95'] for s in e['samples'] if s['delay_s'] == delay) for e in row['events']]))}
            for delay in [.05, .3, 1.2]}}))
