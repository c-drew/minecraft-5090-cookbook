#!/usr/bin/env bash
# Build the cookbook's Radiance jar: upstream Radiance + MCVR at pinned commits, plus patches/.
#
# Usage: scripts/build.sh [WORK_DIR]        (default: ./work)
# Output: WORK_DIR/Radiance/build/libs/radiance-*.jar
# Optional: MCVR_CAVE_COUNTS=1 applies cave-count, sampling and cache corrections.
# Read docs/cave-artifacts.md for its brightness calibration and performance cost.
#
# Needs: git, cmake, ninja, a C++20 compiler, JDK 21 (JAVA_HOME), Vulkan headers and shaderc
# (Arch: vulkan-headers shaderc), network access for the first run (~2 GB of MCVR submodules
# and the Gradle/Loom downloads).
#
# Existing clones in WORK_DIR are reused and reset to the pinned commits, so re-running is cheap.
# RADIANCE_REPO / MCVR_REPO override the clone URLs (e.g. local mirrors).
set -euo pipefail

RADIANCE_COMMIT=414d8e3   # Minecraft-Radiance/Radiance main, 0.1.5 + README updates
MCVR_COMMIT=9905c81       # Minecraft-Radiance/MCVR "update to 0.1.5"
RADIANCE_REPO=${RADIANCE_REPO:-https://github.com/Minecraft-Radiance/Radiance.git}
MCVR_REPO=${MCVR_REPO:-https://github.com/Minecraft-Radiance/MCVR.git}

root=$(cd "$(dirname "$0")/.." && pwd)
work=$(realpath -m "${1:-$root/work}")
mkdir -p "$work"
# git am needs an identity; it only lands in the local clones.
export GIT_COMMITTER_NAME=cookbook GIT_COMMITTER_EMAIL=cookbook@localhost

checkout() { # DIR REPO COMMIT PATCH_DIR
    local dir=$1 repo=$2 commit=$3 patches=$4
    [ -d "$dir/.git" ] || git clone "$repo" "$dir"
    git -C "$dir" am --abort >/dev/null 2>&1 || true
    git -C "$dir" fetch -q origin || true
    git -C "$dir" checkout -q -B cookbook "$commit"
    git -C "$dir" reset -q --hard "$commit"
    git -C "$dir" am -q "$patches"/*.patch
    echo "$(basename "$dir"): $(git -C "$dir" rev-list --count "$commit"..HEAD) patches on $commit"
}

checkout "$work/Radiance" "$RADIANCE_REPO" "$RADIANCE_COMMIT" "$root/patches/radiance"
checkout "$work/MCVR" "$MCVR_REPO" "$MCVR_COMMIT" "$root/patches/mcvr"
if [[ ${MCVR_CAVE_COUNTS:-0} == 1 ]]; then
    git -C "$work/MCVR" am -q "$root/patches/experimental/cave-counts/"*.patch
fi
git -C "$work/MCVR" submodule update --init --recursive --depth 1
bash "$root/scripts/apply-sharc-patches.sh" "$work/MCVR"

# JNI headers for the engine build.
(cd "$work/Radiance" && ./gradlew --quiet compileJava)

shaderc=()
for lib in /usr/lib/libshaderc_shared.so /usr/lib/x86_64-linux-gnu/libshaderc_shared.so; do
    [ -f "$lib" ] && shaderc=(-DSHADERC_LIBRARY="$lib") && break
done
cmake -S "$work/MCVR" -B "$work/MCVR/build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DJAVA_PROJECT_ROOT_DIR="$work/Radiance" \
    -DUSE_AMD=OFF -DMCVR_ENABLE_FFX_UPSCALER=OFF \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
    -DCMAKE_SKIP_BUILD_RPATH=ON \
    "${shaderc[@]}"
cmake --build "$work/MCVR/build" -j"$(nproc)"
# Installs libcore.so, the SPIR-V shaders and the built-in shader packs (advanced.zip) into
# Radiance/src/main/resources, where the jar build picks them up.
cmake --install "$work/MCVR/build"

(cd "$work/Radiance" && ./gradlew --quiet build)
ls -1 "$work"/Radiance/build/libs/*.jar
