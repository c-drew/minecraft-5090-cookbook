#!/usr/bin/env python3
"""GPU invariants for indirect reconstruction, texture modulation and fog composition."""
from pathlib import Path
import argparse
import json
import os
import re
import subprocess
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--mcvr', type=Path, required=True)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--layer-path', type=Path, default=None)
args = parser.parse_args()
MCVR = args.mcvr.resolve()
SOURCE = args.source.resolve()
OUT = args.output.resolve()
if not (SOURCE / 'common/indirect_prefilter.glsl').is_file():
    parser.error('--source must contain common/indirect_prefilter.glsl')
OUT.mkdir(exist_ok=False)
executable = OUT / 'test'
subprocess.run(['g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Wno-missing-field-initializers',
                '-I', str(MCVR / 'extern/vulkan_headers/include'), str(ROOT / 'tools/indirect-prefilter-test.cpp'),
                '-lvulkan', '-o', str(executable)], check=True)
environment = os.environ | {
    'VK_INSTANCE_LAYERS': 'VK_LAYER_KHRONOS_validation', 'VK_LOADER_DEBUG': 'layer',
    'VK_LAYER_ENABLES': 'VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT',
}
if args.layer_path:
    environment['VK_LAYER_PATH'] = str(args.layer_path)
names = ['constant-light', 'checkerboard-albedo-detail', 'checkerboard-noise-cancellation', 'parallel-depth-edge',
         'geometric-normal-edge', 'shading-normal-edge', 'roughness-edge', 'invalid-neighbors', 'active-size-edge',
         'invalid-center', 'colored-fog-direct-and-emission', 'water-and-colored-fog']
report = {'validation_confirmed': True, 'variants': []}
for radius in (0, 1, 2):
    shader = OUT / f'r{radius}.spv'
    subprocess.run(['glslc', '--target-env=vulkan1.2', '-O', '-fshader-stage=comp',
                    f'-DADV_INDIRECT_PREFILTER_RADIUS={radius}',
                    '-I', str(SOURCE),
                    '-o', str(shader), str(ROOT / 'tools/indirect-prefilter-test.comp')], check=True)
    output = OUT / f'r{radius}.bin'
    with (OUT / f'r{radius}.stdout.log').open('w') as stdout, (OUT / f'r{radius}.stderr.log').open('w') as stderr:
        subprocess.run([str(executable), str(shader), str(output)], env=environment, stdout=stdout, stderr=stderr, check=True)
    logs = (OUT / f'r{radius}.stdout.log').read_text() + (OUT / f'r{radius}.stderr.log').read_text()
    assert not re.search(r'VUID-|SYNC-HAZARD|Validation Error', logs)
    assert 'Insert instance layer "VK_LAYER_KHRONOS_validation"' in logs
    assert 'Inserted device layer "VK_LAYER_KHRONOS_validation"' in logs
    values = np.fromfile(output, dtype=np.float32).reshape(64, 4)[:12]
    assert np.isfinite(values).all() and np.all(values[:, 3] == 1)
    expected = np.tile(np.array([0.5, 1, 1.5]), (12, 1))
    expected[1] = np.array([0.05, 0.2, 0.9]) * 2
    center_light = 3 if radius == 0 else 2
    expected[2] = np.array([0.25, 0.5, 0.75]) * center_light
    for case, transmission in [(10, np.array([0.2, 0.4, 0.8])),
                               (11, np.array([0, 0.48, 0.65]) * 0.3 * [0.7, 0.9, 1.0])]:
        expected[case] = ([5, 6, 7] + np.array([0.25, 0.5, 0.75]) * center_light) * transmission + [0.1, 0.3, 0.7]
    checks = []
    for i, name in enumerate(names):
        error = float(np.max(np.abs(values[i, :3] - expected[i])))
        passed = error < (0.01 if i == 6 else 2e-6)
        checks.append({'case': name, 'actual': values[i, :3].tolist(), 'expected': expected[i].tolist(),
                       'max_error': error, 'passed': passed})
    report['variants'].append({'radius': radius, 'checks': checks, 'bounds_valid': True})
    print(f'radius {radius}: {sum(x["passed"] for x in checks)}/{len(checks)} invariants', flush=True)
report['passed'] = all(x['passed'] for v in report['variants'] for x in v['checks'])
(OUT / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
assert report['passed']
