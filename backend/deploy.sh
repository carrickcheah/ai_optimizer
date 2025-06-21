#!/bin/bash

# AI Optimizer Backend - Zeabur Deployment Script
# This script helps deploy the backend to Zeabur cloud platform

set -e  # Exit on any error

echo "🚀 AI Optimizer Backend - Zeabur Deployment"
echo "============================================"

# Check if we're in the right directory
if [ ! -f "main.py" ] || [ ! -f "Dockerfile" ]; then
    echo "❌ Error: Please run this script from the backend directory"
    echo "   Expected files: main.py, Dockerfile"
    exit 1
fi

# Check required environment variables for deployment
echo "🔍 Checking deployment requirements..."

REQUIRED_ENV_VARS=(
    "MARIADB_HOST"
    "MARIADB_USERNAME" 
    "MARIADB_PASSWORD"
    "MARIADB_DATABASE"
    "MARIADB_PORT"
)

MISSING_VARS=()
for var in "${REQUIRED_ENV_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo "⚠️  Warning: Missing environment variables for deployment:"
    printf '   - %s\n' "${MISSING_VARS[@]}"
    echo ""
    echo "💡 Set these in your Zeabur project environment variables:"
    echo "   1. Go to your Zeabur project dashboard"
    echo "   2. Navigate to Variables section"
    echo "   3. Add the missing environment variables"
    echo ""
fi

# Optional environment variables
OPTIONAL_ENV_VARS=(
    "DEEPSEEK_API_KEY"
    "DEEPSEEK_MODEL" 
    "PORT"
    "CORS_ORIGINS"
)

echo "📋 Optional environment variables for full functionality:"
for var in "${OPTIONAL_ENV_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo "   - $var (not set)"
    else
        echo "   ✅ $var (set)"
    fi
done

echo ""
echo "🐳 Docker Build Test"
echo "===================="

# Test Docker build locally
echo "Testing Docker build locally..."
if docker build -t ai-optimizer-backend-test . > /dev/null 2>&1; then
    echo "✅ Docker build successful"
    docker rmi ai-optimizer-backend-test > /dev/null 2>&1 || true
else
    echo "❌ Docker build failed. Please fix Dockerfile issues before deploying."
    exit 1
fi

echo ""
echo "🔗 Zeabur Deployment Instructions"
echo "================================="
echo ""
echo "1. Install Zeabur CLI (if not already installed):"
echo "   npm install -g @zeabur/cli"
echo ""
echo "2. Login to Zeabur:"
echo "   zeabur auth login"
echo ""
echo "3. Deploy this backend:"
echo "   zeabur deploy"
echo ""
echo "4. Set environment variables in Zeabur dashboard:"
echo "   - Database connection variables (required)"
echo "   - DeepSeek API key (for AI reports)"
echo "   - CORS origins (for frontend integration)"
echo ""
echo "5. Your API will be available at:"
echo "   https://your-service-name.zeabur.app"
echo ""

echo "✅ Pre-deployment checks complete!"
echo ""
echo "🚀 Ready for Zeabur deployment!"
echo "   Run: zeabur deploy"