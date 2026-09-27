#!/usr/bin/env python3
"""Average the per-300-frame GPU pass timings in an mcvr-timing jsonl file (optionally the last N lines)."""
import json, sys
path = sys.argv[1]
skip = int(sys.argv[2]) if len(sys.argv) > 2 else 0
take = int(sys.argv[3]) if len(sys.argv) > 3 else None
lines = [json.loads(l) for l in open(path)][skip:]
if take: lines = lines[:take]
keys = sorted({k for d in lines for k in d if k.startswith('gpu.') and k != 'gpu_frames'})
avg = {k: sum(d.get(k, 0) for d in lines) / len(lines) for k in keys}
mx = {k: max(d.get(k, 0) for d in lines) for k in keys}
print(f'{len(lines)} windows, total gpu {sum(avg.values()):.2f} ms (max window {max(sum(d.get(k,0) for k in keys) for d in lines):.2f})')
for k, v in sorted(avg.items(), key=lambda x: -x[1]):
    if v > 0.01:
        print(f'  {k[4:].replace("rt.pass.", ""):40} {v:6.3f}  (max {mx[k]:.3f})')
cpu = sorted(((k, sum(d.get(k, 0) for d in lines) / len(lines)) for k in {k for d in lines for k in d if k.startswith('cpu.')}), key=lambda x: -x[1])[:12]
print('cpu:', ', '.join(f'{k[4:]}={v:.2f}' for k, v in cpu))
