#!/usr/bin/env python3
"""Analyze first-continuation emitter diagnostics with an explicit schema.

The hit-other luminance is the whole continuation's non-directional hit shading;
the metadata classifies its first hit. These are single-frame path counts, not
post-reconstruction artifact counts or a variance estimate.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import numpy as np

spec = importlib.util.spec_from_file_location('raw', Path(__file__).with_name('check-raw-light-capture.py'))
raw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(raw)


def histogram(values):
    keys, counts = np.unique(values, return_counts=True)
    return dict(zip(map(str, keys.tolist()), counts.tolist()))


def group(metadata, selected, schema):
    q = metadata[selected]
    encoded = np.rint(q[:, 1]).astype(np.int64)
    packed = schema in ('lod', 'alpha', 'mask')
    result = {'paths': int(selected.sum()), 'primary_nee_flags': histogram(q[:, 0]),
              'support_bits': histogram(encoded % 64 if packed else encoded),
              'material_emission': histogram(q[:, 3])}
    field = {'coverage': 'matched_facing', 'lod': 'lod_zero_emission',
             'alpha': 'lod_zero_albedo_alpha', 'instance': 'signed_instance',
             'mask': 'signed_instance'}[schema]
    result[field] = histogram(q[:, 2])
    if packed:
        field = {'lod': 'ceil_lod', 'alpha': 'alpha_mode', 'mask': 'instance_mask'}[schema]
        result[field] = histogram(encoded // 64)
    return result


def analyze(path, schema):
    manifest, a, sentinels = raw.read_capture(path)
    assert (path / 'hdr_before.bin').read_bytes() == (path / 'hdr_after.bin').read_bytes()
    metadata = a['indirect_surface'][1]
    sources = a['indirect_surface'][0]
    eligible = a['reconstruction'][0, :, :, 3] > .5
    assert np.isfinite(metadata[eligible]).all()
    first_emissive = eligible & (metadata[:, :, 3] > 1e-6)
    selected = first_emissive & (sources[:, :, 1] > 1)
    return {'id': manifest['id'], 'schema': schema, 'sentinels': sentinels,
            'hdr_exact_identity': True, 'eligible_paths': int(eligible.sum()),
            'all_first_emissive': group(metadata, first_emissive, schema),
            'first_emissive_and_hit_other_y_gt1': group(metadata, selected, schema)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw_directory', type=Path)
    parser.add_argument('--schema', required=True, choices=['coverage', 'lod', 'alpha', 'instance', 'mask'])
    args = parser.parse_args()
    results = [analyze(p.parent, args.schema) for p in sorted(args.raw_directory.glob('*/manifest.json'))]
    assert len(results) == 4
    (args.raw_directory / 'emitter-support-analysis.json').write_text(json.dumps(results, indent=2) + '\n')
    for row in results:
        print(json.dumps({'id': row['id'], 'bright': row['first_emissive_and_hit_other_y_gt1']}))
