# How we measure

Frame-time work lives or dies on measurement. Most of our early "regressions" and "spikes" turned
out to be the measurement setup, not the game.

## Setup

- **A separate test instance** (copy of the play instance), launched by the same launcher.
- **Headless gamescope** as the game's window system: `gamescope --backend headless -W 2560 -H 1440
  -r 0 --mangoapp`. The game renders at full 1440p without touching the desktop, and `-r 0` means
  no refresh cap.
- **mangoapp** (MangoHud as gamescope's separate process) records frame times from gamescope's side.
  In an earlier OpenGL setup, injecting MangoHud into the game itself cost ~12 fps average and
  more on 1% lows, so we keep it out of the game process.
- **Scripted scenes** in a fixed world: a spawn view, a lit base at night (time 18000), a vista with
  distant terrain, and movement: walk or fly forward with a held key (not chat teleports: typing a
  teleport command every second caused its own spikes).
- **Two passes per movement run.** Pass "a" walks into terrain the game hasn't loaded yet, pass "b"
  repeats the same path with everything cached. New terrain is consistently 5–8% slower.
- **20 s settle** after the world loads before measuring, then 30 s of frames. Note this skips the
  first seconds after joining a world, which are the heaviest (chunk and LoD meshing bursts).
- **1% low** = the frame rate of the slowest 1% of frames (per frame, not per second).
- **GPU clocks and utilisation** sampled once a second with `nvidia-smi`, to catch throttling.
- **Image checks**: an F2 screenshot at the start of each measurement, compared with
  `tools/img-diff.py` (RMSE against a reference). Run-to-run noise is ~0.2%.

For per-pass detail, the patched engine writes GPU timestamps per pass (`MCVR_TIMING_FRAMES`) and
render-thread checkpoints per frame (`MCVR_CPU_FRAME_LOG`); see [optimizations.md](optimizations.md).

## Things that quietly ruin measurements

Anything else drawing on the same GPU competes with the game, and it shows up as periodic spikes.
Things we caught:

- **A terminal with an animated spinner** (redrawing about 9 times a second) produced "periodic
  spikes" we spent time chasing. Run benchmarks in the background and leave the desktop idle.
- **A screensaver on another monitor** (a 120 fps terminal animation on two displays) cost about
  0.75 ms per frame. Our bench now stops it before measuring and records the desktop state in each
  result.
- **Frame caps**: a capped run hides everything above the cap and adds its own jitter (see the
  README). Measure uncapped.
- **Overclocks and undervolts**: stock performance varies between sessions. Compare settings in the
  same session, back to back.

## Tools in this repo

| Tool | Use |
|---|---|
| `tools/img-diff.py` | RMSE / luminance difference between screenshots, optional contact sheet |
| `tools/frame-dist.py` | Frame-time histogram and spike spacing for a mangoapp CSV |
| `tools/pass-spikes.py` | Which GPU passes are slow in spike frames (from `MCVR_TIMING_FRAMES`) |
| `tools/timing-summary.py` | Average per-pass GPU times from an `MCVR_TIMING_FILE` log |
| `tools/lactctl.py` | Read or set clock offsets and the undervolt curve through the LACT daemon |

The frame-cap jitter shows up plainly in `tools/frame-dist.py`: on a run capped at 140, 304 of the
frames over 8 ms came exactly 7 frames after the previous one (50 ms at 140 fps), which points at
Minecraft's 20 Hz tick.
