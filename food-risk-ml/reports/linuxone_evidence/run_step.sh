#!/bin/bash
# Usage: run_step.sh <log-name> <command...>
# Runs a command in ~/tracefront/food-risk-ml with the foodrisk venv; logs a provenance header plus all output.
NAME=$1; shift
LOG=~/tracefront-evidence/$NAME.log
cd ~/tracefront/food-risk-ml
export PYTHONPATH=. MPLBACKEND=Agg
source ~/.venvs/foodrisk/bin/activate
{
  echo "=================================================================="
  echo "step:      $NAME"
  echo "utc:       $(date -u +%FT%TZ)"
  echo "host:      $(hostname)   kernel: $(uname -sr)   arch: $(uname -m)"
  echo "machine:   $(grep -m1 -E '^(Type|Manufacturer)' /proc/sysinfo 2>/dev/null | tr -s ' ') $(grep -m1 '^Type' /proc/sysinfo 2>/dev/null | tr -s ' ')"
  echo "os:        $(grep PRETTY_NAME /etc/os-release | cut -d= -f2)"
  echo "python:    $(python -c 'import sys,platform;print(platform.python_version(), sys.byteorder+"-endian")')"
  echo "command:   $*"
  echo "=================================================================="
  /usr/bin/time -v "$@" 2>&1
  echo "exit_code: $?"
} > "$LOG" 2>&1
tail -${TAIL:-25} "$LOG"
