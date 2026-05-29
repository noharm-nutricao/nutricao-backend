#!/bin/bash
set -e

DB_URL="postgresql://postgres@localhost/noharm"
COMPOSE="docker compose -f docker-compose.test.yml"
MIGRATIONS_DIR="$(dirname "$0")/../database/migrations/flyway"

echo "Starting PostgreSQL container..."
$COMPOSE up -d

echo "Waiting for PostgreSQL to be ready..."
until psql "$DB_URL" -c "SELECT 1" >/dev/null 2>&1; do
  sleep 1
done
echo "PostgreSQL is ready."

echo "Loading database migrations..."
for sql_file in "$MIGRATIONS_DIR"/V*__*.sql "$MIGRATIONS_DIR"/R__*.sql; do
  [ -f "$sql_file" ] || continue
  echo "  Applying $(basename "$sql_file")..."
  psql "$DB_URL" -f "$sql_file" -v ON_ERROR_STOP=1
done

echo "Done. Run: make test"
