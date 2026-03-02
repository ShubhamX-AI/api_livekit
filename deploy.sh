#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting deployment..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ .env file not found! Please create one based on .env.example"
    exit 1
fi

echo "Git pulling latest changes..."
git pull origin master

echo "📦 Building and starting containers..."
docker compose up -d --build

echo "🧹 Cleaning up old images..."
docker image prune -a -f

echo "✅ Deployment successful!"
