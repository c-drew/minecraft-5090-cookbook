#!/usr/bin/env python3
"""Compare actual guided GLSL estimates against independent hemisphere quadrature."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--mcvr', type=Path, required=True)
parser.add_argument('--source', type=Path,
                    required=True,
                    help='snapshot containing common/continuation_guide_sampling.glsl')
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--layer-path', help='optional directory containing the Khronos layer manifest')
args = parser.parse_args()
MCVR, OUT = args.mcvr.resolve(), args.output.resolve()
sampler = args.source / 'common/continuation_guide_sampling.glsl'
assert sampler.is_file()
OUT.mkdir(exist_ok=False)
shader = OUT / 'test.spv'
executable = OUT / 'test'
subprocess.run([
    'glslc', '--target-env=vulkan1.2', '-O', '-fshader-stage=comp',
    '-I', str(args.source),
    '-I', str(MCVR / 'src/shader'), '-I', str(MCVR / 'src'),
    '-o', str(shader), str(ROOT / 'tools/continuation-guide-test.comp'),
], check=True)
subprocess.run([
    'g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Wno-missing-field-initializers',
    '-I', str(MCVR / 'extern/vulkan_headers/include'),
    str(ROOT / 'tools/continuation-guide-test.cpp'), '-lvulkan', '-o', str(executable),
], check=True)
env = os.environ | {
    'VK_INSTANCE_LAYERS': 'VK_LAYER_KHRONOS_validation', 'VK_LOADER_DEBUG': 'layer',
    'VK_LAYER_ENABLES': 'VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT',
}
if args.layer_path:
    env['VK_LAYER_PATH'] = args.layer_path
with (OUT / 'stdout.log').open('w') as stdout, (OUT / 'stderr.log').open('w') as stderr:
    subprocess.run([str(executable), str(shader), str(OUT / 'readback.bin')],
                   check=True, env=env, stdout=stdout, stderr=stderr)
logs = (OUT / 'stdout.log').read_text() + (OUT / 'stderr.log').read_text()
assert not re.search(r'VUID-|SYNC-HAZARD|Validation Error', logs)
assert 'Insert instance layer "VK_LAYER_KHRONOS_validation"' in logs
assert 'Inserted device layer "VK_LAYER_KHRONOS_validation"' in logs
meta = [json.loads(x) for x in (OUT / 'stdout.log').read_text().splitlines() if x.startswith('{"gpu":')]
assert len(meta) == 1 and '5090' in meta[0]['gpu']
raw = np.fromfile(OUT / 'readback.bin', dtype=np.float32).reshape(12, 3, 2048, 4)
assert np.isfinite(raw).all()
names = ['no-guide', 'aligned-emitter', 'two-emitter-conditional-guide', 'misaligned-guide',
         'half-occluded-emitter', 'grazing-rough-specular', 'guide-below-surface', 'metal',
         'minimum-cap-width', 'nearby-emitter-hemisphere', 'tangent-hemisphere', 'tilted-surface']
report = {'device': meta[0], 'validation_confirmed': True,
          'sampler_sha256': hashlib.sha256(sampler.read_bytes()).hexdigest(),
          'disney_sha256': hashlib.sha256((MCVR / 'src/shader/util/disney.glsl').read_bytes()).hexdigest(), 'cases': []}
for name, rows in zip(names, raw):
    stats = []
    for row in rows:
        total, square, invalid, count = row.sum(axis=0, dtype=np.float64)
        assert invalid == 0 and count == 1048576
        mean = total / count
        variance = max(0, square / count - mean * mean)
        stats.append({'mean': mean, 'variance': variance, 'standard_error': math.sqrt(variance / count)})
    reference = stats[2]['mean']
    checks = [abs(s['mean'] - reference) <= 6 * s['standard_error'] + 0.002 * reference for s in stats[:2]]
    entry = {'case': name, 'baseline': stats[0], 'guided': stats[1], 'quadrature': {'mean': reference, 'grid': [1024, 1024]},
             'means_match_independent_reference': all(checks),
             'variance_ratio_guided_to_baseline': stats[1]['variance'] / stats[0]['variance']}
    report['cases'].append(entry)
    print(json.dumps(entry), flush=True)
report['no_guide_identical_to_original'] = bool(np.array_equal(raw[0, 0], raw[0, 1]))
report['metal_identical_to_original'] = bool(np.array_equal(raw[7, 0], raw[7, 1]))
report['passed'] = all(x['means_match_independent_reference'] for x in report['cases']) and \
    report['no_guide_identical_to_original'] and report['metal_identical_to_original']
(OUT / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
assert report['passed'], 'Sampler energy/support regression'
