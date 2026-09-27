# SHaRC emission separation probe

This patch is not in the build series. It applies after normal MCVR patches
0001–0013 and optional cave-counts patches 0001–0004, with the SDK allocation
guard. It changes only `world.rgen`, `world/default.rchit` and `world/no_height.rchit`.
Apply with `git apply separate-emission.patch` in that MCVR checkout.

It enables the bundled SDK's separate-emission mode, passes local emission
through the continuation payload, subtracts it before local accumulation, and
supplies it on queries. It adds no ray or buffer. Do not apply it over the later
runtime update-identification patch without reconciling and retesting the two.

The initial compile checker incorrectly gave SHARC_UPDATE to shared hit stages;
the actual engine does not. The experiment exposed this inactive earlier guard.
The independent runtime-flag fix accounts for nearly the same brightness change.
See [results and limitations](../../docs/sharc-separate-emission.md).
