# Explicit player-emitter sampling probe — not selected

The [source diagnostic](../emitter-source/README.md) identified the camera
player's world model as the source of most unmatched bright first hits in the
darker cave view. This private prototype registers its emissive geometry and
samples it directly. It removes covered bright hits, but the first visible
comparison does not establish a useful reduction in turn artifacts. The normal
game remains on `99c78c0e…`.

## Implementation

The native prototype shares the existing UV-clipped emitter extraction with
the player entity. It accepts only the actual indexed-quad layout, retaining
the original transport for unsupported geometry. Camera-relative triangle data
uses the same frame's TLAS translation and a separate buffer for each frame
context. The buffer publishes an empty header when no player lights exist and
grows without truncating support. The tested torch exports 16 triangles with
total area 0.0145806 square blocks.

At eligible rough opaque primary surfaces, the direct pass samples one triangle
using area/power/distance importance, then a uniform point on that triangle.
It evaluates the original Disney material and one visibility ray, including
the player's world mesh. Its emitted-light scale is the previous continuation
scale of 8, rather than the block-light direct scale of 32. Both emitter sides
are sampled because the original hit shader emits on both sides.

A direct-image marker and ray-state bit identify surfaces where this estimator
ran. The first continuation suppresses PBR emission only on a matching
registered player triangle. Separate vertex emission, unsupported geometry,
later bounces, SHaRC updates and smooth/metal/transparent primary paths retain
their existing behavior. The normal ray payload size is unchanged.

## Result and limits

One six-turn pair uses exposure 2, the 144 FPS cap, common wall masks and
confirmed Khronos instance/device plus synchronization validation:

| Metric | Selected control | Player-light probe |
|---|---:|---:|
| Relative settling RMS, 50 ms | 0.024874 | 0.026809 |
| Relative settling RMS, 300 ms | 0.017676 | 0.017679 |
| Relative settling RMS, 1.2 s | 0.010812 | 0.010731 |
| Direct-light GPU pass, final 1,000 records | 0.19718 ms | 0.28578 ms |
| Final-compose GPU pass, final 1,000 records | 1.22142 ms | 1.22995 ms |

Early error is higher and the 300 ms result is essentially unchanged. Visual
review of both six-turn contact sheets does not establish a useful gain.
Settled wall means change by +0.0108 / +0.0282 on a 0–255 scale. This does not
prove brightness equivalence in other scenes. Validation overhead limits these
runs to roughly 134 FPS; their timings are not release throughput or physical
display delivery. Materials, outdoor behavior and uncapped performance were
not tested because the image-quality result does not support selection.

The raw follow-up verifies that this is an active estimator change. It finds
54 covered first-emissive hits in the idle frame and 86 after returning. Every
covered hit has final PBR emission factor zero; none is on a path with remaining
hit-shading luminance above 1. Four unmatched bright paths remain in the return
frame. These are single random captures, not a paired variance estimate.
Source luminances still sum to continuation luminance at every eligible pixel,
within the established half-float tolerance. Readback identities and validation
checks pass. Release and raw variants compile 173/173 and 174/174 shader jobs.

## Reproduce

Apply `probe-after-primary-nee.patch` to the pinned source with all 13 main and
six optional cave patches. Build its native core and package its Advanced
shader archive together. This is an experimental native-plus-shader change;
the shader alone requires a descriptor absent from the selected native build.

For the raw follow-up, additionally apply `../raw-light/native-readback.patch`
and `capture-after-probe.patch`. Layer 0 retains source luminances. Layer 1
contains the caller's player-NEE flag, `payload_flag + 2 * triangle_match`,
the final PBR emission factor, and sampled material emission. The previous
position payload field carries these diagnostic values only at bounce 1,
without setting its motion-validity flag.

Both recipes replay exactly for shader bytes and for native source text after
normalizing CRLF line endings. Native sources were restored with fresh mtimes,
and the production library rebuilt to exact hash `7ae07e54…` after each private
build. [Measurements and hashes](../../measurements/player-emitter-nee-2026-09-27.json)
preserve the unselected result for follow-up work.
