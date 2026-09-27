#!/usr/bin/python
"""Compile-check the advanced shader pack with the engine's stage-define mapping.

Every pass in configs.json is compiled with the attribute defines (current values from the
optional --settings file, else the defaults), the pass's own definitions and
the execution globals. SHaRC query/update defines apply only to ray generation;
hit/miss stages are shared, as in collectRayTracingPassShaderRequests. The update
resolve compute shader receives the update defines. Only checks compilation.

Usage: tools/check-advanced-shaders.py MCVR [--settings FILE] [--pass NAME ...]
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('mcvr', type=Path)
parser.add_argument('--settings', type=Path)
parser.add_argument('--pass', dest='passes', action='append', default=[])
parser.add_argument('--spirv-dir', type=Path, help='write assembly with distinct shared/query/update filenames')
parser.add_argument('--manifest', type=Path, help='record stage definitions and compilation results')
args = parser.parse_args()
ROOT = args.mcvr.resolve()
PACK = ROOT / 'src/shader/world/ray_tracing/internal/advanced'
VALUES = args.settings
if args.spirv_dir:
    args.spirv_dir.mkdir(parents=True, exist_ok=True)

stage = Path(tempfile.mkdtemp(prefix='mcvr-check-'))
shutil.copytree(PACK, stage, dirs_exist_ok=True)
shutil.copytree(ROOT / 'src/shader/util', stage / 'util', dirs_exist_ok=True)
shutil.copytree(ROOT / 'src/common', stage / 'common', dirs_exist_ok=True)
shutil.copytree(ROOT / 'extern/sharc/include', stage / 'extern/sharc/include', dirs_exist_ok=True)

config = json.loads((PACK / 'configs.json').read_text())
values = {}
if VALUES is not None:
    for line in VALUES.read_text().splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            values[k] = v


def attribute_value(attr):
    value = values.get(attr['name'], attr['default_value'])
    kind = attr['type'].split(':', 1)[0]
    if kind == 'bool':
        return '1' if value.endswith('true') else '0'
    if kind == 'enum':
        return str(attr['type'][5:].split('-').index(value))
    if kind == 'vec3':
        return f'vec3({value})'
    return value


defines = {'FACE': '0', 'MCVR_DEVICE_RAY_TRACING_INVOCATION_REORDER': '1', 'MCVR_COMPILER_RAY_TRACING_INVOCATION_REORDER': '1'}
for attr in config['attributes']:
    define, value = attr.get('define'), attribute_value(attr)
    if isinstance(define, str):
        defines[define] = value
    elif isinstance(define, dict):
        for name, expression in define.items():
            defines[name] = expression.replace('X', value)
for section in ('execution', 'execution_post'):
    for variable in config.get(section, {}).get('global_variables', []):
        for name, value in variable.items():
            defines[name] = 'true' if value is True else 'false' if value is False else str(value)

STAGES = {'.rgen': 'rgen', '.rchit': 'rchit', '.rahit': 'rahit', '.rmiss': 'rmiss', '.comp': 'comp',
          '.frag': 'frag', '.vert': 'vert'}
jobs = []
wanted = set(args.passes)
for p in config['passes']:
    if wanted and p['name'] not in wanted:
        continue
    extra = dict(p.get('definitions', {})) | dict(p.get('defines', {}))
    variants = [extra]
    if p.get('query_sharc'):
        variants = [extra | {'USE_SHARC': '1', 'SHARC_QUERY': '1'}]
        if config.get('sharc', {}).get('update_pass') == p['name']:
            variants.append(extra | {'USE_SHARC': '1', 'SHARC_UPDATE': '1'})
    files = [p[k] for k in ('rgen', 'compute', 'fragment', 'vertex') if k in p]
    for group in p.get('hit_groups', {}).values():
        files += list(group.get('shaders', {}).values())
    files += [m['shader'] if isinstance(m, dict) else m for m in p.get('miss', [])]
    for f in dict.fromkeys(files):
        stage_variants = variants if f == p.get('rgen') else [extra]
        for v in stage_variants:
            jobs.append((p['name'], f, v))
    if config.get('sharc', {}).get('update_pass') == p['name']:
        jobs.append((p['name'], config['sharc']['resolve_comp'],
                     extra | {'USE_SHARC': '1', 'SHARC_UPDATE': '1'}))


def compile_one(job):
    name, f, extra = job
    out = '/dev/null'
    if args.spirv_dir:  # write SPIR-V assembly per pass/file for inspection
        variant = 'update' if extra.get('SHARC_UPDATE') == '1' else 'query' if extra.get('SHARC_QUERY') == '1' else 'shared'
        out = str(args.spirv_dir / f"{name}.{f.replace('/', '_')}.{variant}.spvasm")
    command = ['glslc', '--target-env=vulkan1.3', '-O', f'-fshader-stage={STAGES[Path(f).suffix]}', '-I', str(stage),
            '-o', out, str(stage / f)] + (['-S'] if out != '/dev/null' else [])
    command += [f'-D{k}={v}' for k, v in (defines | extra).items()]
    r = subprocess.run(command, capture_output=True, text=True)
    return name, f, extra, r.returncode, r.stderr


failed = 0
results = []
with ThreadPoolExecutor(16) as pool:
    for name, f, extra, code, err in pool.map(compile_one, jobs):
        results.append({"pass": name, "file": f, "stage_definitions": extra, "exit_code": code})
        if code:
            failed += 1
            print(f'FAIL {name} {f} {extra}\n{err[:3000]}')
print(f'{len(jobs) - failed}/{len(jobs)} compiled')
if args.manifest:
    args.manifest.write_text(json.dumps({'attribute_definitions': defines, 'jobs': results,
                                        'compiled': len(jobs) - failed, 'failed': failed}, indent=2) + '\n')
shutil.rmtree(stage)
sys.exit(1 if failed else 0)
