#!/bin/sh
set -eu
: "${JWT_SECRET:?Set a random JWT_SECRET before starting}"
alembic upgrade head
if [ "${SEED_DEMO:-false}" = true ]; then python seed/seed.py; fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
