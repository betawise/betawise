#!/usr/bin/env bash
# Create fresh, disposable static analysis evidence. No emulator or USB access.
set -euo pipefail
workspace=$(cd -- "$(dirname -- "$0")/../../.." && pwd)
output=${1:?Usage: reproduce-static.sh /absolute/empty/output-directory}
case "$output" in /*) ;; *) echo 'Output must be absolute' >&2; exit 1;; esac
mkdir -p -- "$output"
if test -n "$(ls -A -- "$output")"; then
    echo 'Output must be empty; existing evidence is never overwritten' >&2
    exit 1
fi
mkdir -p -- "$output/java-home" "$output/evidence"
cd -- "$workspace"
python3 betawise/research/usb/audit-static.py > "$output/evidence/static-anchors.json"
rom='Ghidra/Alphasmart Neo/SmartApplets/os3kneorom.os3kos'
aw='Ghidra/Alphasmart Neo/SmartApplets/alphawordplus.os3kapp'
for range in '410b26 412cd0 updater' '428598 42882c editor-transfer' \
             '42f6a8 42f998 form-transfer' '41cb80 41d440 usb-events'; do
    read -r first last label <<< "$range"
    m68k-linux-gnu-objdump -D -b binary -m m68k:68000 --adjust-vma=0x410000 \
        --start-address="0x$first" --stop-address="0x$last" "$rom" \
        > "$output/evidence/neo-$label.dis"
done
m68k-linux-gnu-objdump -D -b binary -m m68k:68000 "$aw" > "$output/evidence/neo-alphaword.dis"
export JAVA_TOOL_OPTIONS="-Duser.home=$output/java-home"
"${GHIDRA_HOME:-/opt/ghidra}/support/analyzeHeadless" "$output" neo \
    -import "$rom" -loader BinaryLoader -loader-baseAddr 0x410000 \
    -processor 68000:BE:32:default -noanalysis \
    -scriptPath betawise/research/usb -postScript Dump.java \
    410b26 410b60 410c82 412c82 412bca 412c28 410c20 412b20 \
    43c5ee 43c660 43b6f0 43b660 429cf0 429f14 \
    41f9a0 424780 44044e 44047c 428598 4285ce 42f744 \
    -log "$output/ghidra.log" > "$output/evidence/neo-decompilation.txt" 2>&1
"${GHIDRA_HOME:-/opt/ghidra}/support/analyzeHeadless" "$output" alphaword \
    -import "$aw" -loader BinaryLoader -loader-baseAddr 0 \
    -processor 68000:BE:32:default -noanalysis \
    -scriptPath betawise/research/usb -postScript Dump.java 94 \
    -log "$output/alphaword-ghidra.log" > "$output/evidence/neo-alphaword-entry.txt" 2>&1
