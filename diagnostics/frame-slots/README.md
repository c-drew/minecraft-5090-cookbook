# Reproducing the frame-slot diagnosis

These are temporary instrumentation patches, excluded from the normal build.
The production fix is `patches/mcvr/0013`; it has no new timestamp logger or
environment switch. The diagnostic patches were checked against the exact
archived test sources.

Use a disposable engine checkout with the twelve normal MCVR patches and four
optional cave patches from cookbook commit `e0eca6a`. Apply
`complete-gpu-timing.patch`, build, and save that baseline jar. Then apply
`independent-slots-switch.patch`, rebuild, and save the comparison jar. Do not
apply these on top of production patch 0013.

For both builds, set `MCVR_CPU_FRAME_LOG=/absolute/path/cpu-frames.csv` and
`MCVR_GPU_FRAME_LOG=/absolute/path/complete-gpu-frames.csv`. Enable the two-slot
comparison with `MCVR_INDEPENDENT_FRAME_SLOTS=1`; its default is the old behavior.
Use identical scenes and settings. Read the buffered logs after a clean game
exit. The full protocol and results are in
[frame-slots.md](../../docs/frame-slots.md).

The logger adds five fixed query indices in submission order: upload start,
upload end, world end, overlay end, and final-copy end. It reads results only
after the corresponding resource-slot fence has signaled. Durations include
GPU scheduling inside each envelope. Calibrated device/host clocks estimate
submission-to-start delay, which includes already queued work and semaphore
waits; it is not a driver-only cost. Collection adds no waits to the render loop;
shutdown drains the queue before collecting remaining results.

Place the two CSV files and a `results.json` array in a directory. Each results
entry needs `label`, `engine_window: [start_unix_seconds, end_unix_seconds]`, and
`metrics` (the separate MangoApp summary; use `{}` if unavailable). Then run:

```sh
python3 tools/gpu-span-review.py /path/to/log-directory
python3 -m unittest discover -s tools -p 'test_*metrics.py'
python3 -m unittest discover -s tools -p 'test_gpu_span_review.py'
```

The review joins frame IDs and their CPU timestamps, rejects incomplete windows
or missing/mismatched results, checks clock calibration, and computes both
complete GPU envelopes and intervals between consecutive GPU completions.
Neither is a measurement of delivery to a physical display. Raw game captures
and the private world are not distributed here.
