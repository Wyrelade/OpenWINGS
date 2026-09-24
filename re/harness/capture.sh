#!/bin/sh
# Capture one scripted trace, retrying when the game loads another level. The level is identified
# from two pixel rows the hook copies into the trace header (level_match must name <LEVEL>).
# usage: re/harness/capture.sh <name> <seconds> [LEVEL.LEV=LEGO.LEV] [tx ty = 284 227]
#   script re/harness/scripts/<name>.bin (tools/make_scripts.py), output
#   re/traces/<name>_dosbox_mingw32.json (name should start with the level, e.g. lego_base).
# Prepares the work copy with re/harness/prepare_level.py (only <LEVEL> in re/work/wings/LEV,
# events off, flowing water and waves off) and builds the tracing EXE with the teleport target.
# The work-copy PLAYERS.DAT has n=2 (both human; player 2 idle).
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
n=$1; s=$2; lev=${3:-LEGO.LEV}; tx=${4:-284}; ty=${5:-227}
out="$ROOT/re/traces/${n}_dosbox_mingw32.json"
python "$ROOT/re/harness/prepare_level.py" "$lev"
python "$ROOT/tools/make_trace_exe.py" "$ROOT/original/wings140/WINGS.EXE" "$ROOT/re/work/wings/WINGS.EXE" --teleport "$tx" "$ty"
for try in 1 2 3 4; do
  rm -f "$out"
  "$ROOT/re/harness/run_trace.sh" "$ROOT/re/harness/scripts/$n.bin" "$out" "$s" enter \
    level="$lev" teleport="$tx,$ty" script="$n" events=off flowing=off players=2 dosbox=mingw32-2026.08.31 || true
  taskkill //F //IM dosbox-x.exe > /dev/null 2>&1 || true
  if [ -f "$out" ] && python -c "import json,sys;g=json.load(open(sys.argv[1]))['globals'];m=(g.get('level_match') or ':0').split(':');print('level',m);sys.exit(0 if m[0]==sys.argv[2].upper() and float(m[1])>0.95 else 1)" "$out" "$lev"; then
    echo "ok: $out"; exit 0
  fi
  echo "wrong level loaded, retry $try"
done
exit 1
