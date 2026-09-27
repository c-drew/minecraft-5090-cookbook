# Fast turns in torchlit caves

Status, September 27, 2026: a real reservoir-count defect is corrected and the
observed spots are substantially reduced. Fine transient noise remains. A
sampling optimization preserves comparable stability with 48 candidates. A
subsequent cache-energy correction provides a small additional improvement.
The later [frame scheduling fix](frame-slots.md) reduces rapid-turn engine
stalls while preserving these shader changes. Valid outdoor traversal tests
exceed 144 FPS at the 1% low, but rare longer frames remain. This does not establish a strict 144 FPS minimum or
eliminate all visible defects. An earlier outdoor comparison was invalid; its
correction is retained below.

## Reproduction and diagnosis

The symptom appears immediately after a fast turn to another torchlit wall,
even when a settled screenshot looks clean. Tests used a private copy of a saved
deep cave, SPBR 18_8 Legacy, Voxy v17, four bounces, parallax and SHaRC enabled,
2560×1440 output, and a fixed 1334×750 ray-traced input. No test commands were
sent to the play world.

The camera starts still, then makes three pairs of approximately 180-degree
turns in 0.1 seconds with three seconds between turns. Capture is 1440p60;
rendering is capped at 144. Frame-time measurements happen after recording.
The two Radiance caps (`maxFps` and `inactivityFpsLimit`) must both be set;
Minecraft's vanilla cap does not control this renderer.

