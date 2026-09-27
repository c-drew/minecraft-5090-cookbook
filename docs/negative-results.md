# What didn't work

Measured on the same rig and bench (see [benchmarking.md](benchmarking.md)), none of these made it
into the cookbook. Numbers are fps average or 1% low as noted.

## GPU side

| Idea | Result |
|---|---|
| Shader execution reordering (SER) on bounce rays | +4% outdoors, −3% at a lit base. Branchy or hinted variants were much worse. SER inside the SHaRC update pass hung the GPU (Xid 109). |
| "Fast trace" build flags for chunk and LoD BLASes | ±1%, within noise |
| Opacity micromaps | Upper-bound test: forcing all cut-out geometry opaque changed a forest sprint from 119.9 to 117.8 fps. Any-hit shading isn't the bottleneck, so micromaps can't help. |
| NVIDIA Neural Radiance Cache | Windows-only closed libraries; a quality feature, not a speed one |
| 3 ray bounces instead of 4 | +2–5%, but glass goes black |
| SHaRC lookups on the first bounce for long paths | +5%, visibly flatter distant terrain (RMSE 3.8% vs 0.8% noise) |
| Dynamic resolution (render scale follows GPU load) | DLSS Ray Reconstruction spends ~14 ms of CPU on every render size change, so each change is a hitch. A fixed render scale works. |
| A second graphics queue for BLAS builds | No gain |
| Spatially filter indirect lighting before DLSS RR | 3×3 and 5×5 prototypes add persistent cave speckles. Removing albedo normalization or using displaced parallax geometry does not cure the regression. [Reproduction and limits](../diagnostics/indirect-prefilter/README.md) |
| Earlier secondary cache access after rough primary scattering, on the corrected emission base | Saves about 0.082 ms in final composition in one cave test; no convincing convergence gain, general material/outdoor quality unvalidated. [Isolated probe](../diagnostics/first-secondary-cache/README.md) |
| Explicit area-light sampling at the first rough secondary wall | Small early settling gain does not repeat in lossless capture; adds about 0.20–0.23 ms to final composition. [Probe and measurement audit](../diagnostics/secondary-area-nee/README.md) |
| First rough continuation sampled with a spatiotemporal blue-noise mask | No useful cave settling gain in a valid lossless six-turn pair; adds about 0.037 ms to final composition. Exact GPU mask lookup verified. [Private probe](../diagnostics/stbn-continuation/README.md) |
| Directional specular-reflectance guide on rough opaque walls | Replacing F0 with a roughness/view-dependent GGX approximation does not improve cave settling in one lossless pair. [Guide probe](../diagnostics/specular-reflectance-guide/README.md) |
| Optional NGX frame-duration hint at the 144 FPS cap | A fixed 6.944 ms hint does not improve cave settling against the recent shared control; unsuitable for variable-rate play. [Native diagnostic](../diagnostics/rr-frame-duration/README.md) |

## CPU and scheduling

| Idea | Result |
|---|---|
| Per-frame chunk build budget of 0.3 ms | No gain (kept as an option, off) |
| `chunkBuildingBatchSize=4` (Radiance option) | Worse: 85 fps 1% low on one flying run |
| Vulkan global queue priority `high` | Refused by the NVIDIA driver without `CAP_SYS_NICE` (kept as an option) |
| Chasing render-thread slowdowns as scheduler contention | Per-thread run-queue wait showed the render thread wasn't waiting for a CPU |

## Settings we compared

- **Render distance**: 16, 24 and 32 chunks outdoors gave 162, 155 and 149 fps (before the later
  patches). With LoD terrain beyond 16 chunks, 16 is the sweet spot.
- **DLSS Balanced** instead of Quality: +18–19% and hard to tell apart in stills. The cookbook's
  render scale (0.78125 of Quality) lands between Balanced and Performance.
- **GPU overclock** (+150 MHz core offset): +5% average, at more power and heat. The undervolt
  (3075 MHz at 1000 mV) keeps about half of that gain while drawing 41 W less than stock. Same
  session on this card: stock ~111.6 fps at 505 W, +150 core 117.2 at 520 W, undervolt 114.0 at
  464 W.

## Still open

- **Clouds**: the cloud geometry's acceleration structure is rebuilt every frame. With clouds off,
  standing still went from 216/169 to 224/181 fps (avg/1% low). Caching it is the next easy win.
- **Animated textures** (SPBR has many) are updated on the CPU; not profiled in depth yet.
- **The first seconds after joining a world**: chunk loading and LoD meshing run flat out. Our
  benchmark starts 20 s after the world loads, so this window isn't in the results tables.
