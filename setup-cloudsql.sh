#!/bin/bash
# Cloud SQL Validation Script for Google Cloud Shell

set -e

echo "=== Existing Cloud SQL Validation ==="
echo ""

# Configuration
REGION="us-central1"
DEFAULT_DB_NAME="mra-db"
DEFAULT_DB_USER="mra_user"

read -p "Enter existing Cloud SQL instance name: " DB_INSTANCE
read -p "Enter database name [$DEFAULT_DB_NAME]: " DB_NAME
DB_NAME=${DB_NAME:-$DEFAULT_DB_NAME}
read -p "Enter database user [$DEFAULT_DB_USER]: " DB_USER
DB_USER=${DB_USER:-$DEFAULT_DB_USER}

echo ""
echo "This script will validate:"
echo "  - Cloud SQL instance: $DB_INSTANCE"
echo "  - Database: $DB_NAME"
echo "  - User: $DB_USER"
echo ""

echo "Step 1: Validating Cloud SQL instance..."
if ! gcloud sql instances describe $DB_INSTANCE &>/dev/null; then
  echo "ERROR: Cloud SQL instance '$DB_INSTANCE' was not found."
  echo "Run 'gcloud sql instances list' to find the correct instance name."
  exit 1
fi

DB_VERSION=$(gcloud sql instances describe $DB_INSTANCE --format="value(databaseVersion)")
INSTANCE_REGION=$(gcloud sql instances describe $DB_INSTANCE --format="value(region)")
echo "✓ Instance found"
echo "  - Version: $DB_VERSION"
echo "  - Region: $INSTANCE_REGION"

echo "Step 2: Validating database..."
if ! gcloud sql databases describe $DB_NAME --instance=$DB_INSTANCE &>/dev/null; then
  echo "ERROR: Database '$DB_NAME' was not found in instance '$DB_INSTANCE'."
  echo "Create it with: gcloud sql databases create $DB_NAME --instance=$DB_INSTANCE"
  exit 1
fi
echo "✓ Database found"

echo "Step 3: Validating database user..."
if ! gcloud sql users list --instance=$DB_INSTANCE --format="value(name)" | grep -Fxq "$DB_USER"; then
  echo "ERROR: User '$DB_USER' was not found in instance '$DB_INSTANCE'."
  echo "Create it with: gcloud sql users create $DB_USER --instance=$DB_INSTANCE --password=YOUR_PASSWORD"
  exit 1
fi
echo "✓ User found"

# Get connection name
CLOUD_SQL_CONN=$(gcloud sql instances describe $DB_INSTANCE --format="value(connectionName)")

echo ""
echo "=== Cloud SQL Validation Complete ==="
echo "Connection name: $CLOUD_SQL_CONN"
echo ""
echo "Use these values in the next steps:"
echo "Instance: $DB_INSTANCE"
echo "Database: $DB_NAME"
echo "User: $DB_USER"
echo ""
echo "Next step: Run ./run-migrations.sh to initialize the database"
echo ""
