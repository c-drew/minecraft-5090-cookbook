# Patches

Two series for `git am`, applied by `scripts/build.sh`:

| Directory | Upstream | Base commit |
|---|---|---|
| `mcvr/` | [Minecraft-Radiance/MCVR](https://github.com/Minecraft-Radiance/MCVR) | `9905c81` ("update to 0.1.5") |
| `radiance/` | [Minecraft-Radiance/Radiance](https://github.com/Minecraft-Radiance/Radiance) | `414d8e3` (0.1.5 + README updates) |

`mcvr/0001`–`0003` are the commits (made with GitHub Copilot) from AlexRice13's fork
[AlexRice13/MCVR](https://github.com/AlexRice13/MCVR), unchanged. Everything else is described in
[../docs/optimizations.md](../docs/optimizations.md). All patches are GPL-3.0, like the code they
modify.

By hand:

```sh
git -C MCVR checkout 9905c81 && git -C MCVR am /path/to/patches/mcvr/*.patch
git -C Radiance checkout 414d8e3 && git -C Radiance am /path/to/patches/radiance/*.patch
```
