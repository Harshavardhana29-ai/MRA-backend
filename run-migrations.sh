#!/bin/bash
# Run Alembic migrations and seed data via Cloud SQL Proxy

set -e

echo "=== Database Migration & Seeding ==="
echo ""

# Configuration
DEFAULT_DB_INSTANCE="mra-db"
DEFAULT_DB_NAME="mrd-db"
DEFAULT_DB_USER="postgres"

read -p "Enter existing Cloud SQL instance name [$DEFAULT_DB_INSTANCE]: " DB_INSTANCE
DB_INSTANCE=${DB_INSTANCE:-$DEFAULT_DB_INSTANCE}
read -p "Enter database name [$DEFAULT_DB_NAME]: " DB_NAME
DB_NAME=${DB_NAME:-$DEFAULT_DB_NAME}
read -p "Enter database user [$DEFAULT_DB_USER]: " DB_USER
DB_USER=${DB_USER:-$DEFAULT_DB_USER}

read -p "Enter password for user '$DB_USER': " DB_PASSWORD
echo ""

# Get connection name
CLOUD_SQL_CONN=$(gcloud sql instances describe $DB_INSTANCE --format="value(connectionName)")

echo "Step 1: Starting Cloud SQL Proxy..."
cloud-sql-proxy $CLOUD_SQL_CONN &
PROXY_PID=$!
sleep 3

echo "Step 2: Setting up Python environment..."
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

echo "Step 3: Running Alembic migrations..."
export DATABASE_URL="postgresql+asyncpg://$DB_USER:$DB_PASSWORD@127.0.0.1:5432/$DB_NAME"
alembic upgrade head

echo "Step 4: Seeding initial data..."
python setup.py

echo "Step 5: Cleaning up..."
kill $PROXY_PID
deactivate

echo ""
echo "=== Migration Complete ==="
echo "Database is ready!"
echo ""
