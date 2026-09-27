#!/usr/bin/env bash
# Apply the header correction inside the pinned MCVR submodule, without resetting it.
set -euo pipefail
[[ $# == 1 ]] || { echo "Usage: $0 MCVR_DIR" >&2; exit 2; }
root=$(cd "$(dirname "$0")/.." && pwd)
sdk=$(realpath "$1/extern/sharc")
expected=0b9f58bbc8c41736042d4da964830a247e424a00
[[ $(git -C "$sdk" rev-parse --show-toplevel) == "$sdk" ]] || {
    echo "Initialize MCVR's SHaRC submodule first." >&2; exit 1;
}
[[ $(git -C "$sdk" rev-parse HEAD) == "$expected" ]] || {
    echo "Unexpected SHaRC revision; expected $expected." >&2; exit 1;
}
for patch in "$root"/patches/sharc/*.patch; do
    if git -C "$sdk" apply --reverse --check "$patch" 2>/dev/null; then
        echo "SHaRC: $(basename "$patch") already applied"
    else
        git -C "$sdk" apply --check "$patch"
        git -C "$sdk" apply "$patch"
        echo "SHaRC: applied $(basename "$patch")"
    fi
done
