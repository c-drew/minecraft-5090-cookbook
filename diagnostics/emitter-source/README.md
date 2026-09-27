# Residual emitter sources in the two cave views

These private diagnostics follow the selected [primary emitter correction](../../docs/primary-nee-emission.md).
They preserve the image estimator and separate two different remaining sources
of sparse bright samples. They are not installed rendering changes.

Sixteen stationary raw frames per orientation were captured with camera and
view matrices held constant. Frames are separated by roughly 14–19 rendered
frames; these are not consecutive-frame measurements. Bilinear jitter alignment
is followed by the same fixed wall crops. Every frame passes the sentinel layout
checks, exact no-op HDR identity and source-composition checks.

| View | Weighted continuation variance / HDR variance | Remainder variance / HDR variance |
|---|---:|---:|
| Toward nearby block torches | 36.56% | 63.32% |
| Darker return view | 92.01% | 7.90% |

The remainder is HDR minus weighted continuation, not necessarily just direct
light. Covariance means component percentages need not sum to 100%. Restricting
to stable material guides gives similar results. For 16×16 pixel block means,
continuation accounts for 30.57% and 89.05%, respectively. These describe
stationary pre-reconstruction input variance, not post-turn perceptual quality.

Within **unweighted** continuation, cache data dominates the turned view's
variance. In the return view, other hit shading contributes about 68.6% and
cache about 29.9%, with covariance also present. These are different quantities
from the weighted HDR decomposition. Earlier [material captures](../cache-hit-materials/README.md)
identified later cache-query hits on real torch blocks in the turned view.

## Identifying unmatched first hits

Five further four-frame captures instrument the first continuation hit. Each
keeps source luminances in layer 0 and changes only the metadata schema in
layer 1. They are separate random frames; their counts are not paired variance
comparisons.

- Coverage reaches a valid light neighborhood and positive emitter entries,
  but some glowing hit points match no registered block-light triangle.
- The LOD capture finds full emission at both the sampled level and level zero,
  with ceil(LOD)=0 for the bright unmatched return paths. Mip averaging does not
  explain these hits.
- The alpha capture finds alpha 1 in CUTOUT mode. They are not transparent texels.
- The instance capture classifies 60 of 61 bright first-emissive return paths as
  dynamic geometry, mostly one instance, rather than chunk geometry.
- A narrow inline ray query identifies mask 2 for all 66 selected return paths
  in the mask capture (and all 59 idle paths). The Java/native mapping assigns
  this mask to the camera player's world model. The private scene equips a
  torch in the offhand, making the world-model held torch the likely emitter.

“Bright first-emissive path” here means an emissive first continuation hit and
whole-continuation non-directional hit shading above Y=1. Metadata identifies
that first hit; it does not split every later emission addition. Other views
and thresholds can have other sources.

The mask diagnostic uses the [Khronos ray-query interface](https://github.khronos.org/Vulkan-Site/glslext/latest/glslext/ext/GLSL_EXT_ray_query.html)
to test each TLAS mask bit over a narrow interval around the known hit. It
matches instance, geometry and primitive indices, ignores other candidates,
and changes no lighting decisions. Its extra queries make it unsuitable for
performance measurement. All six shader variants compile 174/174 jobs and
pass confirmed Khronos instance/device and synchronization validation.

## Reproduce

Start with pinned MCVR `9905c81`, the 13 main and six optional cave patches,
and the pinned SHaRC allocation fix. Apply `../raw-light/native-readback.patch`
and **one** `*-after-primary-nee.patch` from this directory. These six independent
patches reproduce every changed shader entry in their tested archive exactly.

Use `sources-after-primary-nee.patch` for the stationary variance series and
the original source-luminance schema. Follow the [readback protocol](../raw-light/README.md).
Keep the four standard stages outside the series. Capture at least eight
stationary frames per orientation with distinct IDs, and place their published
capture directories under `series/turn/000`, `series/turn/001`, etc. and
`series/return/000`, etc. Then run:

```sh
python3 tools/analyze-raw-light-series.py /absolute/raw/directory
```

For the other five patches, layer 0 is unchanged. Layer 1 is:

| Patch/schema | x | y | z | w |
|---|---|---|---|---|
| coverage | primary NEE flag | support bits | matched facing | material emission |
| lod | primary NEE flag | bits + 64×ceil(LOD) | level-zero emission | sampled emission |
| alpha | primary NEE flag | bits + 64×alpha mode | level-zero albedo alpha | emission |
| instance | primary NEE flag | support bits | signed instance | emission |
| mask | primary NEE flag | bits + 64×instance mask | signed instance | emission |

Signed instance is the chunk index when nonnegative; negative values encode
entity custom index as `-index-1`. Support bits are 1=finite origin, 2=valid
center chunk, 4=valid neighborhood entry, 8=positive eligible emitter,
16=point on an emitter triangle, 32=matching triangle faces the ray. Code 15
therefore means no containing triangle was found; code 63 is covered support.

```sh
python3 tools/analyze-emitter-support.py /absolute/raw/directory --schema mask
```

Select the schema matching the patch. The native readback source and production
library were restored after preparing diagnostics. The normal game remains on
`99c78c0e…`. [Measurements](../../measurements/emitter-source-2026-09-27.json)
include artifact hashes, individual results and variance covariances.
