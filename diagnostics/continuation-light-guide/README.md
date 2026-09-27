# Continuation light guides and cache retention

These September 27 diagnostics were **not selected for normal play**. Guiding
all eligible bounce rays added work without reducing the cave-turn settling
error. Guiding only cache updates gave a small, unreplicated difference. Keeping
cache entries longer also failed to improve this test. The installed runtime
update correction, jar `e54e3c58…`, remains the control.

Apply the diagnostic patches after the thirteen normal MCVR patches, optional
cave-counts patches 0001–0005, and the pinned SHaRC allocation correction:

- `cache-only.patch` adds a light-directed proposal to rough opaque diffuse
  continuation sampling, only on SHaRC update paths.
- `all-paths.patch` applies **after** `cache-only.patch` and extends the same
  proposal to eligible viewing paths.
- `retention-1024.patch` is a separate experiment on the control. It changes only
  the resolve shader's stale-entry limit from the configured 256 to 1024 frames.
  The 64-frame accumulation window and cache allocation remain unchanged.

These patches are excluded from build scripts. Remove the diagnostic before
normal play. The two new guide headers must be included when packing the
advanced shader archive; merely replacing its existing entries is insufficient.

The guide selects an emissive triangle from the surrounding 27 chunk sections,
then constructs a broad directional cap around its centroid. It uses current
chunk metadata because SHaRC runs before the light-neighborhood alias pass.
Origin, nonempty-count and buffer-address checks precede dereferencing. The
proposal is discarded before BSDF sampling if its center faces below the
shading surface. It changes no explicit ray budget or bounce limit.

Within the diffuse lobe, sampling mixes the existing cosine proposal with the
cap at probability 0.5. All sampled directions use the resulting full BSDF
mixture density, including directions drawn from the specular proposal. Material
lobe selection is retained. The selected guide is conditioned on before drawing
the direction; its discrete emitter-selection probability is not another factor
in that conditional density. No additional emission term is added. This uses
the [single-sample importance-sampling model](https://pbr-book.org/4ed/Monte_Carlo_Integration/Improving_Efficiency).
A normalized proposal can still increase variance when it points toward an
unhelpful light or neglects other lights.

The actual GLSL sampler is checked on the RTX 5090 against independent uniform
hemisphere quadrature. Twelve fixtures cover absent, aligned, multiple,
misaligned and occluded lights; grazing, tilted and metallic surfaces; and both
cap-width endpoints. Means must agree within six estimated sampling standard
errors plus a 0.2% numerical-reference allowance. No-guide and metal outputs
must also be identical to the original sampler. All checks pass with Khronos
instance/device and synchronization validation enabled. These controlled
integrals do not prove the whole cached, reconstructed renderer unbiased.
They exercise the sampler before the production caller's existing PDF floor,
cache filtering and image reconstruction.

Reproduce that test without launching Minecraft, using the patched MCVR tree:

```sh
python3 tools/check-continuation-guide.py \
  --mcvr /path/to/MCVR \
  --source /path/to/MCVR/src/shader/world/ray_tracing/internal/advanced \
  --output /tmp/continuation-guide-check
```

It requires `glslc`, a C++ compiler, Vulkan, NumPy, and the Khronos validation
layer. Use `--layer-path /path/to/explicit_layer.d` if the layer is not installed
in a standard location. The output directory must be new. The runner selects
the RTX 5090 explicitly and records raw GPU readback, shader hashes and results.

Both guide scopes pass all 173 actual-stage shader compilation jobs. Actual
game-generated closest-hit SPIR-V uses the chunk-light descriptor and the
correct runtime update-bit gate. The retention compute SPIR-V directly compares
incremented stale age against 1024, confirming the diagnostic was active.

Six alternating private cave turns use manual exposure 2, a 144 FPS cap,
60 FPS capture, 1334×750 rays and 2560×1440 output. The other settings are 48
initial candidates, temporal cap 8, emission strengths 32/8, four bounces,
SHaRC update factor 5, SPBR, Voxy v17 and DLSS RR 310.9.1/F. Review uses motion
threshold 3 and the fresh control's wall masks for every variant.

| Variant | Relative RMS, 50 ms | Relative RMS, 300 ms | Cache update, ms | Final compose, ms |
|---|---:|---:|---:|---:|
| Control | 0.029158 | 0.020115 | 0.1369 | 1.2005 |
| Guide cache updates | 0.028054 | 0.019610 | 0.2079 | 1.2062 |
| Guide all eligible paths | 0.029314 | 0.020469 | 0.2099 | 1.7093 |
| Retain cache for 1024 frames | 0.029373 | 0.020071 | 0.1367 | 1.1936 |

These are one capture per variant. The cache-only difference is about 3.8% at
50 ms and 2.5% at 300 ms; no repeat or confidence interval establishes it as a
useful gain. Settled wall means differ by less than 0.031 on the 0–255 scale.
RMS is transient difference from each run's own settled view, not a count of
artifacts or absolute image error. Cost values average the last 1000 completed
GPU timing records in the settled view. Capped headless timing does not establish
physical display delivery or a 144 FPS floor.

Full per-turn values, capture hashes, compiled-stage evidence and sampler results
are in [the measurements](../../measurements/continuation-guide-retention-2026-09-27.json).
Neither experiment changes the selected build or establishes that the remaining
spots are a hardware limit. Sampling and reconstruction of newly revealed
indirect light remain open investigation areas.
