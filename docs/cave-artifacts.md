# Fast turns in torchlit caves

Status, September 27, 2026: a real reservoir-count defect is corrected and the
observed spots are substantially reduced. Fine transient noise remains. The
tested 64-candidate profile costs outdoor performance, so it is experimental and
does not satisfy the goal of a 144 FPS minimum without distracting artifacts.

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
| Outdoor walk, 260 cap, ~24 s timing | 180.7 / 136.0 | 157.1 / 119.8 |

The outdoor average loses about 13%. GPU timestamps put initial light generation
at about 0.34 ms before and 1.18 ms after, averaged over the final twelve
300-frame windows of these runs. The 144 cap hides throughput headroom and
exposes the known client-tick pacing issue; capped 1% lows cannot establish how
the normal VSync configuration presents frames. Outdoor results still lack the
required headroom. No minimum-FPS claim follows from these measurements.

Brightness checks covered the base bedroom by day and night and a sealed stone
room with one and four wall torches. They showed similar brightness and relief.
The bedroom files were originally named `outdoor-day/night`; they are indoor
captures. The timed walking route itself was outdoors.

## Reproducing the experimental profile

Build with the optional patch after the twelve normal MCVR patches:

```sh
MCVR_CAVE_COUNTS=1 scripts/build.sh
```

Close the game and back up the jar, shader settings, `fork.properties`, and DLSS
libraries before installing. Use
[`config/experimental/cave-counts/advanced.zip.txt`](../config/experimental/cave-counts/advanced.zip.txt)
and [`fork.properties`](../config/experimental/cave-counts/fork.properties).
The three relevant shader settings are `initial_samples=64`,
`direct_light_strength=32.0`, and `player_block_light_shadows=render_pipeline.false`.
The sample count is light candidates per pixel, not full path samples.

Download Linux SR and RR libraries from the official
[NVIDIA DLSS 310.9.1 release](https://github.com/NVIDIA/DLSS/tree/v310.9.1/lib/Linux_x86_64/rel).
The engine still requests `.310.5.3` filenames: install the new file contents
under those loader filenames in `minecraft/radiance/`. Verified SHA256:

| Library contents | SHA256 |
|---|---|
| `libnvidia-ngx-dlss.so.310.9.1` | `7561f16cab74e2b7ccf791bf44bb9cc43abb44bcf78f33c5663520ad4e857e02` |
| `libnvidia-ngx-dlssd.so.310.9.1` | `15043b4129a420b09dcd45a0294cb15f135da23054602827f68095f8080b05b0` |

The tested local jar was `9847db5e95db124218b7c80d5ce3952c1f08111f2750301c2f1cf8598036ab23`.
Rebuilding can change jar metadata and native bytes; the hash is provenance for
the tested artifact, not a promise of a byte-identical rebuild. Forty-seven
affected shader variants compiled. The shader-only artifact preserved the prior
camera-corrected Java/native payload, whose native SHA256 was
`9fd73ac6de346bf05564a06fd64bace71037573b3ef7b4a338525286c996c72d`.

To roll back, close the game and restore the saved jar and its corresponding
settings together. Restoring only the jar while leaving strength 32 can greatly
overbrighten the old sampler. The default cookbook recipe remains the historical
performance profile; this experiment is not silently included in it.

## Diagnostic results

- Disabling SHaRC or changing RR from F to E did not remove the fast-turn spots.
- Disabling both reuse stages, or keeping spatial reuse alone, darkened the cave.
  Lower absolute image error from a darker image is not evidence of a fair fix.
- Keeping temporal reuse alone worsened the speckling.
- Rejecting motion behind the prior camera and clamping RG16F motion did not
  materially improve this reproduction; that diagnostic was not installed.
- The count fix at 16 candidates and strength 32 improved early relative RMS by
  about 45%; 64 candidates improved it further at a measurable GPU cost.

The private world snapshot, Voxy jar, NVIDIA binaries, and captures remain local.
This repository distributes the code, settings, protocol, and measured results.
