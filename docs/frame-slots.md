# Independent frame-resource slots

September 27, 2026: patch `mcvr/0013` removes a needless resource-fence wait during
rapid cave turns. The tested release is installed locally. It changes native
frame scheduling, while preserving the preceding sampling/cache fixes, lighting,
materials, resolution, four bounces and SHaRC. Fine post-turn noise and occasional
long frames remain. A strict 144 FPS floor and physical fullscreen delivery are
still unverified.

## Cause and correction

The framework selected command buffers, resource-retention buckets and fences
using the acquired swapchain-image index. In the measured headless path, WSI
sometimes returned the image submitted in the immediately preceding frame. The
CPU then waited for that frame's queued work and rendering before preparing the
next frame, leaving a gap in GPU production.

One captured 17.261 ms engine interval waited 13.498 ms at that fence. The GPU
submission being waited for had an 8.209 ms submission-to-start delay and a
5.348 ms rendering envelope. The subsequent GPU idle gap was 3.671 ms. These
timelines identify serialization; the queued delay is not a driver-only cost.

The patch advances render resources through a bounded two-slot ring. Each slot
is reused only after its fence signals. The acquired image and its image index
are stored separately for the final copy and presentation. Timing query slots,
retained resources and screenshot selection follow the resource slot.

Present-wait semaphores remain indexed by acquired swapchain image. The existing
acquire-semaphore wait protects their reuse, following the
[Khronos semaphore-reuse guidance](https://docs.vulkan.org/guide/latest/swapchain_semaphore_reuse.html).
Two resource slots allow CPU preparation to overlap GPU rendering while bounding
the frames in flight; see [Khronos's explanation](https://docs.vulkan.org/tutorial/latest/03_Drawing_a_triangle/03_Drawing/03_Frames_in_flight.html).
The cursor resets during swapchain recreation. No additional render-resource
slots are allocated; in-flight rendering is bounded to two slots. Input latency
was not measured.

## Matched diagnostic runs

Both builds used the same temporary complete-submission GPU logger. Each scene
had two 30-second timing intervals. Cave intervals contained ten rapid half-turns;
the six-turn video was recorded separately. Forest intervals each traveled a
verified 190.81 blocks on an artificial elevated lane with cleared headroom.

RTX 5090 / 9800X3D, 2560×1440 output, 1334×750 ray input, SPBR, Voxy v17,
48 light candidates, history cap 8, direct-light strength 32, four bounces, SHaRC,
DLSS 310.9.1 with requested RR preset F. Timings are uncapped, VSync off, in
headless Gamescope. No commands were sent to the play world.

| Cave, first / repeat | Previous scheduling | Two independent slots |
|---|---:|---:|
| Engine average FPS | 186.74 / 187.30 | 192.74 / 192.76 |
| Engine 1% low FPS | 98.46 / 107.36 | 155.29 / 155.76 |
| Longest engine interval, ms | 17.261 / 16.853 | 6.902 / 6.828 |
| Engine intervals over 6.944 ms | 82 / 67 | 0 / 0 |
| Longest complete GPU envelope, ms | 5.740 / 5.625 | 5.463 / 5.451 |
| Longest GPU completion interval, ms | 9.024 / 8.927 | 6.055 / 6.029 |
| Largest gap between GPU submissions, ms | 3.687 / 3.674 | 0.947 / 0.930 |

The two-slot diagnostic measured 11,563 complete engine frames with no interval
over the 144 FPS budget. That limited observation does not establish a universal
minimum. Complete GPU envelopes include possible scheduling inside the measured
submission; consecutive GPU-completion intervals additionally expose gaps
between submissions. Frame IDs and CPU start timestamps are matched, and the
reported clock-calibration uncertainty was below 2 microseconds.

MangoApp still reported substantially longer intervals: the two-slot cave runs
had maxima of 36.06 and 41.70 ms. Its measurement boundary differs from the engine
and GPU logs. This discrepancy remains unresolved and is not evidence that all
frames reached a display on time. Neither the GPU logger nor the engine logger
measures physical display delivery.

Forest engine averages remained about 221–222 FPS. The two-slot diagnostic had
1% lows of 145.58/148.78 FPS, but maximum engine intervals of 11.704/9.249 ms.
Its longest GPU-completion intervals were 11.822/7.280 ms. The frame-slot change
therefore does not solve every traversal spike.

## Exact release validation

The initial release removed the temporary GPU logger and frame-slot diagnostic
switch. A later binary audit found that a stale `device.cpp.o` still contained
the optional calibrated-timestamp extension branch, gated by
`MCVR_GPU_FRAME_LOG`. That variable was absent in the release tests and normal
play, so the branch was inactive. The earlier claim that this binary removed
all diagnostic code was too broad. Source restoration had preserved an old
modification time, leaving this object unrecompiled.

Only `libcore.so` differs from the preceding cache-corrected jar; all Java and
shader resources are byte-identical. The following measurements belong to the
initial `4ab830b6…` release, which was playtested before installation. They are
retained under their original binary identity.

| Release, first / repeat | Rapid cave turns | Validated forest lane |
|---|---:|---:|
| Engine average FPS | 191.35 / 191.30 | 222.33 / 221.12 |
| Engine 1% low FPS | 152.01 / 155.63 | 148.99 / 155.96 |
| Longest engine interval, ms | 10.590 / 8.511 | 9.075 / 8.365 |
| Engine intervals over 6.944 ms | 3 / 2 | 19 / 11 |
| MangoApp average FPS | 189.00 / 188.70 | 222.23 / 221.18 |
| MangoApp 1% low FPS | 87.80 / 78.65 | 177.94 / 185.86 |
| Longest MangoApp interval, ms | 21.42 / 41.38 | 8.05 / 6.03 |

Engine coverage exceeds 99.97% in these four windows. The release retains the
main cave improvement, but five of its 11,478 cave intervals exceed 6.944 ms.
The zero-exceedance diagnostic result must not be substituted for this result.
The remaining release spikes combine acquisition/fence waits with other
preparation work; this build has no complete-GPU log to attribute them further.

Six release video turns give mean relative wall RMS of 0.03217 at 50 ms and
0.02145 at 300 ms, with settled luma 81.95/43.53. That is comparable to the prior
cache-corrected profile, not an additional spotted-noise cure. The metric compares
each crop with its own later settled image, exposure-normalized, with roughly
one capture-frame timing uncertainty.

The Khronos 1.4.357.0 validation layer, including synchronization validation,
was loaded in three private material-room launches: diagnostic switch off,
switch on, and exact release with VSync on. All were capped at 30 FPS for
functional checks, not performance measurement. Loader logs confirm layer
insertion; no `VUID-`, `SYNC-HAZARD` or `Validation Error` was reported. The layer
was extracted locally from the official distribution package, without changing
the system installation.

Gold, copper, glass over glowstone, water and stone relief look consistent in
matched captures. Release crop luma changes were +0.021 / −0.062 / +0.028 on a
0–255 scale. These scene checks do not prove synchronization or visual correctness
on every rendering path. Physical fullscreen pacing and comfort still require
an unlocked desktop and a play check.

## Recompiled native validation

The affected source was restored with fresh modification times and its dependent
objects rebuilt. The new binary contains none of the GPU logger, calibrated
extension, turn-reset diagnostic, or frame-slot-switch environment strings.
It changes only the native jar entry; no production source behavior or quality
setting changed. The source patch series is unchanged.

The corrected `7ce983fd…` jar was independently playtested and is now installed.
Both cave intervals again included ten fast turns; both forest intervals traveled
a verified 190.81 blocks. These results are separate from the initial release:

| Recompiled native, first / repeat | Rapid cave turns | Validated forest lane |
|---|---:|---:|
| Engine average FPS | 191.66 / 191.67 | 221.46 / 220.29 |
| Engine 1% low FPS | 154.79 / 153.98 | 145.48 / 153.26 |
| Longest engine interval, ms | 6.926 / 6.965 | 10.939 / 8.550 |
| Engine intervals over 6.944 ms | 0 / 1 | 19 / 12 |
| Longest MangoApp interval, ms | 26.49 / 31.71 | 9.01 / 6.33 |

All four native log windows cover more than 99.97% of their requested duration.
One of 11,498 cave engine intervals exceeds the 144 FPS budget. Longer forest
and MangoApp intervals remain; this does not establish a strict floor or
physical display delivery.

Six new cave turns give relative RMS 0.03148 at 50 ms and 0.02165 at 300 ms,
with settled luma 81.98/43.49. These are comparable to the preceding build;
the native cleanup is not a new noise treatment. A new VSync material launch
loaded Khronos synchronization validation and reported no validation errors.
Matched material crops retain relief and reflections, with luma differences
−0.013 / +0.066 / +0.024 compared with the initial release.

For future diagnostic removal, invalidate the affected compiled objects and
audit the resulting binary in addition to reviewing source diffs. Successful
incremental linking alone did not catch this stale-object issue.

## Source, measurements and recovery

The normal thirteen-patch MCVR series plus all four optional cave patches apply
cleanly. The resulting framework files match the built release sources, and all
87 advanced/common shader sources match the installed jar.
The optional cave profile is still needed for the shader fixes described in
[cave-artifacts.md](cave-artifacts.md).

Installed recompiled jar SHA256:
`7ce983fd0d1276302e22f6f6d0b13e4a08f3f97bd0ceae67ceaafc3afcfa300b`.
Native SHA256:
`7ae07e54c58042e4539cc43656fb03c396b8ede54a9ce69a9161e6fda41bd1a1`.

See the [full-precision measurements](../measurements/frame-slots-2026-09-27.json)
and [diagnostic source and log-review procedure](../diagnostics/frame-slots/README.md).
The analysis tool rejects missing/duplicate/mismatched frame identities and bad
clock calibration; seven synthetic regression tests and all eight diagnostic
measurement windows passed.

Installation replaces only the jar. A new checksum-verified backup retains the
initial frame-slot jar, and its older backup still retains the cache-corrected
jar. Settings and the saved cave-region hash are unchanged. With the game closed,
revert the native cleanup first, then the frame-slot step if desired, before
older cache/sampling steps. The production build has no temporary frame-slot
switch as a rollback option.
