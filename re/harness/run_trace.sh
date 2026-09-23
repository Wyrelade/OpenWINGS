#!/bin/sh
# Run the tracing WINGS.EXE copy in DOSBox-X; guest RAM is mapped from a host file, from which
# tools/trace_extract.py pulls the hook's records. The hook does no DOS file writes.
# usage: re/harness/run_trace.sh <script.bin|-> <out.json> [seconds=40] [autotype keys] [meta...]
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DBX=${DBX:-/d/programs/re/dosbox-x-mingw32/mingw-build/mingw-sdl2/dosbox-x.exe}
SCRIPT=$1; OUT=$2; SECS=${3:-40}; KEYS=${4:-"enter"}; shift 4 2>/dev/null || shift $#
G="$ROOT/re/work/wings"
MEM="$ROOT/re/work/guestmem.bin"
rm -f "$G/SCRIPT.BIN" "$MEM"
[ "$SCRIPT" != "-" ] && cp "$SCRIPT" "$G/SCRIPT.BIN"
CONF="$ROOT/re/work/trace.conf"
awk -v m="memory file=$(cygpath -m "$MEM")" '{print} /^\[dosbox\]$/{print m}' "$ROOT/re/harness/dosbox-trace.conf" > "$CONF"
cat >> "$CONF" <<EOT
mount c "$(cygpath -w "$ROOT/re/work")"
c:
cd wings
autotype -w 6 -p 1 $KEYS
WINGS.EXE -S0
EOT
"$DBX" -conf "$(cygpath -w "$CONF")" -nopromptfolder > "$ROOT/re/work/dbx.log" 2>&1 &
sleep "$SECS"
python "$ROOT/tools/trace_extract.py" "$MEM" "$OUT" "$@" || true
taskkill //F //IM dosbox-x.exe > /dev/null 2>&1 || true
