# Identify cache updates in shared hit shaders

The engine compiles SHaRC update and query ray-generation variants, but shares
their hit and miss shaders. The earlier emission correction in optional patch
0004 depended on `SHARC_UPDATE` inside a hit shader. That define was never passed
to the shared stage, so the correction was inactive in the game.

The configured PBR emission strengths are 32 for camera-visible light and 8 for
indirect light. The first cache-update hit incorrectly used 32; later update hits
used 8. Both were written into the same world cache. Its lighting therefore
depended on how the update path reached the emitter. The cache query-throughput
correction from patch 0004 was active and remains valid. Earlier measurements are
retained, but they cannot be credited to the inactive emission branch.

## Runtime correction

Optional patch 0005 reserves unused bit 20 in the existing ray state. Cache ray
generation sets it once; bounce resets and hit shaders preserve it. The shared
world hit shaders use indirect emission strength for flagged rays, including
their first hit. The transparent-only hit shader follows the same rule.

Normal viewing rays still begin with zeroed state, preserving camera-visible
emission. Ray count, cache size, bounce count, material detail, render resolution,
native code and payload size are unchanged. This does not enable the separate
emission experiment or change any configured light strength.

The bit does not overlap the existing bounce, lobe, fog, surface-cache or cloud
flags. `pad0` is not repurposed; it already carries water/parallax information.

## Verification and compile-check correction

The earlier local checker incorrectly supplied SHaRC flags to every stage and
could report successful compilation of hit variants the engine never used.
The corrected [portable checker](../tools/check-advanced-shaders.py) matches
`collectRayTracingPassShaderRequests`: hit/miss stages get the base definitions;
query/update flags are added to ray generation and update flags to cache resolve.
All 173 advanced shader jobs compile.

```sh
python3 tools/check-advanced-shaders.py /path/to/MCVR \
  --settings /path/to/advanced.zip.txt --manifest /tmp/shader-check.json
```

Add `--pass final_compose` to narrow the check, and `--spirv-dir /tmp/shader-asm`
to retain assembly. Shared/query/update outputs have distinct names. The tool
checks compilation with 5090 capability definitions; it does not measure runtime
performance or prove shader correctness.

Actual game-generated cached SPIR-V independently confirms the update raygen's
bitwise OR with 1048576 and the shared closest-hit shaders' bitwise AND followed
by selection between float 32 and float 8. Those binaries, their hashes, and
the relevant assembly are retained in local evidence. The published patch was
applied after the thirteen normal and four earlier optional patches in an
isolated checkout; all five resulting source files match the tested jar exactly.

## Lighting result

With manual exposure 2.0 and identical wall masks, six cave turns give relative
RMS 0.02917 at 50 ms and 0.01985 at 300 ms, compared with 0.03206 and 0.02122 in
the control. That is approximately 9% and 6% less early settling error. Settled
wall luma changes from 81.99/43.50 to 81.61/42.61. Fine post-turn noise remains;
this is not an artifact count or a proof of a defect-free image.

The glowstone material room changes more: with fixed exposure and a 30-second
initial warmup, its three crop means fall by 12.188 / 10.628 / 11.888 on a 0–255
scale. Stone relief, metals, glass and water remain present. The independent
separate-emission experiment produces nearly identical settled brightness, to
within 0.091 / 0.041 / 0.005. This supports the emission-strength mismatch as
the main source of that lighting change. It is an intentional consequence of
removing the brighter first-update contribution, not a claim of unchanged
brightness or a reference-quality solution for all global illumination.

The separate-emission candidate is kept outside the production series. Its
small apparent additional cave gain is not established as useful independently
of this correction. See [component isolation and that experiment](sharc-separate-emission.md).

The normal-exposure release capture repeats a smaller gain: relative RMS
0.03156 → 0.02927 at 50 ms and 0.02106 → 0.01965 at 300 ms. That capture uses
uncapped rendering; the controlled comparison above uses 144. Comparisons are
within each protocol, not across those different rates and exposure settings.

| Two 30-second intervals, first / repeat | Rapid cave turns | Verified forest lane |
|---|---:|---:|
| Engine average FPS | 193.70 / 193.69 | 222.11 / 221.06 |
| Engine 1% low FPS | 154.89 / 154.15 | 148.72 / 152.64 |
| Longest engine interval, ms | 6.985 / 7.244 | 11.271 / 8.246 |
| Engine intervals over 6.944 ms | 1 / 1 | 19 / 16 |
| MangoApp average FPS | 191.12 / 191.26 | 222.11 / 221.10 |
| MangoApp 1% low FPS | 83.56 / 84.40 | 175.66 / 181.28 |
| Longest MangoApp interval, ms | 31.153 / 30.956 | 9.526 / 6.870 |

Each cave interval contains ten turns; each forest interval covers 190.81 blocks.
Native log coverage exceeds 99.98%. Average throughput is comparable to the
control. Two of 11,620 cave intervals and 35 of 13,293 forest intervals exceed
the 144 FPS budget. A separate 30 FPS VSync material launch confirms Khronos
instance/device and synchronization validation with no reported errors. These
headless engine/MangoApp measurements are not physical display delivery, and
the discrepancy between their cave intervals remains unresolved.

## Installed artifact and recovery

The jar installed at this stage was
`e54e3c58c21c1539f777c6cbb6582bd342549a8c16ba44f98d9760973da7f0a0`.
Only five files in the advanced shader archive change from `579b9def…`; Java
and native resources are identical. Native SHA remains
`7ae07e54c58042e4539cc43656fb03c396b8ede54a9ce69a9161e6fda41bd1a1`.
The private game's extracted archive/native hashes match the candidate.
Normal Minecraft stayed closed; its next startup extracts the new shader archive.
Settings and the saved play-world cave region retain their checksums.

The local jar-only backup restores the preceding allocation-guard release.
Run `tools/install-sharc-update-runtime.py restore` from the local development
tree with Minecraft closed, before older allocation/native/frame-slot/cache
rollbacks. This installer is machine-specific and is not part of the cookbook.
The later [primary emitter correction](primary-nee-emission.md) supersedes this
jar; its rollback must run first.

See [full-precision evidence](../measurements/sharc-update-runtime-2026-09-27.json).
Fine post-turn noise, rare long frames, and physical fullscreen pacing/comfort
remain outstanding; the broader goal is incomplete.
