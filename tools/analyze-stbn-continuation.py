#!/usr/bin/env python3
"""Verify GPU mask fetches against the exact imported byte volume.

The diagnostic stores fetched RGB bytes and the SHaRC frame counter in layer 1.
This verifies activation, coordinates, channel order and frame slicing, not
post-reconstruction quality or absence of Monte Carlo variance.
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
parser.add_argument('--mask', required=True, type=Path)
args = parser.parse_args()
assert args.mask.stat().st_size == 64 * 128 * 128 * 4
mask = np.fromfile(args.mask, np.uint8).reshape(64, 128, 128, 4)
records = []
for manifest_path in sorted(args.directory.glob('*/manifest.json')):
    manifest, a, _ = raw.read_capture(manifest_path.parent)
    assert (manifest_path.parent / 'hdr_before.bin').read_bytes() == (manifest_path.parent / 'hdr_after.bin').read_bytes()
    metadata = a['indirect_surface'][1]
    source = a['indirect_surface'][0]
    eligible = a['reconstruction'][0, :, :, 3] > .5
    active = eligible & (metadata[:, :, 3] >= 0)
    assert active.any()
    assert np.isfinite(metadata[active]).all() and np.isfinite(source[eligible]).all()
    phases = np.unique(metadata[:, :, 3][active])
    assert len(phases) == 1 and phases[0] == int(phases[0])
    frame = int(phases[0])
    y, x = np.indices(active.shape)
    expected = mask[frame & 63, y & 127, x & 127, :3]
    assert np.array_equal(metadata[:, :, :3][active], expected[active]), 'GPU mask lookup differs from source bytes'
    continuation_y = a['reconstruction'][0, :, :, :3].astype(np.float32) @ np.array([.2126, .7152, .0722], np.float32)
    error = np.abs(source.sum(-1) - continuation_y)
    assert np.all(error[eligible] <= .002 * np.abs(continuation_y[eligible]) + .0001)
    records.append({'id':manifest['id'], 'active_eligible_paths':int(active.sum()),
                    'eligible_paths':int(eligible.sum()), 'sharc_frame_counter':frame,
                    'mask_layer':frame & 63, 'gpu_mask_bytes_exact':True,
                    'source_composition_passed':True})
assert len(records) == 4
(args.directory / 'stbn-analysis.json').write_text(json.dumps(records, indent=2)+'\n')
print(json.dumps(records, indent=2))
