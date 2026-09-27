# Isolating the remaining cave signal

September 27, 2026: separating the displayed light components points to unstable
continuation lighting. An experimental SHaRC emission separation reduced early
cave error, but material checks exposed a brightness change. Investigating that
change found an inactive earlier emission correction. The separate-emission
candidate remains a diagnostic; the smaller
[runtime update-identification fix](sharc-update-runtime.md) is the selected
approach for further validation.

## Component experiment

Three captures use identical geometry, six rapid turns, fixed manual exposure
2.0 and the same wall-pixel masks. Rendering is capped at 144; recording is 60 FPS.
Only the final opaque/noisy first-hit contribution changes. The indirect-only
recording shows broad patches fading over seconds.

| Mean over six turns | Full light | Direct plus first-hit emission | Continuation only |
|---|---:|---:|---:|
| Relative wall RMS, 50 ms | 0.03206 | 0.01984 | 0.35373 |
| Relative wall RMS, 300 ms | 0.02122 | 0.01444 | 0.22535 |
| Absolute 8-bit RMS, 50 ms | 2.037 | 1.124 | 4.819 |
| Settled luma, two directions | 81.99 / 43.50 | 78.98 / 39.84 | 12.68 / 16.88 |

These are reconstructed, tone-mapped signals. Their error scores are not additive
shares of total variance, and the dim indirect view changes RR's input distribution.
The result is a lead, not proof that every remaining artifact is indirect light.

The review tool now accepts a motion threshold and a shared mask reference.
Threshold 6 missed the last 1–3 moving frames of the dim view; threshold 3 better
matches its motion trace. All three views were re-reviewed with 3. Shared masks
prevent the dim capture from selecting only its bright islands. Default threshold
6 reproduces the retained historical control metrics exactly. See the
[diagnostic patches and commands](../diagnostics/cave-light-components/README.md).

## Emission separation

The bundled SDK already supports
[`SHARC_SEPARATE_EMISSIVE`](https://github.com/NVIDIA-RTX/SHARC/blob/0b9f58bbc8c41736042d4da964830a247e424a00/include/SharcCommon.h).
The experimental integration stores reflected light locally and supplies exact
local emission when propagating to previous vertices and querying the cache.
It changes three world shaders, with no new rays, native code or buffer layout.
Special hit types are not a complete emission-separation implementation.

The standalone Vulkan test exercises the actual SDK on an RTX 5090. It checks
fresh accumulation, query emission changes, weighted hit/miss propagation, and
resampling an existing cache entry. Separate mode passes all eleven checks;
combined mode matches its explicitly expected old accounting. The four checks
that differ are separation properties, not four safety failures in the SDK.
Both runs confirm Khronos instance/device and synchronization validation, with
no reported errors. This does not validate the entire game integration.

```sh
python3 tools/check-sharc-separate-emission.py /path/to/MCVR /tmp/emission-check --validation
```

The runner requires the pinned SDK with the cookbook allocation guard, an RTX
5090, g++, glslc and the Vulkan loader. Use a new output directory; set
`VK_LAYER_PATH` if validation is not installed system-wide. SDK headers are
verified against the pin and remain subject to NVIDIA's license.

Fixed-exposure cave error fell from 0.03206 to 0.02815 at 50 ms, and from 0.02122
to 0.01962 at 300 ms. A separate normal-exposure capture gave 0.02827 and 0.02020,
against 0.03156 and 0.02106 in the preceding release control. Fine noise remains.

Material-room brightness fell noticeably. With exposure fixed at 2.0 and a
30-second initial warmup, three crop means changed by −12.279 / −10.669 / −11.893
on a 0–255 scale. Automatic exposure and short initial warmup do not explain it.
The independent runtime update fix reproduces those images to within 0.091 /
0.041 / 0.005 crop-mean luma. That points to the old emission-strength mismatch,
not a distinct benefit from spatial emission separation, as the main lighting
change. No claim of an additional useful separation benefit is established.

Exact-candidate cave engine averages were 193.08/192.99 FPS; forest averages
221.67/220.54. Forest 1% lows were worse than the control, 145.92/147.90 versus
151.34/156.01, with rare longer frames. VSync material validation was clean.
These headless measurements do not establish physical display pacing or a
strict 144 FPS floor. The candidate was not installed.

The [full measurements](../measurements/sharc-separate-emission-2026-09-27.json)
retain component results, exact jar hashes, raw SDK readbacks, cave convergence,
timing intervals and material comparisons.
