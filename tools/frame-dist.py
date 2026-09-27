#!/usr/bin/env python3
"""Frame-time distribution and spike spacing for a mangoapp CSV log.

Usage: frame-dist.py MANGOAPP.csv [threshold_ms=7.09]
"""
import csv, sys, collections
p = sys.argv[1]
thr = float(sys.argv[2]) if len(sys.argv) > 2 else 7.09
with open(p) as f:
    next(f); next(f)
    ft = [float(r['frametime']) for r in csv.DictReader(f)]
s = sorted(ft); n = len(ft)
print(f'{n} frames, mean {sum(ft)/n:.2f} ms, fps {1000*n/sum(ft):.1f}, 1% low {1000/(sum(s[-max(1,n//100):])/max(1,n//100)):.1f}')
print('percentiles', ' '.join(f'p{q}={s[min(n-1,int(n*q/100))]:.2f}' for q in [50, 90, 95, 99, 99.9]))
over = [i for i, x in enumerate(ft) if x > thr]
print(f'frames over {thr} ms: {len(over)} ({100*len(over)/n:.1f}%)')
big = [(i, round(ft[i], 1)) for i, x in enumerate(ft) if x > 1.25 * s[n // 2]]
print('frames >1.25x median:', len(big), big[:60])
gaps = collections.Counter(b - a for a, b in zip(over, over[1:]))
print('spacing between frames over threshold (frames: count):', dict(gaps.most_common(8)))
h = collections.Counter(round(x) for x in ft)
print('hist(ms):', dict(sorted(h.items())))
