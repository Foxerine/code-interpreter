#!/bin/bash

# Set the script to exit immediately if any command fails
set -e

# --- Color Definitions ---
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# --- Check if already running ---
CONTAINER_NAME="code-interpreter_gateway"
echo -e "🔎 Checking status of container '${CONTAINER_NAME}'..."

# docker ps -q returns the container ID if it's running
if [ -n "$(docker ps -q --filter "name=^${CONTAINER_NAME}$")" ]; then
    echo -e "${GREEN}✅ The Code Interpreter gateway is already running. No action taken.${NC}"
    # --- MODIFICATION: Fetch and display the token even if it's already running ---
    echo -e "\n🔑 Retrieving existing Auth Token..."
    TOKEN=$(docker exec ${CONTAINER_NAME} cat /gateway/auth_token.txt)
    echo -e "Your Auth Token is: ${YELLOW}${TOKEN}${NC}"
    exit 0
else
    echo -e "   -> Container is not running. Proceeding with startup."
fi

# --- Step 1: Start Docker Compose ---
echo -e "\n🚀 ${GREEN}[Step 1/3] Starting the Code Interpreter environment...${NC}"
# Use --build to ensure images are up-to-date
# Use -d to run in the background
docker-compose up --build -d

# --- Step 2: Clean up builder container ---
echo -e "\n🧹 ${CYAN}[Step 2/3] Cleaning up the temporary builder container...${NC}"

# Find the builder container ID
BUILDER_ID=$(docker ps -a -q --filter "name=code-interpreter_worker_builder")

if [ -n "$BUILDER_ID" ]; then
    echo "   -> Found builder container. Removing it..."
    docker rm "$BUILDER_ID" > /dev/null
    echo -e "   -> ${GREEN}Builder container successfully removed.${NC}"
else
    echo -e "   -> ${YELLOW}No temporary builder container found to clean up. Skipping.${NC}"
fi

# --- Step 3: Wait for and retrieve the Auth Token ---
echo -e "\n🔑 ${CYAN}[Step 3/3] Waiting for Gateway to generate the Auth Token...${NC}"

TOKEN=""
# Poll for 30 seconds (1-second intervals) for the token file to be created
for i in {1..30}; do
    # Try to get the token, suppress "No such file or directory" errors
    TOKEN=$(docker exec ${CONTAINER_NAME} cat /gateway/auth_token.txt 2>/dev/null || true)
    if [ -n "$TOKEN" ]; then
        break
    fi
    echo -n "."
    sleep 1
done

echo "" # Newline after the dots

if [ -z "$TOKEN" ]; then
    echo -e "\n${RED}❌ Timed out waiting for the Auth Token.${NC}"
    echo -e "   Please check the gateway container logs with: ${YELLOW}docker logs ${CONTAINER_NAME}${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Token successfully retrieved!${NC}"
echo -e "\n🎉 ${GREEN}Startup complete. The system is ready.${NC}"
echo -e "Your Auth Token is: ${YELLOW}${TOKEN}${NC}"
