#!/usr/bin/env python3
"""Review post-turn convergence, using each shot's own settled image as a reference.

This is a transient-image difference proxy, not an absolute quality score.
Exposure is normalized within each wall crop. Torch, hands and HUD are excluded.
The motion end is estimated from captured frames, not ffmpeg startup time.
"""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

parser = argparse.ArgumentParser()
parser.add_argument('directory', type=Path)
parser.add_argument('--motion-threshold', type=float, default=6.0,
                    help='8-bit mean frame difference used to detect motion; lower for dim component views')
parser.add_argument('--mask-reference', type=Path,
                    help='reviewed full-light capture used to select identical wall pixels across components')
args = parser.parse_args()
p = args.directory
if not 0.0 < args.motion_threshold < 255.0:
    parser.error('--motion-threshold must be between 0 and 255')
events = json.loads((p / 'turn-events.json').read_text())
raw = subprocess.check_output([
    'ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(p / 'fast-turns.mp4'),
    '-vf', 'fps=60,scale=640:360', '-pix_fmt', 'gray', '-f', 'rawvideo', '-'])
frames = np.frombuffer(raw, np.uint8).reshape(-1, 360, 640)
reference_frames = reference_events = None
if args.mask_reference:
    reference_events = json.loads((args.mask_reference / 'convergence.json').read_text())['events']
    if len(reference_events) != len(events):
        raise RuntimeError('Mask reference must contain the same number of turns')
    reference_raw = subprocess.check_output([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-i', str(args.mask_reference / 'fast-turns.mp4'),
        '-vf', 'fps=60,scale=640:360', '-pix_fmt', 'gray', '-f', 'rawvideo', '-'])
    reference_frames = np.frombuffer(reference_raw, np.uint8).reshape(-1, 360, 640)
motion = np.zeros(len(frames))
for i in range(1, len(frames)):
    motion[i] = np.mean(np.abs(frames[i, :230].astype(float) - frames[i - 1, :230]))

rows = []
delays = (0.05, 0.15, 0.3, 0.6, 1.2, 2.3)
sheet = Image.new('RGB', (len(delays) * 320, len(events) * 265), '#141820')
draw = ImageDraw.Draw(sheet)
for i, event in enumerate(events):
    # Search broadly enough to allow X11/capture latency, but not the next turn.
    start = max(1, int((event['start'] - 0.4) * 60))
    stop = min(len(frames), int((event['end'] + 0.8) * 60))
    candidates = np.flatnonzero(motion[start:stop] > args.motion_threshold) + start
    if not len(candidates):
        raise RuntimeError(f'No rapid turn detected for event {i}')
    # A nearby animated torch can exceed the threshold long after the turn.
    # Follow the strongest camera-motion burst, allowing at most two quiet
    # frames within it, instead of accepting every later isolated change.
    peak = int(start + np.argmax(motion[start:stop]))
    end = peak
    quiet = 0
    for n in range(peak + 1, stop):
        if motion[n] > args.motion_threshold:
            end = n
            quiet = 0
        else:
            quiet += 1
            if quiet > 2:
                break
    if end / 60 > event['end'] + 0.25:
        raise RuntimeError(f'Unstable image prevents reliable turn-end alignment for event {i}')
    down = event['yaw'] > 0
    box = (10, 15, 250, 200) if down else (400, 15, 635, 195)
    x0, y0, x1, y1 = box
    target_ids = range(end + 120, min(end + 156, len(frames)))
    target = np.mean(frames[list(target_ids), y0:y1, x0:x1], axis=0)
    mask_target = target
    if reference_events is not None:
        reference = reference_events[i]
        if reference['event']['yaw'] != event['yaw'] or reference['crop_at_640x360'] != list(box):
            raise RuntimeError('Mask reference uses different turns or crops')
        reference_end = reference['motion_end_frame']
        mask_target = np.mean(reference_frames[reference_end + 120:reference_end + 156, y0:y1, x0:x1], axis=0)
    mask = (mask_target > 15) & (mask_target < 225)
    if not np.any(mask):
        raise RuntimeError(f'No valid wall pixels for event {i}')
    target_mean = target[mask].mean()
    if target_mean <= 0:
        raise RuntimeError(f'Zero reference brightness for event {i}')
    samples = []
    for j, delay in enumerate(delays):
        n = min(end + round(delay * 60), len(frames) - 1)
        crop = frames[n, y0:y1, x0:x1].astype(float)
        gain = target_mean / max(crop[mask].mean(), 1.0)
        residual = crop * gain - target
        rms = float(np.sqrt(np.mean(residual[mask] ** 2)))
        # Report a relative score too: darker images otherwise look artificially
        # better by the absolute 8-bit error alone.
        samples.append({'delay_s': delay, 'frame': n, 'rms_8bit': rms,
                        'rms_relative_to_mean': rms / target_mean, 'gain': gain})
        im = Image.fromarray(frames[n]).crop(box).resize((320, 235))
        x, y = j * 320, i * 265
        sheet.paste(im, (x, y + 30))
        draw.text((x + 6, y + 8), f'{i + 1} {delay:.2f}s  RMS {rms:.2f}', fill='white')
    rows.append({'event': event, 'motion_end_frame': end,
                 'motion_end_video_s': end / 60, 'crop_at_640x360': box,
                 'settled_mean_8bit': float(target_mean), 'mask_pixels': int(mask.sum()), 'samples': samples})
result = {'note': __doc__, 'motion_threshold': args.motion_threshold,
          'motion_end_method': 'strongest motion burst; at most two quiet frames; late-end guard',
          'mask_reference': str(args.mask_reference) if args.mask_reference else None, 'events': rows}
(p / 'convergence.json').write_text(json.dumps(result, indent=2) + '\n')
sheet.save(p / 'convergence.png')
print(json.dumps({'directory': str(p), 'motion_ends': [r['motion_end_video_s'] for r in rows],
                  'mean_rms_by_delay': {str(d): round(float(np.mean([r['samples'][j]['rms_8bit'] for r in rows])), 3)
                                        for j, d in enumerate(delays)}}))
