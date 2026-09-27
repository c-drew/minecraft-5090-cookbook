# Residual cache-hit samples after primary emitter accounting

The selected [primary emitter correction](../../docs/primary-nee-emission.md)
removes many bright first-secondary hits. This follow-up records where the
remaining successful SHaRC queries land, without changing the image estimator.
It is a diagnostic, not an installed rendering change.

Each successful query records its world position, hit material emission,
unweighted cached RGB radiance, and bounce index. Four private GPU readbacks
pass known-value layout tests, finite-value checks, and exact no-filter HDR
identity. Khronos instance/device and synchronization validation report no
errors. All 174 shader jobs compile.

Among cache-query paths whose **whole continuation** exceeds luminance 1:

| View | Paths | Emissive query surfaces | Query at bounce 2 |
|---|---:|---:|---:|
| Just after turning | 244 | 239 | 242 |
| Turned, settled | 261 | 259 | 260 |

Bounce 0 is the visible primary surface. Of these query positions, 243/244
early and 261/261 settled lie in two torch blocks, confirmed by reading the
saved region's block-state palettes. This points to sparse later emitter
intersections, rather than nonemissive surfaces accidentally receiving bright
cache entries, as the dominant extreme-sample case in this turned view.
It does not establish what dominates the final reconstructed image's variance.

The other orientation illustrates a measurement limitation: whole continuation
can already contain an earlier emissive hit before a later, dim cache lookup.
Threshold counts and continuation-energy sums are therefore not cache-only
energy attribution. The original source diagnostic also counts hit emission
only after failed cache queries; it cannot identify the material at a successful
cache hit. Use this schema for that purpose.

## Earlier cache lookup probe

A separate one-file probe admits first-secondary queries only when the primary
NEE guard is active and the secondary material is rough, opaque, nonmetallic,
and nonemissive. Emissive first hits keep the selected estimator partition;
transparent and smooth paths retain the existing policy.

One six-turn comparison at exposure 2 / 144 FPS gives relative RMS
0.024932 → 0.024026 at 50 ms and 0.017643 → 0.017123 at 300 ms. These small
3.6% / 2.9% differences are unreplicated. Final-compose GPU time changes
1.21789 → 1.23585 ms in the last 1,000 capped records. Wall mean changes are
+0.043 / +0.010 gray levels. Visual review does not establish a useful further
improvement. This probe is **not selected or installed**; materials, outdoor
behavior and uncapped performance were not validated. It compiles 173/173 jobs.

## Reproduce

Start with pinned MCVR `9905c81`, all 13 main and six optional cave patches,
and the pinned SHaRC allocation fix. Apply
`../raw-light/native-readback.patch`, then `capture-after-primary-nee.patch`.
The latter adds the no-op reconstruction pass and this capture schema directly
to the selected source, avoiding the older prefilter patch's JSON-formatting
context. All four changed shader entries reproduce the tested archive exactly.

Follow the [raw readback protocol](../raw-light/README.md). The two RGBA32F
`indirect_surface` layers now mean:

- Layer 0: successful query world position xyz, material emission.
- Layer 1: unweighted cached RGB, bounce + 1; zero in w means no query.

Run `tools/analyze-cache-hit-materials.py /absolute/capture/directory` with
NumPy installed. The source-attribution analyzer expects a different schema
and must not be used on these captures.

To reproduce the earlier-query probe instead, apply
`early-cache-after-primary-nee.patch` directly to the selected production
source, without the readback patches. Its world shader also replays exactly.

[Measurements](../../measurements/cache-hit-materials-2026-09-27.json) include
the diagnostic hashes and full results. The normal game remains on
`99c78c0e…`; these captures do not measure physical display pacing or comfort.
