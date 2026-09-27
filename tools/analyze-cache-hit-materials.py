#!/usr/bin/env python3
"""Summarize cache-hit geometry and material diagnostics without tone mapping.

Thresholds refer to the whole continuation sample. They can include radiance
accumulated before the cache lookup and are not cache-only energy attribution.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import numpy as np

spec = importlib.util.spec_from_file_location('raw', Path(__file__).with_name('check-raw-light-capture.py'))
raw_capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(raw_capture)
Y = np.array([.2126, .7152, .0722], np.float32)


def analyze(path):
    manifest, arrays, _ = raw_capture.read_capture(path)
    position_material = arrays['indirect_surface'][0]
    cache_bounce = arrays['indirect_surface'][1]
    raw = arrays['reconstruction'][0].astype(np.float32)
    eligible = raw[:, :, 3] > .5
    valid = eligible & (cache_bounce[:, :, 3] > 0)
    total_y = raw[:, :, :3] @ Y
    cache_y = cache_bounce[:, :, :3] @ Y
    emission = position_material[:, :, 3] > 1e-6
    assert np.isfinite(position_material[valid]).all()
    assert np.isfinite(cache_bounce[valid]).all()
    record = {'id': manifest['id'], 'eligible_pixels': int(eligible.sum()),
              'cache_hits': int(valid.sum()), 'thresholds': []}
    for threshold in (.001, .1, .5, 1, 2):
        selected = valid & (total_y > threshold)
        record['thresholds'].append({
            'continuation_y_threshold': threshold,
            'cache_pixels': int(selected.sum()),
            'emissive_cache_hits': int((selected & emission).sum()),
            'nonemissive_cache_hits': int((selected & ~emission).sum()),
            'continuation_y_sum_emissive_hits': float(total_y[selected & emission].astype(np.float64).sum()),
            'continuation_y_sum_nonemissive_hits': float(total_y[selected & ~emission].astype(np.float64).sum()),
            'unweighted_cache_y_mean': float(cache_y[selected].astype(np.float64).mean()) if selected.any() else 0,
            'bounce_counts': {str(b): int((selected & (cache_bounce[:, :, 3] == b + 1)).sum()) for b in (1, 2, 3)}})
    selected = valid & (total_y > 1)
    positions = np.floor(position_material[selected, :3]).astype(int)
    unique, inverse, count = np.unique(positions, axis=0, return_inverse=True, return_counts=True)
    energy = np.bincount(inverse, weights=total_y[selected])
    order = np.argsort(energy)[-12:][::-1]
    record['top_cache_hit_blocks_for_continuation_y_gt1'] = [
        {'block': unique[i].tolist(), 'count': int(count[i]), 'continuation_y_sum': float(energy[i])}
        for i in order]
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    results = [analyze(p.parent) for p in sorted(args.directory.glob('*/manifest.json'))]
    assert len(results) == 4
    (args.directory / 'cache-hit-analysis.json').write_text(json.dumps(results, indent=2) + '\n')
    for row in results:
        threshold = next(t for t in row['thresholds'] if t['continuation_y_threshold'] == 1)
        print(json.dumps({'id': row['id'], **threshold}))
