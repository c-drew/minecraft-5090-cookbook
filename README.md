# The 5090 Minecraft Cookbook

Minecraft on a single RTX 5090 with hardware path tracing, DLSS Ray Reconstruction and distant
terrain, targeting 1440p at 144 Hz.

This repo is the recipe (mods, settings, system config) plus a set of engine patches for
[Radiance](https://github.com/Minecraft-Radiance/Radiance), the Vulkan path-tracing renderer for
Minecraft. Every number below was measured on the hardware listed.

It is a personal project. It is not affiliated with Radiance, Voxy, Mojang, Microsoft or NVIDIA.

**September 27 cave follow-up:** rapid turns in torchlit caves reveal transient spotted artifacts
that the original standing and movement benchmarks did not catch. Camera and shadow improvements
are included below; they do not eliminate the light-sampling artifacts. A minimum of 144 FPS with
no visible defects remains a target, not a verified result across gameplay. See the
[cave investigation and optional sampling/cache corrections](docs/cave-artifacts.md) for measurements,
reproduction steps, and a correction to an invalid outdoor-walking comparison.
The subsequent [frame scheduling fix](docs/frame-slots.md) substantially improves
engine timing during rapid turns without changing shader quality. Rare long
frames and physical display validation remain unresolved.
The [cache-allocation correction](docs/sharc-overflow.md) fixes a separately
reproduced GPU failure path; it does not establish a cure for the remaining spots.

## Results

Historical performance profile: 1440p output, uncapped, 30 s runs, render distance 16, distant
terrain on, 16 ReSTIR candidates, DLSS runtime 310.5.3. These measurements predate the cave
artifact investigation. They measure throughput headroom, not a guaranteed frame-rate floor.

| Scene | Avg fps | 1% low fps |
|---|---|---|
| Walking into new terrain | 180 | 147 |
| Walking the same path again | 192 | 150 |
| Flying into new terrain | 235 | 149 |
| Flying the same path again | 235 | 158 |
| Lit base at night | 199 | 165 |
| Distant-terrain vista | 246 | 200 |
| Standing still | 228 | 186 |

How we got there, on the hardest scene (flying over new terrain, 1% low):

| Step | Avg / 1% low |
|---|---|
| Starting point (already with the earlier CPU fixes, render scale 0.8125) | 212 / 97–106 |
| Stable chunk slots in the world prepare pass (patch mcvr/0005) | 219 / 129–137 |
| Coalesced metadata copies (same patch) | 223 / 140–151 |
| Render scale 0.78125 and 16 ReSTIR candidates (settings) | 235 / 149–158 |

The first step, before any of that: AlexRice13's three CPU commits (patches mcvr/0001–0003) on
upstream Radiance 0.1.5 took an outdoor scene from 95.7 to 152.5 fps (1% low 73 → 123) at DLSS
Quality, with an identical image.

## The rig

| Part | What we used |
|---|---|
| GPU | RTX 5090 (Gigabyte AORUS Master, air cooled), undervolted to 3075 MHz at 1000 mV, memory +1000 MHz |
| CPU | Ryzen 7 9800X3D |
| RAM | 64 GB |
| Display | 2560x1440, 144 Hz with VRR, DisplayPort |
| OS | Arch-based ([Omarchy](https://omarchy.org)) with the CachyOS kernel 7.2, Hyprland 0.56, NVIDIA 615.71 |
| Launcher / Java | Prism Launcher, Temurin 21, `-XX:+UseZGC -XX:+ZGenerational`, 16 GB max heap |

Everything is Linux-first. The patches are platform-neutral C++/Java/GLSL, but the build script and
system notes assume Linux.

## The stack, and why

- **Minecraft 1.21.4 + Fabric.** Radiance only exists for 1.21.4.
- **Radiance 0.1.5 + MCVR** (its C++ Vulkan engine) with the built-in **Advanced** shader pack.
  It replaces the whole OpenGL renderer and path-traces the scene in hardware: ReSTIR direct light,
  a SHaRC radiance cache for bounces, DLSS Ray Reconstruction as denoiser and upscaler. Nothing
  else on Minecraft looks like it.
- **The patches in this repo**, applied to pinned upstream commits: frame-time spikes removed,
  a render-scale setting, an exact frame limiter, distant-terrain support. See
  [What the patches do](#what-the-patches-do).
- **[SPBR](https://github.com/ShulkerSakura/SPBR)** (vanilla-style PBR and parallax) for
  materials. Radiance reads it directly.
- **Distant terrain (LoD).** We run a 1.21.4 backport of [Voxy](https://modrinth.com/mod/voxy)
  that feeds LoD meshes into Radiance's acceleration structure through `LodBridge` (patch
  radiance/0002). Voxy's license does not allow redistribution, so the Voxy side is **not** in this
  repo; see [docs/lod.md](docs/lod.md). Without it, everything else here works, with vanilla render
  distance only.

## Recipe

1. **Instance.** In Prism Launcher, create a Minecraft 1.21.4 instance with Fabric Loader and add
   Fabric API (0.119.4+1.21.4). Java 21. JVM arguments: `-XX:+UseZGC -XX:+ZGenerational`, max
   memory 16 GB.
2. **Build the mod** (Linux; needs git, cmake, ninja, a C++20 compiler, JDK 21, Vulkan headers,
   shaderc):
   ```sh
   scripts/build.sh          # clones upstream at pinned commits, applies patches/, builds
   ```
   Copy `work/Radiance/build/libs/Radiance-0.1.5-alpha-fabric-1.21.4.jar` into the instance's
   `mods/`.
3. **DLSS runtime.** Radiance does not ship NVIDIA's DLSS libraries. Download
   `libnvidia-ngx-dlss.so.310.5.3` and `libnvidia-ngx-dlssd.so.310.5.3` from
   [NVIDIA/DLSS v310.5.3](https://github.com/NVIDIA/DLSS/tree/v310.5.3/lib/Linux_x86_64/rel) into
   `minecraft/radiance/` (see Radiance's README for the license terms).
4. **Textures.** Put SPBR in `resourcepacks/` and enable it.
5. **Engine settings.** Copy [config/fork.properties](config/fork.properties) to
   `minecraft/radiance/fork.properties`. It sets the render scale (below).
6. **Shader pack settings.** Start the game once, then copy
   [config/advanced.zip.txt](config/advanced.zip.txt) over
   `minecraft/radiance/shaders/world/ray_tracing/advanced.zip.txt`. The setting that matters for
   speed is `initial_samples=16` (ReSTIR candidates per pixel; the pack's default is 32). The rest
   is taste.
7. **In game** (Radiance's video settings): DLSS mode Quality, ray bounces 4, **VSync on**,
   **max framerate unlimited**, fullscreen. Vanilla: render distance 16, simulation distance 10.
   Our full Radiance options are in
   [config/radiance-options.properties](config/radiance-options.properties).
8. **Display.** Turn on VRR for fullscreen games in your compositor. Hyprland pieces are in
   [config/hyprland.lua](config/hyprland.lua).
9. **Optional: undervolt.** [tools/lactctl.py](tools/lactctl.py) sets the curve through
   [LACT](https://github.com/ilya-zlobintsev/LACT): `lactctl.py undervolt 3075 1000 2000`. Every
   card is different; test for stability.

### Render scale

`MCVR_RENDER_SCALE` in `fork.properties` sets the ray-traced resolution per axis, relative to DLSS
Quality's (1708x960 at 1440p). The cookbook uses **0.78125 = 1334x750**, which is between DLSS
Balanced and Performance. Side by side with Quality, the difference is hard to spot (RMSE 1.5%
between screenshots, distant foliage slightly softer). That static comparison does not measure
fast-turn stability or prove a minimum FPS. Use 1.0 for plain Quality if you have headroom to spare.

### Frame pacing: VSync on, not a frame cap

The most noticeable fix wasn't in the engine. With a 140 fps cap the game showed ~139 and felt
unchanged no matter how much headroom the GPU had. Two reasons:

- The limiter drifted (fixed in patch mcvr/0007: 138.9 → 140.0 fps).
- **Under a frame cap, every 7th frame is ~1.3 ms late and the next ~1.5 ms early.** Seven frames at
  140 fps is 50 ms, the client tick: Minecraft runs its 20 Hz game tick on the render thread. When
  the GPU is the limit, frames queue and the tick's extra CPU work is hidden. Under a cap, nothing
  is queued and every tick shows. Measured on a scene whose uncapped 1% low is 186 fps: capped at
  140, the 1% low drops to 110.

So: **VSync on, framerate unlimited, fullscreen, VRR on.** The swapchain keeps a couple of frames
queued, which absorbs the tick, the display gets a new frame every refresh, and VRR covers the rare
frame that misses. In play this sits at a steady 144 on the F3 counter. The cost is roughly one
frame (~7 ms) of extra input latency.

## What the patches do

`patches/` holds two main series for `git am`, pinned to Radiance `414d8e3` and MCVR `9905c81`,
plus a header correction applied inside MCVR's pinned SHaRC submodule.
Details and measurements are in [docs/optimizations.md](docs/optimizations.md).

| Patch | Effect |
|---|---|
| mcvr/0001–0003 | AlexRice13's CPU work: faster world prepare, cached SBT mappings and TLAS buffers, reused upload buffers |
| mcvr/0004 | Render scale between the DLSS presets, `fork.properties` settings file, GPU/CPU frame timing logs |
| mcvr/0005 | Stable chunk slots: the per-frame world prepare touches only changed chunks, not all ~30k; coalesced uploads. The biggest 1%-low win |
| mcvr/0006 | Chunk vertex packing moved off the render thread; optional per-frame build budget |
| mcvr/0007 | Exact frame limiter |
| mcvr/0008 | Cheaper GPU passes: SHaRC table 4M entries, one-layer surface-cache clears, early-out in continuation passes |
| mcvr/0009 | Optional Vulkan global queue priority; ray query / SER capability plumbing |
| mcvr/0010 | Per-block texture tiling for LoD terrain |
| mcvr/0011 | Give DLSS RR the same camera view as primary rays, including bobbing and hurt effects |
| mcvr/0012 | Optional player block-light shadow switch; default on, can remove the camera player's cave silhouette |
| mcvr/0013 | Separate two render-resource slots from acquired display images, avoiding needless fence serialization |
| sharc/0001 | Preserve the invalid index when cache allocation fails, preventing unrelated slot-zero reads/writes |
| radiance/0001 | Render thread: cheaper chunk rebuild queue, indexed block entities, smaller per-object buffers |
| radiance/0002 | `LodBridge`: native chunk slots for LoD meshes after the vanilla grid |
| radiance/0003 | No fluid walls facing unloaded chunks |

## More

- [docs/optimizations.md](docs/optimizations.md): each change, why, and what it bought
- [docs/benchmarking.md](docs/benchmarking.md): how we measure, and the desktop things that
  quietly ruin measurements
- [docs/negative-results.md](docs/negative-results.md): what we tried that didn't help, so you
  don't have to
- [docs/lod.md](docs/lod.md): how distant terrain gets into a path tracer

## Credits

- **Radiance and MCVR**: the [Minecraft-Radiance](https://github.com/Minecraft-Radiance) team
  (Puxuan Wang, Jiong Liu and contributors). All of this is built on their renderer.
- **AlexRice13**: the MCVR CPU optimizations in patches mcvr/0001–0003, from
  [AlexRice13/MCVR](https://github.com/AlexRice13/MCVR).
- **MCRcortex**: [Voxy](https://modrinth.com/mod/voxy), the LoD engine behind our distant terrain.
- **ShulkerSakura**: [SPBR](https://github.com/ShulkerSakura/SPBR), built on Poudingue's
  [Vanilla Normals Renewed](https://github.com/Poudingue/Vanilla-Normals-Renewed).
- **NVIDIA**: DLSS Ray Reconstruction and [SHaRC](https://github.com/NVIDIA-RTX/SHARC).
- **James Seibel and contributors**: [Distant Horizons](https://gitlab.com/distant-horizons-team/distant-horizons),
  which we also tested with Radiance.
- Measurement and tuning tools: [gamescope](https://github.com/ValveSoftware/gamescope) and
  [MangoHud](https://github.com/flightlessmango/MangoHud), [LACT](https://github.com/ilya-zlobintsev/LACT).
- Desktop: [Hyprland](https://hypr.land), [Omarchy](https://omarchy.org), [CachyOS](https://cachyos.org).

Built by [c-drew](https://github.com/c-drew) with Claude Code.

## License

The main patch series modify GPL-3.0 code (Radiance, MCVR) and are GPL-3.0, as are the scripts
and tools (see [LICENSE](LICENSE)). SHaRC retains its separate upstream license;
see [patches/sharc/README.md](patches/sharc/README.md). The documentation is
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Minecraft is a trademark of Mojang Studios; NVIDIA, RTX and DLSS are trademarks of NVIDIA.
