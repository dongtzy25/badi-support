#!/bin/sh
# Container start-up: bring the schema up to date, add demo data on first run, start the API.
set -e
alembic upgrade head
python -m app.seed --if-empty
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
