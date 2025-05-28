#!/bin/bash

# Exit on error
set -e

# Change to the project directory
cd "$(dirname "$0")"

# Define log colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Starting AI Optimizer Development Environment ===${NC}"

# Function to stop all background processes on exit
cleanup() {
  echo -e "${YELLOW}Stopping all processes...${NC}"
  kill $(jobs -p) 2>/dev/null || true
  echo -e "${GREEN}Done!${NC}"
}

# Register the cleanup function to be called on exit
trap cleanup EXIT

# Start the backend
echo -e "${BLUE}Starting Backend on port 8000...${NC}"
cd backend
python -m app.main &
echo -e "${GREEN}Backend started!${NC}"

# Wait a moment for the backend to initialize
sleep 2

# Start the frontend
echo -e "${BLUE}Starting Frontend on port 3000...${NC}"
cd ../frontend
npm run dev &
echo -e "${GREEN}Frontend started!${NC}"

echo -e "${GREEN}✅ Development environment is running!${NC}"
echo -e "${YELLOW}Frontend:${NC} http://localhost:3000"
echo -e "${YELLOW}Backend API:${NC} http://localhost:8000"
echo -e "${BLUE}Press Ctrl+C to stop all servers${NC}"

# Keep the script running until Ctrl+C
wait 