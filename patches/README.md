# Patches

Two main series for `git am`, applied by `scripts/build.sh`:

| Directory | Upstream | Base commit |
|---|---|---|
| `mcvr/` | [Minecraft-Radiance/MCVR](https://github.com/Minecraft-Radiance/MCVR) | `9905c81` ("update to 0.1.5") |
| `radiance/` | [Minecraft-Radiance/Radiance](https://github.com/Minecraft-Radiance/Radiance) | `414d8e3` (0.1.5 + README updates) |

`mcvr/0001`–`0003` are the commits (made with GitHub Copilot) from AlexRice13's fork
[AlexRice13/MCVR](https://github.com/AlexRice13/MCVR), unchanged. Everything else is described in
[../docs/optimizations.md](../docs/optimizations.md). These main-series patches
are GPL-3.0, like the code they modify. The separate [SHaRC header patch](sharc/README.md)
applies with `git apply` inside the pinned submodule after initialization;
SHaRC retains its upstream license.

`mcvr/0011` fixes the view matrix passed to DLSS Ray Reconstruction. `0012` adds
`player_block_light_shadows` (default true); setting it false omits only the camera player's
block-light shadow. Sun shadows, reflections, and shadows of other entities remain. Both were
built and exercised in the private cave test instance. Neither is a complete cure for the
transient spots after rapid turns.

`mcvr/0013` separates the render-resource ring from swapchain image selection.
Present-wait semaphores remain per acquired image. The tested release improves
rapid-turn engine pacing while leaving shaders unchanged; see
[the measurements and remaining limits](../docs/frame-slots.md).

`experimental/cave-counts/` is a separate opt-in series applied after the normal
MCVR patches with `MCVR_CAVE_COUNTS=1 scripts/build.sh`. It corrects failed-sample
count retention and requires a matching lighting calibration. See
[the evidence and limitations](../docs/cave-artifacts.md) before enabling it.

By hand:

```sh
git -C MCVR checkout 9905c81 && git -C MCVR am /path/to/patches/mcvr/*.patch
git -C Radiance checkout 414d8e3 && git -C Radiance am /path/to/patches/radiance/*.patch
git -C MCVR submodule update --init --recursive --depth 1
bash scripts/apply-sharc-patches.sh /path/to/MCVR
```
