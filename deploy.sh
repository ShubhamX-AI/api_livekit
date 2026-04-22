#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting deployment..."

ROLE="${1:-full}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found! Please create one based on .env.example"
    exit 1
fi

echo "Git pulling latest changes..."
git pull origin master

if [ "$ROLE" = "control" ]; then
    unset API_DOCKERFILE
    unset DISPATCHER_DOCKERFILE
    unset AGENT_DOCKERFILE
    echo "📦 Deploying control-plane services (api + sip_dispatcher)..."
    docker compose --profile control up -d --build
elif [ "$ROLE" = "agent" ]; then
    unset API_DOCKERFILE
    unset DISPATCHER_DOCKERFILE
    unset AGENT_DOCKERFILE
    echo "📦 Deploying agent worker services..."
    docker compose --profile agent up -d --build
elif [ "$ROLE" = "full" ]; then
    export API_DOCKERFILE="Dockerfile"
    export DISPATCHER_DOCKERFILE="Dockerfile"
    export AGENT_DOCKERFILE="Dockerfile"
    echo "📦 Deploying all services (control + agent) using original Dockerfile..."
    docker compose --profile control --profile agent up -d --build
else
    echo "❌ Invalid role: $ROLE (expected: control | agent | full)"
    exit 1
fi

echo "🧹 Cleaning up..."
docker system prune -a -f

echo "✅ Deployment successful!"
