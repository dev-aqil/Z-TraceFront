#!/bin/bash
# Use the existing LinuxONE runtime and native model registries. No package installation or retraining.
set -euo pipefail
BACKEND=$(cd "$(dirname "$0")" && pwd)
ML=$(cd "$BACKEND/../food-risk-ml" && pwd)
VENV=~/.venvs/foodrisk
"$VENV/bin/python" -B "$BACKEND/prepare_ml.py" "$ML"
cd "$ML"
"$VENV/bin/python" -B - <<'PY'
from src.api.spin import Family, default_catalog
catalog = default_catalog()
for name, family in catalog.items():
    if not isinstance(family, Family):
        raise SystemExit(f'{name}: {family}')
    print('model family loaded:', name, family.members[0][2].meta['model_version'])
PY
sudo tee /etc/systemd/system/tracefront-ml.service >/dev/null <<EOF
[Unit]
Description=Tracefront pathogen sample inference
After=network.target

[Service]
User=$(whoami)
WorkingDirectory=$ML
ExecStart=$VENV/bin/python -B -m uvicorn src.api.app:app --host 127.0.0.1 --port 8100
Restart=on-failure
RestartSec=3
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable -q tracefront-ml
sudo systemctl restart tracefront-ml
ready=0
for _ in $(seq 45); do
  if curl -fsS http://127.0.0.1:8100/health >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
[ "$ready" = 1 ] || { echo "ML health check failed"; exit 1; }
systemctl is-active tracefront-ml
