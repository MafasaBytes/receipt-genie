#!/bin/bash
set -e

cd /app/backend

# Run DB migrations
python -m migrations.add_vat_columns 2>/dev/null || true
python -m migrations.add_is_credit_column 2>/dev/null || true
python -m migrations.add_items_verified_column 2>/dev/null || true

# Start nginx in background
nginx

# Start FastAPI (uvicorn)
exec uvicorn main:app --host 127.0.0.1 --port 8000 --workers 1 --log-level info
