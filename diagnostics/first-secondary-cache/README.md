# First-secondary cache admission: diagnostic only

Allowing an earlier SHaRC lookup after rough primary scattering did not clearly
improve the cave's fast-turn settling. It saved about 0.082 ms in final
composition in this short capped test, but is not selected or installed.
Outdoor and general material quality have not been validated for this probe.

Apply `first-secondary.patch` after the thirteen main MCVR patches, optional
cave-counts patches 0001–0005, and the pinned SHaRC allocation correction. The
base is runtime-update jar `e54e3c58…`; the candidate is `ec413724…`.
Do not apply the indirect-prefilter diagnostics with this patch.

`traceSecondary` previously always began with its primary-camera exclusion
enabled, even though its input ray had already scattered at the first surface.
This probe clears that exclusion only for the opaque continuation branch at
bounce 1 with primary roughness ≥0.5 and metallic <0.5. All transparent branches
retain the old exclusion. Remaining distance, lobe and cone tests are unchanged;
cache misses fall back to the original path tracing. There is no additional
hand exclusion beyond these material/bounce conditions.

An older query-gating experiment combined three changes and used the older
cache-emission behavior. This test isolates first-secondary admission on the
corrected runtime-update base. It does not retry the combined incoming-lobe and
cone correction, and its result cannot establish those other changes' effects.

Both runs use six rapid private cave turns, fixed exposure 2, 144 FPS caps,
60 Hz capture, 1334×750 rays and 2560×1440 output. Sampling remains 48/history8,
direct/indirect strengths 32/8, four bounces and SHaRC update factor 5, with SPBR,
Voxy v17 and DLSS 310.9.1/F. The candidate compiles 173/173 actual-stage shader
jobs. No normal game files were changed.

| Variant | Relative RMS at 50 ms | At 300 ms | Final composition, ms |
| --- | ---: | ---: | ---: |
| Corrected runtime-update control | 0.028709 | 0.019661 | 1.217763 |
| Earlier secondary cache access | 0.028294 | 0.019928 | 1.135791 |

Settled wall means change by approximately +0.036 and −0.035 on a 0–255 scale
for the two directions. The slight early difference reverses at 300 ms. With
one capture per variant and approximately one video-frame alignment uncertainty,
this is not a demonstrated quality gain. The selected build remains unchanged.

RMS compares each run with its own settled image, with normalized crop exposure;
it is not ground-truth error. Pass costs average the final 1,000 settled GPU
records under the cap, not uncapped game throughput or physical FPS. See the
[complete measurements and hashes](../../measurements/first-secondary-cache-2026-09-27.json).
