# Directional specular-reflectance guide — not selected

Replacing the constant F0 guide on rough opaque walls with a directional GGX
reflectance approximation did not improve rapid-turn cave settling in one
six-turn control/candidate pair. The selected play build remains `99c78c0e…`.

The existing renderer passes F0 directly as specular albedo. NVIDIA's
[integration guide, section 4.2.1](https://github.com/NVIDIA-RTX/Streamline/blob/main/docs/ProgrammingGuideDLSS_RR.md#421-specular-albedo-generation)
describes a directional approximation using F0, roughness and view cosine.
The probe expands that formula into scalar polynomials to avoid matrix layout
ambiguity. Alpha is roughness squared, matching the current Disney BSDF. The
test is limited to nonmetal, nonemissive, rough opaque first surfaces and excludes
hands and primary-surface replacement paths. It changes only the specular-albedo
guide; HDR lighting, ray count and all other guides retain their original code.
This is a suggested guide approximation, not an exact integral of Radiance's
dielectric Fresnel model or a demonstrated fix for the cave artifact.

| Native-resolution measure | Control → probe |
|---|---:|
| Relative wall RMS, 50 ms | 0.026540 → 0.027541 |
| Relative wall RMS, 300 ms | 0.018348 → 0.019015 |
| Relative wall RMS, 1.2 s | 0.012134 → 0.012290 |
| 95th percentile 32px tile RMS, 50 ms | 2.4384 → 2.4693 |
| Primary-pass GPU interval | 0.24959 → 0.24974 ms |

The darker return orientation accounts for most of the small regression; the
brighter orientation is nearly unchanged. Contact-sheet review does not establish
a visible improvement. The pair uses fixed exposure 2, cap 144, 1334×750 ray
input and 2560×1440 lossless YUV444 capture. These are own-settled-reference
residuals, not ground truth, artifact counts or a comfort assessment. GPU times
use the last 1,000 capped records and do not measure physical display delivery.

All 173 stage-correct shader jobs compile. Confirmed Khronos instance/device
and synchronization validation is clean. The unchanged items render normally
in the validation and candidate captures. A CPU sweep of 90,601 view-cosine /
roughness combinations verifies finite values and positive rational denominators;
this does not substitute for numerical GPU readback. No raw guide readback,
uncapped performance or material/outdoor follow-up was pursued for this rejected
candidate.

Apply `probe-after-primary-nee.patch` after all 13 main and six optional cave
patches to reproduce the two tested shader entries. Patch replay matches the
tested archive exactly. Native code and Java are unchanged.
[Measurements and hashes](../../measurements/specular-reflectance-guide-2026-09-27.json)
retain the comparison and scope.
