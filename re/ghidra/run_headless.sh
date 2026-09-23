#!/bin/sh
# Headless Ghidra wrapper. usage: re/ghidra/run_headless.sh <analyzeHeadless args...>
GHIDRA=${GHIDRA:-/d/programs/re/ghidra_12.1.4_PUBLIC}
export JAVA_HOME=${JAVA_HOME_21:-/d/programs/re/jdk-21.0.12.1+1}
export PATH="$JAVA_HOME/bin:$PATH"
exec "$GHIDRA/support/analyzeHeadless.bat" "$@"
