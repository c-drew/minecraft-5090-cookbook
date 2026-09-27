# Separating the cave lighting inputs

These are diagnostic patches, excluded from the production build. Apply one at
a time with `git apply` after the thirteen normal MCVR patches and experimental
cave-counts patches 0001–0004, with the SHaRC allocation correction. The full-light
control is jar `579b9def1361bbec15381fdf1de2b90cf13837de6bc92e48bc71491e829992d5`.
Remove the diagnostic before normal play. Do not combine these patches.

Both change only the final combination for opaque/noisy first hits in
`world/world.rgen`. The direct view keeps first-hit emission and direct light;
the indirect view keeps continuation radiance. Transparent and other special
paths are not a complete light decomposition. The SHaRC update branch and
sampling source are unchanged. An optimizer can remove unused work, so this is
not an equal-cost performance comparison.

Use identical private cave geometry, six alternating fast turns, ray resolution,
48 candidates, history cap 8, direct strength 32, four bounces, SHaRC, SPBR and
DLSS RR. Set automatic exposure off and manual exposure to 2.0 for all three
views, then confirm these values survive Java's saved `pipeline.yaml`. This
prevents auto exposure from brightening the indirect-only view independently.

Review full light first, then both components using its wall-pixel mask:

```sh
python3 tools/cave-turn-review.py FULL --motion-threshold 3
python3 tools/cave-turn-review.py DIRECT --motion-threshold 3 --mask-reference FULL
python3 tools/cave-turn-review.py INDIRECT --motion-threshold 3 --mask-reference FULL
```

The threshold is an 8-bit mean frame difference, not a lighting setting. The
usual threshold 6 missed the last 1–3 moving frames of the dim indirect view;
3 matches the observed final motion to about one captured frame. The shared
mask avoids selecting only the bright islands of the dim component. All cases
use the same six masks: 41318, 40774, 41322, 40758, 41319 and 40770 pixels.

The measurement is exposure-normalized post-turn difference against each
capture's own settled image. Ray Reconstruction and tone mapping are nonlinear:
component error scores cannot be added or treated as shares of total variance.
These tests identify an unstable signal worth investigating; they do not prove
that every remaining visible spot comes from it.

See [measurements](../../measurements/sharc-separate-emission-2026-09-27.json)
and [the subsequent cache-emission experiment](../../docs/sharc-separate-emission.md).
