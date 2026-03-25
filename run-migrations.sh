#!/bin/bash
# Run Alembic migrations and seed data via Cloud SQL Proxy
 
set -e
 
echo "=== Database Migration & Seeding ==="
echo ""
 
# Configuration
DEFAULT_DB_INSTANCE="mra-db"
DEFAULT_DB_NAME="mra-db"
DEFAULT_DB_USER="postgres"
DEFAULT_DB_PORT="5433"
 
read -p "Enter existing Cloud SQL instance name [$DEFAULT_DB_INSTANCE]: " DB_INSTANCE
DB_INSTANCE=${DB_INSTANCE:-$DEFAULT_DB_INSTANCE}
read -p "Enter database name [$DEFAULT_DB_NAME]: " DB_NAME
DB_NAME=${DB_NAME:-$DEFAULT_DB_NAME}
read -p "Enter database user [$DEFAULT_DB_USER]: " DB_USER
DB_USER=${DB_USER:-$DEFAULT_DB_USER}
read -p "Enter local proxy port [$DEFAULT_DB_PORT]: " DB_PORT
DB_PORT=${DB_PORT:-$DEFAULT_DB_PORT}
 
read -s -p "Enter password for user '$DB_USER': " DB_PASSWORD
echo ""
 
ENCODED_DB_PASSWORD=$(python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=''))" "$DB_PASSWORD")
 
# Get connection name
CLOUD_SQL_CONN=$(gcloud sql instances describe $DB_INSTANCE --format="value(connectionName)")
 
echo "Step 1: Starting Cloud SQL Proxy..."
cloud-sql-proxy --address 127.0.0.1 --port $DB_PORT $CLOUD_SQL_CONN &
PROXY_PID=$!
trap 'kill $PROXY_PID 2>/dev/null || true' EXIT
sleep 3
 
echo "Step 2: Setting up Python environment..."
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
 
echo "Step 3: Running Alembic migrations..."
export DATABASE_URL="postgresql+asyncpg://$DB_USER:$ENCODED_DB_PASSWORD@127.0.0.1:$DB_PORT/$DB_NAME"
alembic upgrade head
 
echo "Step 4: Seeding initial data..."
python -m app.seed
 
echo "Step 5: Cleaning up..."
kill $PROXY_PID
trap - EXIT
deactivate
 
echo ""
echo "=== Migration Complete ==="
echo "Database is ready!"
echo ""