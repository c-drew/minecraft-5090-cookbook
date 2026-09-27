#!/usr/bin/env python3
"""Check and summarize the raygen source-attribution diagnostic."""
import argparse
import importlib.util
import json
from pathlib import Path
import numpy as np

spec = importlib.util.spec_from_file_location('raw_capture', Path(__file__).with_name('check-raw-light-capture.py'))
raw_capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(raw_capture)
NAMES = ['hit_direct', 'hit_other', 'cached', 'miss']


def analyze(path, bounce_split=False):
    manifest, a, _ = raw_capture.read_capture(path)
    valid = a['reconstruction'][0, :, :, 3] > .5
    total = a['reconstruction'][0, :, :, :3].astype(np.float32) @ np.array([.2126, .7152, .0722], np.float32)
    components = a['indirect_surface'][0]
    meta = a['indirect_surface'][1]
    assert np.isfinite(components[valid]).all() and np.isfinite(meta[valid]).all()
    error = np.abs(total - components.sum(2))
    bad = valid & (error > np.maximum(np.abs(total) * .002, 1e-6))
    result = {'id': manifest['id'], 'eligible_pixels': int(valid.sum()),
              'component_sum_mismatch_pixels': int(bad.sum()), 'max_sum_error': float(error[valid].max()),
              'mean_luminance': float(total[valid].mean()),
              'component_mean': dict(zip(NAMES, components[valid].astype(np.float64).mean(0).tolist())),
              'thresholds': []}
    for threshold in (.001, .1, .5, 1, 2):
        selected = valid & (total > threshold)
        count = int(selected.sum())
        dominant = components.argmax(2)
        record = {'threshold': threshold, 'count': count,
            'dominant_component': {name: int((selected & (dominant == i)).sum()) for i, name in enumerate(NAMES)},
            'component_luminance_sum': dict(zip(NAMES, components[selected].astype(np.float64).sum(0).tolist()))}
        if bounce_split:
            record.update({'first_hit_other_sum': float(meta[:, :, 0][selected].astype(np.float64).sum()),
                           'later_hit_other_sum': float(meta[:, :, 1][selected].astype(np.float64).sum()),
                           'first_emissive_hit_pixels': int((selected & (meta[:, :, 3] > 0)).sum())})
        else:
            record.update({'emissive_hit_pixels': int((selected & (meta[:, :, 1] > 0)).sum()),
                           'first_lobe_counts': {str(lobe): int((selected & (meta[:, :, 3] == lobe)).sum()) for lobe in (-1, 0, 1, 2)},
                           'max_incoming_throughput': float(meta[:, :, 2][selected].max()) if count else 0})
        result['thresholds'].append(record)
    if bounce_split:
        mismatch = valid & (np.abs(components[:, :, 1] - meta[:, :, 0] - meta[:, :, 1]) > 1e-5)
        assert not mismatch.any()
        result.update({'bounce_split_mismatch_pixels': int(mismatch.sum()),
                       'first_hit_other_mean': float(meta[:, :, 0][valid].astype(np.float64).mean()),
                       'later_hit_other_mean': float(meta[:, :, 1][valid].astype(np.float64).mean())})
    assert not bad.any(), result
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--bounce-split', action='store_true')
    args = parser.parse_args()
    results = [analyze(p.parent, args.bounce_split) for p in sorted(args.directory.glob('*/manifest.json'))]
    assert len(results) == 4
    name = 'bounce-analysis.json' if args.bounce_split else 'source-analysis.json'
    (args.directory / name).write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))
