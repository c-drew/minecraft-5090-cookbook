# Raw lighting captures before Ray Reconstruction

GPU readbacks verify that the rejected spatial filter executes its intended
arithmetic on real cave data. They also identify sparse emissive-surface hits
as the largest bright continuation component in this cave. These diagnostics
are not an installed fix or a performance measurement.

Sixteen frames were captured: four stages each for the radius-zero control,
3×3 filter, source attribution, and bounce attribution. Each run captures the
original view, about 50 ms after a rapid turn, after three seconds in that view,
and after returning. These are single samples at each stage, not a temporal
variance estimate. Disk readback disturbs later frame timing.

## What the captures establish

All known-value images pass channel, row, and array-layer checks. The no-filter
HDR is byte-identical before and after the no-op pass. All captured HDR values
are finite, and removing the recorded continuation leaves no materially
negative composition remainder. Khronos instance/device validation and
synchronization validation are confirmed without reported errors.

A NumPy replay of the actual 3×3 loader, geometry tests, albedo normalization,
weights, and colored transmission has zero unexpected pixels in all four
filtered frames. The tolerance is three half-float ULPs or 0.00002, whichever is
larger. Maximum absolute differences are 0.000977–0.003906; these are consistent
with floating-point operation ordering and half-float storage. This supports
the integration arithmetic, not the filter's visual suitability.

In the turned view, the filter spreads the bright input samples:

| Stage | Raw continuation pixels above Y=0.1 | Filtered pixels above Y=0.1 | Newly above threshold |
|---|---:|---:|---:|
| Early | 2,915 | 15,233 | 12,553 |
| Settled | 2,989 | 15,924 | 13,107 |

Higher peaks decrease, but more pixels receive moderately bright samples.
Combined with the separately observed persistent post-RR speckles, this is
evidence against that particular prefilter. It does not isolate every detail
of DLSS RR's response or establish that all spatial filtering must fail.

The source diagnostic separates hit direct lighting, remaining hit shading,
cached radiance, and misses without changing the estimator. Their luminances
sum to the recorded raw continuation within half-float tolerance at every
eligible pixel. Among 2,047 samples above Y=1 just after turning, 1,777 are
dominated by remaining hit shading and 270 by cache data. All 1,777 hit-dominated
pixels encountered emissive materials. The cave's default hit shader has one
local shading iteration: after its explicit directional-light contribution,
the remaining addition is emission. Misses are negligible here.

A separate bounce diagnostic finds that 99.82% of this hit-emission energy in
the early turned frame, and 99.95% after settling, occurs at the first secondary
hit. That is the camera → visible wall → emitter path. The primary area-light
pass also estimates direct emitter illumination, while continuation emission
is added without an MIS weight. Checking emitter coverage before partitioning
these overlapping estimators is therefore a concrete next lead. The accounting
principle is illustrated by [PBRT's simple path tracer](https://pbr-book.org/4ed/Light_Transport_I_Surface_Reflection/A_Simple_Path_Tracer),
which includes BSDF-hit emission only when it was not already handled by light
sampling, with an exception for specular paths. Actual engine coverage must
still be verified; blindly dropping all secondary emission is not justified.

## Reproduce the readback

These patches apply to the selected runtime-update source base (normal jar
`e54e3c58…`, native `7ae07e54…`). First apply the main MCVR patches, optional
cave-counts patches 0001–0005, and pinned SHaRC allocation fix. Then apply
`../indirect-prefilter/prefilter-r1.patch` and, for the no-filter control,
`../indirect-prefilter/r0-after-r1.patch`.

Apply `native-readback.patch`, rebuild the native core, and package its exact
binary alongside the selected diagnostic shader archive. The native diagnostic
is inactive unless `MCVR_RAW_CAPTURE_DIR` is an absolute directory. Create a new
empty directory and supply it in the private game's environment. While that
game is rendering, atomically rename a JSON file containing `{"id":"idle"}` to
`request.json` in that directory. Repeat with distinct IDs `turn-early`,
`turn-settled`, and `return-settled` at the intended camera stages.

The renderer records active pixels, copies tightly packed image layers, restores
the original layouts, and retains readback buffers until the owning resource
slot's fence is confirmed complete. It invalidates host memory before writing
the binaries. An atomic `manifest.json` publication indicates completion.
Three 3×2×2-layer sentinel images use RGBA16F, RGBA32F, and RGBA8 UNORM, with
different known values per layer. Captures include HDR before/after filtering,
continuation, transmission, material/geometry guides, and component images.

For source attribution, apply `sources-after-r0.patch` after the no-filter
control. It uses the diagnostic `indirect_surface` image name for two RGBA32F
layers: four source luminances, then hit count, emissive-hit count, maximum
incoming throughput, and first BSDF lobe. Applying `bounces-after-sources.patch`
changes only that second layer to first/later non-direct hit luminance,
first-hit direct luminance, and first-hit emissive count. Do not interpret the
second layer using the wrong schema.

With NumPy installed, run from the cookbook root:

```sh
python3 tools/check-raw-light-capture.py /absolute/capture/directory --identity
python3 tools/replay-indirect-prefilter.py /absolute/r1/capture/directory
python3 tools/analyze-raw-light-sources.py /absolute/source/capture/directory
python3 tools/analyze-raw-light-sources.py /absolute/bounce/capture/directory --bounce-split
```

Omit `--identity` for the filtered run. The replay expects radius 1. The
validators require all four capture stages and check their actual image sizes
and formats. The source/bounce shader configurations compile 174/174
actual-stage jobs. Native source was restored and rebuilt to the exact original
`7ae07e54…` binary after preparing the diagnostic jars. The play instance and
saved cave were unchanged.

[Measurements and raw-capture hashes](../../measurements/raw-light-2026-09-27.json)
record the evidence without committing gigabytes of game-image data. These
readback runs cannot establish a physical 144 FPS floor or user comfort.
