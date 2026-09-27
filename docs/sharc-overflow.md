# Failed SHaRC allocations must not alias slot zero

The later [runtime update-identification release](sharc-update-runtime.md)
retains this allocation guard and supersedes the installed artifact recorded here.

September 27, 2026: a standalone RTX 5090 test reproduces an allocation-failure
bug in the bundled SHaRC 1.6.5 shaders. A small header correction passes all
twelve GPU invariants and is installed after private cave, forest and material
regression checks. The defect is real, but the cave recordings do not
establish it as the cause of the remaining post-turn spots.

## Failure and correction

`HashMapInsert` tries sixteen entries. When none can accept the key, it returns
false and sets its output index to zero. `HashMapInsertEntry` ignored that false
result and returned zero to its callers. The later read/write helpers reject
only `HASH_GRID_INVALID_CACHE_INDEX`, so the failed insertion could read and
overwrite unrelated lighting at slot zero. A bright resolved value there could
also cause a path to stop and propagate that unrelated light to earlier vertices.

The wrapper now returns the invalid-index sentinel on failure. Existing guards
skip that entry, while later path contributions can still reach earlier valid
vertices. The fix does not terminate the whole update path or disable valid
uses of slot zero. It changes no buffer layout, sampling budget or quality setting.

The [patch](../patches/sharc/0001-Preserve-invalid-index-on-allocation-failure.patch)
applies inside the pinned SHaRC submodule, after initialization, for both normal
and optional cookbook builds. The helper checks the exact SDK revision and
recognizes repeat application. The main MCVR patch series cannot directly patch
a file inside its separately tracked submodule.

## Direct GPU reproduction

The test compiles the actual SDK functions into a Vulkan compute shader and
reads coherent GPU output after a shader-to-host barrier and fence. It does not
infer results from a reconstructed screenshot. Tests cover successful insertion
and duplicate lookup at zero, a full probe window, preservation of occupied keys,
finding an existing key through that window, absent lookup, failed-hit writes,
prefix-path lighting propagation and valid lighting writes at zero.

With a full bucket and bright unrelated slot zero, the original shader fails
four of twelve safety invariants. It writes the failed hit into zero, then
resamples unrelated `(7,7,7)` lighting instead of continuing the path. The fixed
shader passes all twelve: slot zero remains untouched and the earlier valid
vertex receives `(4,5,6)` from the hit and subsequent weighted miss. The old
shader's exact broken result is explicitly checked as a negative control.

Both executions confirm Khronos instance/device validation and synchronization
validation, with no reported `VUID-`, `SYNC-HAZARD` or `Validation Error`. This is
a deterministic failure-path test, not a concurrent stress test or a proof of
correctness for every SDK path.

After initializing the cookbook build's submodules:

```sh
bash scripts/apply-sharc-patches.sh /path/to/MCVR
python3 tools/check-sharc-overflow.py /path/to/MCVR /tmp/sharc-overflow-check --validation
```

The output directory must be new. The runner needs `g++`, `glslc`, the Vulkan
loader and an RTX 5090. It uses MCVR's bundled Vulkan headers. Install the Khronos
validation layer or point `VK_LAYER_PATH` at an extracted layer manifest.
The runner extracts baseline headers at the exact SDK pin into the output
directory, leaves working source alone, and retains both raw JSON outputs and
loader logs. Without `--validation`, the functional test still runs, but layer
insertion is not required or claimed.

## Cave result and remaining work

Six fresh fast turns give relative wall RMS 0.03156 at 50 ms and 0.02106 at
300 ms, compared with 0.03148 and 0.02165 before this correction. Settled wall
luma is 82.00/43.52 versus 81.98/43.49. That is comparable convergence and
brightness, not a demonstrated cure for the remaining noise. The earlier
allocation-counter overlay displayed 115 failures both before and after its
six-turn recording; it did not connect new allocation failures to those turns.

The exact candidate preserves all Java/native resources and changes only
`extern/sharc/include/HashGridCommon.h` inside the advanced shader archive.
Ninety-two affected world variants and the dedicated cache-resolve shader
compile. The game's extracted archive and native library match the candidate.

| Two 30-second intervals, first / repeat | Rapid cave turns | Validated forest lane |
|---|---:|---:|
| Engine average FPS | 192.68 / 192.67 | 222.22 / 221.16 |
| Engine 1% low FPS | 156.39 / 157.32 | 151.34 / 156.01 |
| Longest engine interval, ms | 6.997 / 7.046 | 10.210 / 9.375 |
| Engine intervals over 6.944 ms | 1 / 1 | 15 / 10 |
| MangoApp average FPS | 190.38 / 190.07 | 222.13 / 221.22 |
| MangoApp 1% low FPS | 86.60 / 82.54 | 177.23 / 178.94 |
| Longest MangoApp interval, ms | 31.151 / 31.181 | 7.680 / 8.292 |

Each cave timing interval contains ten rapid turns; each forest interval covers
a verified 190.81 blocks. Native log coverage exceeds 99.97% in all four windows.
Throughput is comparable to the previous native rebuild. Two of 11,559 cave
engine intervals and 25 of 13,299 forest intervals exceed the 144 FPS budget.
The earlier engine/MangoApp discrepancy is still present.

Three matched material views retain stone relief, metals, glass and water;
crop-mean luma changes by +0.030 / −0.036 / −0.097 on a 0–255 scale. A separate
30 FPS VSync material launch confirms Khronos synchronization validation and
reports no validation errors. These are limited scene checks, not a guarantee
about every material or synchronization path.

Fine post-turn noise, rare long frames, and physical fullscreen pacing/comfort
remain unresolved. The private tests use a disposable world and headless
Gamescope; engine and MangoApp intervals do not measure physical display delivery.

## Artifact and recovery

Installed jar SHA256:
`579b9def1361bbec15381fdf1de2b90cf13837de6bc92e48bc71491e829992d5`.
Native SHA256 remains
`7ae07e54c58042e4539cc43656fb03c396b8ede54a9ce69a9161e6fda41bd1a1`.
The normal game stayed closed; its next startup extracts the corrected shader
archive. Settings and the saved play-world cave region retain their checksums.

See [full-precision measurements and raw GPU outputs](../measurements/sharc-overflow-2026-09-27.json).
The local jar-only backup precedes this change. Restore it before the older
native/frame-slot/cache/sampling rollbacks. No lighting recalibration is required
when reverting just this allocation guard to the preceding `7ce983fd…` jar.
