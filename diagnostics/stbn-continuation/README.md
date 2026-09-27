# First-continuation blue-noise sampling — not selected

Replacing the first rough opaque continuation's random numbers with a
spatiotemporal blue-noise mask did not establish a useful reduction in rapid-turn
cave blotches. The selected play build remains `99c78c0e…`.

## Scope

The probe changes only the first camera continuation on rough, opaque, nonmetal,
nonemissive surfaces, excluding hands and primary-surface replacement paths.
The Disney estimator and PDF remain unchanged. Its three RNG advances supply
jitter inside 8-bit mask bins, preserving subsequent RNG state. Coordinates
repeat every 128 pixels and the SHaRC frame counter selects one of 64 slices.
The existing file-backed array-texture loader supplies the RGBA8 UNORM asset;
native code, Java, ray count and lighting scales stay unchanged.

The public patch excludes the third-party mask. The fetch tool retrieves pinned
NVIDIA bytes and retains their **separate non-commercial evaluation license**.
The cookbook's license does not apply to that asset. The copied Disney sampler
retains the upstream attribution and MIT notice in `SOURCE-NOTICES.txt` and in
the existing `util/disney.glsl` shipped with the shader pack.

## Measured result

One valid six-turn control/candidate pair uses 2560×1440 lossless YUV444 capture,
1334×750 ray input, fixed exposure 2 and a 144 FPS cap.

| Native-resolution measure | Control → probe |
|---|---:|
| Relative wall RMS, 50 ms | 0.026921 → 0.027357 |
| Relative wall RMS, 300 ms | 0.018621 → 0.018442 |
| Relative wall RMS, 1.2 s | 0.012091 → 0.012053 |
| 95th percentile 32px tile RMS, 50 ms | 2.4659 → 2.4623 |
| Final-compose GPU interval | 1.1904 → 1.2270 ms |

Native crops and contact sheets do not show a useful improvement. The small
mixed differences do not justify further performance/material selection tests.
These measurements compare each run with its own settled image using common
wall masks; they are not ground truth, artifact counts or a comfort assessment.
GPU intervals use the final 1,000 capped records, not physical display delivery.

An earlier candidate launch is **invalid for quality comparison**: it logged a
missing block/item atlas, showed magenta inventory icons and opaque held-item
planes over the walls. Validation, raw-readback and unchanged-build repeat
launches had normal items. The loading failure's cause is unconfirmed; it must
not be reported as a sampling regression. The rejected scores are retained in
the measurement record with an explicit invalid marker. The cave review tool
now rejects this log marker before calculating scores; the known invalid launch
was used to verify the guard without modifying its preserved records.

## Validation and replay

Release/raw compilation passes 173/173 and 174/174 stage-correct shader jobs.
Khronos instance/device and synchronization validation are active and clean.
Every sampled GPU RGB byte matches the source mask at the expected pixel and
frame: 217,793 idle, 228,529 returned, 491,693 turned-early and 499,206 turned-settled
eligible paths. HDR identity, source composition, finite values and readback
sentinels pass. This confirms activation, not effectiveness.

Apply `probe-after-primary-nee.patch` after all 13 main and six optional cave
patches. Run `python3 tools/fetch-stbn-probe-asset.py ADVANCED_DIRECTORY` before
packaging. The tool requires Pillow and may reuse local downloads via
`--archive STBN.zip --license License.txt`. Review the upstream asset license.
No asset or compiled game binary is included in this repository.

For raw diagnostics, also apply `../raw-light/native-readback.patch` and
`capture-after-probe.patch`. Layer 0 retains whole-continuation source luminance;
layer 1 contains fetched RGB bytes and the SHaRC frame counter. Run
`tools/analyze-stbn-continuation.py RAW_DIRECTORY --mask PATH_TO_RGBA8`.
Both patch recipes replay to exact tested shader bytes.

[Measurements](../../measurements/stbn-continuation-2026-09-27.json) record valid
and invalid trials separately. [Upstream NVIDIA STBN](https://github.com/NVIDIA-RTX/STBN)
is pinned to `48b2839e4d8b7f0202ac72c6b0ae720d235a5b8b`.
