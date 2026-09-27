#!/usr/bin/env python3
"""Check the secondary NEE source schema in four private raw captures.

Counts describe traced paths, not post-reconstruction artifacts. The cache
source is for the whole continuation; it may include a later cache hit even
when the covered bounce-two emitter correctly bypassed the cache.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import numpy as np

spec = importlib.util.spec_from_file_location('raw', Path(__file__).with_name('check-raw-light-capture.py'))
raw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(raw)

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('directory', type=Path)
args = parser.parse_args()
records = []
for manifest_path in sorted(args.directory.glob('*/manifest.json')):
    manifest, a, sentinels = raw.read_capture(manifest_path.parent)
    assert (manifest_path.parent / 'hdr_before.bin').read_bytes() == (manifest_path.parent / 'hdr_after.bin').read_bytes()
    source = a['indirect_surface'][0]
    metadata = a['indirect_surface'][1]
    eligible = a['reconstruction'][0, :, :, 3] > .5
    assert np.isfinite(source[eligible]).all() and np.isfinite(metadata[eligible]).all()
    continuation_y = a['reconstruction'][0, :, :, :3].astype(np.float32) @ np.array([.2126, .7152, .0722], np.float32)
    error = np.abs(source.sum(-1) - continuation_y)
    assert np.all(error[eligible] <= .002 * np.abs(continuation_y[eligible]) + .0001)
    attempted = eligible & (metadata[:, :, 1] > .5)
    covered = eligible & (metadata[:, :, 2] > .5)
    assert not np.any(covered & ~attempted)
    assert not np.any(covered & (metadata[:, :, 3] <= 1e-6))
    records.append({'id': manifest['id'], 'eligible_paths': int(eligible.sum()),
                    'supported_secondary_nee_paths': int(attempted.sum()),
                    'covered_bounce_two_emitters': int(covered.sum()),
                    'nonzero_direct_source_paths': int((eligible & (source[:, :, 0] > 1e-8)).sum()),
                    'source_composition_passed': True, 'finite': True})
assert len(records) == 4
(args.directory / 'secondary-nee-analysis.json').write_text(json.dumps(records, indent=2) + '\n')
print(json.dumps(records, indent=2))
