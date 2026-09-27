# SHaRC header correction

This patch applies inside `MCVR/extern/sharc`, at pinned SDK 1.6.5 commit
`0b9f58bbc8c41736042d4da964830a247e424a00`. It is applied with `git apply`,
after submodule initialization, by `scripts/build.sh`. Repeating the helper
recognizes the already-applied patch; it does not reset the submodule.

Failed cache insertion returns `HASH_GRID_INVALID_CACHE_INDEX` instead of
aliasing unrelated slot zero. Existing guards then skip the failed allocation
while contributions can still reach earlier valid vertices. Legitimate slot
zero remains usable. See [the GPU test and playtests](../../docs/sharc-overflow.md).

This software contains source code provided by NVIDIA Corporation. SHaRC is
subject to the [NVIDIA RTX SDKs license at the pinned revision](https://github.com/NVIDIA-RTX/SHARC/blob/0b9f58bbc8c41736042d4da964830a247e424a00/License.md),
not the cookbook's GPL license. The SDK itself is fetched from upstream, not
vendored here; its notices remain intact.