Visibility discarded a failed reservoir's attempted sample count, and reuse
omitted zero-contribution donors from normalization. This conditioned reuse on
bright survivors. The correction retains counts through visibility rejection,
empty RIS output, and temporal/spatial reuse. NVIDIA's
[RTXDI reservoir reference](https://github.com/NVIDIA-RTX/RTXDI-Library/blob/main/Include/Rtxdi/DI/Reservoir.hlsli)
also retains the count when discarding an invisible selected sample. This is a
bookkeeping correction, not a claim that the complete implementation has
visibility-aware, unbiased resampling.

The earlier camera patch supplies the effected view matrix to RR, matching
primary rays, depth, and motion vectors. The optional player-shadow switch
removes a separate large silhouette cast by the camera player. Neither fixes
the sample-count defect by itself.

## Evidence and limitations

Both fast-turn variants below use official DLSS 310.9.1, requested RR preset F,
and the camera/shadow changes. The baseline has 16 candidates and direct-light
strength 4. The corrected profile has 64 candidates and strength 32. Recalibration
is necessary because fixing the survivor bias lowers the previous brightness.

| Mean over six turns | Baseline | Corrected profile |
|---|---:|---:|
| Relative wall RMS at 50 ms after turn | 0.09653 | 0.03666 |
| At 150 ms | 0.06559 | 0.02969 |
| At 300 ms | 0.04732 | 0.02382 |
| At 600 ms | 0.03051 | 0.01753 |
| At 1.2 s | 0.01656 | 0.01215 |
| Settled wall luma, two directions (8-bit) | 85.6 / 45.1 | 82.1 / 43.8 |

Each wall crop is compared with its own settled image, with exposure normalized
inside the crop. Hands, torch flame, and HUD are excluded. Motion end is estimated
from the video to roughly one captured frame. This measures convergence; it is
not an absolute image-quality score, an artifact count, or proof of zero defects.
At native capture resolution the dense mottling is visibly reduced.

The [recorded measurements](../measurements/cave-turn-2026-09-27.json) retain the
six events and exact timing metrics. To review another capture with the same
protocol, run `python3 tools/cave-turn-review.py CAPTURE_DIR` with NumPy, Pillow,
and FFmpeg installed. The directory must contain `fast-turns.mp4` and
`turn-events.json`; the latter records each input's start/end seconds and yaw.
The tool writes convergence JSON and a contact sheet. Fixed wall crops are
specific to these two camera directions and must be adjusted for another scene.

| Performance comparison | Baseline avg / 1% low | Corrected avg / 1% low |
|---|---:|---:|
| Cave, 144 FPS cap, ~8 s timing | 144.0 / 111.4 | 143.9 / 110.9 |
| Invalid walking test: player trapped in terrain, ~24 s | 180.7 / 136.0 | 157.1 / 119.8 |

**Correction:** those last two numbers were initially described as an outdoor
walk and a 13% outdoor regression. End-of-run captures show the camera inside
terrain. The movement command inherited Y=63 from the prior indoor scene instead
of setting the outdoor starting height. The outdoor claim is withdrawn. The
runner now fixes the start height to 76 and records actual start/end positions,
rejecting a walking classification when horizontal travel is too small.

In the invalid route, GPU timestamps put initial light generation at about
0.34 ms before and 1.18 ms after, averaged over the final twelve 300-frame windows.
That is useful evidence of shader cost at that camera, not outdoor throughput.
The 144 cap hides throughput headroom and
exposes the known client-tick pacing issue; capped 1% lows cannot establish how
the normal VSync configuration presents frames. No minimum-FPS claim follows
from these measurements. New movement runs also use a completed 30-second log;
the earlier short tests read a still-growing CSV partway through its default
30-second recording interval.

Brightness checks covered the base bedroom by day and night and a sealed stone
room with one and four wall torches. They showed similar brightness and relief.
The bedroom files were originally named `outdoor-day/night`; they are indoor
captures. The subsequent intended outdoor walking route was invalid as described
above. The fast-turn cave capture and fixed-camera lighting checks are unaffected.

## Reproducing the experimental profile

Build with the optional patches after the thirteen normal MCVR patches:

```sh
MCVR_CAVE_COUNTS=1 scripts/build.sh
```

Close the game and back up the jar, shader settings, `fork.properties`, and DLSS
libraries before installing. Use
[`config/experimental/cave-counts/advanced.zip.txt`](../config/experimental/cave-counts/advanced.zip.txt)
and [`fork.properties`](../config/experimental/cave-counts/fork.properties).
The relevant shader settings are `initial_samples=48`,
`direct_light_strength=32.0`, `temporal_confidence_cap=8.0`, and
`player_block_light_shadows=render_pipeline.false`.
The sample count is light candidates per pixel, not full path samples.

The current optional stack includes the count correction, sampling optimizations
and cache-energy correction below. To reproduce the earlier count-only comparison, apply only
experimental patch 0001 and use 64 candidates with history cap 24.

Download Linux SR and RR libraries from the official
[NVIDIA DLSS 310.9.1 release](https://github.com/NVIDIA/DLSS/tree/v310.9.1/lib/Linux_x86_64/rel).
The engine still requests `.310.5.3` filenames: install the new file contents
under those loader filenames in `minecraft/radiance/`. Verified SHA256:

| Library contents | SHA256 |
|---|---|
| `libnvidia-ngx-dlss.so.310.9.1` | `7561f16cab74e2b7ccf791bf44bb9cc43abb44bcf78f33c5663520ad4e857e02` |
| `libnvidia-ngx-dlssd.so.310.9.1` | `15043b4129a420b09dcd45a0294cb15f135da23054602827f68095f8080b05b0` |

The count-only local jar was `9847db5e95db124218b7c80d5ce3952c1f08111f2750301c2f1cf8598036ab23`.
Rebuilding can change jar metadata and native bytes; the hash is provenance for
the tested artifact, not a promise of a byte-identical rebuild. Forty-seven
affected shader variants compiled. The shader-only artifact preserved the prior
camera-corrected Java/native payload, whose native SHA256 was
`9fd73ac6de346bf05564a06fd64bace71037573b3ef7b4a338525286c996c72d`.

## Reducing sampling cost without changing final material shading

Two additional experimental patches use a cheaper, positive importance target
for rough opaque dielectrics (roughness at least 0.35) and randomly shifted
Hammersley points for light/chunk source choices. Smooth, metallic and
transmissive targets retain the full material evaluation. Final shading always
uses the original Disney BRDF, traced visibility and parallax shadows.
Candidate count falls from 64 to 48; render resolution, four bounces, SHaRC,
textures and the reconstruction model stay the same.

The [RTXDI application bridge](https://github.com/NVIDIA-RTX/RTXDI/blob/main/Doc/RtxdiApplicationBridge.md)
permits approximate importance BRDFs, distinct from final shading. The source
sequence follows the [Hammersley construction](https://www.pbr-book.org/4ed/Sampling_and_Reconstruction/Halton_Sampler),
with independent uniform shifts per pixel/frame. Source marginals and existing
proposal PDFs are retained; alias decisions and points on lights remain random.
Explicit unoccluded targets also make initial, temporal and spatial stages
consistent. This is not credited with removing a live height march: the compute
surface-preparation path already disables that march in this configuration.

| Mean relative wall RMS over six turns | Count fix, 64 | Optimized, 48 |
|---|---:|---:|
| 50 ms after turn | 0.03666 | 0.0381 |
| 150 ms | 0.02969 | 0.0304 |
| 300 ms | 0.02382 | 0.0242 |
| 600 ms | 0.01753 | 0.0178 |
| 1.2 s | 0.01215 | 0.0122 |

This is comparable convergence, not an additional artifact reduction over the
64-candidate fix. Both retain fine transient noise. The optimized profile is
about 60% lower than the original faulty sampler at 50 ms and 49% lower at
300 ms by this metric. Settled wall brightness stays near 82/44.

The corrected outdoor test uses an artificial elevated forest lane: an invisible
floor at Y=79 and cleared headroom prevent collision with terrain and trees.
All four 30-second runs traveled 190.8 blocks, verified from start/end positions
and endpoint captures. The first fixed-height natural-route attempt hit a tree
after 23.2 blocks and was rejected.

| Forest lane, 260 cap, headless Gamescope | Count fix, 64 | Optimized, 48 |
|---|---:|---:|
| First pass, average / 1% low FPS | 216.1 / 170.0 | 222.5 / 172.8 |
| Repeat, average / 1% low FPS | 214.9 / 176.6 | 221.6 / 183.2 |
| Frames over 6.944 ms, both runs | 6 / 12,794 | 6 / 13,210 |
| Worst observed frame | 10.14 ms | 10.43 ms |

The small throughput gain does not establish a strict 144 FPS minimum.
Thirty-second rapid-turn diagnostics also show outliers: the optimized profile
averaged 190.4 FPS but MangoApp's 1% low was 65.6 FPS, with a 59.3 ms maximum gap.
Engine timestamps do not reproduce the largest gaps: world GPU passes remained
near 5 ms and render-thread frames peaked near 16 ms in the same interval.
The discrepancy between game rendering and the nested presentation/timing path
remains unresolved. A visible VSync run aborted because the desktop was locked;
it is not a display-validation result. A separate attempt to defer the swapchain
acquire wait produced no useful gain and was rejected.

Three matched material views include gold, copper, glass over glowstone and water.
Lighting/reflections remained visually comparable; average crop luma differed
by less than 0.1/255. This is a limited material check, not a guarantee about all
resource-pack materials. All 194 advanced shader variants compiled. The tested
jar changes only the advanced shader archive; Java/native bytes are preserved.
Its SHA256 is `0a74c082111f70e404a319d88ce65ba2f9392d33b5f55922db78f5b0b3a18271`.
See [sampling measurements](../measurements/cave-sampling-2026-09-27.json) for
full precision, configuration, convergence events and valid movement records.

## Shorter reservoir history

The selected settings additionally lower `temporal_confidence_cap` from 24 to 8.
The shader limits temporal carry to one quarter of this cap, with a minimum of
one, so this reduces the maximum previous-reservoir merge count from 6 to 2.
It also lowers the spatial output confidence cap. This affects reservoir
resampling history; it does not blur the rendered image or change DLSS's history
settings. Final shading, shadows and render resolution remain unchanged.

| Mean relative wall RMS | Optimized 48, cap 24 (6 turns) | Cap 8 (12 turns, two launches) |
|---|---:|---:|
| 50 ms | 0.03814 | 0.03320 |
| 150 ms | 0.03036 | 0.02622 |
| 300 ms | 0.02417 | 0.02210 |
| 600 ms | 0.01781 | 0.01629 |
| 1.2 s | 0.01225 | 0.01166 |
| 2.3 s | 0.00352 | 0.00356 |

The improvement repeated, with nearly unchanged settled brightness (82.23/44.00
versus 82.06/43.76). Early convergence improves by about 13% over the optimized
cap-24 profile, and 66% versus the original faulty sampler by this metric.
Some settling noise remains. Cap 4 gave similar early convergence but somewhat
more settled noise, so cap 8 was retained. These figures do not establish a
perceptual threshold or guarantee that every scene is artifact-free.

The cap-8 forest repeats averaged 221.8 / 221.7 FPS, with 1% lows of
166.6 / 181.6 FPS. Both traveled the same verified 190.8 blocks. Five of
13,192 frames exceeded 6.944 ms; the worst was 11.55 ms. Throughput is comparable
to cap 24, and the strict frame-time floor remains unproven.
The gold/copper/glass/water comparison was repeated with cap 8. Surface relief,
lighting and reflections remained comparable; crop-mean luma differences from
the count-64 profile were +0.165, +0.114 and -0.115 on the 8-bit scale.

A diagnostic with three visibility-tested RIS groups of 16 candidates, instead
of one group of 48, did not materially improve convergence. That shader change
was rejected and is not part of the published patch stack.

To roll back, close the game and restore the saved jar and its corresponding
settings together. Restoring only the jar while leaving strength 32 can greatly
overbrighten the old sampler. The default cookbook recipe remains the historical
performance profile; this experiment is not silently included in it.

## Diagnostic results

- With the corrected 48-candidate profile and cap 8, removing temporal reuse
  worsened early relative wall RMS (0.04450 at 50 ms, versus about 0.03320).
  The cave also brightened. The diagnostic was rejected.
- Randomly shifted, stratified spatial-donor positions gave no material gain
  (0.03336 at 50 ms). The published shader retains the tested random positions.
- Earlier, pre-count-fix tests disabling SHaRC or changing RR from F to E did not
  remove the fast-turn spots. Later cache-disabled results are documented below.
- Disabling both reuse stages, or keeping spatial reuse alone, darkened the cave.
  Lower absolute image error from a darker image is not evidence of a fair fix.
- Keeping temporal reuse alone worsened the speckling.
- Rejecting motion behind the prior camera and clamping RG16F motion did not
  materially improve this reproduction; that diagnostic was not installed.
- The count fix at 16 candidates and strength 32 improved early relative RMS by
  about 45%; 64 candidates improved it further at a measurable GPU cost.

Further tests of the corrected 48-candidate, cap-8 profile help separate remaining
noise sources. One-bounce lighting lowers 50 ms relative RMS to 0.01925, but
darkens the walls and removes indirect lighting. Raising light candidates to
128 retains four bounces but gives only 0.03187, close to the preceding 0.03320.
Neither was selected. Averaging two indirect paths gives 0.03241 at 50 ms and
0.02086 at 300 ms, while final-compose GPU time rises from about 1.22 to 3.00 ms.
That diagnostic retains first-path guide data and is not suitable for shipping;
the small image gain also does not justify its GPU cost.

Source inspection found another guide mismatch: final-compose resamples an
opaque BSDF but can classify its hit distance using the primary pass's earlier
lobe choice. A candidate classifies the actual continuation before tracing.
It compiled in all 92 affected shader variants and completed the cave run,
but this convergence test was essentially unchanged. It remains archived,
pending material/other-denoiser review, and is not in the published patch stack.
See the [diagnostic measurements](../measurements/cave-diagnostics-2026-09-27.json)
for exact results and limitations.

The private world snapshot, Voxy jar, NVIDIA binaries, and captures remain local.
This repository distributes the code, settings, protocol, and measured results.

## Distinguishing engine timing from compositor timing

Two 30-second tests use the pre-cache-correction 48-candidate, cap-8 profile and ten
rapid turns per interval. Recording stops before these measurements. The native
log covers more than 99.97% of each explicit window. It measures one engine
`acquireContext` entry to the next, including Java work and GPU/presentation
waits; it does not measure when a physical display shows an image.

| Measurement, first / repeat run | Engine wall interval | MangoApp interval |
|---|---:|---:|
| Average FPS | 193.25 / 193.28 | 190.16 / 190.58 |
| 1% low FPS | 106.12 / 107.65 | 60.34 / 66.90 |
| Worst interval, ms | 15.46 / 15.20 | 64.58 / 70.19 |
| Intervals over 6.944 ms | 77 / 77 | 48 / 54 |

The engine's longest intervals spend roughly 13 ms waiting on a frame fence.
These are real engine delays to investigate. The much larger MangoApp gaps
cannot be treated as equivalent engine-frame durations. These headless results
also do not establish how the normal fullscreen VSync path behaves.

There is a source-level timing-protocol lead: the first two timing fields in
[Gamescope 3.16.25](https://github.com/ValveSoftware/gamescope/blob/3.16.25/src/mangoapp.cpp)
and [MangoHud v0.8.4](https://github.com/flightlessmango/MangoHud/blob/v0.8.4/src/app/mangoapp_proto.h)
have opposite names/order. Gamescope fills its first timing field from
[image-readiness notifications](https://github.com/ValveSoftware/gamescope/blob/3.16.25/src/commit.cpp),
and this MangoHud version logs that field. These upstream tags match the installed
version numbers, but distribution patches and installed binary layout have not
been checked. This is not a confirmed installed-binary bug or proof that the
compositor delivered every rendered frame.

The [timing audit](../measurements/cave-timing-audit-2026-09-27.json) preserves
both sets of metrics and their scopes. To analyze a complete native log:

```sh
python3 tools/engine_frame_metrics.py cpu-frames.csv --start UNIX_SECONDS --end UNIX_SECONDS
```

Read it after the game exits so buffered rows are complete. Only intervals wholly
inside the requested window are counted. Inspect `window_coverage`; missing or
incomplete logs must not be used to claim a frame-time floor. The private runner
now records this window and parses the native log after clean shutdown whenever
`MCVR_CPU_FRAME_LOG` is enabled.

## Correcting cached-radiance energy

Experimental patch 0004 fixes two cache-bookkeeping issues. On a cache hit, the
query path previously added cached radiance after local shading and weighted it
with the newly sampled BSDF. It now replaces that local contribution and uses
the incoming path throughput. The SHaRC entry already includes local radiance
and later weighted path contributions. Material demodulation and separate
emission are disabled in this build.

Cache updates also used camera-visible emission strength at bounce zero and
indirect strength at later bounces, writing both to the same world cache. The
update variants now consistently use indirect emission strength. Normal
camera-visible emission and the separate vertex-emission term are unchanged.
This follows the update/query separation in NVIDIA's
[SHaRC integration guide](https://github.com/NVIDIA-RTX/SHARC/blob/main/docs/Integration.md).
Cache eligibility and cone gating are unchanged in the selected build.

The installed profile retains 48 candidates, history cap 8, strength 32, four
bounces and SHaRC. Two launches with six turns each give:

| Mean relative wall RMS | Before cache correction | After, 12 turns |
|---|---:|---:|
| 50 ms | 0.03320 | 0.03080 |
| 150 ms | 0.02622 | 0.02479 |
| 300 ms | 0.02210 | 0.02118 |
| 600 ms | 0.01629 | 0.01586 |
| 1.2 s | 0.01166 | 0.01136 |
| 2.3 s | 0.00356 | 0.00350 |

Settled wall luma is 81.97/43.53 versus 82.23/44.00. This is about 7% lower early
error from the cache correction, and about 68% lower than the original faulty
sampler. Fine transient noise remains. The metric compares each image with its
own later settled reference; it cannot establish unbiased lighting, an artifact
count, or absence of discomfort during play.

Three material captures retain surface relief and metallic/glass/water
reflections. Mean crop luma changes by +3.70/+2.15/+0.10 on the 8-bit scale.
These checks cover a limited set of materials. Ninety-two affected shader
variants compiled, and all 85 advanced shader sources in the clean patch-stack
checkout match the tested jar. Java/native payloads are unchanged. Tested jar
SHA256: `c10e03af5f90c563621d32346cb804db0415c6e39e07a432140f82b56427f600`.

Four forest intervals each traveled a verified 190.81 blocks on the same
artificial elevated lane. The first two averaged 221.96/221.20 FPS in MangoApp,
comparable to the preceding profile. The first interval includes a 49.11 ms gap
without an accompanying native log; its cause remains unknown. Two instrumented
repeats did not reproduce that gap:

| Instrumented repeat, first / second | Engine wall interval | MangoApp interval |
|---|---:|---:|
| Average FPS | 222.61 / 220.65 | 222.52 / 220.70 |
| 1% low FPS | 146.29 / 146.04 | 181.21 / 179.10 |
| Worst interval, ms | 8.91 / 10.30 | 6.63 / 8.81 |
| Intervals over 6.944 ms | 22 / 28 | 0 / 2 |

Native log coverage exceeds 99.98% for each 30-second interval. These results
retain the original outlier and distinguish the timing sources; they do not
prove a strict 144 FPS floor or delivery to a physical fullscreen display.

Disabling SHaRC was also tested with the preceding shader build. Four uncached
bounces lower 50 ms relative RMS to 0.02854 and raise forest average throughput
to about 240 FPS, but darken the three material crops by 11.62/8.61/2.56 luma.
Eight uncached bounces recover only part of that room lighting and reduce
throughput to about 218 FPS. Both cache-disabled profiles were rejected as
general replacements. The combined correction retains the brighter interiors.
Individual query-only and emission-only jars were built but not independently
playtested, so their visual effects cannot be separated from this experiment.

A separate eligibility diagnostic used preceding-surface roughness and the
incoming lobe, admitted the first secondary hit after rough/diffuse scattering,
and squared GGX alpha in the glossy cone. It compiled in all 92 affected variants
but worsened six-turn relative RMS to 0.06609 at 50 ms and 0.04069 at 300 ms.
Settled luma rose to 86.12/44.01. It was rejected, never installed, and the source
was restored. Those three changes were tested together; the result does not
attribute the regression to an individual component.

See [cache measurements](../measurements/cave-cache-energy-2026-09-27.json) for
full-precision results, all twelve turn events, and the rejected alternatives.
The cache correction changes only the jar; reverting just this step restores
the preceding optimized jar while keeping its matching settings. The later
[frame scheduling change](frame-slots.md) has its own jar-only rollback, which
must run first if installed. Revert the cache step before the earlier
sampling/count steps.


## Further rapid-turn diagnostics

Three follow-ups did not usefully reduce the remaining noise. Each comparison
used its own six-turn control, the same installed lighting profile, a 144 FPS
rendering cap and 60 FPS capture. The diagnostic builds were never installed.

| Relative wall RMS, control → treatment | 50 ms | 300 ms |
|---|---:|---:|
| RR history reset during/just after rapid rotation |0.03146→0.03223|0.02140→0.02179|
| Cache-update density: one pixel per 5×5 block → 3×3 |0.03091→0.03079|0.02083→0.02103|
| A quarter of cache updates aimed at the opposite view |0.03079→0.03110|0.02071→0.02102|

The reset probe's final repeat logged 27 reset episodes to retained stderr.
An earlier stdout marker was discarded by the private launcher, so that initial
enabled run did not independently establish activation. The confirmed repeat
did. This rejects that reset policy, not every possible RR history change.

The first density comparison was also invalid: Java silently removed the
native-recognized field because the module descriptor did not expose it. The
corrected test changed only the descriptor, then verified the requested value
in the saved configuration. Mean GPU update cost rose from 0.1381 to 0.2136 ms
in the final 1,200 frames, with no useful image gain. The local harness now rejects
these native options when the selected jar does not declare them.

The opposite-view probe redirected 25% of the existing update budget behind
the camera. Camera/query rays and throughput weights stayed unchanged. All 92
affected shader variants compiled; settled luma changed from 81.98/43.53 to
81.99/43.73. It also gave no useful convergence gain. These results leave the
installed cache density and update directions unchanged. See the
[scoped follow-up measurements](../measurements/cave-followups-2026-09-27.json).

A separate shader-counter audit found 115 failed cache allocations before the
six-turn recording and the same displayed total afterward. This exposed a
source error: failed insertion returns slot 0, and its caller ignores the
failure flag, allowing an unrelated cache entry to be used. The observation
does not link that failure path to the rapid-turn spots. The settled binary
overlay is an observation through RR/tone mapping, not raw buffer readback;
a targeted overflow correctness test and fix remain outstanding. The overlay
also makes this run unsuitable for convergence or performance scoring.
[Optional diagnostic patches and activation checks](../diagnostics/cave-followups/README.md)
are kept outside the production series.
