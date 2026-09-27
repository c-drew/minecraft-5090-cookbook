# Optional cave-noise diagnostics

These are private-test experiments, not part of the normal patch series and
not installed in the play profile. See ../../docs/cave-artifacts.md and
../../measurements/cave-followups-2026-09-27.json for scoped results. The patches
apply individually after the thirteen normal MCVR patches and four optional
cave patches. Do not combine them when reproducing an isolated comparison. The allocation
patch also requires the pinned SHaRC submodule headers (version1.6.5, commit
`0b9f58bbc8c41736042d4da964830a247e424a00`); it was checked against that exact SDK header and the clean patch-stack
world shader, rather than an uninitialized submodule directory.

- `rr-turn-reset.patch`: native probe; set `MCVR_DLSS_TURN_RESET_DEGREES=5` to
  reset RR during interframe rotations of at least 5 degrees and on the first
  following frame. Use 0 as control. Retain native **stderr** to verify actual
  reset episodes. Native stdout was discarded by the original private launcher.
- `opposite-view.patch`: shader probe; redirects one quarter of the existing
  cache-update rays to the opposite view. No change to query/camera rays or
  their throughput. Compile all SHaRC query/update variants and replace only
  `world/world.rgen` in the advanced shader pack for the treatment jar.
- `allocation-audit.patch`: shader counters plus a binary overlay. Native code
  already allocates and zeroes a lock buffer, unused by the 64-bit atomic path.
  Two words count failed and attempted insertions. The upper row after the red
  tile is failures, and the lower row after green is attempts: 32 bits, least
  significant first, each cell 12×12 ray-input pixels. Compile all affected
  world variants and SHaRC resolve. Replace only `world/world.rgen` and
  `extern/sharc/include/HashGridCommon.h` in the advanced shader pack. This
  changes the picture and adds atomic-counter overhead: do not use these
  captures to score image quality or performance. The overlay passes through
  RR/tone mapping; read settled, clearly separated cells and treat rapidly
  changing displayed attempt totals as approximate, not raw GPU readback.

The density test requires no native/shader code change. Add this existing
native option to `attributeConfigs` in the jar's `modules/ray_tracing.yaml`:

```yaml
  - name: "render_pipeline.module.ray_tracing.attribute.sharc_update_downsample_factor"
    type: "int_range:1-16"
    value: "5"
```

Then set its pipeline value to 5 or 3 in matched runs. Confirm it survives the
Java preset's configuration round trip. Merely adding an undeclared field to
pipeline.yaml does not work: Java silently drops it. The native/shader payloads
must remain identical between these two runs.

Archive each diagnostic source and jar before restoring production source.
Restoring a file with an old modification time can leave its compiled object
stale. Invalidate/rebuild affected objects and inspect the resulting binary
when removing native diagnostics; the earlier release required this correction.
