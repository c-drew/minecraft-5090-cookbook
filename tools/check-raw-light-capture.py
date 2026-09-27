#!/usr/bin/env python3
"""Check exact readback layout and summarize pre-RR data, without tone mapping."""
from pathlib import Path
import argparse
import json
import numpy as np

FORMATS = {37: ('u1', 4), 76: ('<f2', 1), 83: ('<f2', 2), 97: ('<f2', 4), 109: ('<f4', 4)}


def read_capture(path):
    manifest = json.loads((path / 'manifest.json').read_text())
    assert manifest['gpu_fence_confirmed'] is True
    arrays = {}
    for item in manifest['images']:
        dtype, channels = FORMATS[item['format']]
        file = path / item['file']
        assert file.stat().st_size == item['bytes']
        expected = item['layers'] * item['height'] * item['width'] * channels * np.dtype(dtype).itemsize
        assert expected == item['bytes'], (item['name'], expected, item['bytes'])
        arrays[item['name']] = np.fromfile(file, dtype=dtype).reshape(item['layers'], item['height'], item['width'], channels)
    sentinel_results = []
    for fmt in (97, 109, 37):
        values = arrays[f'sentinel_{fmt}'].astype(np.float32)
        if fmt == 37:
            values /= 255
        expected = np.array([[1, .5, .25, 1], [.75, .25, .5, 0]], dtype=np.float32)[:, None, None, :]
        error = float(np.max(np.abs(values - expected)))
        assert values.shape == (2, 2, 3, 4)
        assert error <= (1 / 255 if fmt == 37 else 0)
        sentinel_results.append({'format': fmt, 'shape': list(values.shape), 'max_error': error, 'passed': True})
    return manifest, arrays, sentinel_results


def summarize(path, identity=False):
    manifest, a, sentinels = read_capture(path)
    before = a['hdr_before'][0, :, :, :3].astype(np.float32)
    after = a['hdr_after'][0, :, :, :3].astype(np.float32)
    assert before.shape == after.shape
    equal = (path / 'hdr_before.bin').read_bytes() == (path / 'hdr_after.bin').read_bytes()
    if identity:
        assert equal, 'No-filter HDR changed between capture points'
    result = {'id': manifest['id'], 'frame': manifest['frame'], 'sentinels': sentinels,
              'hdr_exact_identity': equal, 'hdr_nonfinite_before': int((~np.isfinite(before)).any(-1).sum()),
              'hdr_nonfinite_after': int((~np.isfinite(after)).any(-1).sum())}
    if 'reconstruction' in a:
        raw = a['reconstruction'][0, :, :, :3].astype(np.float32)
        transmission = a['reconstruction'][1, :, :, :3].astype(np.float32)
        eligible = a['reconstruction'][0, :, :, 3] > .5
        finite = np.isfinite(raw).all(-1) & np.isfinite(transmission).all(-1) & np.isfinite(before).all(-1)
        usable = eligible & finite
        original = raw * transmission
        residual = before - original
        tolerance = .002 * (np.abs(before) + np.abs(original)) + .0001
        bad = usable & (residual < -tolerance).any(-1)
        luminance = raw @ np.array([.2126, .7152, .0722], np.float32)
        delta = after - before
        result.update({'eligible_pixels': int(eligible.sum()), 'eligible_nonfinite_pixels': int((eligible & ~finite).sum()),
                       'negative_remainder_pixels': int(bad.sum()),
                       'raw_luminance_quantiles': {str(q): float(np.percentile(luminance[usable], q)) for q in (0, 50, 90, 99, 99.9, 99.99, 100)},
                       'max_absolute_hdr_delta': float(np.nanmax(np.abs(delta))),
                       'negative_remainder_min_rgb': residual[usable].min(0).tolist()})
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--identity', action='store_true')
    args = parser.parse_args()
    results = [summarize(p.parent, args.identity) for p in sorted(args.directory.glob('*/manifest.json'))]
    assert len(results) == 4, 'Expected all four private capture stages'
    (args.directory / 'validation.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))
