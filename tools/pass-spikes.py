#!/usr/bin/env python3
"""Per-pass view of GPU spike frames from an MCVR_TIMING_FRAMES log.

Usage: tools/pass-spikes.py PASSES.csv [threshold_ms_over_median=0.8] [last_n_frames=6000]
"""
import collections, sys
import numpy as np

thr = float(sys.argv[2]) if len(sys.argv) > 2 else 0.8
last = int(sys.argv[3]) if len(sys.argv) > 3 else 6000
rows = []
for line in open(sys.argv[1]):
    d = {}
    for p in line.strip().split(',')[1:]:
        k, v = p.split('=')
        d[k] = d.get(k, 0) + float(v)
    rows.append(d)
rows = rows[-last:]
count = collections.Counter(k for r in rows for k in r)
names = [n for n, c in count.items() if c > len(rows) * 0.9]
M = np.array([[r.get(n, 0) for n in names] for r in rows])
tot = M.sum(1)
med = np.median(tot)
spk = tot > med + thr
print(f'{sys.argv[1]}: frames {len(rows)}  median {med:.3f}  p99 {np.percentile(tot, 99):.3f}  '
      f'spikes(>{thr}) {spk.sum()} ({100 * spk.mean():.1f}%)  worst1% mean {np.sort(tot)[-len(tot)//100:].mean():.3f}')
if spk.sum():
    diff = M[spk].mean(0) - np.median(M, 0)
    for i in np.argsort(-diff)[:6]:
        print(f'  {names[i]:36} median {np.median(M[:, i]):.3f}  spike {M[spk, i].mean():.3f}  ratio {M[spk, i].mean() / max(np.median(M[:, i]), 1e-6):.2f}')
    g = np.diff(np.where(spk)[0]); v, c = np.unique(g, return_counts=True)
    print('  gaps (count, frames):', [(int(a), int(b)) for a, b in sorted(zip(c, v), reverse=True)[:8]])
