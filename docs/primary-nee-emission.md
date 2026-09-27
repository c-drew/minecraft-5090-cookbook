# Avoid overlapping primary emitter contributions

The primary area-light pass estimates illumination from nearby emissive
triangles. The continuation ray then independently adds emission when it hits
one of those same lights immediately after leaving the visible surface. Both
contributions entered the image at full configured strength, without an MIS
weight. Sparse bright continuation hits made newly revealed cave walls less
stable after a fast turn.

[Raw GPU captures](../diagnostics/raw-light/README.md) identified this path:
almost all non-cache emissive continuation energy in the turned cave view came
from the first secondary hit. A guarded partition of these estimators reduces
the settling error in two independent comparisons. It is a partial correction;
remaining cache samples and temporal reconstruction still produce some noise.

## Scope of the correction

Optional patch 0006 uses ray-state bit 21 to identify the first continuation
segment of an opaque, rough, nonmetallic primary surface whose direct-light
pass ran with ReSTIR enabled. Shared world hit shaders suppress their PBR
emission term only if the hit belongs to the area sampler's current support:

- A current, positive-probability light-neighborhood entry must contain it.
- The corresponding chunk origin and storage index must still be valid.
- The emitter must have positive area/radiance and face the incoming ray.
- The hit must lie on a registered emitter triangle, within a 0.0005-block
  plane tolerance and 0.0001 barycentric tolerance.

Primary origin and prepared-surface chunk coordinates must agree. Missed
matches conservatively retain the original emission. Material emission is
removed at its original shading expression, preserving separate vertex
emission and avoiding subtraction of half-float material values afterward.
The decision concerns the sampler's support, not whether one realized reservoir
sample happened to select that particular light.

Later bounces, SHaRC updates, camera-visible emitters, transparent paths, primary
metals and smooth reflections retain their previous behavior. The first ray
still traces and shades its hit normally. Ray count, path depth, render size,
payload size, cache configuration, native code and Java are unchanged. The final
pass declares its light-neighborhood buffer dependency explicitly. The
accounting approach follows the light-sampling partition described in
[PBRT's simple path tracer](https://pbr-book.org/4ed/Light_Transport_I_Surface_Reflection/A_Simple_Path_Tracer);
this does not establish that the entire ReSTIR/cached renderer is unbiased.

## Results

Four six-turn captures use manual exposure 2, a 144 FPS cap, shared wall masks,
1334×750 input, 2560×1440 output, DLSS 310.9.1/F, SPBR and Voxy v17. Settings
remain 48 candidates, history 8, emission strengths 32/8, four bounces and
SHaRC update factor 5. The second pair reverses run order.

| Run | Relative RMS at 50 ms | At 300 ms | Settled final-compose GPU time |
|---|---:|---:|---:|
| Control | 0.029721 | 0.020313 | 1.2164 ms |
| Candidate | 0.024333 | 0.017407 | 1.2415 ms |
| Candidate repeat | 0.023995 | 0.017227 | 1.2605 ms |
| Control repeat | 0.029015 | 0.019588 | 1.1972 ms |

The improvement is 17–18% at 50 ms and 12–14% at 300 ms. These are differences
from each capture's own settled view, with normalized crop exposure, not an
artifact count or ground-truth image error. The nearby-torch view improves
more than the darker return view. Removing overlapping light dims the bright
wall by about 2 on a 0–255 gray scale; this is not a brightness-neutral change.

The diagnostic candidate's early turned raw capture has 244 continuation samples
above Y=1, versus 2,047 in the earlier source capture. Only one is dominated by
remaining hit shading, versus 1,777 before. Cache samples remain. These are
different random frames and cannot be treated as a paired variance estimate.

The three material views retain glass, water, metal reflections and parallax
relief. Crop mean changes are −0.411 / −0.160 / −0.059 gray levels. Animated
water and torches differ between captures, so their pixel RMSE is not an
absolute material-quality metric. The candidate passes confirmed Khronos
instance/device and synchronization validation in the raw and VSync material
runs. The release compiles 173/173 shader jobs; the readback variant compiles
174/174. Replaying all 13 main and six optional patches from pinned MCVR
`9905c81` reproduces the six tested shader files exactly.

Two uncapped 30-second cave intervals with ten rapid turns each average
192.62 / 192.49 FPS, with 1% lows of 156.65 / 155.88. One of 11,551 measured
intervals exceeds 6.944 ms; the worst is 7.383 ms. The preceding build averaged
193.70 / 193.69 in its earlier cave runs. These are native acquire-to-acquire
engine intervals in private Gamescope, not physical display delivery.

Four 30-second forest traversals compare the release with a fresh control.
Each covers 190.81 blocks on the same artificial Y=80 lane:

| Build/run | Average FPS | 1% low FPS | Worst interval | Intervals over 6.944 ms |
|---|---:|---:|---:|---:|
| Control A | 221.52 | 140.39 | 12.188 ms | 25 / 6,645 |
| Control B | 220.12 | 153.56 | 9.419 ms | 10 / 6,602 |
| Candidate A | 220.90 | 142.93 | 15.797 ms | 21 / 6,626 |
| Candidate B | 219.70 | 148.69 | 18.185 ms | 13 / 6,590 |

Average throughput differs by less than 0.3% from this control. Slow-frame
counts are similar and the candidate has the longest individual stalls; this
small sample does not establish a tail-latency improvement or a strict 144 FPS
floor. Material checks and repeated convergence gains support retaining the
correction. Remaining spots and physical fullscreen pacing/comfort are unresolved.

See [full-precision measurements](../measurements/primary-nee-emission-2026-09-27.json).

## Artifact and recovery

Release jar: `99c78c0eb5399cb73a92f7430ee03726a0a4cfb634acbf8d8d2639f847e2d777`.
Advanced archive: `d3b05b17c1b50eadf7a177c905bf4c9eec27e34583f7ca1f1bfd1cbcdb6bea44`.
Native remains `7ae07e54c58042e4539cc43656fb03c396b8ede54a9ce69a9161e6fda41bd1a1`.
Only six entries inside the Advanced archive differ from `e54e3c58…`.

Installed September 27 at 13:03 EDT. The local installer is
`tools/install-primary-nee-dedup.py`; its
rollback restores `e54e3c58…` and must precede older runtime-update rollbacks.
Run `python3 tools/install-primary-nee-dedup.py restore` from the development
tree with Minecraft closed. The backup is
`~/.local/state/minecraft-5090/play-backup-20260927-primary-nee-dedup`.
The normal game stayed closed; protected settings and the saved cave region
retain their checksums. Its next startup extracts the new shader archive.
