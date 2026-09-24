#!/bin/sh
# Capture one scripted trace on LEGO.LEV, retrying when the game loads another level
# (level choice is not always the LEVELS.DAT entry; seen: RINTAMA 800x150 and other 400x400
# levels). The level is identified from two pixel rows the hook copies into the trace header.
# usage: re/harness/capture.sh <name> <seconds>
# Prereqs: tools/make_trace_exe.py ... --teleport 284 227 into re/work/wings, and the
# work-copy re/work/wings/LEV/LEGO.LEV with rain/snow/bombing/civilians set to 0, all other
# levels moved to re/work/LEV_hidden (the game picks random levels otherwise), and the work-copy
# PLAYERS.DAT with n=2 (both human; player 2 idle).
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
n=$1; s=$2
out="$ROOT/re/traces/lego_${n}_dosbox_mingw32.json"
for try in 1 2 3 4; do
  rm -f "$out"
  "$ROOT/re/harness/run_trace.sh" "$ROOT/re/harness/scripts/$n.bin" "$out" "$s" enter \
    level=LEGO.LEV teleport=284,227 script=$n events=off players=2 dosbox=mingw32-2026.08.31
  if [ -f "$out" ] && python -c "import json,sys;g=json.load(open(sys.argv[1]))['globals'];m=(g.get('level_match') or ':0').split(':');print('level',m);sys.exit(0 if m[0]=='LEGO.LEV' and float(m[1])>0.95 else 1)" "$out"; then
    echo "ok: $out"; exit 0
  fi
  echo "wrong level loaded, retry $try"
done
exit 1
