#!/bin/bash
# Backend Deployment Script for Google Cloud Shell

set -e  # Exit on any error

echo "=== MRA Backend Deployment ==="
echo ""

# Get project ID
PROJECT_ID=$(gcloud config get-value project)
echo "Project ID: $PROJECT_ID"

# Configuration
REGION="us-central1"
SERVICE_NAME="mra-backend"
DEFAULT_DB_INSTANCE="mra-db"
DEFAULT_DB_NAME="mrd-db"
DEFAULT_DB_USER="postgres"

echo ""
read -p "Enter existing Cloud SQL instance name [$DEFAULT_DB_INSTANCE]: " DB_INSTANCE
DB_INSTANCE=${DB_INSTANCE:-$DEFAULT_DB_INSTANCE}
read -p "Enter database name [$DEFAULT_DB_NAME]: " DB_NAME
DB_NAME=${DB_NAME:-$DEFAULT_DB_NAME}
read -p "Enter database user [$DEFAULT_DB_USER]: " DB_USER
DB_USER=${DB_USER:-$DEFAULT_DB_USER}

echo ""
read -p "Enter Cloud SQL instance password for user '$DB_USER': " DB_PASSWORD
echo ""

# Build and push container
echo "Step 1: Building Docker image..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

# Get Cloud SQL connection name
CLOUD_SQL_CONN=$(gcloud sql instances describe $DB_INSTANCE --format="value(connectionName)" 2>/dev/null || echo "")

if [ -z "$CLOUD_SQL_CONN" ]; then
  echo ""
  echo "WARNING: Cloud SQL instance '$DB_INSTANCE' not found."
  echo "Deploying backend without database connection."
  echo "You need to provide the correct existing instance name (see setup-cloudsql.sh)"
  echo ""
  
  # Deploy without Cloud SQL
  gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --port 8080 \
    --set-env-vars "NEWS_AGENT_API_URL=https://news-agent-gateway-bnwb9717.uc.gateway.dev/ask"
else
  echo "Step 2: Deploying to Cloud Run with Cloud SQL..."
  
  # Deploy with Cloud SQL
  gcloud run deploy $SERVICE_NAME \
    --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --port 8080 \
    --add-cloudsql-instances $CLOUD_SQL_CONN \
    --set-env-vars "DATABASE_URL=postgresql+asyncpg://$DB_USER:$DB_PASSWORD@/$DB_NAME?host=/cloudsql/$CLOUD_SQL_CONN" \
    --set-env-vars "NEWS_AGENT_API_URL=https://news-agent-gateway-bnwb9717.uc.gateway.dev/ask" \
    --set-env-vars "CORS_ORIGINS=https://storage.googleapis.com"
fi

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format="value(status.url)")

echo ""
echo "=== Deployment Complete ==="
echo "Backend URL: $SERVICE_URL"
echo ""
echo "IMPORTANT: Save this URL for frontend deployment!"
echo "You'll need: $SERVICE_URL/api"
echo ""
