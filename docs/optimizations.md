# What the patches do

Each section is one patch in `patches/`. Numbers are from the benchmark in
[benchmarking.md](benchmarking.md): 1440p output, RTX 5090, render distance 16, uncapped.

Radiance splits into a Java mod (hooks into Minecraft, gathers geometry) and MCVR, a C++ Vulkan
engine (acceleration structures, ray tracing passes, DLSS). Most per-frame CPU work that caused
spikes lived on the render thread in MCVR's *world prepare* pass.

## mcvr/0001–0003: AlexRice13's CPU work

Three commits from [AlexRice13/MCVR](https://github.com/AlexRice13/MCVR): a leaner world prepare
path, cached shader binding table mappings and TLAS buffers, and reused ray tracing upload
buffers. On an outdoor scene they took upstream 0.1.5 from 95.7 to 152.5 fps (1% low 73 → 123)
with an identical image. The later patches build on them.

## mcvr/0004: render scale, settings file, timing tools

**Render scale.** DLSS offers fixed presets (Quality renders at 2/3 of the output per axis,
Performance at 1/2). The render-resolution images keep the preset's size and each frame renders
into their top-left sub-rectangle, which DLSS Ray Reconstruction is told about. So any size between
the presets works: `MCVR_RENDER_SCALE=0.78125` renders 1333x750 for a 2560x1440 output. Every pass
that used to read an image size reads the frame's render size from the world uniform buffer
instead, and temporal passes reproject with the previous frame's size.

The patch also has a dynamic mode (`MCVR_DRS=1`) that picks the scale from measured GPU time. It is
off by default: DLSS-RR spends about 14 ms of CPU every time the render size changes, even back to a
size it used before, so changing size mid-game is itself a hitch.

**Settings file.** `mcvr_fork::setting(NAME)` returns the environment variable `NAME`, or else the
same key from `<game dir>/radiance/fork.properties`. Launchers rewrite their own settings; this
file survives.

**Timing.** `MCVR_TIMING_FILE` / `MCVR_TIMING_FRAMES` write GPU timestamps per pass
(`tools/timing-summary.py`, `tools/pass-spikes.py` read them). `MCVR_CPU_FRAME_LOG` writes one
line per frame with render-thread checkpoints (acquire, entities, submit, present) and profiler
zones.

## mcvr/0005: stable chunk slots (the big one)

**Problem.** Every frame, world prepare rebuilt the TLAS instance list and the per-geometry
metadata (buffer addresses, offsets) for every chunk slot: about 30,000 at render distance 16.
Normally cheap, but while chunks stream in (flying, walking into new terrain) it cost up to ~4 ms
of render-thread time, which showed up directly as 1% lows.

**Change.**
- Each chunk slot owns a fixed range of metadata (8 geometries per slot), and its TLAS instance
  custom index is the slot number, so nothing moves when other chunks change.
- `Chunk1::markChanged()` bumps a per-slot serial on every visible change; a frame rewrites only
  slots whose serial changed.
- Shader binding table offsets come from one block per distinct hit-group signature, shared by
  all slots with that signature.
- The TLAS is built from raw `VkAccelerationStructureInstanceKHR` data in a persistent buffer,
  and refitted instead of rebuilt when the set of active slots is unchanged.

**Copy coalescing.** Crossing a chunk border relocates about 800 slots at once. Uploading each
slot's metadata as its own copy region made ~2400 regions and cost 1–3 ms of GPU time. Regions
closer than 16 KB are now merged: the copy step's p99 went from 1.80 ms to 0.16 ms.

**Result** (flying over new terrain): 1% low 97–106 → 140–151 fps. Screenshots are identical.

## mcvr/0006: chunk builds off the render thread

Converting a chunk's vertices to the engine's position/material/index layout now happens on the
thread that queues the build, so the render thread's batch build only appends ready data.
`MCVR_CHUNK_BUILD_BUDGET_MS` caps render-thread time spent scheduling batches per frame; it is off
by default because 0.3 ms showed no gain.

## mcvr/0007: exact frame limiter

After sleeping until the deadline, the limiter re-anchored on the moment it actually woke, so every
oversleep carried into the next frame: a 140 fps cap ran at 138.9. Deadlines now follow each other
by exactly one period (a late frame still restarts the schedule, with no catch-up burst). Capped at
140: 138.92 → 140.01 fps.

Note: with this game, VSync is the better choice anyway; see the frame pacing section of the
README.

## mcvr/0008: cheaper GPU passes

- **SHaRC table 4M entries** instead of 8M. The resolve pass walks the whole table every frame
  (0.17 ms at 8M). `MCVR_SHARC_CAPACITY_LOG2` overrides it.
- **Surface-cache clears.** A cache entry is only valid when layer 7's `w` holds the valid flag and
  every reader checks it, so clearing writes that one layer instead of all eight, and the secondary
  cache is cleared only for sky pixels.
- **Continuation passes** (reflection and refraction through glass and water) return early for
  pixels whose first hit isn't transparent, before loading and re-shading both surface caches.

## mcvr/0009: device options

`MCVR_QUEUE_PRIORITY=high|realtime|low` asks for a Vulkan global queue priority and falls back to
the default if the driver refuses (NVIDIA refuses `high` without `CAP_SYS_NICE`). Ray query and
NVIDIA's ray tracing invocation reorder (SER) are enabled when present and exposed to shaders as
defines. The shipped shaders don't use SER; see [negative-results.md](negative-results.md).

## mcvr/0010: per-block texture tiling for LoD terrain

LoD meshes draw one quad per 2^L-block voxel. Stretching the block's texture across that quad
magnifies texels and turns leaf cut-outs into holes several blocks wide. The LoD mesher writes the
voxel size into the (otherwise unused for blocks) glint UV, and the hit shaders repeat the texture
once per block and scale the ray-cone derivatives to match.

## radiance/0001: render thread, Java side

- **Rebuild queue.** A `ConcurrentHashMap` was iterated and cleared every frame. Both walk the
  whole table, which stays at its peak size after a burst of rebuilds (world load, travel), so every
  later frame paid for the burst. Now a queue plus a set of queued indices; draining costs only
  what's queued, and chunks enqueued during the drain are no longer lost.
- **Block entities.** Chunks rebuilt with block entities are indexed instead of walking every chunk
  section each frame, and the index is re-verified 1/60 of the storage per frame. (Our first version
  re-scanned everything every 60th frame, which spiked; spreading it took the 1% low at render
  distance 32 from 91 to 109 fps.) Block entities the dispatcher wouldn't draw (no renderer, unsupported
  state, out of range) are skipped before any buffers are allocated.
- Per-object vertex storage starts at 16 KB instead of 768 KB, and render layer names are encoded
  to native strings once instead of twice per layer per frame (upstream issue #252).

## radiance/0002: LodBridge

4096 extra native chunk slots after the vanilla grid, each holding one LoD mesh at any world
origin. A LoD provider uploads meshes in the vanilla block vertex format through the same path chunk
rebuilds use. Details in [lod.md](lod.md).

## radiance/0003: fluid walls at the loaded edge

At the edge of the loaded area the neighbouring chunk reads as air, so rivers and oceans grew a
wall facing it: very visible against LoD terrain. Those sides are skipped; the edge chunk is
rebuilt when the neighbour loads.

## Settings changes (no patch)

- **ReSTIR initial candidates 16** (Advanced pack `initial_samples`, default 32). Lit base at night:
  175/136 → 187/156 fps (avg/1% low); screenshot RMSE 0.21%, the same as run-to-run noise.
- **Render scale 0.78125** (see above). Against DLSS Quality: RMSE 1.5%.
