# Secondary area-light sampling — not selected

Explicit torch sampling at the first rough secondary wall did not reliably
reduce rapid-turn cave artifacts. Two six-turn control/candidate pairs retain
the selected `99c78c0e…` profile. The experimental jar was never installed.

## Implementation

The shader-only probe draws four independent light proposals from the existing
chunk neighborhoods, resamples one by its contribution, and traces one shadow
ray. It runs at the first nonemissive rough secondary wall following an eligible
rough opaque primary surface. Its emission scale is 8, preserving the original
continuation scale. Zero-contribution proposals remain in the denominator.

A ray flag marks sampler support, including attempts that return zero. At the
next hit, only matching block emitters suppress their PBR emission. That covered
hit bypasses the cache so cached emission cannot reintroduce the sampled term;
the path continues to preserve reflected transport. SHaRC update paths, vertex
emission, unsupported lights and other materials retain their original behavior.
Five archive entries change; native code and payload size stay unchanged.

## Results

The pairs use fixed exposure 2, cap 144, 2560×1440 output, 1334×750 ray input,
and the same six rapid turns. The second uses lossless H.264 encoding of YUV444
frames. RGB-to-YUV conversion still rounds; this is not an RGB-exact recording.
A three-frame randomized YUV444 encode/decode check is byte-exact.

| Native-resolution measurement | QP18 control → probe | Lossless control → probe |
|---|---:|---:|
| Relative wall RMS, 50 ms | 0.027184 → 0.026412 | 0.027469 → 0.028085 |
| Relative wall RMS, 300 ms | 0.019436 → 0.019559 | 0.018516 → 0.018943 |
| Relative wall RMS, 1.2 s | 0.012834 → 0.012887 | 0.012185 → 0.012168 |
| 95th percentile 32px tile RMS, 50 ms | 2.4704 → 2.3750 | 2.5409 → 2.5492 |
| Final-compose GPU interval | 1.2460 → 1.4778 ms | 1.2514 → 1.4479 ms |

The small early gain does not repeat. Contact-sheet and native crop review also
do not establish a useful improvement. Timings are the last 1,000 capped GPU
records, not uncapped throughput or physical display delivery. Each run is
compared with its own settled reference using common control wall masks; these
are transient differences, not ground truth, artifact counts or proof of comfort.
Material/outdoor checks were not pursued for this unselected candidate.

Raw diagnostic captures confirm active secondary sampling on 59,821 / 62,261 /
281,867 / 285,864 eligible paths (idle / returned / turned early / turned settled).
The corresponding covered bounce-two emitter counts are 92 / 114 / 509 / 480.
All four captures pass finite-value, HDR identity, source-composition and readback
layout checks. Khronos instance/device and synchronization validation are active
and clean. Release/raw shader compilation passes 173/173 and 174/174 jobs.
Counts describe traced paths, not visible artifacts.

## Measurement correction

An animated nearby torch exceeded the old global-motion threshold after the
camera had stopped. The old detector picked frame 520 instead of 474 for the
third lossless control turn. Its settled window then overlapped the next turn;
those original scores are invalid and preserved locally as superseded results.

`tools/cave-turn-review.py` now follows the strongest motion burst, permits at
most two intervening quiet frames, and rejects an excessively late endpoint.
The QP18 probe's fifth endpoint also changes, from 856 to 852. All numbers above
use corrected endpoints. The audit leaves all 24 endpoints of the two published
primary-emitter comparisons unchanged; their 17–18% early gain is unaffected.

`tools/review-cave-fullres.py CONTROL CANDIDATE` uses those reviewed endpoints
to measure the original 1440p wall pixels and 32px tiles without downscaling.
It requires the fixed 1440p60 cave protocol. Existing 640×360 review remains
available; do not compare scores across resolutions or recording codecs.

## Reproduce

Apply `probe-after-primary-nee.patch` after all 13 main and six optional cave
patches. Package the Advanced archive with the selected native library. For
raw diagnostics, also apply `../raw-light/native-readback.patch` and
`capture-after-probe.patch`, then build the diagnostic native library.

Raw source layer 0 contains whole-continuation luminances: direct shading
(now including secondary area NEE), other hit shading, cache and miss. Layer 1
contains primary-NEE eligibility, secondary-sampler support, covered bounce-two
emitter status and bounce-two material emission. A later cache hit can still
contribute on a path whose covered bounce-two emitter bypassed the cache.
Use `tools/analyze-secondary-area-nee.py RAW_DIRECTORY` for this schema.

Both saved patch recipes replay to exact tested shader bytes.
[Measurements and build hashes](../../measurements/secondary-area-nee-2026-09-27.json)
include the corrected comparisons and endpoint audit.
