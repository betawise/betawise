#!/usr/bin/env bash
# Private original images remain local. Output must be fresh and disposable.
set -euo pipefail
workspace=$(cd -- "$(dirname -- "$0")/../../.." && pwd)
output=${1:?Usage: reproduce-native-static.sh /absolute/empty/output-directory}
case "$output" in /*) ;; *) echo 'Output must be absolute' >&2; exit 1;; esac
mkdir -p -- "$output"
if test -n "$(ls -A -- "$output")"; then echo 'Output must be empty' >&2; exit 1; fi
mkdir -p -- "$output/evidence" "$output/java-home"
cd -- "$workspace"
python3 betawise/research/usb/audit-native-usb.py > "$output/evidence/native-anchors.json"
export JAVA_TOOL_OPTIONS="-Duser.home=$output/java-home"
for record in 'os3kneorom os3kos 410000 41ca36 440064 44015a 4402f6 4403c2 4403de 4404d6 440578 44083a 440d7e 441064 4411a4 4411f4 44129e 43f97a 43fb48 43fbc6 41f90a 41f95c 41f9a0 41f9fe 41faa4 41faf4' \
              'alphawordplus os3kapp 0 94 8844' \
              'alphaquiz os3kapp 0 e20 71dc 74f2' \
              'keywords os3kapp 0 63e 117e' \
              'keywordswireless os3kapp 0 734 4a20' \
              'mathfactsinaflash os3kapp 0 ea' \
              'mathfactsoffline os3kapp 0 94'; do
    read -r -a fields <<< "$record"
    name=${fields[0]}; extension=${fields[1]}; base=${fields[2]}
    image="Ghidra/Alphasmart Neo/SmartApplets/$name.$extension"
    m68k-linux-gnu-objdump -D -b binary -m m68k:68000 --adjust-vma="0x$base" \
        "$image" > "$output/evidence/$name.dis"
    "${GHIDRA_HOME:-/opt/ghidra}/support/analyzeHeadless" "$output" "$name" \
        -import "$image" -loader BinaryLoader -loader-baseAddr "0x$base" \
        -processor 68000:BE:32:default -noanalysis -scriptPath betawise/research/usb \
        -postScript Dump.java "${fields[@]:3}" -log "$output/$name.log" \
        > "$output/evidence/$name-ghidra.txt" 2>&1
    # Headless may report script failure without a failing process exit code.
    if ! grep -q 'Save succeeded for file' "$output/evidence/$name-ghidra.txt"; then
        echo "Ghidra import/dump failed: $name" >&2; exit 1
    fi
    echo "PASS static import/dump $name"
done
