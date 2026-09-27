# Optional reconstruction frame-duration hint — not selected

Supplying `InFrameTimeDeltaInMsec = 1000 / 144` did not improve rapid-turn cave
settling at the 144 FPS test cap. The selected renderer leaves this optional
NGX field at zero. Its SDK comment describes a denoising/motion timing hint;
zero is allowed and its presence alone does not establish an integration bug.

This native-only diagnostic changes one evaluation field and prints a marker
when the DLSS feature is initialized. All shader, Java and other jar entries
are identical to the selected `99c78c0e…` build. The constant is solely for
the capped comparison and is unsuitable for variable-rate normal play.

| Native-resolution measure | Selected control → hint probe |
|---|---:|
| Relative wall RMS, 50 ms | 0.026540 → 0.027486 |
| Relative wall RMS, 300 ms | 0.018348 → 0.018625 |
| Relative wall RMS, 1.2 s | 0.012134 → 0.012129 |
| 95th percentile 32px tile RMS, 50 ms | 2.4384 → 2.5631 |
| DLSS GPU interval | 1.02416 → 1.02556 ms |

The six candidate turns reuse the recent, unchanged selected-build control
from the [reflectance-guide comparison](../specular-reflectance-guide/README.md).
This is not an additional independent control run. Output is 2560×1440,
ray input 1334×750, exposure 2 and lossless YUV444 recording. Scores compare
each run with its own settled image, using common wall masks. They are not
ground truth, artifact counts or a comfort assessment. Timing uses the last
1,000 capped GPU records, not physical display delivery.

Native compilation and confirmed Khronos instance/device plus synchronization
validation pass. Both game launches print the expected native marker. Normal
items and the remaining cave blotches are visible in the candidate capture.
No useful gain justified implementing live frame timing or pursuing uncapped,
material or outdoor checks. This result does not prove the SDK ignores the hint.

Apply `probe-after-primary-nee.patch` after all 13 main and six optional cave
patches, then rebuild the native core. Patch replay matches tested source text
after newline normalization. The production wrapper was restored with fresh
mtime and the exact selected `7ae07e54…` library rebuilt before capture.
The play jar was not changed.

[Measurements and hashes](../../measurements/rr-frame-duration-2026-09-27.json)
include the shared-control provenance and scope.
