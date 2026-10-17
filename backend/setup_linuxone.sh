#!/bin/bash
# Runs on the LinuxONE server; deploy.ps1 unpacks backend/ into ~/tracefront first, next to food-risk-ml
# (analysis.py imports its cold-chain rules). Installs PostgreSQL, creates the tracefront database and runs the API
# as the tracefront-backend service. Safe to re-run: keeps the database and its password, restarts on the new code.
set -euo pipefail
BACKEND=$(cd "$(dirname "$0")" && pwd)
VENV=~/.venvs/foodrisk          # venv the ML API already uses; system site-packages give it apt numpy/pandas
PORT=8000
cd "$BACKEND"

echo "== 1. PostgreSQL + driver (apt: psycopg2-binary has no s390x wheel)"
if [ "${TRACEFRONT_SKIP_INSTALL:-0}" != 1 ]; then
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql python3-psycopg2 >/dev/null
fi
sudo systemctl enable -q --now postgresql

echo "== 2. Database role and database"
pg() { (cd /tmp && sudo -u postgres psql -v ON_ERROR_STOP=1 -qtA "$@"); }
[ "$(pg -c "SELECT 1 FROM pg_roles WHERE rolname='tracefront'")" = 1 ] || pg -c "CREATE ROLE tracefront LOGIN"
[ "$(pg -c "SELECT 1 FROM pg_database WHERE datname='tracefront'")" = 1 ] || pg -c "CREATE DATABASE tracefront OWNER tracefront"
if [ ! -f .env ]; then
  PW=$(openssl rand -hex 16)    # never printed; lives only in backend/.env (mode 600)
  echo "ALTER ROLE tracefront PASSWORD '$PW';" | pg    # via stdin so it never shows in the process list
  (umask 077; echo "DATABASE_URL=postgresql://tracefront:$PW@localhost:5432/tracefront" > .env)
fi

echo "== 3. Python packages"
# SQLAlchemy pinned as in requirements.txt: 2.1 switched postgresql:// to the psycopg 3 driver, apt gives psycopg2
if [ "${TRACEFRONT_SKIP_INSTALL:-0}" != 1 ]; then
  "$VENV/bin/pip" install -q sqlalchemy==2.0.35 python-dotenv networkx python-multipart
fi
"$VENV/bin/python" -c "import psycopg2, fastapi, uvicorn, pandas" || { echo "venv cannot see apt psycopg2"; exit 1; }

echo "== 4. Backend tests"
"$VENV/bin/python" - <<'PY'
import importlib
for m in ("app.test_analysis", "app.test_risk"):
    mod = importlib.import_module(m)
    for name in sorted(n for n in dir(mod) if n.startswith("test_")):
        getattr(mod, name)()
        print("  pass", m, name)
PY
"$VENV/bin/python" -B -m unittest app.test_system -v

echo "== 5. Always-on service (survives logout and reboot)"
sudo tee /etc/systemd/system/tracefront-backend.service >/dev/null <<EOF
[Unit]
Description=Tracefront backend API
After=network.target postgresql.service
Requires=postgresql.service

[Service]
User=$(whoami)
WorkingDirectory=$BACKEND
ExecStart=$VENV/bin/python -B -m uvicorn app.main:app --host 127.0.0.1 --port $PORT
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable -q tracefront-backend
sudo systemctl restart tracefront-backend

echo "== 6. Verify"
ready=0
for _ in $(seq 30); do
  if curl -fsS "http://127.0.0.1:$PORT/api/health" 2>/dev/null; then ready=1; break; fi
  sleep 1
done
[ "$ready" = 1 ] || { echo "backend health check failed"; exit 1; }
echo; systemctl is-active tracefront-backend
