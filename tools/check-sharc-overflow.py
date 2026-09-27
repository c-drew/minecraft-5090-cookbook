#!/usr/bin/env python3
"""Compile actual SHaRC functions and verify baseline/fixed behavior on an RTX 5090."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

PIN = '0b9f58bbc8c41736042d4da964830a247e424a00'
ORIGINAL = 'adce84cdd622d8e8657fedf804df47a2fec5c9a10ec013c7f29500a80e85c5f6'
FIXED = '31a865b7cad7d898ac61fa405c121a75c434fdcbb15aa6660d09b5f4fcff7d6e'
TOOLS = Path(__file__).resolve().parent


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mcvr', type=Path, help='MCVR with initialized, corrected SHaRC submodule')
    parser.add_argument('output', type=Path, help='new directory for binaries, raw JSON and logs')
    parser.add_argument('--validation', action='store_true', help='require Khronos and synchronization validation')
    args = parser.parse_args()
    mcvr, out = args.mcvr.resolve(), args.output.resolve()
    sdk = mcvr / 'extern/sharc'
    assert subprocess.check_output(['git', '-C', str(sdk), 'rev-parse', 'HEAD'], text=True).strip() == PIN
    header = sdk / 'include/HashGridCommon.h'
    assert hashlib.sha256(header.read_bytes()).hexdigest() == FIXED, 'Apply the cookbook SHaRC patch first'
    out.mkdir(parents=True, exist_ok=False)
    baseline = out / 'baseline-sdk'
    baseline.mkdir()
    # Extract only tracked include files at the pin; never modify the working SDK.
    names = subprocess.check_output(['git', '-C', str(sdk), 'ls-tree', '-r', '--name-only', PIN, 'include'], text=True).splitlines()
    for name in names:
        destination = baseline / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(subprocess.check_output(['git', '-C', str(sdk), 'show', f'{PIN}:{name}']))
    assert hashlib.sha256((baseline / 'include/HashGridCommon.h').read_bytes()).hexdigest() == ORIGINAL
    executable = out / 'sharc-overflow-test'
    run('g++', '-std=c++20', '-O2', '-Wall', '-Wextra', '-Wno-missing-field-initializers',
        '-I', str(mcvr / 'extern/vulkan_headers/include'), str(TOOLS / 'sharc-overflow-test.cpp'),
        '-lvulkan', '-o', str(executable))
    environment = os.environ.copy()
    if args.validation:
        environment.update(VK_INSTANCE_LAYERS='VK_LAYER_KHRONOS_validation', VK_LOADER_DEBUG='layer',
                           VK_LAYER_ENABLES='VK_VALIDATION_FEATURE_ENABLE_SYNCHRONIZATION_VALIDATION_EXT')
    for label, include, expectation in [('baseline', baseline / 'include', '--expect-bug'),
                                        ('fixed', sdk / 'include', '--expect-safe')]:
        shader = out / f'{label}.spv'
        run('glslc', '--target-env=vulkan1.2', '-O', '-fshader-stage=comp',
            '-I', str(include), '-o', str(shader), str(TOOLS / 'sharc-overflow-test.comp'))
        with (out / f'{label}.stdout.log').open('w') as stdout, (out / f'{label}.stderr.log').open('w') as stderr:
            run(str(executable), str(shader), expectation, env=environment, stdout=stdout, stderr=stderr)
        output = (out / f'{label}.stdout.log').read_text()
        records = [json.loads(line) for line in output.splitlines() if line.startswith('{"gpu":')]
        assert len(records) == 1 and records[0]['expected_outcome_verified']
        logs = output + (out / f'{label}.stderr.log').read_text()
        assert not re.search(r'VUID-|SYNC-HAZARD|Validation Error', logs), f'{label}: validation errors'
        if args.validation:
            assert 'Insert instance layer "VK_LAYER_KHRONOS_validation"' in logs
            assert 'Inserted device layer "VK_LAYER_KHRONOS_validation"' in logs
        record = records[0]
        record['synchronization_validation_confirmed'] = args.validation
        (out / f'{label}.json').write_text(json.dumps(record, indent=2) + '\n')
        print(f'{label}: expected outcome verified; {sum(record["checks"].values())}/12 safe invariants')


if __name__ == '__main__':
    main()
