#!/usr/bin/env bash
set -euo pipefail

if [[ $# != 2 ]]; then
    echo "Usage: $0 {nix|ats} NEW_WORKSPACE" >&2
    exit 2
fi
profile=$1
case "$profile" in
    nix) owner=nixiy; revision=5980dbcf70c2bbbe9a4953bbc63c516a0f6caec8 ;;
    ats) owner=freedom96960324; revision=38e8079b911539dabdcc4838cdbbbf14e2a9150f ;;
    *) echo "Unknown profile: $profile" >&2; exit 2 ;;
esac
repository=$(cd "$(dirname "$0")" && pwd)
mkdir "$2"
workspace=$(cd "$2" && pwd)
keyboard="$workspace/keyboard"
output="$workspace/output"

git init -q "$keyboard"
git -C "$keyboard" fetch --quiet --depth=1 "https://github.com/$owner/zmk-config-nickey44a-pad.git" "$revision"
git -C "$keyboard" checkout -q --detach FETCH_HEAD
git -C "$keyboard" apply "$repository/profiles/$profile.patch"

# The keyboard is itself a Zephyr module. Keep its zephyr/module.yml apart
# from west's checkout of Zephyr, while preserving the keyboard's root CMake.
cd "$workspace"
cp -R "$keyboard/config" config
west init -l config
west update zmk
# The ZMK fork imports Zephyr via a moving branch. Pin that imported project
# in the local manifest and keep the fork's own module import/blocklist.
python3 - <<'PY'
from pathlib import Path
import yaml
manifest = Path("config/west.yml")
config = yaml.safe_load(manifest.read_text())
upstream = yaml.safe_load(Path("zmk/app/west.yml").read_text())
zephyr = next(p for p in upstream["manifest"]["projects"] if p["name"] == "zephyr")
zephyr["revision"] = "dacab4875df72109b96cc8977547a0dc04875bcd"
# Keep ZMK's explicit nanopb fork ahead of the optional Zephyr module.
config["manifest"]["projects"].extend(upstream["manifest"]["projects"])
manifest.write_text(yaml.safe_dump(config, sort_keys=False))
PY
west update --fetch-opt=--filter=tree:0
git -C zmk apply "$repository/patches/wheel-resolution.patch"
west zephyr-export
mkdir "$output"
for side in left right; do
    if [[ "$side" == right ]]; then
        shield=nickey44a_r
        snippets=(-S studio-rpc-usb-uart)
        options=(-DCONFIG_ZMK_STUDIO=y)
    else
        shield=nickey44a_l
        snippets=()
        options=()
    fi
    west build -s zmk/app -d "build-$side" -b seeeduino_xiao_ble "${snippets[@]}" -- \
        "-DSHIELD=$shield rgbled_adapter" "-DZMK_CONFIG=$workspace/config" \
        "-DZMK_EXTRA_MODULES=$keyboard" "${options[@]}"
    cp "build-$side/zephyr/zmk.uf2" "$output/$profile-$side.uf2"
done
python3 "$repository/verify.py" "$profile" "$workspace/build-left" "$workspace/build-right" "$workspace/zephyr"
cp "$repository/THIRD_PARTY_NOTICES.txt" "$output/"
(cd "$output" && sha256sum ./*.uf2 > SHA256SUMS)
