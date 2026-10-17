#!/bin/bash
# Serve the LinuxONE-trained Campylobacter model on localhost only, query it, log, stop.
cd ~/tracefront/food-risk-ml
export PYTHONPATH=. FOOD_RISK_PATHOGEN=campylobacter
LOG=~/tracefront-evidence/campylobacter/15_api.log
~/.venvs/foodrisk/bin/python -m uvicorn src.api.app:app --host 127.0.0.1 --port 8100 > /tmp/uvicorn_campy.log 2>&1 &
PID=$!
for i in $(seq 1 30); do curl -s -o /dev/null http://127.0.0.1:8100/health && break; sleep 1; done
{
  echo "utc: $(date -u +%FT%TZ)  host: $(hostname)  arch: $(uname -m)  server: uvicorn on 127.0.0.1:8100 (pid $PID)  FOOD_RISK_PATHOGEN=$FOOD_RISK_PATHOGEN"
  echo "== GET /health"; curl -s http://127.0.0.1:8100/health; echo
  echo "== POST /predict  (body: docs/examples/predict_request.json)"; cat docs/examples/predict_request.json; echo
  curl -s -w '\n== latency_seconds %{time_total}\n' -X POST http://127.0.0.1:8100/predict -H "Content-Type: application/json" \
    -d @docs/examples/predict_request.json
} > "$LOG" 2>&1
kill $PID
cat "$LOG"
