# Distant terrain in a path tracer

Rasterizing LoD mods (Distant Horizons, Voxy) draw far terrain with their own OpenGL renderer.
Radiance has no OpenGL renderer: every pixel is a ray against a Vulkan acceleration structure. For
far terrain to exist, cast shadows and show up in reflections, it has to be geometry in that
acceleration structure.

## How it works here

**Radiance side (in this repo, patch radiance/0002, `LodBridge`).**
- The native chunk store gets 4096 extra slots after the vanilla chunk grid. Each holds one LoD
  mesh at any world origin, built into its own BLAS like a vanilla chunk section.
- Grid lookups in the shaders stop at the vanilla grid size, so LoD slots are only ever reached by
  rays.
- A provider calls `LodBridge.upload(generation, slot, originX, originY, originZ, buffers)` with
  meshes in the vanilla block vertex format (`Map<RenderLayer, BuiltBuffer>`, positions relative
  to the origin), exactly like a chunk rebuild, or `LodBridge.clear(...)`.
- The slot store is recreated on world or render distance changes; `generation()` changes with it
  and stale uploads are dropped.
- `LodBridge.renderedColumns(world)` returns the chunk columns Radiance is drawing right now, so the
  provider can leave exactly those out. (The render-distance circle isn't enough: vanilla only
  builds a chunk once all four neighbours are loaded, so the outer ring would be a hole.)
- Patch mcvr/0010 tiles textures per block on LoD quads, and radiance/0003 removes the fluid walls
  vanilla draws toward unloaded chunks.

**Provider side (not in this repo).** We use a 1.21.4 backport of Voxy (its last 1.21.4-era source,
with its OpenGL renderer removed) that ingests chunks as usual, plans rings of LoD levels 1–4
around the player on a background thread, and meshes them clipped against `renderedColumns`, with
skirts only against opaque neighbours. Voxy's license is "All rights reserved. Do not redistribute", so this
part isn't published.

Cost on the vista scene: about 0.85 ms of GPU time per frame, almost all of it shading the newly
visible far terrain rather than tracing it.

## Other providers

`LodBridge` doesn't know about Voxy. Anything that can produce vanilla-format quads for far terrain
can feed it. [Distant Horizons](https://gitlab.com/distant-horizons-team/distant-horizons) 3.3.2
runs alongside Radiance on 1.21.4 without problems (its own drawing never runs, because Radiance
replaces the world renderer), so a DH adapter is a plausible next step.
